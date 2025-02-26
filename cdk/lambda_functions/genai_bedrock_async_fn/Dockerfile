FROM public.ecr.aws/lambda/python:3.13

# Set working directory
WORKDIR /var/task

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the Lambda function code
COPY *.py .

# Set the CMD to your handler
CMD ["genai_bedrock_async_fn.lambda_handler"]