import React, { memo, useMemo, useCallback } from "react";
import {
	Box,
	Typography,
	CircularProgress,
	IconButton,
	Tooltip,
	Chip,
} from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { okaidia } from "react-syntax-highlighter/dist/esm/styles/prism";
import CodeBlock from "./CodeBlock";
import MessageHeader from "./MessageHeader";

const ChatMessage = memo(
	({
		raw_message,
		onSend,
		isLastMessage,
		role,
		content,
		responseTime,
		isStreaming,
		isVideoStreaming,
		timestamp,
		outputTokenCount,
		model,
		isImage,
		isVideo,
		imageAlt,
		prompt,
		reactThemeMode,
	}) => {
		// Memoized helper functions
		const formatContent = useCallback((content, outputTokenCount) => {
			if (!outputTokenCount || outputTokenCount < 4096) return content;

			const contentslice = content.slice(-100).trim();
			return `${content}\n\r\n\r---\n\r**This response was too large and may have been cut short. If you would like to see the rest of this response, ask me this:** \n\n\nI did not receive your full last response. please re-send me the remainder of the final response starting from the text: \n\r\n\r"${contentslice}"`;
		}, []);

		const reformatFilename = useCallback((filename) => {
			if (!filename) return "";
			const lastPart = filename.includes("/")
				? filename.split("/").pop()
				: filename;
			const parts = lastPart.split("-");
			return parts.length > 1 ? parts.slice(1).join("-") : lastPart;
		}, []);

		// Memoized values
		const hasError = useMemo(
			() => raw_message?.error && raw_message.error.trim() !== "",
			[raw_message],
		);

		const { messageContent, attachments } = useMemo(() => {
			if (hasError) {
				return { messageContent: raw_message.error, attachments: [] };
			}

			if (Array.isArray(content)) {
				const textContent = content
					.filter((item) => item.text)
					.map((item) => item.text)
					.join(" ");

				const newAttachments = content.reduce((acc, item) => {
					if (item.image?.s3source?.s3key) {
						acc.push({
							type: "image",
							s3Key: reformatFilename(item.image.s3source.s3key),
						});
					}
					if (item.document?.s3source?.s3key) {
						acc.push({
							type: "document",
							s3Key: reformatFilename(item.document.s3source.s3key),
						});
					}
          if (item.video?.s3source?.s3key) {
						acc.push({
							type: "video",
							s3Key: reformatFilename(item.video.s3source.s3key),
						});
					}
					return acc;
				}, []);

				return { messageContent: textContent, attachments: newAttachments };
			}

			return { messageContent: content, attachments: [] };
		}, [content, hasError, raw_message, reformatFilename]);

		const handleRefresh = useCallback(() => {
			onSend(null, null, true);
		}, [onSend]);

		const isAssistant = role === "Assistant" || role === "assistant";
		const isHuman = role === "Human" || role === "user";

		const renderContent = useCallback(() => {
			if (isImage) {
				return (
					<>
						<Typography
							variant="body1"
							color={
								reactThemeMode === "light"
									? hasError
										? "red.main"
										: "text.primary"
									: "text.secondary"
							}
						>{`Generated Image of: ${prompt}`}</Typography>
						<img
							src={messageContent}
							alt={imageAlt || "Generated image"}
							style={{ maxWidth: "100%", height: "auto" }}
						/>
					</>
				);
			}
			if (isVideo) {
				return (
					<>
						<Typography>{`Generated Video of: ${prompt}`}</Typography>
						{/* biome-ignore lint/a11y/useMediaCaption: <explanation> */}
						<video controls>
							<source src={messageContent} type="video/mp4" />
						</video>
					</>
				);
			}

			return (
				<>
					<ReactMarkdown
						remarkPlugins={[remarkGfm]}
						components={{
							code({ node, inline, className, children, ...props }) {
								const match = /language-(\w+)/.exec(className || "");
								const language = match ? match[1] : "";

								return !inline && language && language.trim() !== "" ? (
									<CodeBlock
										code={String(children).trim()}
										language={language}
										style={okaidia}
									/>
								) : (
									<code className={className}>{children}</code>
								);
							},
							li: ({ node, checked, ...props }) => {
								if (typeof checked === "boolean") {
									return (
										<Typography
											component="li"
											variant="body1"
											sx={{
												listStyle: "none",
												display: "flex",
												alignItems: "center",
												"&::before": {
													content: checked ? '"☑️"' : '"⬜"',
													marginRight: "0.5rem",
												},
											}}
											{...props}
										/>
									);
								}
								return (
									<Typography
										component="li"
										variant="body1"
										sx={{
											lineHeight: 1.6,
											"&::marker": {
												fontSize: "1.2rem",
												fontWeight: "bold",
											},
										}}
										{...props}
									/>
								);
							},
							p: (props) => (
								<Typography
									component="p"
									variant="body1"
									whiteSpace="pre-wrap"
									sx={{ mb: 2 }}
									{...props}
								/>
							),
							table: ({ node, ...props }) => (
								<Box sx={{ overflowX: "auto", my: 2 }}>
									<table
										style={{
											borderCollapse: "collapse",
											width: "100%",
											minWidth: "400px",
											marginBottom: "1rem",
										}}
										{...props}
									/>
								</Box>
							),
							thead: ({ node, ...props }) => (
								<thead
									style={{
										backgroundColor: "#f5f5f5",
										borderBottom: "2px solid #ddd",
									}}
									{...props}
								/>
							),
							th: ({ node, ...props }) => (
								<th
									style={{
										border: "1px solid #ddd",
										padding: "12px 8px",
										textAlign: "left",
										fontWeight: "bold",
									}}
									{...props}
								/>
							),
							td: ({ node, ...props }) => (
								<td
									style={{
										border: "1px solid #ddd",
										padding: "8px",
										verticalAlign: "top",
									}}
									{...props}
								/>
							),
							del: ({ node, ...props }) => (
								<Typography
									component="del"
									sx={{
										color: "text.secondary",
										textDecoration: "line-through",
									}}
									{...props}
								/>
							),
							a: ({ node, href, ...props }) => (
								<Typography
									component="a"
									href={href}
									sx={{
										color: "primary.main",
										textDecoration: "none",
										"&:hover": {
											textDecoration: "underline",
										},
										...(href === props.children[0] && {
											fontFamily: "monospace",
											backgroundColor: "action.hover",
											padding: "0.2em 0.4em",
											borderRadius: "3px",
										}),
									}}
									target="_blank"
									rel="noopener noreferrer"
									{...props}
								/>
							),
							blockquote: ({ node, ...props }) => (
								<Box
									component="blockquote"
									sx={{
										borderLeft: 4,
										borderLeftColor: "grey.300",
										pl: 2,
										my: 2,
										color: "text.secondary",
										"& p": {
											m: 0,
										},
									}}
									{...props}
								/>
							),
							hr: ({ node, ...props }) => (
								<Box
									component="hr"
									sx={{
										border: "none",
										height: "1px",
										backgroundColor: "grey.300",
										my: 2,
									}}
									{...props}
								/>
							),
						}}
					>
						{formatContent(messageContent, outputTokenCount)}
					</ReactMarkdown>
					{attachments.length > 0 && (
						<Box mt={2} display="flex" flexWrap="wrap" gap={1}>
							{attachments.map((attachment, index) => (
								<Chip
									key={index}
									label={attachment.s3Key}
                  color={
                    attachment.type === "image" ? "primary" :
                    attachment.type === "video" ? "secondary" :
                    attachment.type === "document" ? "warning" :
                    "success"
                    }	
									sx={{ml: 1}}
									size="small"
								/>
							))}
						</Box>
					)}
				</>
			);
		}, [
			isImage,
			isVideo,
			messageContent,
			prompt,
			imageAlt,
			attachments,
			formatContent,
			outputTokenCount,
		]);

		return (
			<Box
				sx={{
					width: "99%",
					maxWidth: "99%",
					mb: 2,
					p: 2,
					borderRadius: 2,
					position: "relative",
					alignSelf: isHuman ? "flex-end" : "flex-start",
					bgcolor:
						reactThemeMode === "light"
							? hasError
								? "#FFCCCB"
								: isHuman
									? "grey.200"
									: "background.paper"
							: hasError
								? "#DC3545"
								: isHuman
									? "grey.800"
									: "background.paper",
					boxShadow: isAssistant ? "0 1px 2px rgba(0, 0, 0, 0.1)" : "none",
					userSelect: "text",
				}}
			>
				<Box display="flex" alignItems="center" justifyContent="space-between">
					<Box display="flex" alignItems="center">
						<MessageHeader role={role} timestamp={timestamp} model={model} />
						{isAssistant && (
							<>
								{isStreaming && (
									<Box ml={1}>
										<CircularProgress size="1rem" color="inherit" />
									</Box>
								)}
								{responseTime && (
									<Typography variant="body2" ml={1} color="text.secondary">
										(Response Time: {responseTime}ms)
									</Typography>
								)}
							</>
						)}
					</Box>
					{hasError && isLastMessage && (
						<Tooltip title="Send the previous message again" arrow>
							<IconButton
								aria-label="refresh"
								onClick={handleRefresh}
								size="small"
								color={
									reactThemeMode === "light"
										? "action.active"
										: "action.selected"
								}
								sx={{ position: "absolute", top: 8, right: 8 }}
							>
								<RefreshIcon fontSize="small" />
							</IconButton>
						</Tooltip>
					)}
				</Box>
				<Box mt={1}>{renderContent()}</Box>
			</Box>
		);
	},
);

export default ChatMessage;
