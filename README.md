# TiAmazon - Amazon Settlement Analytics

This project analyzes Amazon settlement data through an automated pipeline: load data -> clean -> feature engineering -> analysis -> export results -> generate a PDF report.

The main goal is to create a PDF report at `outputs/amazon_settlement_report.pdf`.

## 1. Environment Requirements

- macOS/Linux (recommended)
- Python 3.11+
- Up-to-date `pip`

Quick check:

```bash
python3 --version
pip --version
```

## 2. Project Structure

```text
TiAmazon/
  data/
    <raw settlement files .csv/.tsv/.txt>
    processed/
  outputs/
  src/
  tests/
  main.py
  main.ipynb
  requirements.txt
```

Notes:
- Place raw settlement files in the `data/` folder.
- Do not edit raw files directly.

## 3. Setup and Installation

### Step 1: Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 2: Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Run the Pipeline to Generate the PDF

Run the following command from the project root:

```bash
python main.py
```

The pipeline will:
1. Load all settlement files in `data/`
2. Standardize column names and validate the schema
3. Clean the data (parse datetimes, convert numeric values, clean text, filter transaction types)
4. Build financial metrics and time-based features
5. Analyze SKU, time series, geography, and fee patterns
6. Extract insights
7. Export CSV files and generate a PDF report

## 5. Expected Outputs

After a successful run, you should see:

- `data/processed/clean.csv`
- `outputs/sku_performance.csv`
- `outputs/daily_report.csv`
- `outputs/geographic_performance.csv`
- `outputs/fee_breakdown.csv`
- `outputs/order_level_report.csv`
- `outputs/top_sku_by_revenue.csv`
- `outputs/top_sku_by_profit.csv`
- `outputs/low_or_negative_margin_sku.csv`
- `outputs/abnormal_high_fee_sku.csv`
- `outputs/top_regions_by_profit.csv`
- `outputs/best_days_by_profit.csv`
- `outputs/worst_days_by_profit.csv`
- `outputs/amazon_settlement_report.pdf`

## 6. Verify the PDF Was Created

Check that the PDF file exists:

```bash
ls -lh outputs/amazon_settlement_report.pdf
```

If the file exists and is larger than 0 bytes, the export succeeded.

## 7. Run the Notebook (Optional)

If you want to inspect tables and charts in more detail:

```bash
jupyter notebook main.ipynb
```

The notebook is useful for intermediate checks and result comparison, but the main PDF export is handled by `main.py`.

## 8. Run Tests Before Production Use

```bash
pytest -q
```

The tests cover important logic such as schema validation and numeric/currency parsing.

## 9. Common Errors and Fixes

### Error: `No data files found in .../data`

Cause:
- The `data/` folder does not contain any raw settlement files.

Fix:
- Copy a `.csv` file (or `.tsv`, `.txt`) into `data/`, then run `python main.py` again.

### Error: Schema validation fails (missing columns)

Cause:
- The input file is missing required columns such as `date_time`, `settlement_id`, `type`, `sku`, and others.

Fix:
- Verify that the input file matches the expected Amazon settlement format.
- Make sure the header row is correct and column names were not changed.

### Totals by type are incorrect because of number formatting

Handled in code:
- Currency parsing removes `$` and `,` before calling `pd.to_numeric`.

Recommended checks:
- Run `pytest -q` to make sure there are no regressions.
- Compare summary tables in the notebook if you need to audit the results.

## 10. Quick Run Commands (Copy/Paste)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pytest -q
python main.py
ls -lh outputs/amazon_settlement_report.pdf
```
