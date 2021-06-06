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
# "Global variables".
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
# Create (and log) a correlation ID for this specific request.
# ---------------------------------------------------------------------------------------------------------------------

def create_correlation_id():
    correlation_id = str(uuid.uuid4())
    LOGGER.debug("correlation_id: %s", correlation_id)
    return correlation_id

# ---------------------------------------------------------------------------------------------------------------------
# Capture (and log) the current timestamp as the one the ride completion was submitted.
# ---------------------------------------------------------------------------------------------------------------------

def create_submitted_at():
    submitted_at = datetime.datetime.utcnow()
    LOGGER.debug("submitted_at: %s", submitted_at.isoformat())
    return submitted_at

# ---------------------------------------------------------------------------------------------------------------------
# Log event and context details.
# ---------------------------------------------------------------------------------------------------------------------

def log_event_and_context(event, context):
    LOGGER.debug("event: %s", event)
    # Uncomment the next line if you need the incoming Lambda event pretty-printed in your log.
    #print("event:\n" + json.dumps(event, indent=4))
    LOGGER.debug("context: %s", context)

# ---------------------------------------------------------------------------------------------------------------------
# Persist the incoming ride details.
# ---------------------------------------------------------------------------------------------------------------------

def persist_rfq(customer_id, correlation_id, from_location, to_location, submitted_at, timeout_in_secs, timeout_at, rfq_details):
    try:
        LOGGER.debug("Persist the incoming RFQ details.")
        table_name = os.environ.get(ENV_RFQ_REQUEST_TABLE_NAME, STR_NONE)
        LOGGER.debug("table_name: %s", table_name)

        ddb_client = boto3.client("dynamodb")
        response = ddb_client.put_item(
            TableName = table_name,
            Item = {
                "customer-id"    : { "S": customer_id },
                "correlation-id" : { "S": correlation_id },
                "from-location"  : { "S": from_location },
                "to-location"    : { "S": to_location },
                "submitted-at"   : { "S": submitted_at.isoformat() },
                "timeout-in-secs": { "N": str(timeout_in_secs) },
                "timeout-at"     : { "S": timeout_at.isoformat() },
                "rfq-details"    : { "S": json.dumps(rfq_details) }
            }
        )
    except Exception as ex:
        LOGGER.exception("Something went wrong with persisting the RFQ details.")
        LOGGER.exception(ex)
        return 0
    else:
        LOGGER.debug("RFQ details successfully persisted.")
        LOGGER.debug("DDB response: %s", response)
        return 1

# ---------------------------------------------------------------------------------------------------------------------
# Publish RFQ to RFQ request topic.
# ---------------------------------------------------------------------------------------------------------------------

def publish_rfq(customer_id, correlation_id, from_location, to_location, submitted_at, timeout_in_secs, timeout_at, rfq_details):
    try:
        LOGGER.debug("Publish ride details to ride completion topic.")
        topic_arn = os.environ.get(ENV_RFQ_REQUEST_TOPIC_ARN, STR_NONE)
        LOGGER.debug("topic_arn: %s", topic_arn)
        # Determine correlation ID key and value.
        msg_meta_correlation_id_key = os.environ.get(ENV_MSG_META_CORRELATION_ID_KEY)
        LOGGER.debug("Correlation ID key: %s", msg_meta_correlation_id_key)
        msg_meta_correlation_id_value = correlation_id
        LOGGER.debug("Correlation ID value: %s", msg_meta_correlation_id_value)
        # Determine return address key and value.
        msg_meta_return_address_key = os.environ.get(ENV_MSG_META_RETURN_ADDRESS_KEY)
        LOGGER.debug("Return address key: %s", msg_meta_return_address_key)
        msg_meta_return_address_value = os.environ.get(ENV_RFQ_RESPONSE_QUEUE_URL)
        LOGGER.debug("Return address value: %s", msg_meta_return_address_value)

        sns_client = boto3.client("sns")
        response = sns_client.publish(
            TargetArn = topic_arn,
            # The message body contains just the RFQ details.
            Message = json.dumps({'default': json.dumps(rfq_details)}),
            MessageStructure = "json",
            # Next to correlation ID and return address, other data may also be interesting for message filtering.
            MessageAttributes = {
                msg_meta_correlation_id_key: { "DataType": "String", "StringValue": msg_meta_correlation_id_value },
                msg_meta_return_address_key: { "DataType": "String", "StringValue": msg_meta_return_address_value },
                "customer-id": { "DataType": "String", "StringValue": customer_id },
                "from-location": { "DataType": "String", "StringValue": from_location },
                "to-location": { "DataType": "String", "StringValue": to_location },
                "timeout_in_secs": { "DataType": "Number", "StringValue": str(timeout_in_secs) }
            }
        )
    except Exception as ex:
        LOGGER.exception("Something went wrong with publishing the RFQ details.")
        LOGGER.exception(ex)
        return 0
    else:
        LOGGER.debug("RFQ details successfully published.")
        LOGGER.debug("SNS response: %s", response)
        return 1

