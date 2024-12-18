# Flow:

Browser -> API Gateway websocket -> genai_bedrock_router_fn -> other lambda functions

# Which function will you be routed to?

genai_bedrock_agents_client_fn - If you're using Bedrock Agents, Bedrock Prompt Flows, or Bedrock Knowledge Bases, you will be routed to genai_bedrock_agents_client_fn

genai_bedrock_async_fn - If you're using a Large Language Model by itself, such as plain old Claude 3.5 Sonnetv2, or the latest flavor of Llama, you will be routed to genai_bedrock_async_fn

genai_bedrock_image_fn - If you are requesting an image to be generated, you will be routed to the genai_bedrock_image_fn

The rest of the functions are used to support security, config, lists of models available, etc.

# How does the code decide where to route you?
Have a look at /sample-json/1-message-from-browser.json

The genai_bedrock_router_fn uses the field: selected_mode.category to determine which function to call.

The json message is built by the react application.

The category is determined by the user, when they select which model to use, from the drop downs that are at the top right of the chatbot gui.

The chatbot gui is built in react, and you can start with react-chatbot/src/App.js to see how that is put together (there are no docs on the react-chatbot yet - that's a bigger job than I can handle at the moment)