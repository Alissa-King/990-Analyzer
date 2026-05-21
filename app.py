from flask import Flask, render_template, request, redirect, url_for, flash
import requests
from analyzer import fetch_org, search_orgs, compute_metrics, health_score, grade
from sample_data import SAMPLE_ORG, SAMPLE_FILINGS

app = Flask(__name__)
app.secret_key = "990-analyzer-secret"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    ein = request.args.get("ein", "").strip()

    if ein:
        return redirect(url_for("org_detail", ein=ein.replace("-", "")))

    if not query:
        return redirect(url_for("index"))

    try:
        results = search_orgs(query)
    except requests.RequestException as e:
        flash(f"Search failed: {e}", "danger")
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
        breakdown=breakdown,
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