# ---------------------------------------------------------------------------------------------------------------------
# Create the self link URL for the new RFQ status resource.
# ---------------------------------------------------------------------------------------------------------------------

def create_rfq_status_link(event, customer_id, correlation_id):

    LOGGER.debug("Create the self link URL for the new RFQ status resource.")

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

    rfq_status_link = link_base_url + "/retrieve-rfq-status"
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

    # Capture the current timestamp as the one where the ride completion was submitted.    
    submitted_at = create_submitted_at()
    # Create a unique correlation ID for this specific ride completion submission.
    correlation_id = create_correlation_id()
    # Log environment details.
    log_env_details()
    # Log request details.
    log_event_and_context(event, context)

    # Extract ride details as JSON object.
    rfq_details = json.loads(event["body"])
    # Add additional info also to the original RFQ details.
    rfq_details.update({"submitted-at": submitted_at.isoformat()})
    rfq_details.update({"correlation-id": correlation_id})
    # Extract customer ID from RFQ details.
    customer_id = rfq_details["customer-id"]
    LOGGER.debug("customer_id: %s", customer_id)
    # Extract start point of the ride from RFQ details.
    from_location = rfq_details["from-location"]
    LOGGER.debug("from_location: %s", from_location)
    # Extract end point of the ride from RFQ details.
    to_location = rfq_details["to-location"]
    LOGGER.debug("to_location: %s", to_location)
    # Extract RFQ timeout from RFQ details.
    timeout_in_secs = rfq_details["timeout-in-secs"]
    LOGGER.debug("timeout_in_secs: %s", timeout_in_secs)
    # Calculate when RFQ will time out based on the RFQ timeout value.
    timeout_at = submitted_at + datetime.timedelta(hours=0, minutes=0, seconds=timeout_in_secs)
    LOGGER.debug("timeout_at: %s", timeout_at)
    # Add the concrete timeout timestamp also to the RFQ details.
    rfq_details.update({"timeout-at": timeout_at.isoformat()})

    # Persist RFQ details.
    persist_rfq(customer_id, correlation_id, from_location, to_location, submitted_at, timeout_in_secs, timeout_at, rfq_details)

    # Publish RFQ details to the RFQ topic.
    publish_rfq(customer_id, correlation_id, from_location, to_location, submitted_at, timeout_in_secs, timeout_at, rfq_details)

    # Prepare self link for the new RFQ status resource.
    rfq_status_link = create_rfq_status_link(event, customer_id, correlation_id)

    data = {
        "links": {
            "self": rfq_status_link
        },
        "status": "running",
        "eta": timeout_at.isoformat()
    }

    return {
        "statusCode": 202,
        "body": json.dumps(data),
        "headers": {
            "Location": rfq_status_link,
            "Content-Location": rfq_status_link,
            "Content-Type": "application/json"
        }
    }

# ---------------------------------------------------------------------------------------------------------------------
