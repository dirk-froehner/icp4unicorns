import logging
import json

# ---------------------------------------------------------------------------------------------------------------------
# Globals.
# ---------------------------------------------------------------------------------------------------------------------

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

# ---------------------------------------------------------------------------------------------------------------------
# Lambda handler.
# ---------------------------------------------------------------------------------------------------------------------

def lambda_handler(event, context):

    # We expect SNS messages coming in in a "Records" array, within each record, there's an object "Sns".
    # Within that object:
    # - The message body is in the "Message" object.
    # - Message meta data is in the "MessageAttributes" object.
    for record in event["Records"]:
        event_details = json.loads(record["Sns"]["Message"])
        LOGGER.info(event_details)

# ---------------------------------------------------------------------------------------------------------------------
