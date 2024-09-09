#!/bin/bash
rm -rf ./cdk/lambda_functions/python_layer/python/*
python3 -m pip install boto3 PyJWT django pytz -t ./cdk/lambda_functions/python_layer/python --upgrade

