import os
import re
import logging
from flask import Flask, render_template, request, redirect, url_for, flash
import requests
from analyzer import fetch_org, search_orgs, compute_metrics, health_score, grade, key_signals, generate_summary

_COLOR_HEX = {
    "success":   "#059669",
    "info":      "#0284c7",
    "warning":   "#d97706",
    "orange":    "#ea580c",
    "danger":    "#dc2626",
    "secondary": "#6b7280",
}
from sample_data import SAMPLE_ORG, SAMPLE_FILINGS

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "990-analyzer-secret")


@app.route("/")
def index():
    return render_template("index.html")


_EIN_RE = re.compile(r"^\d{2}-?\d{7}$")


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()

    if not query:
        return redirect(url_for("index"))

    # Auto-detect EIN: 9 digits optionally formatted as XX-XXXXXXX
    if _EIN_RE.match(query):
        return redirect(url_for("org_detail", ein=query.replace("-", "")))

    try:
        results = search_orgs(query)
    except requests.RequestException as e:
        flash(f"Search failed: {e}", "danger")
        results = []
    except Exception as e:
        logging.exception("Unexpected error in search")
        flash("An unexpected error occurred. Please try again.", "danger")
        results = []

    return render_template("search_results.html", query=query, results=results)


@app.route("/org/<ein>")
def org_detail(ein):
    try:
        org, filings = fetch_org(ein)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            flash(f"No organization found for EIN {ein}.", "warning")
        else:
            flash(f"API error: {e}", "danger")
        return redirect(url_for("index"))
    except requests.RequestException as e:
        flash(f"Network error: {e}", "danger")
        return redirect(url_for("index"))
    except Exception as e:
        logging.exception("Unexpected error fetching org %s", ein)
        flash("An unexpected error occurred. Please try again.", "danger")
        return redirect(url_for("index"))

    if not org:
        flash(f"No organization found for EIN {ein}.", "warning")
        return redirect(url_for("index"))

    return _render_org(org, filings)


@app.route("/demo")
def demo():
    """Load the sample org without hitting any external API."""
    return _render_org(SAMPLE_ORG, SAMPLE_FILINGS)


def _render_org(org, filings):
    metrics = compute_metrics(filings)
    score, breakdown = health_score(metrics)
    letter, color = grade(score)
    color_hex = _COLOR_HEX.get(color, "#6b7280")
    signals = key_signals(metrics)
    summary = generate_summary(org.get("name", "This organization"), metrics, score)

    years = [m["year"] for m in metrics]
    revenues = [m["total_revenue"] for m in metrics]
    expenses = [m["total_expenses"] for m in metrics]
    net_assets = [m["net_assets"] for m in metrics]
    prog_exp = [m["program_expenses"] for m in metrics]
    mgmt_exp = [m["mgmt_expenses"] for m in metrics]
    fund_exp = [m["fundraising_expenses"] for m in metrics]

    return render_template(
        "org_detail.html",
        org=org,
        metrics=metrics,
        score=score,
        letter=letter,
        color=color,
        color_hex=color_hex,
        breakdown=breakdown,
        signals=signals,
        summary=summary,
        years=years,
        revenues=revenues,
        expenses=expenses,
        net_assets=net_assets,
        prog_exp=prog_exp,
        mgmt_exp=mgmt_exp,
        fund_exp=fund_exp,
        latest=metrics[-1] if metrics else None,
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
