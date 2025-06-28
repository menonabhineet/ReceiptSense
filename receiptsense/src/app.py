import json, os, uuid, boto3, decimal
from boto3.dynamodb.conditions import Key

textract = boto3.client("textract")
dynamo   = boto3.resource("dynamodb")
table    = dynamo.Table(os.environ["TABLE_NAME"])

def handler(event, context):
    # 1. Get bucket/key from event
    record = event["Records"][0]["s3"]
    bucket = record["bucket"]["name"]
    key    = record["object"]["key"]

    # 2. Textract AnalyzeExpense
    res = textract.analyze_expense(
        Document={"S3Object": {"Bucket": bucket, "Name": key}}
    )

    # 3. Pull a few common fields (vendor, total, date)
    vendor = total = date = "UNKNOWN"
    for doc in res["ExpenseDocuments"]:
        for f in doc["SummaryFields"]:
            n = f["Type"]["Text"]
            v = f.get("ValueDetection", {}).get("Text", "")
            if n == "VENDOR_NAME":  vendor = v
            if n == "TOTAL":        total  = v
            if n == "INVOICE_RECEIPT_DATE": date = v

    # 4. Persist
    item = {
        "ReceiptId": str(uuid.uuid4()),
        "FileKey": key,
        "Vendor": vendor,
        "Date": date,
        "Total": decimal.Decimal(total.replace("$","")) if total.replace(".","",1).isdigit() else decimal.Decimal("0"),
    }
    table.put_item(Item=item)
    return {"statusCode": 200, "body": json.dumps(item, default=str)}
