#!/bin/bash
rm -rf ./cdk/lambda_functions/python_layer/python/*
pip install boto3 PyJWT -t ./cdk/lambda_functions/python_layer/python --upgrade
