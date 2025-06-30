import os, csv, io, json, boto3, time, uuid
table   = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
s3      = boto3.client("s3")
bucket  = os.environ["BUCKET_NAME"]

def handler(event, _):
    scan = table.scan()
    rows = scan["Items"]

    csv_buf = io.StringIO()
    writer  = csv.DictWriter(csv_buf, fieldnames=["TxDate","Vendor","Total","ReceiptId"])
    writer.writeheader()
    for r in rows:
        writer.writerow({
            "TxDate":  r.get("Date",""),
            "Vendor":  r.get("Vendor",""),
            "Total":   r.get("Total",""),
            "ReceiptId": r["ReceiptId"]
        })

    key = f"exports/{uuid.uuid4()}.csv"
    s3.put_object(Bucket=bucket, Key=key, Body=csv_buf.getvalue(), ContentType="text/csv")

    url = s3.generate_presigned_url("get_object",
                                    Params={"Bucket": bucket, "Key": key},
                                    ExpiresIn=900)

    return {
        "statusCode": 200,
        "headers": {"Access-Control-Allow-Origin": "*"},
        "body": json.dumps({"download": url})
    }
