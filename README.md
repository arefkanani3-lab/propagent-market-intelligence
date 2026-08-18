# PropAgent Market Intelligence Engine — V0

نسخه اولیه Backend برای تبدیل فایل‌های DLD به Market Intelligence قابل استفاده توسط PropAgent.

## V0 چه کار می‌کند؟

1. فایل `CSV` یا `XLSX` معاملات DLD را می‌گیرد.
2. ستون‌ها را Normalize می‌کند.
3. Duplicateها و رکوردهای غیرقابل استفاده را مدیریت می‌کند.
4. داده را داخل PostgreSQL ذخیره می‌کند.
5. برای هر Area آمار بازار تولید می‌کند:
   - تعداد معاملات
   - Average Price
   - Median Price
   - Average PPSF
   - Median PPSF
   - Min / Max Price
6. برای یک Subject Property، Comparable پیدا می‌کند.
7. Estimated Market Value و Value Range تولید می‌کند.
8. Asking Price را با Estimated Value مقایسه می‌کند.
9. Confidence Score و لیست Comparables برمی‌گرداند.

> این V0 یک مدل تحلیلی/Comparable است و «ارزیابی رسمی یا licensed valuation» نیست.

---

## Architecture

```text
DLD CSV / Excel
      ↓
Ingestion API
      ↓
Cleaning + Normalization
      ↓
PostgreSQL
      ↓
Market Analytics
      ↓
Comparable Engine
      ↓
Valuation Engine
      ↓
REST API
      ↓
PropAgent / AI Agent / Dashboard
```

---

## سریع‌ترین روش اجرا با Docker

### 1) Docker Desktop را نصب و اجرا کنید

### 2) داخل فولدر پروژه:

```bash
docker compose up --build
```

### 3) Swagger را باز کنید

```text
http://localhost:8000/docs
```

API آماده است.

---

## Endpointها

### Health

```http
GET /health
```

### Upload DLD file

```http
POST /ingest/dld
Content-Type: multipart/form-data
file=<CSV or XLSX>
```

خروجی نمونه:

```json
{
  "raw_rows": 1029,
  "valid_rows": 1029,
  "inserted": 1029,
  "duplicates_skipped": 0
}
```

اگر همان فایل دوباره Upload شود، Duplicateها دوباره وارد Database نمی‌شوند.

### Market Analytics by Area

```http
GET /analytics/areas?lookback_days=365
```

خروجی هر Area شامل:

```json
{
  "area": "JUMEIRAH VILLAGE CIRCLE",
  "transactions": 48,
  "average_price": 0,
  "median_price": 0,
  "average_ppsf": 0,
  "median_ppsf": 0,
  "min_price": 0,
  "max_price": 0
}
```

اعداد بالا صرفاً شکل Response را نشان می‌دهند و صفرها Placeholder هستند.

### Property Valuation

```http
POST /valuation
Content-Type: application/json
```

Body:

```json
{
  "area": "JUMEIRAH VILLAGE CIRCLE",
  "project": null,
  "property_subtype": "Villa",
  "bedrooms": 3,
  "size_sqm": 160,
  "asking_price": 3000000,
  "lookback_days": 365,
  "max_size_difference": 0.35,
  "max_comparables": 10
}
```

خروجی:

```text
Estimated Market Value
Estimated Low / High
Estimated PPSF
Asking vs Estimate %
Comparable Count
Eligible Transaction Count
Confidence Score
Comparable Transactions
```

---

## منطق Comparable V0

Candidateها ابتدا بر اساس موارد زیر Filter می‌شوند:

```text
Area
+ Project (optional)
+ Property Subtype (optional)
+ Bedrooms (optional)
+ Lookback Period
+ Size Difference
```

سپس Similarity بر اساس:

```text
Size Proximity
+ Transaction Recency
```

محاسبه می‌شود.

Top Comparables انتخاب می‌شوند و:

```text
Similarity Weighted PPSF
× Subject Size
=
Estimated Market Value
```

اگر Project مشخص شده باشد ولی کمتر از 3 Comparable وجود داشته باشد، V0 به‌صورت خودکار از Project Level به Area Level Fallback می‌کند.

---

## نکته مهم برای Accuracy

این نسخه هنوز نباید به‌عنوان Final AVM استفاده شود.

مرحله بعدی باید **Backtesting / Validation** باشد:

```text
Known DLD Transaction
→ Hide its actual sale price
→ Estimate using transactions available before that sale
→ Compare Estimate vs Actual
→ Calculate MAPE / Median Error / % within ±5%, ±10%, ±15%
```

بعد از این تست می‌توانیم Weightها، Fallback Rules و Confidence Score را Calibration کنیم.

---

## توسعه‌های بعدی

### V0.2
- Project → Community → Area fallback hierarchy
- Outlier detection
- Median / trimmed PPSF
- Validation / Backtesting Engine
- Time-adjusted comparables

### V0.3
- DLD Rent data
- Rental Yield Engine
- 3/6/12 month trends
- Liquidity / transaction velocity

### V1
- Current Listings
- Asking Price Intelligence
- Below Market Detector
- Opportunity Score

### V2
- Buyer Profile
- Property Recommendation Engine
- AI Explanation / Agent Copilot
