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
ENV_MSG_META_RETURN_ADDRESS_KEY = "MSG_META_RETURN_ADDRESS_KEY"

ENV_UNICORN_ID = "UNICORN_ID"

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
# Retrieve unicorn ID from environment.
# ---------------------------------------------------------------------------------------------------------------------

def retrieve_unicorn_id():
    unicorn_id = os.environ.get(ENV_UNICORN_ID, STR_NONE + "__" + str(uuid.uuid4()))
    LOGGER.debug("unicorn_id: %s", unicorn_id)
    return unicorn_id

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
        correlation_id_value = correlation_id_item["Value"]
        return correlation_id_value
    except KeyError as error:
        LOGGER.exception("No '%s' key in message meta data.", os.environ.get(ENV_MSG_META_CORRELATION_ID_KEY))
        return STR_NONE

# ---------------------------------------------------------------------------------------------------------------------
# Extract return address from message meta data.
# ---------------------------------------------------------------------------------------------------------------------

def extract_return_address(message_attributes):
    try:
        return_address_item = message_attributes[os.environ.get(ENV_MSG_META_RETURN_ADDRESS_KEY)]
        return_address_value = return_address_item["Value"]
        return return_address_value
    except KeyError as error:
        LOGGER.exception("No '%s' key in message meta data.", os.environ.get(ENV_MSG_META_RETURN_ADDRESS_KEY))
        return STR_NONE

# ---------------------------------------------------------------------------------------------------------------------
# Send RFQ response to RFQ response queue.
# ---------------------------------------------------------------------------------------------------------------------

def send_rfq_response(return_address, correlation_id, unicorn_id, rfq_response):
    LOGGER.debug("Send RFQ response to RFQ response queue.")
    LOGGER.debug("return_address: %s", return_address)

    # Construct message attributes with correlation ID.
    msg_meta_correlation_id_key = os.environ.get(ENV_MSG_META_CORRELATION_ID_KEY)
    LOGGER.debug("Response message attributes - correlation ID key: %s", msg_meta_correlation_id_key)
    msg_meta_correlation_id_value = correlation_id
    LOGGER.debug("Response message attributes - correlation ID value: %s", msg_meta_correlation_id_value)
    message_attributes = {
        msg_meta_correlation_id_key: {"StringValue": correlation_id, "DataType": "String"},
        "unicorn-id": {"StringValue": unicorn_id, "DataType": "String"}
    }
    LOGGER.debug("Resulting message_attributes object: %s", message_attributes)
    #sqs = boto3.resource("sqs")
    #rfq_response_queue = sqs.get_queue_by_name(QueueName=return_address)
    sqs = boto3.resource("sqs")
    rfq_response_queue = sqs.Queue(return_address)
    LOGGER.debug("rfq_response_queue: %s: ", rfq_response_queue)
    response = rfq_response_queue.send_message(
        MessageBody = json.dumps(rfq_response), MessageAttributes = message_attributes
    )
    LOGGER.debug("Message successfully sent.")
    LOGGER.debug("SQS response: %s", response)

# ---------------------------------------------------------------------------------------------------------------------
# Main.
# ---------------------------------------------------------------------------------------------------------------------

def lambda_handler(event, context):

    # If the environment advises on a specific debug level, set it accordingly.
    update_debug_level(event, context)

    # Retrieve unicorn ID from environment.
    unicorn_id = retrieve_unicorn_id()

    # Log environment details.
    log_env_details()
    # Log request details.
    log_event_and_context(event, context)

    # We expect either SNS or SQS messages coming in - both will appear within an array called "Records".
    # Within each record, SNS data appears in an object calles "Sns". Within that object:
    # - The message body is in the "Message" object.
    # - Message meta data is in the "MessageAttributes" object.
    # In case we receive an SQS message here, it will be from topic-queue-chaining.
    # All relevant data from the SNS message is going to be stuffed into the "body" object of a record.
    # Within that "body" object, we will find the "Message" and "MessageAttributes" objects again.
    count = 0
    for record in event["Records"]:
        count += 1
        LOGGER.debug("Looking into record #%d:", count)

        # Extract RFQ details and message meta data.
        if "Sns" in record:
            # Direct message reception from SNS.
            LOGGER.debug("Direct message reception from SNS.")
            rfq_details = json.loads(record["Sns"]["Message"])
            message_attributes = record["Sns"]["MessageAttributes"]
        else:
            # Indirect message reception via buffering SQS queue due to topic-queue-chaining.
            LOGGER.debug("Indirect message reception via buffering SQS queue due to topic-queue-chaining.")
            body = json.loads(record["body"])
            rfq_details = json.loads(body["Message"])
            LOGGER.debug("FIXME: This branch is only prepared, need to add to extract message attributes from the SQS message.")
        LOGGER.debug("rfq_details: %s", rfq_details)
        LOGGER.debug("message_attributes: %s", message_attributes)

        # Extract correlation ID from message meta data.
        correlation_id = extract_correlation_id(message_attributes)
        LOGGER.debug("correlation_id: %s", correlation_id)
        # Extract customer ID from RFQ.
        customer_id = rfq_details["customer-id"]
        LOGGER.debug("customer_id: %s", customer_id)
        # Extract return address from message meta data.
        return_address = extract_return_address(message_attributes)
        LOGGER.debug("return_address: %s", return_address)
        
        # Create a random RFQ response.
        rfq_response = {
            "unicorn-id": unicorn_id,
            "customer-id": customer_id,
            "price": 2.95,
            "goodies": [ "FREE_DRINKS_NON_ALC", "FREE_DRINKS_ALC" ]
        }        
        LOGGER.debug("rfq_response: %s", rfq_response)

        # Send RFQ response to RFQ response queue.
        send_rfq_response(return_address, correlation_id, unicorn_id, rfq_response)

# ---------------------------------------------------------------------------------------------------------------------
