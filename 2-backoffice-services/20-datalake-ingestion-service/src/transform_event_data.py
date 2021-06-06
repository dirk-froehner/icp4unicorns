from __future__ import print_function

import base64

print('Loading function')


def lambda_handler(event, context):
    output = []

    for record in event['records']:
        print(record['recordId'])
        payload = base64.b64decode(record['data'])

        # Do custom processing on the payload here

        output_record = {
            'recordId': record['recordId'],
            'result': 'Ok',
            'data': base64.b64encode(payload)
        }
        output.append(output_record)

    print('Successfully processed {} records.'.format(len(event['records'])))

    return {'records': output}

import logging
import json

# ---------------------------------------------------------------------------------------------------------------------
# Main.
# ---------------------------------------------------------------------------------------------------------------------

def lambda_handler(event, context):

    LOGGER = logging.getLogger(__name__)
    LOGGER.setLevel(logging.DEBUG)

    # We expect SNS messages coming in in a "Records" array, within each record, there's an object "Sns".
    # Within that object:
    # - The message body is in the "Message" object.
    # - Message meta data is in the "MessageAttributes" object.
    for record in event["Records"]:
        event_details = json.loads(record["Sns"]["Message"])
        LOGGER.info(event_details)

# ---------------------------------------------------------------------------------------------------------------------
