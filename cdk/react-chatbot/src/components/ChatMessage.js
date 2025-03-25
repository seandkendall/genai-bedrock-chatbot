/* eslint-disable react-hooks/exhaustive-deps */
import React, {
	memo,
	useMemo,
	useCallback,
	useEffect,
	useState,
	useRef,
} from "react";
import {
	Box,
	Typography,
	CircularProgress,
	IconButton,
	Button,
	Tooltip,
	Chip,
	Accordion,
	AccordionSummary,
	AccordionDetails,
} from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import CheckIcon from "@mui/icons-material/Check";
import KeyboardArrowUpIcon from "@mui/icons-material/KeyboardArrowUp";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { MathJaxContext, MathJax } from "better-react-mathjax";

import { okaidia } from "react-syntax-highlighter/dist/esm/styles/prism";
import CodeBlock from "./CodeBlock";
import MessageHeader from "./MessageHeader";

import "./ChatMessage.css";
const messageTrimThreshold = 500;

const ChatMessage = memo(
	({
		message,
		onSend,
		isLastMessage,
		reactThemeMode,
		resetTrimmedMessages,
	}) => {
		const [copied, setCopied] = useState(false);
		const messageRef = useRef(null);
		const [showFullMessage, setShowFullMessage] = useState(false);

		// biome-ignore lint/correctness/useExhaustiveDependencies: not needed
		useEffect(() => {
			setShowFullMessage(false);
		}, [resetTrimmedMessages]);

		const parseDeepseekResponse = useCallback((content) => {
			const sections = { user: "", think: "", response: "", system: "" };
			const sectionRegex = /<(user|think|system)>([\s\S]*?)<\/\1>/gi;

			// Use matchAll instead of exec
			for (const match of content.matchAll(sectionRegex)) {
				const [, type, text] = match;
				sections[type] = text.trim();
			}

			sections.response = content.replace(sectionRegex, "").trim();
			return sections;
		}, []);

		const handleCopyMessage = () => {
			if (message.content) {
				// Extract text content if it's in an array format
				let textToCopy = "";
				if (Array.isArray(message.content)) {
					textToCopy = message.content
						.filter((item) => item.text)
						.map((item) => item.text)
						.join(" ");
				} else {
					textToCopy = message.content;
				}

				navigator.clipboard
					.writeText(textToCopy)
					.then(() => {
						setCopied(true);
						setTimeout(() => setCopied(false), 2000);
					})
					.catch((err) => console.error("Failed to copy text: ", err));
			}
		};

		const formatContent = useCallback(
			(content, outputTokenCount, trimLongMessages) => {
				let formattedContent = "";

				// Check if content contains 'think', 'system' or 'user' tags
				if (/<\/?(?:think|user|system)>/i.test(content)) {
					// Parse the Deepseek response
					const parsedContent = parseDeepseekResponse(content);

					// Combine the parsed sections into a single string, using Markdown syntax
					if (parsedContent.user) {
						formattedContent += `## User Input Summary\n\n${parsedContent.user}\n\n`;
					}

					if (parsedContent.think) {
						formattedContent += `## Thinking Process\n\n${parsedContent.think}\n\n`;
					}

					if (parsedContent.system) {
						formattedContent += `## System\n\n${parsedContent.system}\n\n`;
					}

					if (parsedContent.response) {
						formattedContent += `## Response\n\n${parsedContent.response}`;
					}

					formattedContent = formattedContent.trim();
				} else {
					// If no tags are present, use the raw content
					formattedContent = content.trim();
				}
				if (
					trimLongMessages &&
					formattedContent.length > messageTrimThreshold
				) {
					formattedContent = `${formattedContent.substring(0, 100)}...${formattedContent.substring(formattedContent.length - (messageTrimThreshold - 100))}. ...`;
				}
				return formattedContent;
			},
			[parseDeepseekResponse],
		);

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
			() =>
				message?.raw_message?.error && message.raw_message?.error.trim() !== "",
			[message],
		);
		const [expanded, setExpanded] = useState(message?.is_reasoning === true);

		const { messageContent, attachments } = useMemo(() => {
			if (hasError) {
				return {
					messageContent: message?.raw_message?.error,
					attachments: [],
				};
			}
			if (Array.isArray(message.content)) {
				// Extract text content
				const textContent = message.content
					.filter((item) => item.text)
					.map((item) => item.text)
					.join(" ");

				const newAttachments = message.content.reduce((acc, item) => {
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

				return {
					messageContent: textContent,
					attachments: newAttachments,
				};
			}
			const textContent = message.content || "";

			// Handle case where content_items might not exist
			const contentItems = message.content_items || [];

			const newAttachments = contentItems.reduce((acc, item) => {
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

			return {
				messageContent: textContent,
				attachments: newAttachments,
			};
		}, [message.content, hasError, message, reformatFilename]);

		const handleRefresh = useCallback(() => {
			onSend(null, null, true, false);
		}, [onSend]);

		const isHuman = message.role === "Human" || message.role === "user";
		// biome-ignore lint/correctness/useExhaustiveDependencies: Not Needed
		const renderContent = useCallback(() => {
			if (message.isImage) {
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
						>{`Generated Image of: ${message.prompt}`}</Typography>
						<img
							src={messageContent}
							alt={message.imageAlt || "Generated image"}
							style={{ maxWidth: "100%", height: "auto" }}
						/>
					</>
				);
			}
			if (message.isVideo) {
				return (
					<>
						<Typography>{`Generated Video of: ${message.prompt}`}</Typography>
						{/* biome-ignore lint/a11y/useMediaCaption: <explanation> */}
						<video controls>
							<source src={messageContent} type="video/mp4" />
						</video>
					</>
				);
			}
			if (message.role === "Human" || message.role === "user") {
				return (
					<>
						{formatContent(
							messageContent,
							message.outputTokenCount,
							!isLastMessage && !showFullMessage,
						)}

						{!isLastMessage &&
							!showFullMessage &&
							messageContent &&
							messageContent.length > messageTrimThreshold && (
								<Button
									size="small"
									onClick={() => setShowFullMessage(true)}
									sx={{
										borderColor:
											reactThemeMode === "dark"
												? "rgba(255, 255, 255, 0.3)"
												: "rgba(0, 0, 0, 0.23)",
										color: reactThemeMode === "dark" ? "white" : "inherit",
									}}
								>
									Load Entire Message
								</Button>
							)}
						{attachments.length > 0 && (
							<Box sx={{ mt: 2, display: "flex", flexWrap: "wrap", gap: 1 }}>
								{attachments.map((attachment) => (
									<Chip
										key={`${attachment.type}-${attachment.s3Key || attachment.name}`}
										label={attachment.s3Key || attachment.name}
										sx={{
											backgroundColor:
												attachment.type === "image"
													? "#e3f2fd"
													: attachment.type === "video"
														? "#e8f5e9"
														: "#fff3e0",
											color: "text.primary",
											"& .MuiChip-label": {
												color:
													reactThemeMode === "dark" ? "#121212" : "inherit",
											},
										}}
										size="small"
									/>
									// <Chip
									// 	key={attachment.s3Key}
									// 	label={attachment.s3Key}
									// 	variant="outlined"
									// 	size="small"
									// />
								))}
							</Box>
						)}
					</>
				);
			}
			return (
				<>
					<MathJaxContext>
						<MathJax>
							<ReactMarkdown
								remarkPlugins={[remarkGfm, remarkMath]}
								rehypePlugins={[rehypeKatex]}
								components={{
									math: ({ value }) => (
										<div>
											<MathJax>{`\\[${value}\\]`}</MathJax>
										</div>
									),
									inlineMath: ({ value }) => (
										<span>
											<MathJax>{`\\(${value}\\)`}</MathJax>
										</span>
									),
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
												backgroundColor:
													reactThemeMode === "dark" ? "#424242" : "#f5f5f5",
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
								{formatContent(
									messageContent,
									message.outputTokenCount,
									!isLastMessage && !showFullMessage,
								)}
							</ReactMarkdown>
						</MathJax>
					</MathJaxContext>
					{!isLastMessage &&
						!showFullMessage &&
						messageContent &&
						messageContent.length > messageTrimThreshold && (
							<Box sx={{ display: "flex", justifyContent: "center", mt: 2 }}>
								<Button
									variant="outlined"
									size="small"
									onClick={() => setShowFullMessage(true)}
									sx={{
										borderColor:
											reactThemeMode === "dark"
												? "rgba(255, 255, 255, 0.3)"
												: "rgba(0, 0, 0, 0.23)",
										color: reactThemeMode === "dark" ? "white" : "inherit",
									}}
								>
									Load Entire Message
								</Button>
							</Box>
						)}

					{attachments.length > 0 && (
						<Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mt: 1 }}>
							{attachments.map((attachment) => (
								<Chip
									key={`${attachment.type}-${attachment.s3Key || attachment.name}`}
									label={attachment.s3Key || attachment.name}
									sx={{
										backgroundColor:
											attachment.type === "image"
												? "#e3f2fd"
												: attachment.type === "video"
													? "#e8f5e9"
													: "#fff3e0",
										color: "text.primary",
										"& .MuiChip-label": {
											color: reactThemeMode === "dark" ? "#121212" : "inherit",
										},
									}}
									size="small"
								/>
							))}
						</Box>
					)}
				</>
			);
		}, [
			message.isImage,
			message.isVideo,
			messageContent,
			message.prompt,
			message.imageAlt,
			attachments,
			formatContent,
			message.outputTokenCount,
			showFullMessage,
			reactThemeMode,
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
								? "#FFCCCB" //Light Error Background color
								: isHuman
									? "grey.200" //Light Human Background color
									: "background.paper" //Light assistant Background color
							: hasError
								? "#DC3545" //Dark Error Background color
								: isHuman
									? "grey.800" //Dark Human Background color
									: "grey.600", //Dark assistant Background color
					boxShadow:
						message?.role?.toLowerCase() === "assistant"
							? "0 1px 2px rgba(0, 0, 0, 0.1)"
							: "none",
					userSelect: "text",
				}}
				ref={messageRef}
			>
				<Box display="flex" alignItems="center" justifyContent="space-between">
					<Box display="flex" alignItems="center">
						{(message.role === "Human" || message.role === "user") && (
							<Tooltip title={copied ? "Copied!" : "Copy message"}>
								<IconButton
									onClick={handleCopyMessage}
									size="small"
									sx={{
										position: "absolute",
										top: "8px",
										right: "8px",
										color: copied ? "success.main" : "action.active",
									}}
								>
									{copied ? (
										<CheckIcon fontSize="small" />
									) : (
										<ContentCopyIcon fontSize="small" />
									)}
								</IconButton>
							</Tooltip>
						)}

						<MessageHeader
							role={message.role}
							timestamp={message.timestamp}
							model={message.model}
						/>
						{message?.role?.toLowerCase() === "assistant" && (
							<>
								{message.isStreaming && (
									<Box ml={1}>
										<CircularProgress size="1rem" color="inherit" />
									</Box>
								)}
								{message.responseTime && (
									<Typography variant="body2" ml={1} color="text.secondary">
										(Response Time: {message.responseTime}ms)
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
				{message?.role?.toLowerCase() === "assistant" &&
					message?.reasoning &&
					message?.reasoning?.trim().length > 1 && (
						<Accordion
							expanded={message?.is_reasoning === true || expanded}
							onChange={() => setExpanded(!expanded)}
							sx={{
								mb: 2,
								backgroundColor:
									reactThemeMode === "dark" ? "#323232" : "#f0f4f8", // Darker than #2a2a2a for contrast
								"&:before": { display: "none" },
							}}
						>
							<AccordionSummary
								expandIcon={<ExpandMoreIcon />}
								aria-controls="reasoning-content"
								id="reasoning-panel-header"
								className="reasoning-panel-header"
							>
								<Typography variant="subtitle1">
									{message?.is_reasoning === true
										? "AI Reasoning (in progress...)"
										: "AI Reasoning"}
								</Typography>
							</AccordionSummary>
							<AccordionDetails>{message?.reasoning}</AccordionDetails>
						</Accordion>
					)}
				<Box mt={1}>{renderContent()}</Box>
				<Tooltip title="Scroll to message top">
					<IconButton
						onClick={() =>
							messageRef.current?.scrollIntoView({ behavior: "smooth" })
						}
						size="small"
						sx={{
							position: "absolute",
							bottom: "8px",
							right: "8px",
							bgcolor:
								reactThemeMode === "dark"
									? "rgba(255, 255, 255, 0.1)"
									: "rgba(0, 0, 0, 0.05)",
							"&:hover": {
								bgcolor:
									reactThemeMode === "dark"
										? "rgba(255, 255, 255, 0.2)"
										: "rgba(0, 0, 0, 0.1)",
							},
							padding: "4px",
						}}
					>
						<KeyboardArrowUpIcon fontSize="small" />
					</IconButton>
				</Tooltip>
			</Box>
		);
	},
);

export default ChatMessage;
