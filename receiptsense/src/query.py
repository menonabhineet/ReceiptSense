import os, json, boto3
from datetime import datetime, timedelta
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.conditions import Attr

table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])

def _month_range(yyyy_mm: str):
    """'2025-06' → ('2025-06-01', '2025-06-30')"""
    first = datetime.strptime(yyyy_mm, "%Y-%m")
    # jump to next month, back 1 day
    last  = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    return first.strftime("%Y-%m-%d"), last.strftime("%Y-%m-%d")

def handler(event, _ctx):
    qs = event.get("queryStringParameters") or {}
    vendor = qs.get("vendor")
    month  = qs.get("month") 
    txdate = qs.get("date")               # yyyy-mm-dd

    if vendor:
        resp = table.scan(
            FilterExpression=Attr("VendorNorm").contains(vendor.lower())
        )
    elif month:
        resp = table.scan(
            IndexName="DateIndex",
            FilterExpression=Attr("TxDate").begins_with(month)
    )
    elif txdate:
        resp = table.query(
            IndexName="DateIndex",
            KeyConditionExpression=Key("TxDate").eq(txdate)
        )
    else:
        resp = table.scan()

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*", },
        "body": json.dumps(resp["Items"], default=str),
    }
