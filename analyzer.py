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
    # ProPublica returns ein as an integer; normalize to zero-padded string.
    if "ein" in org:
        org["ein"] = str(org["ein"] or "").zfill(9)
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
        # ProPublica uses inconsistent field names across filing years; try both.
        fundraise_exp = f.get("totfunrndng") or f.get("fundfees") or 0
        mgmt_exp = f.get("totmngmntservcs") or f.get("mngmntservcs") or 0
        # If the API returned no breakdown but we have a total, infer the rest.
        if not mgmt_exp and exp > (prog_exp + fundraise_exp):
            mgmt_exp = max(0, exp - prog_exp - fundraise_exp)
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


def key_signals(metrics):
    """
    Return a list of (level, message) for the most important findings.
    level is 'good', 'ok', or 'bad'.
    """
    if not metrics:
        return []

    latest = metrics[-1]
    signals = []

    per = latest["program_expense_ratio"]
    if per is not None:
        if per >= 80:
            signals.append(("good", f"{per}% of spending goes directly to programs — well above the 75% standard"))
        elif per >= 75:
            signals.append(("good", f"{per}% program expense ratio meets the 75% benchmark set by charity watchdogs"))
        elif per >= 60:
            signals.append(("ok", f"{per}% goes to programs — slightly below the 75% target, but not alarming"))
        else:
            signals.append(("bad", f"Only {per}% of spending reaches programs — overhead is high for a nonprofit"))

    mor = latest["months_of_reserves"]
    if mor is not None:
        if mor >= 6:
            signals.append(("good", f"{mor} months of operating reserves — strong cushion if funding is disrupted"))
        elif mor >= 3:
            signals.append(("ok", f"{mor} months of operating reserves — within the recommended 3–6 month range"))
        elif mor >= 1:
            signals.append(("bad", f"Only {mor} months of reserves — below the 3-month minimum most experts recommend"))
        else:
            signals.append(("bad", "Less than 1 month of operating reserves — very limited financial runway"))

    sm = latest["surplus_margin"]
    if sm is not None:
        if sm >= 5:
            signals.append(("good", f"Ended the year with a {sm}% surplus — actively building financial strength"))
        elif sm >= 0:
            signals.append(("ok", f"Near break-even ({sm}% surplus margin) — revenue covered expenses"))
        elif sm >= -5:
            signals.append(("ok", f"Spent {abs(sm):.1f}% more than it raised — small deficit worth monitoring"))
        else:
            signals.append(("bad", f"Spent {abs(sm):.1f}% more than it raised — a deficit this size is hard to sustain"))

    if len(metrics) >= 2:
        rev_list = [m["total_revenue"] for m in metrics if m["total_revenue"]]
        if len(rev_list) >= 2 and rev_list[-2]:
            trend = (rev_list[-1] - rev_list[-2]) / rev_list[-2] * 100
            if trend >= 10:
                signals.append(("good", f"Revenue grew {trend:.1f}% last year — strong upward momentum"))
            elif trend >= 3:
                signals.append(("good", f"Revenue grew {trend:.1f}% last year"))
            elif trend >= -3:
                signals.append(("ok", f"Revenue was roughly flat last year ({trend:+.1f}%)"))
            elif trend >= -10:
                signals.append(("bad", f"Revenue declined {abs(trend):.1f}% last year — worth investigating"))
            else:
                signals.append(("bad", f"Revenue dropped {abs(trend):.1f}% last year — a significant decline"))

    lta = latest["liabilities_to_assets"]
    if lta is not None and lta > 50:
        if lta > 80:
            signals.append(("bad", f"Liabilities are {lta}% of total assets — the organization carries a heavy debt load"))
        else:
            signals.append(("ok", f"Liabilities are {lta}% of assets — moderate but manageable debt level"))

    return signals


def generate_summary(org_name, metrics, score):
    """Return a 2–4 sentence plain-language health summary."""
    if not metrics or score is None:
        return None

    latest = metrics[-1]
    year = latest["year"]
    parts = []

    if score >= 85:
        parts.append(f"Based on {year} IRS filings, {org_name} is in excellent financial health.")
    elif score >= 70:
        parts.append(f"Based on {year} IRS filings, {org_name} is in good financial health.")
    elif score >= 55:
        parts.append(f"Based on {year} IRS filings, {org_name} shows adequate financial health with some areas to watch.")
    elif score >= 40:
        parts.append(f"Based on {year} IRS filings, {org_name} shows concerning financial indicators.")
    else:
        parts.append(f"Based on {year} IRS filings, {org_name} shows signs of significant financial stress.")

    per = latest["program_expense_ratio"]
    if per is not None:
        if per >= 80:
            parts.append(
                f"An impressive {per}% of total spending goes directly to programs and services — "
                f"well above the 75% standard that charity watchdogs like Charity Navigator use."
            )
        elif per >= 75:
            parts.append(
                f"{per}% of spending goes to programs, meeting the 75% standard used by charity watchdogs."
            )
        elif per >= 60:
            parts.append(
                f"{per}% of spending goes to programs, which is below the 75% standard "
                f"but not unusual for organizations with high administrative complexity."
            )
        else:
            parts.append(
                f"Only {per}% of spending reaches programs; the remaining {100 - per}% covers administration "
                f"and fundraising, which is higher than what most charity watchdogs recommend."
            )

    mor = latest["months_of_reserves"]
    if mor is not None:
        if mor >= 12:
            parts.append(
                f"The organization holds {mor} months of operating reserves — an exceptionally strong "
                f"financial cushion that provides stability through disruptions."
            )
        elif mor >= 6:
            parts.append(
                f"With {mor} months of operating reserves, the organization has a solid financial "
                f"cushion well within the healthy 3–6 month range."
            )
        elif mor >= 3:
            parts.append(
                f"The organization holds {mor} months of operating reserves, within the recommended 3–6 month range."
            )
        elif mor >= 1:
            parts.append(
                f"Operating reserves of only {mor} months are below the recommended 3-month minimum, "
                f"meaning the organization has limited runway if revenue were to drop unexpectedly."
            )
        else:
            parts.append(
                f"The organization has less than one month of operating reserves, "
                f"which is a significant financial vulnerability."
            )

    return " ".join(parts)


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
