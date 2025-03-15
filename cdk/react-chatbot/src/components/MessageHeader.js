import React, { useState } from "react";
import { Typography, Tooltip } from "@mui/material";

const MessageHeader = ({ role, timestamp, model }) => {
	const [showTooltip, setShowTooltip] = useState(false);

	const handleMouseEnter = () => {
		setShowTooltip(true);
	};

	const handleMouseLeave = () => {
		setShowTooltip(false);
	};

	const formatTimestamp = (timestamp, model) => {
		// Parse the timestamp in ISO 8601 format
		const date = new Date(timestamp);
		// Convert the UTC timestamp to the local timezone
		const formattedTimestamp = date.toLocaleString();
		if (model) {
			return `${formattedTimestamp} (${model})`;
		}
		return formattedTimestamp;
	};

	const formatRole = (role) => {
		if (role === "user") {
			return "Human";
		}if (role?.toLowerCase() === "assistant") {
			return "Assistant";
		}
		return role;
	};

	return (
		<Tooltip
			open={showTooltip}
			title={formatTimestamp(timestamp, model)}
			arrow
			onMouseEnter={handleMouseEnter}
			onMouseLeave={handleMouseLeave}
		>
			<Typography variant="subtitle2" fontWeight="bold">
				{formatRole(role)}
			</Typography>
		</Tooltip>
	);
};

export default MessageHeader;
