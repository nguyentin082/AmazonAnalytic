# TiAmazon - Amazon Settlement Analytics

Du an phan tich Amazon Settlement theo pipeline tu dong: load data -> clean -> feature engineering -> analysis -> export bang ket qua -> xuat PDF report.

Muc tieu chinh: tao file report PDF o duong dan `outputs/amazon_settlement_report.pdf`.

## 1. Yeu cau moi truong

- macOS/Linux (khuyen nghi)
- Python 3.11+
- pip moi

Kiem tra nhanh:

```bash
python3 --version
pip --version
```

## 2. Cau truc thu muc

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

Luu y:
- Dat file raw settlement vao thu muc `data/`.
- Khong sua file raw truc tiep.

## 3. Cai dat va khoi tao

### Buoc 1: Tao virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Buoc 2: Cai dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Chay pipeline de xuat PDF

Chay lenh sau tai root project:

```bash
python main.py
```

Pipeline se thuc hien:
1. Load tat ca file settlement trong `data/`
2. Chuan hoa ten cot va validate schema
3. Clean data (parse datetime, convert numeric, clean text, filter transaction type)
4. Tao metrics tai chinh va time features
5. Phan tich SKU, time series, geography, fee
6. Trich xuat insights
7. Export CSV va tao PDF report

## 5. Dau ra mong doi

Sau khi chay thanh cong, ban se co:

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

## 6. Xac nhan PDF da tao dung

Kiem tra file PDF ton tai:

```bash
ls -lh outputs/amazon_settlement_report.pdf
```

Neu thay file co kich thuoc > 0 bytes la da xuat thanh cong.

## 7. Chay notebook (tuy chon)

Neu ban muon xem bang va chart chi tiet:

```bash
jupyter notebook main.ipynb
```

Notebook giup kiem tra trung gian va doi chieu ket qua, nhung viec xuat PDF chinh da duoc `main.py` xu ly.

## 8. Chay test truoc khi chay that

```bash
pytest -q
```

Test se kiem tra cac logic quan trong nhu schema validation va parse numeric/currency.

## 9. Loi thuong gap va cach xu ly

### Loi: `No data files found in .../data`

Nguyen nhan:
- Thu muc `data/` khong co file raw settlement.

Cach xu ly:
- Copy file `.csv` (hoac `.tsv`, `.txt`) vao `data/` roi chay lai `python main.py`.

### Loi validate schema (missing columns)

Nguyen nhan:
- File dau vao thieu cot bat buoc (vd: `date_time`, `settlement_id`, `type`, `sku`, ...).

Cach xu ly:
- Kiem tra file dau vao co dung Amazon settlement format khong.
- Dam bao dong header dung va ten cot khong bi thay doi.

### Tong tien theo type bi sai do dinh dang so

Da xu ly trong code:
- Parse tien te da bo ky tu `$` va dau `,` truoc khi `pd.to_numeric`.

Ban nen:
- Chay `pytest -q` de dam bao khong bi hoi quy.
- Doi chieu bang tong trong notebook neu can audit.

## 10. Lenh chay nhanh (copy/paste)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pytest -q
python main.py
ls -lh outputs/amazon_settlement_report.pdf
```
