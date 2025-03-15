import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";
import reportWebVitals from "./reportWebVitals";
import { AwsRum } from "aws-rum-web";
import * as Sentry from "@sentry/react";

import configJson from "./config.json";
let awsRum = null;
const sentry_dsn = configJson?.sentry_dsn
if (sentry_dsn && sentry_dsn?.length > 0) {
	Sentry.init({
		dsn: sentry_dsn,
		integrations: [Sentry.browserTracingIntegration(),Sentry.replayIntegration()],
		tracesSampleRate: 1.0,
		replaysSessionSampleRate: 0.1,
  		replaysOnErrorSampleRate: 1.0,
		tracePropagationTargets: ["localhost",configJson.aws_chatbot_url,`${configJson.aws_chatbot_url}/`,configJson.aws_chatbot_url.replace("https://", "")],
	});
}
try {
	const config = {
		sessionSampleRate: 1,
		identityPoolId: configJson.rum_identity_pool_id,
		endpoint: `https://dataplane.rum.${configJson.rum_application_region}.amazonaws.com`,
		telemetries: ["performance", "errors", "http"],
		allowCookies: true,
		enableXRay: true,
	};

	const APPLICATION_ID = configJson.rum_application_id;
	const APPLICATION_VERSION = configJson.rum_application_version;
	const APPLICATION_REGION = configJson.rum_application_region;
	awsRum = new AwsRum(
		APPLICATION_ID,
		APPLICATION_VERSION,
		APPLICATION_REGION,
		config,
	);
} catch (error) {
	console.log(error);
	// Ignore errors thrown during CloudWatch RUM web client initialization
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
	<React.StrictMode>
		<App awsRum={awsRum} />
	</React.StrictMode>,
);

reportWebVitals();
