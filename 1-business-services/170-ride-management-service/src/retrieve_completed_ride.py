import os
import sys
import logging
import json
import datetime
import random
import time
import uuid
import boto3
from botocore.exceptions import ClientError
from pprint import pprint
import aux
import aux_api

# ---------------------------------------------------------------------------------------------------------------------
# "Global variables" - what is the correct term for these things in Python?
# ---------------------------------------------------------------------------------------------------------------------

ENV_STAGE = "STAGE"
ENV_WORKLOAD = "WORKLOAD"
ENV_SERVICE = "SERVICE"
ENV_LOG_LEVEL = "LOG_LEVEL"
ENV_RIDES_STORE_TABLE_NAME = "RIDES_STORE_TABLE_NAME"

STR_NONE = "NONE"

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

# ---------------------------------------------------------------------------------------------------------------------
# If the environment advises on a specific debug level, set it accordingly.
# ---------------------------------------------------------------------------------------------------------------------

def update_debug_level(event, context):
    LOGGER.debug("Checking for a directive for the log level in environment variable %s.", ENV_LOG_LEVEL)
    env_log_level = os.environ.get(ENV_LOG_LEVEL, STR_NONE)
    LOGGER.debug("Found: %s", env_log_level)
    numeric_log_level = getattr(logging, env_log_level.upper(), None)
    if not isinstance(numeric_log_level, int):
        # If we didn't find a valid log level directive, let's stay with DEBUG.
        LOGGER.debug("No valid directive found, so staying with DEBUG.")
        LOGGER.setLevel(logging.DEBUG)
    else:
        # Adjust log level according to the directive we found.
        LOGGER.debug("Adjusting log level to %d now.", numeric_log_level)
        LOGGER.setLevel(numeric_log_level)

# ---------------------------------------------------------------------------------------------------------------------
# Log environment details.
# ---------------------------------------------------------------------------------------------------------------------

def log_env_details():
    LOGGER.debug("environment variables: %s", os.environ)

# ---------------------------------------------------------------------------------------------------------------------
# Log event and context details.
# ---------------------------------------------------------------------------------------------------------------------

def log_event_and_context(event, context):
    LOGGER.debug("event: %s", event)
    # Uncomment the next line if you need the incoming Lambda event pretty-printed in your log.
    #print("event:\n" + json.dumps(event, indent=4))
    LOGGER.debug("context: %s", context)

# ---------------------------------------------------------------------------------------------------------------------
# Retrieve the current timestamp.
# ---------------------------------------------------------------------------------------------------------------------

def get_current_date():
    current_date = datetime.date.today().isoformat()
    LOGGER.debug("current_date: %s", current_date)
    return current_date

# ---------------------------------------------------------------------------------------------------------------------
# Update metric for requests per customer.
# ---------------------------------------------------------------------------------------------------------------------

def update_metric_for_requests_per_customer(customer_id):
    cloudwatch = boto3.client("cloudwatch")
    response = cloudwatch.put_metric_data(
        # MetricData = [{
        #     "MetricName": "KPIs",
        #     "Dimensions": [{
        #         "Name": "customer-id",
        #         "Value": customer_id
        #     }, {
        #         "Name": "unicorn-id",
        #         "Value": unicorn_id
        #     }],
        #     "Unit": "None",
        #     "Value": random.randint(1, 500)
        # }],
        MetricData = [{
            "MetricName": "Completed ride retrievals per customer",
            "Dimensions": [{
                "Name": "customer-id",
                "Value": customer_id
            }],
            "Unit": "Count",
            "Value": 1
        }],
        Namespace = "Wild Rydes"
    )
    LOGGER.debug("CW response: %s", response)

def get_or_create_log_stream(cw_logs, log_group_name, log_stream_name):
    
    response = cw_logs.describe_log_streams(
        logGroupName = log_group_name,
        logStreamNamePrefix = log_stream_name,
        orderBy = "LogStreamName",
        descending = True,
        nextToken = 'string',
        limit = 5
    )

def log_full_request(event):
    
    current_date = get_current_date()
    cw_logs = boto3.client('logs')
    LOG_GROUP = "FULL-REQUESTS"
    LOG_STREAM = LOG_GROUP + "_" + current_date
    #cw_logs.create_log_group(logGroupName=LOG_GROUP)
    cw_logs.create_log_stream(logGroupName=LOG_GROUP, logStreamName=LOG_STREAM)
    timestamp = int(round(time.time() * 1000))

    data = {
        "protocol": event["headers"]["X-Forwarded-Proto"],
        "host": event["headers"]["Host"],
        "path": event["requestContext"]["path"],
        "query-string-parameters": event["queryStringParameters"]
    }

    response = cw_logs.put_log_events(
    logGroupName=LOG_GROUP,
    logStreamName=LOG_STREAM,
    logEvents=[
        {
            "timestamp": timestamp,
            "message": time.strftime('%Y-%m-%d %H:%M:%S') + "\t" + json.dumps(data)
        }
    ])    

