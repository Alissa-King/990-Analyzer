# 990 Agency Health Analyzer

A Flask web app that pulls IRS Form 990 data from the **ProPublica Nonprofit Explorer API** and produces an instant financial health report for any U.S. nonprofit.

## Features

- **Search** by EIN or organization name
- **Health Score** (0–100, letter grade) calculated from:
  - Program Expense Ratio — what share of spending goes to programs
  - Operating Reserves — months of expenses covered by net assets
  - Surplus Margin — whether revenue exceeds expenses
  - Revenue Trend — year-over-year growth
  - Liability Ratio — debt relative to total assets
- **Interactive charts** — revenue vs. expenses, net assets trend, stacked expense breakdown
- **Year-by-year table** with color-coded surplus/deficit
- **Demo mode** at `/demo` — works with no internet access

## Quick Start

```bash
pip install -r requirements.txt
python app.py
```

Then open http://localhost:5000.

## Usage

1. Enter a 9-digit EIN (e.g. `53-0196605`) and click **Analyze**
2. Or type an organization name and click **Search**, then pick from results
3. Visit `/demo` to see a sample report without any API calls

## Data Source

Financial data comes from the [ProPublica Nonprofit Explorer API](https://projects.propublica.org/nonprofits/api/v2) which indexes IRS e-file submissions. Not all nonprofits file electronically; paper filers won't appear.

## Production Deployment

```bash
gunicorn app:app -b 0.0.0.0:8000
```
