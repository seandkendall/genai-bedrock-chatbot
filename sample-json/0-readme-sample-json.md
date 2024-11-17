In this folder you will find some json that was captured via browser developer tools.  

The json was transmitted via websocket in the order it is numbered here.

The files to look at are:

1-message-from-browser.json - has the format that will be seen by back end lambda functions.  The first lambda function in the function chain is genai_bedrock_router_fn.

4-message-returned-from-api-3.json - content_block_delta message contains text that is displayed to end user.  There can be many of these returned for each response.

5-message-returned-from-api-4.json - citation_data message contains citation data that is correlated to the content_block_delta message.

