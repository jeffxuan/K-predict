# K-predict

K-predict is a bilingual SCI/SIC investment-contest research workbench. It wraps
Kronos price forecasting, multi-factor scoring, prediction-error auditing, and
report-ready research notes into one local web app.

给同学看的图文下载指南：[docs/download-guide.md](docs/download-guide.md)

The first release focuses on the three contest stocks used by the prototype:

- `ADBE`
- `LLY`
- `GOOGL`

This project is for competition research and report writing. It is not financial
advice and is not intended for live trading.

## What Students Can Do

- Run Kronos `mini`, `small`, or `base` predictions from a browser.
- Compare predicted prices with holdout actual prices.
- Save every prediction and error audit locally.
- Review macro, fundamental, ESG, portfolio, and risk context.
- Export Chinese/English research notes for an investment-contest report.
- See exactly which files are inputs, outputs, demo data, and report material.

## Requirements

- Python 3.9-3.11
- Node.js 20+
- Git
- Internet access for the first Kronos clone and first Hugging Face model download

## First Install

If you are not familiar with command-line tools, start from the illustrated
Chinese guide: [docs/download-guide.md](docs/download-guide.md).

Clone this repository, then run:

```bash
bash scripts/setup_workbench.sh
```

The setup script will:

1. Clone Kronos into `kronos_repo/`.
2. Create `kronos_repo/.venv`.
3. Install Kronos, Flask API, and test dependencies.
4. Install React dependencies in `app/`.
5. Prepare small demo CSV files under `data/`.

`kronos_repo/`, virtual environments, `node_modules`, build files, and generated
outputs are intentionally not committed to GitHub.

## Start The Workbench

```bash
bash scripts/start_workbench.sh
```

Then open:

```text
http://127.0.0.1:5173
```

Keep the terminal open while using the app. Press `Ctrl+C` to stop both the API
and React dev server.

The first Kronos prediction can be slow because model weights are downloaded
from Hugging Face. For a quick classroom demo, start with `Kronos-mini`; for
stronger report evidence, compare against `Kronos-base`.

## Workbench Pages

- `Overview`: macro holding score, portfolio weights, factor ranking, latest runs
- `Data Library`: every important file, its purpose, source, and report status
- `Run Prediction`: choose ticker, model, lookback, and prediction length
- `Error Audit`: MAPE, direction accuracy, predicted return, actual return
- `Research Notes`: AI-readable notes for report writing
- `Guide`: bilingual workflow instructions

Use the language button in the top bar to switch between Chinese and English.

## Data Layout

Committed example data:

- `data/prices.csv`: unified OHLCV table
- `data/fundamentals.csv`: ROE, growth, valuation, FCFF, Z-score, industry
- `data/esg.csv`: ESG rating, risk score, governance notes
- `data/macro.csv`: Fed, GDP, unemployment, VIX, flows, macro scores
- `data/portfolio.csv`: default contest portfolio weights
- `data/kronos_daily/*.csv`: Kronos-ready daily price files

Generated local outputs:

- `outputs/ui_predictions/{model}/{ticker}_*.json`
- `outputs/ui_research_log/prediction_runs.csv`
- `outputs/ui_research_log/prediction_points.csv`
- `outputs/ui_research_log/research_notes.md`
- `outputs/multifactor_report.json`

Generated outputs are ignored by Git so each team can keep its own experiment
history without publishing local paths, logs, or model results.

## Script Workflow

Prepare or refresh demo data:

```bash
kronos_repo/.venv/bin/python scripts/prepare_data.py --no-live --overwrite-prices
```

Run the multi-factor report:

```bash
kronos_repo/.venv/bin/python scripts/run_pipeline.py
```

Audit Kronos JSON prediction files:

```bash
kronos_repo/.venv/bin/python scripts/audit_predictions.py \
  --results-dir outputs/ui_predictions \
  --output-dir outputs/ui_research_log
```

## Verification

Frontend build:

```bash
cd app
npm run build
```

Python tests:

```bash
kronos_repo/.venv/bin/python -m pytest -q tests
```

## Repository

GitHub: [jeffxuan/K-predict](https://github.com/jeffxuan/K-predict)
