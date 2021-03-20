import os
import sys
import logging
import json
import datetime
import uuid
import boto3
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
# Extract correlation ID from message meta data.
# ---------------------------------------------------------------------------------------------------------------------

def extract_correlation_id(message_attributes):
    try:
        correlation_id_item = message_attributes[os.environ.get(ENV_MSG_META_CORRELATION_ID_KEY)]
        correlation_id_value = correlation_id_item["stringValue"]
        return correlation_id_value
    except KeyError as error:
        LOGGER.exception("No '%s' key in message meta data.", os.environ.get(ENV_MSG_META_CORRELATION_ID_KEY))
        return STR_NONE

# ---------------------------------------------------------------------------------------------------------------------
# Extract unicorn ID from message meta data.
# ---------------------------------------------------------------------------------------------------------------------

def extract_unicorn_id(message_attributes):
    try:
        correlation_id_item = message_attributes["unicorn-id"]
        correlation_id_value = correlation_id_item["stringValue"]
        return correlation_id_value
    except KeyError as error:
        LOGGER.exception("No '%s' key in message meta data.", "unicorn-id")
        return STR_NONE

# ---------------------------------------------------------------------------------------------------------------------
# Store incoming RFQ response.
# ---------------------------------------------------------------------------------------------------------------------

def store_rfq_response(rfq_response, correlation_id, unicorn_id):
    try:
        LOGGER.debug("Store incoming RFQ response.")
        table_name = os.environ.get(ENV_RFQ_RESPONSE_TABLE_NAME)
        LOGGER.debug("table_name: %s", table_name)

        # Partition key is "correlation-id (String)"; sort key is "unicorn-id (String)"
        ddb_client = boto3.client("dynamodb")
        response = ddb_client.put_item(
            TableName = table_name,
            Item = {
                "correlation-id": { "S": correlation_id },
                "unicorn-id"    : { "S": unicorn_id },
                "rfq-response"  : { "S": json.dumps(rfq_response) }
            }
        )
    except Exception as ex:
        LOGGER.exception("Something went wrong with persisting the RFQ response.")
        LOGGER.exception(ex)
        return 0
    else:
        LOGGER.debug("RFQ response successfully persisted.")
        LOGGER.debug("DDB response: %s", response)
        return 1

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

    count = 0
    for record in event["Records"]:
        count += 1
        LOGGER.debug("Looking into record #%d:", count)

        rfq_response = json.loads(record["body"])
        LOGGER.debug("rfq_response: %s", rfq_response)
        message_attributes = record["messageAttributes"]
        LOGGER.debug("message_attributes: %s", message_attributes)
        correlation_id = extract_correlation_id(message_attributes)
        LOGGER.debug("correlation_id: %s", correlation_id)
        unicorn_id = extract_unicorn_id(message_attributes)
        LOGGER.debug("unicorn_id: %s", unicorn_id)
        
        # Memorize the RFQ response in the RFQ database.
        store_rfq_response(rfq_response, correlation_id, unicorn_id)

# ---------------------------------------------------------------------------------------------------------------------
