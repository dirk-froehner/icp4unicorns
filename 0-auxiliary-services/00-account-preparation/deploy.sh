#!/bin/bash

# Echo environment variables.
echo "Environment variables:"
echo "SAM_AWS_ACCOUNT_ID = "$SAM_AWS_ACCOUNT_ID
echo "SAM_AWS_REGION     = "$SAM_AWS_REGION
echo "SAM_AWS_PROFILE    = "$SAM_AWS_PROFILE
echo "SAM_STAGE          = "$SAM_STAGE
echo "SAM_BUCKET_NAME    = "$SAM_BUCKET_NAME

# FIXME: For all stages beyond DEV, we need to override some CloudFormation template parameters!

# Without further interaction, the following command deploys the stack.
# Note: Since the CloudFormation template aims to create a named role, we need to use `--capabilities CAPABILITY_NAMED_IAM` in the arguments.

sam deploy --debug --stack-name $SAM_STAGE-wrbs-auxs-acct --capabilities CAPABILITY_NAMED_IAM --s3-bucket $SAM_BUCKET_NAME --profile $SAM_AWS_PROFILE --region $SAM_AWS_REGION --tags Stage=$SAM_STAGE Workload=wrbs Context=auxs Service=acct WorkloadLongName=wild-rydes-backend-services ContextLongName=auxiliary-services ServiceLongName=account-preparation
