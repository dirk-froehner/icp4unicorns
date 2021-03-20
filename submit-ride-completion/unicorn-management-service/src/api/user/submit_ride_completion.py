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
ENV_RIDES_STORE_TABLE_NAME = "RIDES_STORE_TABLE_NAME"
ENV_RIDE_COMPLETION_TOPIC_ARN = "RIDE_COMPLETION_TOPIC_ARN"
ENV_RIDE_COMPLETION_TOPIC_NAME = "RIDE_COMPLETION_TOPIC_NAME"
ENV_SERVICE_API_BASE_URL = "SERVICE_API_BASE_URL"

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
    submitted_at = datetime.datetime.utcnow().isoformat()
    LOGGER.debug("submitted_at: %s", submitted_at)
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
# Publish ride details to ride completion topic.
# ---------------------------------------------------------------------------------------------------------------------

def publish_ride_details(unicorn_id, customer_id, submitted_at, ride_id, fare, distance, correlation_id, ride_details):
    try:
        LOGGER.debug("Publish ride details to ride completion topic.")
        topic_arn = os.environ.get(ENV_RIDE_COMPLETION_TOPIC_ARN, STR_NONE)
        LOGGER.debug("topic_arn: %s", topic_arn)

        sns_client = boto3.client("sns")
        response = sns_client.publish(
            TargetArn = topic_arn,
            # The message body contains just the ride details.
            Message = json.dumps({'default': json.dumps(ride_details)}),
            MessageStructure = "json",
            # Certain data from the ride details could be interesting for message filtering, hence go into meta data.
            MessageAttributes = {
                "unicorn-id": { "DataType": "String", "StringValue": unicorn_id },
                "customer-id": { "DataType": "String", "StringValue": customer_id },
                "fare": { "DataType": "Number", "StringValue": str(fare) },
                "distance": { "DataType": "Number", "StringValue": str(distance) },
                "correlation-id": { "DataType": "String", "StringValue": correlation_id }
            }
        )
    except Exception as ex:
        LOGGER.exception("Something went wrong with publishing the ride details.")
        LOGGER.exception(ex)
        return 0
    else:
        LOGGER.debug("Ride details successfully published.")
        LOGGER.debug("SNS response: %s", response)
        return 1

# ---------------------------------------------------------------------------------------------------------------------
# Create the self link URL for the new completed ride resource.
# ---------------------------------------------------------------------------------------------------------------------

def create_self_link_url(event, unicorn_id, customer_id, submitted_at):

    LOGGER.debug("Create the self link URL for the new completed ride resource.")

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

    completed_ride_link = link_base_url + "/retrieve-completed-ride"
    completed_ride_link += "?unicorn-id=" + unicorn_id
    completed_ride_link += "&customer-id=" + customer_id
    completed_ride_link += "&submitted-at=" + submitted_at
    LOGGER.debug("completed_ride_link: %s", completed_ride_link)

    return completed_ride_link

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
    ride_details = json.loads(event["body"])
    # Add additional info also to the original ride details.
    ride_details.update({"submitted-at": submitted_at})
    ride_details.update({"correlation-id": correlation_id})
    # Extract unicorn ID from ride details.
    unicorn_id = ride_details["unicorn-id"]
    LOGGER.debug("unicorn_id: %s", unicorn_id)
    # Extract customer ID from ride details.
    customer_id = ride_details["customer-id"]
    LOGGER.debug("customer_id: %s", customer_id)
    # Extract ride ID from ride details.
    ride_id = ride_details["ride-id"]
    LOGGER.debug("ride_id: %s", ride_id)
    # Extract fare from ride details.
    fare = ride_details["fare"]
    LOGGER.debug("fare: %d", fare)
    # Extract distance from ride details.
    distance = ride_details["distance"]
    LOGGER.debug("distance: %d", distance)

    # Persist ride details.
    persist_ride_details(unicorn_id, customer_id, submitted_at, ride_id, fare, distance, correlation_id, ride_details)

    # Send ride details to the ride completion topic.
    publish_ride_details(unicorn_id, customer_id, submitted_at, ride_id, fare, distance, correlation_id, ride_details)

    # Prepare self link for the new completed ride resource.
    completed_ride_link = create_self_link_url(event, unicorn_id, customer_id, submitted_at)

    data = {
        "links": {
            "self": completed_ride_link
        },
        #"title": "Ride " + ride_id + " for customer " + customer_id + " is completed by unicorn " + unicorn_id,
        "unicorn-id": unicorn_id,
        "customer-id": customer_id,
        "submitted-at": submitted_at,
        "ride-details": ride_details
    }

    return {
        "statusCode": 201,
        "body": json.dumps(data),
        "headers": {
            "Location": completed_ride_link,
            "Content-Location": completed_ride_link,
            "Content-Type": "application/json"
        }
    }
