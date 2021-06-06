import os
import sys
import logging
import json
import datetime
import dateutil.parser
import uuid
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from pprint import pprint

# ---------------------------------------------------------------------------------------------------------------------
# "Global variables" - what is the correct term for these things in Python?
# ---------------------------------------------------------------------------------------------------------------------

ENV_STAGE = "STAGE"
ENV_WORKLOAD = "WORKLOAD"
ENV_SERVICE = "SERVICE"
ENV_LOG_LEVEL = "LOG_LEVEL"

ENV_RFQ_REQUEST_TABLE_NAME = "RFQ_REQUEST_TABLE_NAME"
ENV_RFQ_RESPONSE_TABLE_NAME = "RFQ_RESPONSE_TABLE_NAME"

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
# Assemble the current RFQ status details.
# ---------------------------------------------------------------------------------------------------------------------

def fetch_rfq_request(customer_id, correlation_id):
    try:
        LOGGER.debug("Fetch RFQ request details from the database.")
        table_name = os.environ.get(ENV_RFQ_REQUEST_TABLE_NAME)
        LOGGER.debug("table_name: %s", table_name)

        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)
        response = table.get_item(Key = { "customer-id": customer_id, "correlation-id": correlation_id })

        LOGGER.debug("RFQ request details successfully fetched.")
        LOGGER.debug("response: %s", response)
        
        rfq_request = json.loads(response["Item"]["rfq-details"])
        
        LOGGER.debug("rfq_request: %s", rfq_request)
        return rfq_request
    except Exception as ex:
        LOGGER.exception("Something went wrong with fetching the RFQ request.")
        LOGGER.exception(ex)
        return STR_NONE

def fetch_rfq_responses(correlation_id):
    try:
        LOGGER.debug("Fetch RFQ responses from the database.")
        table_name = os.environ.get(ENV_RFQ_RESPONSE_TABLE_NAME)
        LOGGER.debug("table_name: %s", table_name)

        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)
        response = table.query(KeyConditionExpression = Key("correlation-id").eq(correlation_id))
        LOGGER.debug("RFQ responses successfully fetched.")
        LOGGER.debug("response: %s", response)

        #rfq_responses = response["Items"]
        rfq_responses = []
        count = 0
        for item in response["Items"]:
            count += 1
            LOGGER.debug("Looking into item #%d:", count)
            rfq_response = json.loads(item["rfq-response"])
            rfq_response.update({"correlation-id": item["correlation-id"]})
            LOGGER.debug("Prepared quote #%d: %s", count, rfq_response)
            rfq_responses.append(rfq_response)
        
        LOGGER.debug("rfq_responses: %s", rfq_responses)
        return rfq_responses
    except Exception as ex:
        LOGGER.exception("Something went wrong with fetching the RFQ responses.")
        LOGGER.exception(ex)
        return 0

# ---------------------------------------------------------------------------------------------------------------------
# Create self link for RFQ result resource.
# ---------------------------------------------------------------------------------------------------------------------

def create_self_link(event, customer_id, correlation_id):

    LOGGER.debug("Create self link for RFQ result resource.")
    link_protocol = event["headers"]["X-Forwarded-Proto"]
    LOGGER.debug("link_protocol: %s", link_protocol)

    link_host = event["headers"]["Host"]
    LOGGER.debug("link_host: %s", link_host)

    link_path = event["requestContext"]["path"]
    LOGGER.debug("link_path: %s", link_path)

    link_base_url = link_protocol + "://" + link_host + link_path
    LOGGER.debug("link_base_url: %s", link_base_url)
    
    link_full_url = link_base_url
    link_full_url += "?customer-id=" + customer_id
    link_full_url += "&correlation-id=" + correlation_id
    LOGGER.debug("link_full_url: %s", link_full_url)

    return link_full_url

# ---------------------------------------------------------------------------------------------------------------------
# Main.
# ---------------------------------------------------------------------------------------------------------------------

def lambda_handler(event, context):

    # If the environment advises on a specific debug level, set it accordingly.
    update_debug_level(event, context)

    # Log environment details.
    log_env_details()
    # Log request details.
    log_event_and_context(event, context)

    # Extract customer ID from request query parameter.
    customer_id = event["queryStringParameters"]["customer-id"]
    LOGGER.debug("customer_id: %s", customer_id)
    # Extract correlation-id from request query parameter.
    correlation_id = event["queryStringParameters"]["correlation-id"]
    LOGGER.debug("correlation_id: %s", correlation_id)
    
    # Fetch ride details from database.
    rfq_request = fetch_rfq_request(customer_id, correlation_id)
    rfq_responses = fetch_rfq_responses(correlation_id)

    # Create self link for the resource representation.
    self_link = create_self_link(event, customer_id, correlation_id)

    data = {
        "links": {
            "self": self_link
        }
    }
    data.update({
        "ride-data": rfq_request,
        "quotes": rfq_responses
    })

    return {
        "statusCode": 200,
        "body": json.dumps(data),
        "headers": {
            "Content-Type": "application/json"
        }
    }

# ---------------------------------------------------------------------------------------------------------------------
