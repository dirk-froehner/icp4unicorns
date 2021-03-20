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

ENV_MSG_META_CORRELATION_ID_KEY = "MSG_META_CORRELATION_ID_KEY"
ENV_MSG_META_RETURN_ADDRESS_KEY = "MSG_META_RETURN_ADDRESS_KEY"

ENV_RFQ_REQUEST_TABLE_NAME = "RFQ_REQUEST_TABLE_NAME"
ENV_RFQ_REQUEST_TOPIC_NAME = "RFQ_REQUEST_TOPIC_NAME"
ENV_RFQ_REQUEST_TOPIC_ARN = "RFQ_REQUEST_TOPIC_ARN"

ENV_RFQ_RESPONSE_TABLE_NAME = "RFQ_RESPONSE_TABLE_NAME"
ENV_RFQ_RESPONSE_QUEUE_NAME = "RFQ_RESPONSE_QUEUE_NAME"
ENV_RFQ_RESPONSE_QUEUE_URL = "RFQ_RESPONSE_QUEUE_URL"

STR_NONE = "NONE"

LINK_REL_RFQ_RESULT = "http://a42.guru/passenger-service/rfq-result"

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
        rfq_request = response["Item"]
        LOGGER.debug("rfq_request: %s", rfq_request)
        return rfq_request
    except Exception as ex:
        LOGGER.exception("Something went wrong with fetching the RFQ request.")
        LOGGER.exception(ex)
        return STR_NONE

def fetch_rfq_response_count(correlation_id):
    try:
        LOGGER.debug("Fetch RFQ response count from the database.")
        table_name = os.environ.get(ENV_RFQ_RESPONSE_TABLE_NAME)
        LOGGER.debug("table_name: %s", table_name)

        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)
        response = table.query(KeyConditionExpression = Key("correlation-id").eq(correlation_id))
        LOGGER.debug("RFQ responses successfully fetched.")
        LOGGER.debug("response: %s", response)

        response_count = response["Count"]
        LOGGER.debug("response_count: %d", response_count)
        return response_count
    except Exception as ex:
        LOGGER.exception("Something went wrong with fetching the RFQ responses.")
        LOGGER.exception(ex)
        return 0

def fetch_status_details(customer_id, correlation_id):
    try:
        LOGGER.debug("Assemble the current RFQ status details.")

        rfq_request = fetch_rfq_request(customer_id, correlation_id)
        response_count = fetch_rfq_response_count(correlation_id)
        
        # We want to provide the following data to the user:
        # status ::= running | done
        # eta ::= <concrete timestamp when RFQ is over>
        # response-count ::= <number of responses that already arrived>
        timeout_at_iso = rfq_request["timeout-at"]
        LOGGER.debug("timeout_at_iso: %s", timeout_at_iso)
        timeout_at = datetime.datetime.fromisoformat(timeout_at_iso)
        LOGGER.debug("timeout_at: %s", timeout_at)
        now = datetime.datetime.utcnow()
        LOGGER.debug("now: %s", now)
        LOGGER.debug("response_count: %d", response_count)

        status_details = {
            "response-count": response_count
        }
        if now > timeout_at:
            status_details.update({"status": "done"})
        else:
            status_details.update({"status": "running"})
            status_details.update({"eta": timeout_at_iso})
        LOGGER.debug("status_details: %s", status_details)
        return status_details
    except Exception as ex:
        LOGGER.exception("Something went wrong with fetching the RFQ status details.")
        LOGGER.exception(ex)
        return STR_NONE

# ---------------------------------------------------------------------------------------------------------------------
# Create self link for RFQ status resource.
# ---------------------------------------------------------------------------------------------------------------------

def create_self_link(event, customer_id, correlation_id):

    LOGGER.debug("Create self link for RFQ status resource.")
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
# Create link for RFQ result resource in case the RFQ is done.
# ---------------------------------------------------------------------------------------------------------------------

def create_rfq_result_link(event, customer_id, correlation_id):

    LOGGER.debug("Create link for the RFQ result resource.")

    link_protocol = event["headers"]["X-Forwarded-Proto"]
    LOGGER.debug("link_protocol: %s", link_protocol)

    link_host = event["headers"]["Host"]
    LOGGER.debug("link_host: %s", link_host)

    link_stage = event["requestContext"]["stage"]
    LOGGER.debug("link_stage: %s", link_stage)

    link_base_url = link_protocol + "://" + link_host
    
    request_context_path = event["requestContext"]["path"]
    if request_context_path.startswith("/" + link_stage):
        # We need to include the stage in constructed resource URLs.
        link_base_url += "/" + link_stage

    link_base_url += "/api/user"
    LOGGER.debug("link_base_url: %s", link_base_url)

    rfq_status_link = link_base_url + "/retrieve-rfq-result"
    rfq_status_link += "?customer-id=" + customer_id
    rfq_status_link += "&correlation-id=" + correlation_id
    LOGGER.debug("rfq_status_link: %s", rfq_status_link)

    return rfq_status_link

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
    status_details = fetch_status_details(customer_id, correlation_id)

    # Create self link for the resource representation.
    self_link = create_self_link(event, customer_id, correlation_id)
    
    data = status_details
    data.update({
        "links": {
            "self": self_link
        }
    })

    # In case the RFQ is already done, create a link for the RFQ result.
    if status_details["status"] == "done":
        rfq_result_link = create_rfq_result_link(event, customer_id, correlation_id)
        data["links"].update({LINK_REL_RFQ_RESULT: rfq_result_link})

    return {
        "statusCode": 200,
        "body": json.dumps(data),
        "headers": {
            "Content-Type": "application/json"
        }
    }

# ---------------------------------------------------------------------------------------------------------------------
