import os
import sys
import logging
import json
import datetime
import uuid
import boto3
from botocore.exceptions import ClientError
from pprint import pprint
import aux
import aux_api
from completed_ride import CompletedRide

# ---------------------------------------------------------------------------------------------------------------------
# "Global variables".
# ---------------------------------------------------------------------------------------------------------------------

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

ENV_RIDE_COMPLETION_TOPIC_ARN = "RIDE_COMPLETION_TOPIC_ARN"
ENV_RIDE_COMPLETION_TOPIC_NAME = "RIDE_COMPLETION_TOPIC_NAME"
#ENV_SERVICE_API_BASE_URL = "SERVICE_API_BASE_URL"

# ---------------------------------------------------------------------------------------------------------------------
# Publish ride details to ride completion topic.
# ---------------------------------------------------------------------------------------------------------------------

def publish_ride_details(completed_ride):
    try:
        LOGGER.debug("Publish ride details to ride completion topic.")
        topic_arn = os.environ.get(ENV_RIDE_COMPLETION_TOPIC_ARN, aux.STR_NONE)
        LOGGER.debug("topic_arn: %s", topic_arn)

        sns_client = boto3.client("sns")
        response = sns_client.publish(
            TargetArn = topic_arn,
            # The message body contains just the ride details.
            Message = json.dumps({'default': json.dumps(completed_ride.get_ride_details())}),
            MessageStructure = "json",
            # Certain data from the ride details could be interesting for message filtering, hence go into meta data.
            MessageAttributes = {
                "unicorn-id": { "DataType": "String", "StringValue": completed_ride.get_unicorn_id() },
                "customer-id": { "DataType": "String", "StringValue": completed_ride.get_customer_id() },
                "fare": { "DataType": "Number", "StringValue": completed_ride.get_fare_as_string() },
                "distance": { "DataType": "Number", "StringValue": completed_ride.get_distance_as_string() },
                "correlation-id": { "DataType": "String", "StringValue": completed_ride.get_correlation_id() }
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

def create_self_link_url(event, completed_ride):

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
    completed_ride_link += "?unicorn-id=" + completed_ride.get_unicorn_id()
    completed_ride_link += "&customer-id=" + completed_ride.get_customer_id()
    completed_ride_link += "&submitted-at=" + completed_ride.get_submitted_at()
    LOGGER.debug("completed_ride_link: %s", completed_ride_link)

    return completed_ride_link

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

    # Create a new completed ride object from the incoming event.
    try:
        LOGGER.debug("Create a new completed ride object from the incoming event.")
        completed_ride = CompletedRide(LOGGER, event, event[aux.EK_BODY])
    except Exception as ex:
        LOGGER.exception(aux_api.BAD_REQUEST_NO_JSON_BODY)
        LOGGER.exception(ex)
        return aux_api.bad_request(LOGGER, event, aux_api.BAD_REQUEST_NO_JSON_BODY, ex)

    # Persist ride details.
    # Feature request: Eventually respond with Internal Server Error if this fails.
    completed_ride.persist_ride_details()

    # Send ride details to the ride completion topic.
    # Feature request: If this fails, add a scheduled process to retry.
    publish_ride_details(completed_ride)

    # Prepare self link for the new completed ride resource.
    # Feature request: Make this an instance operation of a CompletedRide instance?
    completed_ride_link = create_self_link_url(event, completed_ride)

    data = {
        "links": {
            "self": completed_ride_link
        },
        "unicorn-id": completed_ride.get_unicorn_id(),
        "customer-id": completed_ride.get_customer_id(),
        "submitted-at": completed_ride.get_submitted_at(),
        "ride-details": completed_ride.get_ride_details()
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

# ---------------------------------------------------------------------------------------------------------------------
