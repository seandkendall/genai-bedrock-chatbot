Help me build code for a serverless application running on aws serverless services. 
The application will do the following:
1. User sends an email to receipts.kayla@k5l.ca or receipts.sean@k5l.ca, with attachments. each attachment is an image of a receipt or invoice
2. The original email with attachment will be saved in an S3 bucket, within a prefix of original_emails, further partitioned by user (sean or kayla), then year, then month. When saving attachments, the filename MUST start with a timestamp prefix in the format: "YYYY-MM-DD" and end in the ogirinal filename. the example will look like this: "2025-01-19-image1.jpg". If a file with the same name already exists, then first check to see if the file is a duplicate by checking the exact file size, and checksum. if the size and checksum matches, we can ignore the file, otherwise upload the new file with a counter in the filename. for example "2025-01-19-image1-2.jpg", and "2025-01-19-image1-3.jpg", and "2025-01-19-image1-4.jpg"
3. Using the eventbridge 'Object Created' event type for the specific s3 bucket and the 'original_emails' prefix, trigger an AWS Lambda function named 'IncomingReceiptProcessorFunction'
4. The IncomingReceiptProcessorFunction will send the image into Amazon Bedrock using the Amazon Bedrock Converse API to execute a question about the input image.
Here is an example of the BODY to send to the converse API when we are asking information about an image
message = {
        "role": "user",
        "content": [
            {
                "text": "<Text Prompt>"
            },
            {
                    "image": {
                        "format": 'png',
                        "source": {
                            "bytes": image
                        }
                    }
            }
        ]
    }

Text prompt to use in original Bedrock Converse Request:
This is an image of a receipt or invoice. inspect this receipt or invoice and respond in the following well structured JSON format:
{"Vendor":"ABS Stores Inc.","Description":"Description of the Transaction","Date":"2025-01-19", "Time":"13:24", "TransactionID":"ODR6254","Category":"Meals and Entertainment","BusinessOrPersonal":"BUSINESS","AmountTotal":123.22, "AmountTip":1.23, "AmountTipPercentage":0.02, "AmountSubtotal":120.00, "AmountTax":3.22,"AmountCurrency":"CAD", "PaymentType":"Visa", "PaymentIdentifier":"XXXXXXXXXXXX7249", "LocationCity":"Calgary", "LocationProvinceState":"Alberta", "LocationCountry":"Canada", "LocationPostalCodeZip":"T1S4K6", "LocationPhoneNumber":"1-403-555-1234", "OrderID":"12345ABC", "NumberOfGuests":3, "LineItems":[{"Description":"item description", "Category":"Meals and Entertainment", "Quantity":1, "Amount":12.34}]}
Not all fields are mandatory, provide the details that you can identify in this document. The Category fields will not be found on the document, while inspecting the document, identify the correct category for the full document, as well as each individual line-item.
Allowed categories are: Accounting Fees, Advertising, Bank Service Charges, Business Licenses & Permits, Computer – Hardware, Computer – Hosting, Computer – Internet, Computer – Software, Equipment Repair, HOA, Import Fees, Insurance - Home, Insurance – Vehicles, Interest Expense, Materials, Meals and Entertainment, Office Expense, Parking, Postage & Delivery, Professional Fees, Property Taxes, Renovations - Home, Repairs & Maintenance, Shipping/Delivery, Shop Cleaning and Maintenance, Small Tools & Equipment, Subscriptions, Supplies, Taxi/Uber/Lyft, Telephone – Wireless, Utilities, Vehicle Loan Interest - Annual, Vehicle Payment, Vehicle – Fuel, Vehicle – Repairs & Maintenance, Workshop


Application principals:
The application will be named 'KendallReceiptProcessor'
The application will only use one S3 bucket with multiple folders/prefixes inside to organize the different types of files in different states
Only use AWS Serverless services such as: API Gateway, DynamoDB, AWS Lambda (Using Python 3.13 ONLY, with boto3), S3, EventBridge, SQS, SNS, SES, Cloudwatch, Xray, AWS PowerTools, Amazon Bedrock. You DONT NEED to use all of these services, and you can suggest additional services for approval if needed.
All code needs to be deployed using aws CDK V2 for python
The code will be deployed by the user running a script in the root directory named deploy.sh
deploy.sh will be able to be run on any Mac or Amazon Linux or Ubuntu Linux
deploy.sh MUST check the system for needed software packages, and if they do not exist, it will install them using the appropriate package manager (such as Brew for mac, YUM for amazon linux or apt for ubuntu)
deploy.sh must be able to run without any human intervention. if an input is needed, allow for an input flag instead of a blocking human prompt.
deploy.sh will exit the script if any part in the script fails
deploy.sh MUST provide detailed logs upon failure so its easy to debug
deploy.sh, once successful MUST output important information such as the e-mail addresses that can be used to send emails to or website URL's if any exist