# src/query.py
import os, json, boto3
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.conditions import Attr

table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])

def handler(event, _ctx):
    qs = event.get("queryStringParameters") or {}
    vendor = qs.get("vendor")
    txdate = qs.get("date")               # yyyy-mm-dd

    if vendor:
        resp = table.scan(
            FilterExpression=Attr("Vendor").contains(vendor)
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
