// hard-coded pricing for now, until amazon releases an API for this
// reference: https://aws.amazon.com/bedrock/pricing/
// List of models: https://docs.aws.amazon.com/bedrock/latest/userguide/model-ids.html

export const modelPrices = {
	// Amazon Titan Text Models
	"amazon.titan-text-express-v1": {
		pricePer1000InputTokens: 0.0008,
		pricePer1000OutputTokens: 0.0016,
	},
	"amazon.titan-text-express-v1:0:8k": {
		pricePer1000InputTokens: 0.0008,
		pricePer1000OutputTokens: 0.0016,
	},
	"amazon.titan-text-lite-v1": {
		pricePer1000InputTokens: 0.0003,
		pricePer1000OutputTokens: 0.0004,
	},
	"amazon.titan-text-lite-v1:0:4k": {
		pricePer1000InputTokens: 0.0003,
		pricePer1000OutputTokens: 0.0004,
	},
	"amazon.titan-text-premier-v1:0": {
		pricePer1000InputTokens: 0.0013,
		pricePer1000OutputTokens: 0.0017,
	},

	// Amazon Titan Image Models
	"amazon.titan-image-generator-v1": {
		pricePerImage: 0.08,
	},
	"amazon.titan-image-generator-v1:0": {
		pricePerImage: 0.08,
	},
	"amazon.titan-image-generator-v2:0": {
		pricePerImage: 0.08,
	},
	"amazon.titan-tg1-large": {
		pricePerImage: 0.08,
	},

	// Amazon Nova Models
	"amazon.nova-pro-v1:0": {
		pricePer1000InputTokens: 0.0008,
		pricePer1000OutputTokens: 0.0032,
	},
	"amazon.nova-pro-v1:0:300k": {
		pricePer1000InputTokens: 0.0008,
		pricePer1000OutputTokens: 0.0032,
	},
	"amazon.nova-lite-v1:0": {
		pricePer1000InputTokens: 0.00006,
		pricePer1000OutputTokens: 0.00024,
	},
	"amazon.nova-lite-v1:0:300k": {
		pricePer1000InputTokens: 0.00006,
		pricePer1000OutputTokens: 0.00024,
	},
	"amazon.nova-micro-v1:0": {
		pricePer1000InputTokens: 0.000035,
		pricePer1000OutputTokens: 0.00014,
	},
	"amazon.nova-micro-v1:0:128k": {
		pricePer1000InputTokens: 0.000035,
		pricePer1000OutputTokens: 0.00014,
	},
	"amazon.nova-canvas-v1:0": {
		pricePerImage: 0.08,
	},
	"amazon.nova-reel-v1:0": {
		pricePerImage: 0.08,
	},

	// Embedding Models
	"amazon.titan-embed-text-v1": {
		pricePer1000InputTokens: 0.0001,
		pricePer1000OutputTokens: 0,
	},
	"amazon.titan-embed-text-v1:2:8k": {
		pricePer1000InputTokens: 0.0001,
		pricePer1000OutputTokens: 0,
	},
	"amazon.titan-embed-text-v2:0": {
		pricePer1000InputTokens: 0.0001,
		pricePer1000OutputTokens: 0,
	},
	"amazon.titan-embed-text-v2:0:8k": {
		pricePer1000InputTokens: 0.0001,
		pricePer1000OutputTokens: 0,
	},
	"amazon.titan-embed-image-v1": {
		pricePer1000InputTokens: 0.0001,
		pricePer1000OutputTokens: 0,
	},
	"amazon.titan-embed-image-v1:0": {
		pricePer1000InputTokens: 0.0001,
		pricePer1000OutputTokens: 0,
	},
	"amazon.titan-embed-g1-text-02": {
		pricePer1000InputTokens: 0.0001,
		pricePer1000OutputTokens: 0,
	},

	// Anthropic Claude Models
	"anthropic.claude-instant-v1": {
		pricePer1000InputTokens: 0.0008,
		pricePer1000OutputTokens: 0.0024,
	},
	"anthropic.claude-instant-v1:2:100k": {
		pricePer1000InputTokens: 0.0008,
		pricePer1000OutputTokens: 0.0024,
	},
	"anthropic.claude-v2": {
		pricePer1000InputTokens: 0.008,
		pricePer1000OutputTokens: 0.024,
	},
	"anthropic.claude-v2:1": {
		pricePer1000InputTokens: 0.008,
		pricePer1000OutputTokens: 0.024,
	},
	"anthropic.claude-v2:0:18k": {
		pricePer1000InputTokens: 0.008,
		pricePer1000OutputTokens: 0.024,
	},
	"anthropic.claude-v2:0:100k": {
		pricePer1000InputTokens: 0.008,
		pricePer1000OutputTokens: 0.024,
	},
	"anthropic.claude-v2:1:18k": {
		pricePer1000InputTokens: 0.008,
		pricePer1000OutputTokens: 0.024,
	},
	"anthropic.claude-v2:1:200k": {
		pricePer1000InputTokens: 0.008,
		pricePer1000OutputTokens: 0.024,
	},
	"anthropic.claude-3-sonnet-20240229-v1:0": {
		pricePer1000InputTokens: 0.003,
		pricePer1000OutputTokens: 0.015,
	},
	"anthropic.claude-3-sonnet-20240229-v1:0:28k": {
		pricePer1000InputTokens: 0.003,
		pricePer1000OutputTokens: 0.015,
	},
	"anthropic.claude-3-sonnet-20240229-v1:0:200k": {
		pricePer1000InputTokens: 0.003,
		pricePer1000OutputTokens: 0.015,
	},
	"anthropic.claude-3-haiku-20240307-v1:0": {
		pricePer1000InputTokens: 0.00025,
		pricePer1000OutputTokens: 0.00125,
	},
	"anthropic.claude-3-haiku-20240307-v1:0:200k": {
		pricePer1000InputTokens: 0.00025,
		pricePer1000OutputTokens: 0.00125,
	},
	"anthropic.claude-3-opus-20240229-v1:0": {
		pricePer1000InputTokens: 0.015,
		pricePer1000OutputTokens: 0.075,
	},
	"anthropic.claude-3-opus-20240229-v1:0:12k": {
		pricePer1000InputTokens: 0.015,
		pricePer1000OutputTokens: 0.075,
	},
	"anthropic.claude-3-opus-20240229-v1:0:28k": {
		pricePer1000InputTokens: 0.015,
		pricePer1000OutputTokens: 0.075,
	},
	"anthropic.claude-3-opus-20240229-v1:0:200k": {
		pricePer1000InputTokens: 0.015,
		pricePer1000OutputTokens: 0.075,
	},

	// Meta Models
	"meta.llama3-8b-instruct-v1:0": {
		pricePer1000InputTokens: 0.0004,
		pricePer1000OutputTokens: 0.0006,
	},
	"meta.llama3-70b-instruct-v1:0": {
		pricePer1000InputTokens: 0.0018,
		pricePer1000OutputTokens: 0.0024,
	},
	"meta.llama3-1-8b-instruct-v1:0": {
		pricePer1000InputTokens: 0.0004,
		pricePer1000OutputTokens: 0.0006,
	},
	"meta.llama3-1-70b-instruct-v1:0": {
		pricePer1000InputTokens: 0.0018,
		pricePer1000OutputTokens: 0.0024,
	},
	"meta.llama3-2-1b-instruct-v1:0": {
		pricePer1000InputTokens: 0.0002,
		pricePer1000OutputTokens: 0.0003,
	},
	"meta.llama3-2-3b-instruct-v1:0": {
		pricePer1000InputTokens: 0.0003,
		pricePer1000OutputTokens: 0.0004,
	},
	"meta.llama3-2-11b-instruct-v1:0": {
		pricePer1000InputTokens: 0.0006,
		pricePer1000OutputTokens: 0.0008,
	},
	"meta.llama3-2-90b-instruct-v1:0": {
		pricePer1000InputTokens: 0.002,
		pricePer1000OutputTokens: 0.0026,
	},
	"meta.llama3-3-70b-instruct-v1:0": {
		pricePer1000InputTokens: 0.0018,
		pricePer1000OutputTokens: 0.0024,
	},

	// Mistral Models
	"mistral.mistral-7b-instruct-v0:2": {
		pricePer1000InputTokens: 0.0004,
		pricePer1000OutputTokens: 0.0012,
	},
	"mistral.mixtral-8x7b-instruct-v0:1": {
		pricePer1000InputTokens: 0.0008,
		pricePer1000OutputTokens: 0.0024,
	},
	"mistral.mistral-large-2402-v1:0": {
		pricePer1000InputTokens: 0.004,
		pricePer1000OutputTokens: 0.012,
	},
	"mistral.mistral-small-2402-v1:0": {
		pricePer1000InputTokens: 0.0006,
		pricePer1000OutputTokens: 0.0018,
	},

	// AI21 Models
	"ai21.jamba-instruct-v1:0": {
		pricePer1000InputTokens: 0.0005,
		pricePer1000OutputTokens: 0.0007,
	},
	"ai21.jamba-1-5-large-v1:0": {
		pricePer1000InputTokens: 0.002,
		pricePer1000OutputTokens: 0.008,
	},
	"ai21.jamba-1-5-mini-v1:0": {
		pricePer1000InputTokens: 0.0002,
		pricePer1000OutputTokens: 0.0004,
	},

	// Cohere Models
	"cohere.command-text-v14": {
		pricePer1000InputTokens: 0.0015,
		pricePer1000OutputTokens: 0.002,
	},
	"cohere.command-text-v14:7:4k": {
		pricePer1000InputTokens: 0.0015,
		pricePer1000OutputTokens: 0.002,
	},
	"cohere.command-light-text-v14": {
		pricePer1000InputTokens: 0.0003,
		pricePer1000OutputTokens: 0.0006,
	},
	"cohere.command-light-text-v14:7:4k": {
		pricePer1000InputTokens: 0.0003,
		pricePer1000OutputTokens: 0.0006,
	},
	"cohere.command-r-v1:0": {
		pricePer1000InputTokens: 0.0015,
		pricePer1000OutputTokens: 0.002,
	},
	"cohere.command-r-plus-v1:0": {
		pricePer1000InputTokens: 0.003,
		pricePer1000OutputTokens: 0.004,
	},
	"cohere.embed-english-v3:0": {
		pricePer1000InputTokens: 0.0001,
		pricePer1000OutputTokens: 0,
	},
	"cohere.embed-english-v3:0:512": {
		pricePer1000InputTokens: 0.0001,
		pricePer1000OutputTokens: 0,
	},
	"cohere.embed-multilingual-v3:0": {
		pricePer1000InputTokens: 0.0001,
		pricePer1000OutputTokens: 0,
	},
	"cohere.embed-multilingual-v3:0:512": {
		pricePer1000InputTokens: 0.0001,
		pricePer1000OutputTokens: 0,
	},

	// Stability AI Models
	"stability.stable-diffusion-xl-v1": {
		pricePerImage: 0.02,
	},
	"stability.stable-diffusion-xl-v1:0": {
		pricePerImage: 0.02,
	},

	// DeepSeek Models
	"deepseek.r1-v1:0": {
		pricePer1000InputTokens: 0.0008,
		pricePer1000OutputTokens: 0.0024,
	},

	"us.anthropic.claude-3-sonnet-20240229-v1:0": {
		pricePer1000InputTokens: 0.003,
		pricePer1000OutputTokens: 0.015,
	},
	"us.anthropic.claude-3-opus-20240229-v1:0": {
		pricePer1000InputTokens: 0.015,
		pricePer1000OutputTokens: 0.075,
	},
	"us.anthropic.claude-3-haiku-20240307-v1:0": {
		pricePer1000InputTokens: 0.00025,
		pricePer1000OutputTokens: 0.00125,
	},
	"us.meta.llama3-2-11b-instruct-v1:0": {
		pricePer1000InputTokens: 0.0006,
		pricePer1000OutputTokens: 0.0008,
	},
	"us.meta.llama3-2-3b-instruct-v1:0": {
		pricePer1000InputTokens: 0.0003,
		pricePer1000OutputTokens: 0.0004,
	},
	"us.meta.llama3-2-90b-instruct-v1:0": {
		pricePer1000InputTokens: 0.002,
		pricePer1000OutputTokens: 0.0026,
	},
	"us.meta.llama3-2-1b-instruct-v1:0": {
		pricePer1000InputTokens: 0.0002,
		pricePer1000OutputTokens: 0.0003,
	},
	"us.anthropic.claude-3-5-sonnet-20241022-v1:0": {
		pricePer1000InputTokens: 0.003,
		pricePer1000OutputTokens: 0.015,
	},
	"us.anthropic.claude-3-5-haiku-20241022-v1:0": {
		pricePer1000InputTokens: 0.00025,
		pricePer1000OutputTokens: 0.00125,
	},
	"us.meta.llama3-1-8b-instruct-v1:0": {
		pricePer1000InputTokens: 0.0004,
		pricePer1000OutputTokens: 0.0006,
	},
	"us.meta.llama3-1-70b-instruct-v1:0": {
		pricePer1000InputTokens: 0.0018,
		pricePer1000OutputTokens: 0.0024,
	},
	"us.amazon.nova-lite-v1:0": {
		pricePer1000InputTokens: 0.00006,
		pricePer1000OutputTokens: 0.00024,
	},
	"us.amazon.nova-pro-v1:0": {
		pricePer1000InputTokens: 0.0008,
		pricePer1000OutputTokens: 0.0032,
	},
	"us.amazon.nova-micro-v1:0": {
		pricePer1000InputTokens: 0.000035,
		pricePer1000OutputTokens: 0.00014,
	},
	"us.meta.llama3-3-70b-instruct-v1:0": {
		pricePer1000InputTokens: 0.0018,
		pricePer1000OutputTokens: 0.0024,
	},
	"us.anthropic.claude-3-5-sonnet-20241022-v2:0": {
		pricePer1000InputTokens: 0.003,
		pricePer1000OutputTokens: 0.015,
	},
	"us.anthropic.claude-3-7-sonnet-20250219-v1:0": {
		pricePer1000InputTokens: 0.003,
		pricePer1000OutputTokens: 0.015,
	},
	"us.deepseek.r1-v1:0": {
		pricePer1000InputTokens: 0.0008,
		pricePer1000OutputTokens: 0.0024,
	},
};
