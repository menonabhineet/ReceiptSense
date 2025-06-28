# src/presign.py
import os, json, boto3, uuid

s3 = boto3.client("s3")
bucket = os.environ["BUCKET"]

def handler(event, _ctx):
    try:
        key = f"{uuid.uuid4()}.jpg"
        presigned = s3.generate_presigned_post(
            Bucket=bucket,
            Key=key,
            Fields={"Content-Type": "image/jpeg"},
            Conditions=[["starts-with", "$Content-Type", "image/"]],
            ExpiresIn=300,
        )
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*"
            },
            "body": json.dumps({
                "presigned": presigned,
                "key": key
            }),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*"
            },
            "body": json.dumps({"error": str(e)}),
        }
