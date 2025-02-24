import json
from app import process_plan

def handler(event, context):
    plan        = json.loads(event["body"])
    param_full  = event.get("queryStringParameters", {}).get("full")

    if param_full and param_full.lower() == "true":
        param_full = True
    else:
        param_full = False

    result      = process_plan(plan, param_full)

    return {
        'statusCode': 200,
        'body': result
    }