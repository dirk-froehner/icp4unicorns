# Application preparation "service"

## Scope

This stack creates shared resources that have no specific service as their owner and shares their details through AWS SSM Parameter Store.

Resources in scope are:
* Amazon S3 bucket that serves as data lake bucket for the raw data tier.
* Amazon SNS topic for "logging" all Lambda events coming from API GW.
* Amazon SNS topic for "logging" all Lambda events coming from SNS.
* Amazon SNS topic for "logging" all Lambda events coming from SQS.

The above mentioned SNS topics for "logging" Lambda events are used for experimentation. The author is not saying that this is a recommended approach for overcoming the current lack of complete request logging in Amazon API Gateway.

## Deployment

The stack can be deployed without further interaction as described in the `deploy.sh` script in this folder.
