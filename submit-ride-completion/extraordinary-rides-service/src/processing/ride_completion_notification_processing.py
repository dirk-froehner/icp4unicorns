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
# Persist the incoming ride details.
# ---------------------------------------------------------------------------------------------------------------------

def persist_ride_details(unicorn_id, customer_id, submitted_at, ride_id, fare, distance, correlation_id, ride_details):
    try:
        LOGGER.debug("Persist the incoming ride details.")
        table_name = os.environ.get(ENV_RIDES_STORE_TABLE_NAME)
        LOGGER.debug("table_name: %s", table_name)

        ddb_client = boto3.client("dynamodb")
        response = ddb_client.put_item(
            TableName = table_name,
            Item = {
                "unicorn-id"     : { "S": unicorn_id },
                "customer-id"    : { "S": customer_id },
                "submitted-at"   : { "S": submitted_at },
                "ride-id"        : { "S": ride_id },
                "fare"           : { "N": str(fare) },
                "distance"       : { "N": str(distance) },
                "correlation-id" : { "S": correlation_id },
                "ride-details"   : { "S": json.dumps(ride_details) }
            }
        )
    except Exception as ex:
        LOGGER.exception("Something went wrong with persisting the ride details.")
        LOGGER.exception(ex)
        return 0
    else:
        LOGGER.debug("Ride details successfully persisted.")
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

        # Extract ride details from record.
        ride_details = {}
        if "Sns" in record:
            # Direct message reception from SNS.
            LOGGER.debug("Direct message reception from SNS.")
            ride_details = json.loads(record["Sns"]["Message"])
        else:
            # Indirect message reception via buffering SQS queue due to topic-queue-chaining.
            LOGGER.debug("Indirect message reception via buffering SQS queue due to topic-queue-chaining.")
            body = json.loads(record["body"])
            ride_details = json.loads(body["Message"])
        LOGGER.debug("ride_details: %s", ride_details)

        # Extract unicorn ID from ride details.
        unicorn_id = ride_details["unicorn-id"]
        LOGGER.debug("unicorn_id: %s", unicorn_id)
        # Extract customer ID from ride details.
        customer_id = ride_details["customer-id"]
        LOGGER.debug("customer_id: %s", customer_id)
        # Extract submitted-at from ride details.
        submitted_at = ride_details["submitted-at"]
        LOGGER.debug("submitted_at: %s", submitted_at)
        # Extract ride ID from ride details.
        ride_id = ride_details["ride-id"]
        LOGGER.debug("ride_id: %s", ride_id)
        # Extract fare from ride details.
        fare = ride_details["fare"]
        LOGGER.debug("fare: %s", fare)
        # Extract distance from ride details.
        distance = ride_details["distance"]
        LOGGER.debug("distance: %s", distance)
        # Extract correlation ID from ride details.
        correlation_id = ride_details["correlation-id"]
        LOGGER.debug("correlation_id: %s", correlation_id)

        # Persist ride details.
        persist_ride_details(unicorn_id, customer_id, submitted_at, ride_id, fare, distance, correlation_id, ride_details)

# ---------------------------------------------------------------------------------------------------------------------
