"""
990 financial health analyzer — fetches data from ProPublica Nonprofit Explorer API.
"""

import requests

PROPUBLICA_BASE = "https://projects.propublica.org/nonprofits/api/v2"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; 990HealthAnalyzer/1.0; "
        "+https://github.com/alissa-king/990-analyzer)"
    ),
    "Accept": "application/json",
}


def _get(url, params=None):
    r = requests.get(url, params=params, headers=_HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


def search_orgs(query):
    """Search nonprofits by name. Returns list of org summaries."""
    data = _get(f"{PROPUBLICA_BASE}/search.json", params={"q": query})
    orgs = data.get("organizations", [])
    # ProPublica returns ein as an integer; normalize to zero-padded string.
    for org in orgs:
        org["ein"] = str(org.get("ein", "") or "").zfill(9)
    return orgs


def fetch_org(ein):
    """Fetch full org profile + all 990 filings for a given EIN."""
    clean = ein.replace("-", "").strip()
    data = _get(f"{PROPUBLICA_BASE}/organizations/{clean}.json")
    org = data.get("organization", {})
    filings = data.get("filings_with_data", [])
    return org, sorted(filings, key=lambda f: f.get("tax_prd_yr", 0))


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def _pct(numerator, denominator):
    if not denominator:
        return None
    return round(numerator / denominator * 100, 1)


def _months_of_reserves(net_assets, total_expenses):
    """Net assets / (total expenses / 12) = months of operating reserves."""
    if not total_expenses:
        return None
    return round(net_assets / (total_expenses / 12), 1)


def compute_metrics(filings):
    """
    For each filing compute the key health ratios.
    Returns a list of dicts, one per year, sorted ascending.
    """
    rows = []
    for f in filings:
        year = f.get("tax_prd_yr")
        rev = f.get("totrevenue") or 0
        exp = f.get("totfuncexpns") or 0
        assets = f.get("totassetsend") or 0
        liabilities = f.get("totliabend") or 0
        net_assets = assets - liabilities

        prog_exp = f.get("prgmservexpns") or 0
        mgmt_exp = f.get("totmngmntservcs") or 0
        fundraise_exp = f.get("totfunrndng") or 0
        contribs = f.get("totcntrbgfts") or 0
        officer_comp = f.get("compofcers") or 0

        rows.append(
            {
                "year": year,
                "total_revenue": rev,
                "total_expenses": exp,
                "net_surplus": rev - exp,
                "total_assets": assets,
                "total_liabilities": liabilities,
                "net_assets": net_assets,
                "program_expenses": prog_exp,
                "mgmt_expenses": mgmt_exp,
                "fundraising_expenses": fundraise_exp,
                "contributions": contribs,
                "officer_comp": officer_comp,
                # ratios
                "program_expense_ratio": _pct(prog_exp, exp),
                "fundraising_efficiency": _pct(fundraise_exp, contribs) if contribs else None,
                "liabilities_to_assets": _pct(liabilities, assets),
                "months_of_reserves": _months_of_reserves(net_assets, exp),
                "surplus_margin": _pct(rev - exp, rev) if rev else None,
            }
        )
    return rows


def health_score(metrics_rows):
    """
    Produce an overall health score 0-100 from the most recent year's data.
    Returns (score, breakdown) where breakdown is a list of (label, points, max, note).
    """
    if not metrics_rows:
        return None, []

    latest = metrics_rows[-1]
    breakdown = []
    total = 0

    # 1. Program expense ratio (0-30 pts) — charity watchdogs like ≥75%
    per = latest["program_expense_ratio"]
    if per is not None:
        pts = min(30, round(per * 30 / 100))
        note = f"{per}% of expenses go to programs"
    else:
        pts = 0
        note = "No data"
    breakdown.append(("Program Expense Ratio", pts, 30, note))
    total += pts

    # 2. Months of operating reserves (0-25 pts) — 3–6 months is healthy
    mor = latest["months_of_reserves"]
    if mor is not None:
        if mor >= 6:
            pts = 25
        elif mor >= 3:
            pts = round(15 + (mor - 3) / 3 * 10)
        elif mor >= 1:
            pts = round(mor / 3 * 15)
        else:
            pts = 0
        note = f"{mor} months of reserves"
    else:
        pts = 0
        note = "No data"
    breakdown.append(("Operating Reserves", pts, 25, note))
    total += pts

    # 3. Surplus margin (0-20 pts) — positive margin is good
    sm = latest["surplus_margin"]
    if sm is not None:
        if sm >= 5:
            pts = 20
        elif sm >= 0:
            pts = round(sm / 5 * 20)
        else:
            pts = max(0, round(20 + sm * 2))  # each % below 0 costs 2 pts
    else:
        pts = 0
        sm = 0
        note = "No data"
    if sm is not None:
        note = f"{sm:+.1f}% surplus margin"
    breakdown.append(("Surplus Margin", pts, 20, note))
    total += pts

    # 4. Revenue trend (0-15 pts) — look at last 3 years
    if len(metrics_rows) >= 2:
        rev_rows = [r["total_revenue"] for r in metrics_rows if r["total_revenue"]]
        if len(rev_rows) >= 2:
            trend = (rev_rows[-1] - rev_rows[-2]) / rev_rows[-2] * 100 if rev_rows[-2] else 0
            if trend >= 5:
                pts = 15
            elif trend >= 0:
                pts = round(trend / 5 * 15)
            else:
                pts = max(0, round(15 + trend))
            note = f"{trend:+.1f}% YoY revenue change"
        else:
            pts = 7
            note = "Insufficient data"
    else:
        pts = 7
        note = "Single year only"
    breakdown.append(("Revenue Trend", pts, 15, note))
    total += pts

    # 5. Liabilities to assets (0-10 pts) — lower is better, <50% is fine
    lta = latest["liabilities_to_assets"]
    if lta is not None:
        if lta <= 20:
            pts = 10
        elif lta <= 50:
            pts = round(10 - (lta - 20) / 30 * 5)
        elif lta <= 100:
            pts = round(5 - (lta - 50) / 50 * 5)
        else:
            pts = 0
        note = f"{lta}% liabilities-to-assets"
    else:
        pts = 5
        note = "No data"
    breakdown.append(("Liability Ratio", pts, 10, note))
    total += pts

    return min(100, total), breakdown


def grade(score):
    if score is None:
        return "N/A", "secondary"
    if score >= 85:
        return "A", "success"
    if score >= 70:
        return "B", "info"
    if score >= 55:
        return "C", "warning"
    if score >= 40:
        return "D", "orange"
    return "F", "danger"
