// hard-coded pricing for now, until amazon releases an API for this
// reference: https://aws.amazon.com/bedrock/pricing/
// List of models: https://docs.aws.amazon.com/bedrock/latest/userguide/model-ids.html

export const modelPrices = {
    "amazon.titan-text-express-v1": {
      "pricePer1000InputTokens": 0.0008,
      "pricePer1000OutputTokens": 0.0016
    },
    "amazon.titan-text-lite-v1": {
      "pricePer1000InputTokens": 0.0003,
      "pricePer1000OutputTokens": 0.0004
    },
    "amazon.titan-text-premier-v1:0": {
      "pricePer1000InputTokens": 0.0013,
      "pricePer1000OutputTokens": 0.0017
    },
    "amazon.titan-embed-text-v1": {
      "pricePer1000InputTokens": 0.0001,
      "pricePer1000OutputTokens": 0
    },
    "amazon.titan-embed-text-v2:0": {
      "pricePer1000InputTokens": 0.0001,
      "pricePer1000OutputTokens": 0
    },
    "amazon.titan-embed-image-v1": {
      "pricePer1000InputTokens": 0.0001,
      "pricePer1000OutputTokens": 0
    },
    "amazon.titan-image-generator-v1": {
      "pricePer1000InputTokens": 0.08,
      "pricePer1000OutputTokens": 0
    },
    "amazon.titan-image-generator-v2:0": {
      "pricePer1000InputTokens": 0.08,
      "pricePer1000OutputTokens": 0
    },

    "amazon.nova-pro-v1:0": {
      "pricePer1000InputTokens": 0.0008,
      "pricePer1000OutputTokens": 0.0032
    },
    "amazon.nova-lite-v1:0": {
      "pricePer1000InputTokens": 0.00006,
      "pricePer1000OutputTokens": 0.00024
    },
    "amazon.nova-micro-v1:0": {
      "pricePer1000InputTokens": 0.000035,
      "pricePer1000OutputTokens": 0.00014
    },

    "anthropic.claude-v2": {
      "pricePer1000InputTokens": 0.008,
      "pricePer1000OutputTokens": 0.024
    },
    "anthropic.claude-v2:1": {
      "pricePer1000InputTokens": 0.008,
      "pricePer1000OutputTokens": 0.024
    },
    "anthropic.claude-3-sonnet-20240229-v1:0": {
      "pricePer1000InputTokens": 0.003,
      "pricePer1000OutputTokens": 0.015
    },
    "anthropic.claude-3-5-sonnet-20240620-v1:0": {
      "pricePer1000InputTokens": 0.003,
      "pricePer1000OutputTokens": 0.015
    },
    "anthropic.claude-3-haiku-20240307-v1:0": {
      "pricePer1000InputTokens": 0.00025,
      "pricePer1000OutputTokens": 0.00125
    },
    "anthropic.claude-3-opus-20240229-v1:0": {
      "pricePer1000InputTokens": 0.015,
      "pricePer1000OutputTokens": 0.075
    },
    "anthropic.claude-instant-v1": {
      "pricePer1000InputTokens": 0.0008,
      "pricePer1000OutputTokens": 0.0024
    },
    "mistral.mistral-7b-instruct-v0:2": {
      "pricePer1000InputTokens": 0.0004,
      "pricePer1000OutputTokens": 0.0012
    },
    "mistral.mixtral-8x7b-instruct-v0:1": {
      "pricePer1000InputTokens": 0.0008,
      "pricePer1000OutputTokens": 0.0024
    },
    "mistral.mistral-large-2402-v1:0": {
      "pricePer1000InputTokens": 0.004,
      "pricePer1000OutputTokens": 0.012
    },
    "mistral.mistral-large-2407-v1:0": {
      "pricePer1000InputTokens": 0.003,
      "pricePer1000OutputTokens": 0.009
    },
    "mistral.mistral-small-2402-v1:0": {
      "pricePer1000InputTokens": 0.0006,
      "pricePer1000OutputTokens": 0.0018
    },
    "meta.llama2-13b-chat-v1": {
      "pricePer1000InputTokens": 0.00075,
      "pricePer1000OutputTokens": 0.001
    },
    "meta.llama2-70b-chat-v1": {
      "pricePer1000InputTokens": 0.00195,
      "pricePer1000OutputTokens": 0.00256
    },
    "meta.llama3-8b-instruct-v1:0": {
      "pricePer1000InputTokens": 0.0004,
      "pricePer1000OutputTokens": 0.0006
    },
    "meta.llama3-70b-instruct-v1:0": {
      "pricePer1000InputTokens": 0.0018,
      "pricePer1000OutputTokens": 0.0024
    },
    "meta.llama3-1-8b-instruct-v1:0": {
      "pricePer1000InputTokens": 0.0004,
      "pricePer1000OutputTokens": 0.0006
    },
    "meta.llama3-1-70b-instruct-v1:0": {
      "pricePer1000InputTokens": 0.0018,
      "pricePer1000OutputTokens": 0.0024
    },
    "meta.llama3-1-405b-instruct-v1:0": {
      "pricePer1000InputTokens": 0.0048,
      "pricePer1000OutputTokens": 0.0064
    },
    "ai21.jamba-instruct-v1:0": { 
        "pricePer1000InputTokens": 0.0005,
        "pricePer1000OutputTokens": 0.0007
    },
    "ai21.jamba-1-5-large-v1:0": { 
        "pricePer1000InputTokens": 0.002,
        "pricePer1000OutputTokens": 0.008
    },
    "ai21.jamba-1-5-mini-v1:0": { 
        "pricePer1000InputTokens": 0.0002,
        "pricePer1000OutputTokens": 0.0004
    },
    "cohere.command-text-v14": { 
        "pricePer1000InputTokens": 0.0015,
        "pricePer1000OutputTokens": 0.002
    },
    "cohere.command-light-text-v14": { 
        "pricePer1000InputTokens": 0.0003,
        "pricePer1000OutputTokens": 0.0006
    },
  };