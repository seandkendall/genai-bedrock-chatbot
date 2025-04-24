import React from "react";
import {
	Box,
	Typography,
	IconButton,
	List,
	ListItem,
	ListItemText,
	CircularProgress,
	Tooltip,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";

const getCategoryIdentifier = (category) => {
	switch (category) {
		case "Bedrock KnowledgeBases":
			return { text: "KB", color: "#4CAF50" }; // Green
		case "Bedrock Models":
			return { text: "LLM", color: "#2196F3" }; // Blue
		case "Bedrock Agents":
			return { text: "AG", color: "#FFC107" }; // Yellow
		case "Bedrock Prompt Flows":
			return { text: "PF", color: "#FF9800" }; // Orange
		case "Bedrock Image Models":
			return { text: "IMG", color: "#FA8072" }; // Salmon
		case "Bedrock Speech Models":
			return { text: "SPH", color: "#4682B4" }; // Steel Blue
		case "Bedrock Video Models":
			return { text: "VID", color: "#9C27B0" }; // Purple
		case "Imported Models":
			return { text: "IMP", color: "#008080" }; // Teal
		default:
			return { text: "", color: "#9E9E9E" }; // Grey
	}
};

const formatModelId = (modelId) => {
	if (!modelId.includes("/")) {
		return modelId;
	}
	const parts = modelId?.split("/");
	return parts[parts.length - 1];
};

const formatDate = (timestamp) => {
	const date = new Date(timestamp * 1000); // Convert seconds to milliseconds
	return date.toLocaleString("en-US", {
		month: "2-digit",
		day: "2-digit",
		year: "numeric",
		hour: "2-digit",
		minute: "2-digit",
		second: "2-digit",
		hour12: true,
	});
};

const LeftSideBar = ({
	handleNewChat,
	handleDeleteChat,
	conversationList,
	handleSelectChat,
	conversationListLoading,
	selectedConversation,
	isDisabled,
	reactThemeMode,
}) => {
	const sidebarStyle = {
		height: "100%",
		display: "flex",
		flexDirection: "column",
		position: "relative",
		bgcolor:
			reactThemeMode === "light" ? "background.paper" : "background.default",
		color: reactThemeMode === "light" ? "text.primary" : "text.secondary",
	};

	return (
		<Box sx={sidebarStyle}>
			<Box
				sx={{
					display: "flex",
					justifyContent: "space-between",
					alignItems: "center",
					p: 2,
				}}
			>
				<Typography variant="h6">
					Chats{" "}
					{conversationList.length > 1 && (
						<Typography component="span" variant="subtitle1">
							({conversationList.length})
						</Typography>
					)}
				</Typography>
				<IconButton onClick={handleNewChat} disabled={isDisabled}>
					<AddIcon />
				</IconButton>
			</Box>
			<List className="left-sidebar" sx={{ flexGrow: 1, overflowY: "auto" }}>
				{conversationList.map((conversation) => {
					return (
						<ListItem
							key={conversation.session_id}
							onClick={() => {
								if (
									!isDisabled &&
									selectedConversation?.session_id !== conversation.session_id
								) {
									handleSelectChat(conversation);
								}
							}}
							className={
								selectedConversation?.session_id === conversation.session_id
									? "Mui-selected"
									: ""
							}
							disabled={isDisabled}
							sx={{
								display: "flex",
								alignItems: "center",
								pr: 2,
								...(selectedConversation?.session_id ===
									conversation.session_id && {
									bgcolor:
										reactThemeMode === "light" ? "action.selected" : "grey.700",
								}),
							}}
						>
							{conversation.category && (
								<Tooltip
									title={`Model: ${formatModelId(conversation?.selected_model_id || conversation?.selected_knowledgebase_id || conversation?.flow_alias_id || conversation?.selected_agent_alias_id)}`}
									arrow
								>
									<Box
										sx={{
											width: 24,
											height: 24,
											borderRadius: "50%",
											backgroundColor: getCategoryIdentifier(
												conversation.category,
											).color,
											display: "flex",
											justifyContent: "center",
											alignItems: "center",
											marginRight: 2,
											cursor: isDisabled ? "default" : "help",
											flexShrink: 0,
											opacity: isDisabled ? 0.5 : 1,
										}}
									>
										<Typography
											variant="caption"
											sx={{ color: "white", fontSize: "0.7rem" }}
										>
											{getCategoryIdentifier(conversation.category).text}
										</Typography>
									</Box>
								</Tooltip>
							)}
							<ListItemText
								primary={conversation.title}
								secondary={formatDate(conversation.last_modified_date)}
								sx={{ flex: 1, minWidth: 0, opacity: isDisabled ? 0.5 : 1 }}
							/>
							<IconButton
								edge="end"
								aria-label="delete"
								onClick={(e) => {
									if (!isDisabled) {
										e.stopPropagation();
										handleDeleteChat(conversation.session_id);
									}
								}}
								disabled={isDisabled}
							>
								<DeleteIcon />
							</IconButton>
						</ListItem>
					);
				})}
			</List>
			{conversationListLoading && (
				<Box
					sx={{
						position: "absolute",
						top: 0,
						left: 0,
						width: "100%",
						height: "100%",
						backgroundColor: "rgba(0, 0, 0, 0.7)",
						display: "flex",
						flexDirection: "column",
						justifyContent: "center",
						alignItems: "center",
						zIndex: 100,
					}}
				>
					<CircularProgress size={40} thickness={4} sx={{ color: "white" }} />
					<Typography variant="body1" sx={{ color: "white", mt: 2 }}>
						Loading chats...
					</Typography>
				</Box>
			)}
		</Box>
	);
};

export default LeftSideBar;
