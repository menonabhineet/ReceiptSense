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
        "FileKey":   key,
        "Total":     _norm_total(total),
        "Items":     line_items,
    }
    table.put_item(Item=item)
    logging.info(" Saved %s", item["ReceiptId"])
    return {"statusCode": 200, "body": json.dumps(item, default=str)}
