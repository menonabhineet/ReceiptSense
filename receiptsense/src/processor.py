# src/processor.py
import os, json, uuid, decimal, re, logging, boto3
from dateutil import parser as dparse

logging.basicConfig(level=logging.INFO)
textract = boto3.client("textract")
table    = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])


def _norm_total(txt: str) -> decimal.Decimal:
    """Strip currency symbols and commas → Decimal."""
    clean = re.sub(r"[^\d.]", "", txt)
    return decimal.Decimal(clean or "0")

def _norm_date(txt: str) -> str:
    """Return yyyy-mm-dd or 1970-01-01 on failure."""
    try:
        return dparse.parse(txt, fuzzy=True).date().isoformat()
    except Exception:
        return "1970-01-01"

def _vendor_norm(raw: str) -> str:
    """
    Ask Claude-3 Sonnet to return the canonical brand name in lowercase.
    Fallback to simple lower() if Bedrock fails or quota exhausted.
    """
    prompt = (
        f'Return only the canonical vendor name in lowercase for: "{raw}". '
        "Do not add extra words.\nAnswer:"
    )
    try:
        body = {
            "modelId": "anthropic.claude-3-sonnet-20240229-v1:0",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 10,
            "temperature": 0
        }
        resp = bedrock.invoke_model(
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json"
        )
        norm = json.loads(resp["body"].read())["content"][0]["text"].strip()
        norm = re.sub(r"\s+", " ", norm).lower()
        return norm or raw.lower()
    except Exception as e:
        logging.warning("Bedrock normaliser failed → %s", e)
        return raw.lower()

def handler(event, _ctx):
    rec   = event["Records"][0]["s3"]
    bucket, key = rec["bucket"]["name"], rec["object"]["key"]
    logging.info("New upload %s/%s", bucket, key)

    # 1. Textract
    tex = textract.analyze_expense(
        Document={"S3Object": {"Bucket": bucket, "Name": key}}
    )

    vendor = total = date = "UNKNOWN"
    line_items = []

    for doc in tex["ExpenseDocuments"]:
        # summary fields
        for fld in doc.get("SummaryFields", []):
            t, v = fld["Type"]["Text"], fld.get("ValueDetection", {}).get("Text", "")
            if t in ("VENDOR_NAME", "VENDOR"):
                vendor = v
            elif t == "TOTAL":
                total  = v.strip()
            elif t in ("INVOICE_RECEIPT_DATE", "DATE"):
                date   = v.strip()

        # individual items
        for grp in doc.get("LineItemGroups", []):
            for itm in grp.get("LineItems", []):
                label = itm["LineItemExpenseFields"][0]["ValueDetection"]["Text"]
                amt   = itm["LineItemExpenseFields"][-1]["ValueDetection"]["Text"]
                line_items.append({"Label": label, "Amount": _norm_total(amt)})

    item = {
        "ReceiptId": str(uuid.uuid4()),
        "Vendor":    vendor,
        "TxDate":    _norm_date(date),
        "VendorNorm": _vendor_norm(vendor),
        "FileKey":   key,
        "Total":     _norm_total(total),
        "Items":     line_items,
    }
    table.put_item(Item=item)
    logging.info(" Saved %s", item["ReceiptId"])
    return {"statusCode": 200, "body": json.dumps(item, default=str)}