# ---------------------------------------------------------------------------------------------------------------------
# Fetch ride details from the database.
# ---------------------------------------------------------------------------------------------------------------------

def fetch_ride_details(unicorn_id, customer_id, submitted_at):
    try:
        LOGGER.debug("Fetch ride details from the database.")
        table_name = os.environ.get(ENV_RIDES_STORE_TABLE_NAME)
        LOGGER.debug("table_name: %s", table_name)

        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)
        response = table.get_item(Key = { "customer-id": customer_id, "submitted-at": submitted_at })

        LOGGER.debug("Ride details successfully fetched.")
        LOGGER.debug("response: %s", response)
        full_item = response["Item"]
        LOGGER.debug("full_item: %s", full_item)
        ride_details = full_item["ride-details"]
        LOGGER.debug("ride_details: %s", ride_details)
        return json.loads(ride_details)
    except Exception as ex:
        LOGGER.exception("Something went wrong with fetching the ride details.")
        LOGGER.exception(ex)
        return STR_NONE

# ---------------------------------------------------------------------------------------------------------------------
# Use meta information from incoming request to construct the self link for the resource representation.
# ---------------------------------------------------------------------------------------------------------------------

def create_self_link_url(event, unicorn_id, customer_id, submitted_at):

    link_protocol = event["headers"]["X-Forwarded-Proto"]
    LOGGER.debug("link_protocol: %s", link_protocol)

    link_host = event["headers"]["Host"]
    LOGGER.debug("link_host: %s", link_host)

    link_path = event["requestContext"]["path"]
    LOGGER.debug("link_path: %s", link_path)

    link_base_url = link_protocol + "://" + link_host + link_path
    LOGGER.debug("link_base_url: %s", link_base_url)
    
    link_full_url = link_base_url
    link_full_url += "?unicorn-id=" + unicorn_id
    link_full_url += "&customer-id=" + customer_id
    link_full_url += "&submitted-at=" + submitted_at
    LOGGER.debug("link_full_url: %s", link_full_url)

    return link_full_url

# ---------------------------------------------------------------------------------------------------------------------
# Lambda handler.
# ---------------------------------------------------------------------------------------------------------------------

def lambda_handler(event, context):

    # If the environment advises on a specific debug level, set it accordingly.
    aux.update_log_level(LOGGER, event, context)
    # Log environment details.
    aux.log_env_details(LOGGER)
    # Log request details.
    aux.log_event_and_context(LOGGER, event, context)
    # Publish Lambda event to the respective event logging topic.
    aux_api.publish_apigw_lambda_event(LOGGER, event)

    # Extract unicorn ID from request query parameter.
    unicorn_id = event["queryStringParameters"]["unicorn-id"]
    LOGGER.debug("unicorn_id: %s", unicorn_id)
    # Extract customer ID from request query parameter.
    customer_id = event["queryStringParameters"]["customer-id"]
    LOGGER.debug("customer_id: %s", customer_id)
    # Update metric for customer ID.
    #update_metric_for_requests_per_customer(customer_id)
    # Log full request.
    #log_full_request(event)
    # Extract submitted-at from request query parameter.
    submitted_at = event["queryStringParameters"]["submitted-at"]
    LOGGER.debug("submitted_at: %s", submitted_at)
    
    # Fetch ride details from database.
    ride_details = fetch_ride_details(unicorn_id, customer_id, submitted_at)

    # Create self link for the resource representation.
    self_link_url = create_self_link_url(event, unicorn_id, customer_id, submitted_at)
    
    # Create response depending on if we found a ride item in the database.
    status_code = 200
    if ride_details == STR_NONE:
        # Oh, we didn't find an item for the input data.
        data = {
            "links": {
                "self": self_link_url
            },
            "error-message": "This is not the ride you're looking for!"
        }
        status_code = 404
    else:
        # We found an item and can create a nice resource representation.
        data = {
            "links": {
                "self": self_link_url
            },
            #"title": "Ride " + ride_id + " for customer " + customer_id + " is completed by unicorn " + unicorn_id,
            "unicorn-id": unicorn_id,
            "customer-id": customer_id,
            "submitted-at": submitted_at,
            "ride-details": ride_details
        }

    # Return resource representation.
    return {
        "statusCode": status_code,
        "body": json.dumps(data),
        "headers": {
            "Content-Type": "application/json"
        }
    }

# ---------------------------------------------------------------------------------------------------------------------
