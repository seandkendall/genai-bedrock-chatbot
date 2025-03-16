import React, { useState } from "react";
import { Typography, Tooltip, Box } from "@mui/material";

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
		}
		if (role?.toLowerCase() === "assistant") {
			return "Assistant";
		}
		return role;
	};

	return (
		<Tooltip
			title={timestamp ? formatTimestamp(timestamp, model) : ""}
			open={showTooltip && Boolean(timestamp)}
			onMouseEnter={handleMouseEnter}
			onMouseLeave={handleMouseLeave}
			arrow
		>
			<Box
				sx={{
					display: "flex",
					justifyContent: "space-between",
					width: "100%",
					pr: 4,
				}}
			>
				<Typography
					variant="subtitle2"
					component="span"
					fontWeight="bold"
					onMouseEnter={handleMouseEnter}
					onMouseLeave={handleMouseLeave}
				>
					{formatRole(role)}
				</Typography>
			</Box>
		</Tooltip>
	);
};

export default MessageHeader;
