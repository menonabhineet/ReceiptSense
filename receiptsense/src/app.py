import os, json, uuid, decimal, re, logging, boto3
from dateutil import parser as dparse

textract = boto3.client("textract")
table    = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
bedrock  = boto3.client("bedrock-runtime", region_name="us-east-1")

logging.basicConfig(level=logging.INFO)

_CATEGORY_MAP = {
    "costco": "groceries",     "walmart": "groceries", "whole foods": "groceries",
    "trader joes": "groceries","kroger": "groceries",  "jewel osco": "groceries",
    "mcdonalds": "dining",     "starbucks": "dining",  "chipotle": "dining", "subway": "dining",
    "panera": "dining",
    "shell": "fuel", "chevron": "fuel", "bp": "fuel", "exxon": "fuel",
    "uber": "travel", "lyft": "travel", "delta": "travel",
}

_CANON_MAP = {
    "costco wholesale": "costco",
    "wholefoods": "whole foods",
    "traderjoes": "trader joes",
    "jewelosco": "jewel osco",
    "lyf": "lyft",
}

_RE_NUM  = re.compile(r"[^\d.]")
_WS      = re.compile(r"\s+")
_PUNCT   = re.compile(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$")

def _clean_vendor(raw: str) -> str:
    txt = _WS.sub(" ", raw)
    txt = _PUNCT.sub("", txt)
    return txt.strip().lower()

def _safe_decimal(raw: str) -> decimal.Decimal:
    try:
        return decimal.Decimal(raw)
    except decimal.InvalidOperation:
        return decimal.Decimal("0")

def _norm_total(txt: str) -> decimal.Decimal:
    return _safe_decimal(_RE_NUM.sub("", txt) or "0")

def _norm_date(txt: str) -> str:
    try:
        return dparse.parse(txt, fuzzy=True).date().isoformat()
    except Exception:
        return "1970-01-01"

def _bedrock_complete(prompt: str, max_tokens: int) -> str:
    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0
    }
    resp = bedrock.invoke_model(
        modelId="anthropic.claude-3-sonnet-20240229-v1:0",
        body=json.dumps(payload),
        contentType="application/json",
        accept="application/json"
    )
    return json.loads(resp["body"].read())["content"][0]["text"].strip()

def _vendor_norm(raw: str) -> str:
    clean = _clean_vendor(raw)
    canonical = _CANON_MAP.get(clean, clean)
    if canonical in _CATEGORY_MAP:
        return canonical
    try:
        prompt = (f'Return only the canonical vendor name in lowercase for: "{clean}". '
                  "Do not add extra words.\nAnswer:")
        norm = _clean_vendor(_bedrock_complete(prompt, 10))
        return norm or canonical
    except Exception as e:
        logging.warning("Vendor norm Bedrock error → %s", e)
        return canonical

def _classify(vendor_norm: str) -> str:
    if vendor_norm in _CATEGORY_MAP:
        return _CATEGORY_MAP[vendor_norm]
    try:
        prompt = (f"Choose one category (groceries, dining, fuel, utilities, "
                  f"travel, other) for vendor:\n{vendor_norm}\nCategory:")
        cat = _clean_vendor(_bedrock_complete(prompt, 5))
        return cat if cat in {"groceries","dining","fuel","utilities","travel"} else "other"
    except Exception as e:
        logging.warning("Category Bedrock error → %s", e)
        return "other"

def handler(event, _ctx):
    rec = event["Records"][0]["s3"]
    bucket, key = rec["bucket"]["name"], rec["object"]["key"]

    tex = textract.analyze_expense(
        Document={"S3Object": {"Bucket": bucket, "Name": key}}
    )

    vendor = total = date = "UNKNOWN"
    line_items = []

    for doc in tex["ExpenseDocuments"]:
        for fld in doc.get("SummaryFields", []):
            t = fld["Type"]["Text"]
            v = fld.get("ValueDetection", {}).get("Text", "")
            if t in ("VENDOR_NAME", "VENDOR"):
                vendor = v.strip()
            elif t == "TOTAL":
                total = v.strip()
            elif t in ("INVOICE_RECEIPT_DATE", "DATE"):
                date = v.strip()

        for grp in doc.get("LineItemGroups", []):
            for itm in grp.get("LineItems", []):
                cells = itm["LineItemExpenseFields"]
                label = cells[0]["ValueDetection"]["Text"]
                amt   = cells[-1]["ValueDetection"]["Text"]
                line_items.append({"Label": label, "Amount": _norm_total(amt)})

    vendor_norm = _vendor_norm(vendor)
    category    = _classify(vendor_norm)

    item = {
        "ReceiptId": str(uuid.uuid4()),
        "Vendor":    vendor,
        "VendorNorm": vendor_norm,
        "Category":  category,
        "TxDate":    _norm_date(date),
        "Date":      date,
        "FileKey":   key,
        "Total":     _norm_total(total),
        "Items":     line_items,
    }
    table.put_item(Item=item)
    logging.info("✅ Saved %s  vendor=%s  cat=%s", item["ReceiptId"], vendor_norm, category)

    return {"statusCode": 200, "body": json.dumps(item, default=str)}
