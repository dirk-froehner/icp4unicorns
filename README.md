# Integration and conversation patterns for unicorns

This private pet project experiments with integration and conversation patterns for microservices. The context is a technology start up business, Wild Rydes Inc., that disrupts passenger transportation by replacing old-fashioned taxi cabs with unicorns. Because unicorns come with a lot more fun and magic than taxis.

## Structure

The project is currently structured in three service families:
1. Auxiliary services (mainly preparing a fresh AWS account and preparing some common application resources)
1. Business services (services that deliver business functionality, e.g. ride booking)
1. Backoffice services (services that deliver backoffice functionality, e.g. datalake ingestion)

There are folders for each service family and within these folders, there are subfolders for each service. All services in the project are currently based on AWS SAM, so there's a `template.yaml` in every service's folder.

## Prerequisites

A local installatino of AWS CLI and AWS SAM is required. To use both tools successfully here, there is a need for an IAM user that has administrator access and whose access key is configured in `.aws/credentials`.

For deployments of AWS SAM apps, an Amazon S3 bucket is required to host the artifacts (e.g. packaged AWS SAM app, transformed AWS CloudFormation template). The `sam deploy` command creates that bucket automatically, but unfortunately only in interactive mode (`--guided`). Hence, a respective bucket needs to be created upfront and passed to the SAM command.

```bash
aws s3 mb s3://<aws-account-id>-<aws-region>-sam-cli-source-bucket --profile <profile> --region <aws-region>
```

## Deployment

In the folder for each service, there is a script `deploy.sh` that uses AWS SAM for deployment. In theory, there's also a `deploy.sh` in the root folder that traverses through the services in the correct order and deploys them, but it needs a bit more love to work reliably.

## Example values

Environment variable:

```bash
export SAM_AWS_ACCOUNT_ID=111111111111
export SAM_AWS_PROFILE=burner1
export SAM_AWS_REGION=eu-central-1
export SAM_STAGE=dev
export SAM_BUCKET_NAME=$SAM_AWS_ACCOUNT_ID-$SAM_AWS_REGION-sam-cli-source-bucket
```

Create the bucket for SAM artifacts:

```bash
aws s3 mb s3://111111111111-eu-central-1-sam-cli-source-bucket --profile burner1 --region eu-central-1
```

## Sample requests

### Sample requests for the "submit ride completion" use case:

    cd submit-ride-completion/unicorn-management-service
    curl -i https://<your-api-gw-base-url>/api/user/submit-ride-completion -d @events/standard-ride.json
    curl -i https://<your-api-gw-base-url>/api/user/submit-ride-completion -d @events/extraordinary-ride.json

### Sample requests for the "instant ride RFQ" use case:

    cd instant-ride-rfq/ride-booking-service
    curl -i https://<your-api-gw-base-url>/api/user/submit-rfq -d @events/instant-ride-rfq.json
