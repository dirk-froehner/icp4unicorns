# Account preparation "service"

## Scope

This stack prepares a fresh AWS account for the following:
* Enable API Gateway to log incoming requests to CloudWatch Logs. See: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-apigateway-account.html

There is a dummy API key created with the actual role to allow Amazon API Gateway to log into CloudWatch Logs - it is deliberately called "dummy", as there has to be some other API GW resource that is created next to the IAM role. Check the documentation.

## Deployment

The stack can be deployed without further interaction as described in the `deploy.sh` script in this folder.
