#!/bin/bash

echo "Deploying Wild Rydes backends:"

# Prepare environment variables.
export SAM_AWS_ACCOUNT_ID=851451666505
export SAM_AWS_REGION=eu-central-1
export SAM_AWS_PROFILE=burner1
export SAM_STAGE=dev
export SAM_BUCKET_NAME=$SAM_AWS_ACCOUNT_ID-$SAM_AWS_REGION-sam-cli-source-bucket

# Create artifact bucket for SAM.
aws s3 mb s3://$SAM_BUCKET_NAME --profile $SAM_AWS_PROFILE --region $SAM_AWS_REGION

# Echo environment variables.
echo "Environment variables:"
echo "SAM_AWS_ACCOUNT_ID = "$SAM_AWS_ACCOUNT_ID
echo "SAM_AWS_REGION     = "$SAM_AWS_REGION
echo "SAM_AWS_PROFILE    = "$SAM_AWS_PROFILE
echo "SAM_STAGE          = "$SAM_STAGE
echo "SAM_BUCKET_NAME    = "$SAM_BUCKET_NAME

# FIXME: For all stages beyond DEV, we need to override some CloudFormation template parameters!

# Execute deploy.sh for each service context.
#source "0-auxiliary-services/deploy.sh"
#source "1-business-services/deploy.sh"
#source "2-backoffice-services/deploy.sh"

# Done.
echo "All done."
