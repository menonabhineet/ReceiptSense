import os, json, boto3
table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])

def handler(event, _):
    rid = event["pathParameters"]["rid"]
    table.delete_item(Key={"ReceiptId": rid})
    return {
    "statusCode": 204,
    "headers": {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "*"
    },
    "body": ""
}
