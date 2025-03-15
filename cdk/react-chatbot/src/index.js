import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";
import reportWebVitals from "./reportWebVitals";
import { AwsRum } from "aws-rum-web";
import * as Sentry from "@sentry/react";

import configJson from "./config.json";
let awsRum = null;

Sentry.init({
	dsn: "https://c71115934787e1391fbbc2b03ea811b1@o4508960664846336.ingest.us.sentry.io/4508960667205632",
	integrations: [Sentry.browserTracingIntegration()],
	tracesSampleRate: 1.0,
	tracePropagationTargets: ["localhost", "https://dznw81y4yvz5r.cloudfront.net/","dznw81y4yvz5r.cloudfront.net"],
});

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
