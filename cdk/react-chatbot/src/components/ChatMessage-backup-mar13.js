import React, {
	memo,
	useMemo,
	useCallback,
	useState,
	useRef,
	useEffect,
} from "react";
import {
	Box,
	Typography,
	CircularProgress,
	IconButton,
	Tooltip,
	Chip,
	Button,
} from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
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
// CHGSDK:995 - Import Accordion components
import Accordion from "@mui/material/Accordion";
import AccordionSummary from "@mui/material/AccordionSummary";
import AccordionDetails from "@mui/material/AccordionDetails";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";

const ChatMessage = memo(
	({
		raw_message,
		onSend,
		isLastMessage,
		role,
		content,
		responseTime,
		isStreaming,
		timestamp,
		outputTokenCount,
		model,
		isImage,
		isVideo,
		is_reasoning,
		imageAlt,
		prompt,
		reactThemeMode,
	}) => {
		const [showFullMessage, setShowFullMessage] = useState(false);
		const [copied, setCopied] = useState(false);
		const messageRef = useRef(null);
		const [reasoningSections, setReasoningSections] = useState([]);
		const [currentReasoningText, setCurrentReasoningText] = useState("");
		const [normalText, setNormalText] = useState("");
		const [expanded, setExpanded] = useState(true);

		const handleShowFullMessage = useCallback(() => {
			setShowFullMessage(true);
		}, []);

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

		useEffect(() => {
			const isAssistant = role === "Assistant" || role === "assistant";
			if (is_reasoning !== undefined && isAssistant) {
				if (is_reasoning) {
					// If reasoning is true, accumulate the reasoning text
					if (typeof content === "string") {
						// Keep accumulating reasoning content using functional update
						setCurrentReasoningText((prev) => prev + content);
						// Clear normal text when in reasoning mode
						setNormalText("");
					} else if (
						Array.isArray(content) &&
						content.some((item) => item.text)
					) {
						const textContent = content
							.filter((item) => item.text)
							.map((item) => item.text)
							.join(" ");
						setCurrentReasoningText((prev) => prev + textContent);
						// Clear normal text when in reasoning mode
						setNormalText("");
					}
				} else {
					// If reasoning switches to false, handle the transition using functional updates
					setCurrentReasoningText((prevReasoningText) => {
						// Only store non-empty reasoning sections
						if (prevReasoningText && prevReasoningText.trim() !== "") {
							// Add current reasoning to sections (use a separate call to avoid unused variable)
							setReasoningSections((prevSections) => [
								...prevSections,
								prevReasoningText,
							]);

							// Set expanded to false to collapse the reasoning section
							setExpanded(false);

							// Return empty string to clear current reasoning
							return "";
						}
						return prevReasoningText;
					});

					// Set the normal (non-reasoning) text
					if (typeof content === "string") {
						setNormalText((prev) => prev + content);
					} else if (
						Array.isArray(content) &&
						content.some((item) => item.text)
					) {
						const textContent = content
							.filter((item) => item.text)
							.map((item) => item.text)
							.join(" ");
						setNormalText((prev) => prev + textContent);
					}
				}
			}
		}, [content, is_reasoning, role]);

		const formatContent = useCallback(
			(content, outputTokenCount) => {
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
			() => Boolean(raw_message?.error) && raw_message.error.trim() !== "",
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

		const handleCopyMessage = useCallback(() => {
			const text = typeof messageContent === "string" ? messageContent : "";
			navigator.clipboard.writeText(text);
			setCopied(true);
			setTimeout(() => setCopied(false), 2000);
		}, [messageContent]);

		const handleScrollToTop = useCallback(() => {
			if (messageRef.current) {
				messageRef.current.scrollIntoView({ behavior: "smooth" });
			}
		}, []);

		const handleRefresh = useCallback(() => {
			onSend(null, null, true, false);
		}, [onSend]);

		const isAssistant = role === "Assistant" || role === "assistant";
		const isHuman = role === "Human" || role === "user";
		// only an assistant can have an is_reasoning value, Humans dont have this capability.
		// if (isAssistant) {
		// 	console.log(
		// 		`(${raw_message?.message_id})SDK ChatMessage.js: is_reasoning? ${Boolean(is_reasoning)}`,
		// 	);
		// 	console.log("SDK messageContent:");
		// 	console.log(messageContent);
		// }

		const renderContent = useCallback(() => {
			if (isImage) {
				return (
					<>
						{`Generated Image of: ${prompt}`}
						<img
							src={messageContent}
							alt={imageAlt}
							style={{
								maxWidth: "100%",
								borderRadius: "5px",
								marginTop: "10px",
							}}
						/>
					</>
				);
			}
			if (isVideo) {
				return (
					<>
						{`Generated Video of: ${prompt}`}
						{/* biome-ignore lint/a11y/useMediaCaption: None  */}
						<video
							controls
							style={{
								maxWidth: "100%",
								borderRadius: "5px",
								marginTop: "10px",
							}}
						>
							<source src={messageContent} type="video/mp4" />
						</video>
					</>
				);
			}

			// Add conditional rendering for Human messages
			if (role === "Human" || role === "user") {
				const messageText =
					typeof messageContent === "string" ? messageContent : "";
				if (messageText.length > 500 && !showFullMessage) {
					return (
						<>
							<Box sx={{ textAlign: "center", mb: 1 }}>
								<Button size="small" onClick={handleShowFullMessage}>
									Show more
								</Button>
							</Box>
							<Box>
								{showFullMessage ? messageText : messageText.slice(-500)}
							</Box>
						</>
					);
				}
				return <Box>{messageText}</Box>;
			}

			// CHGSDK:995 - Updated rendering for assistant messages
			return (
				<>
					{/* Only render reasoning section if we have content for it */}
					{reasoningSections.length > 0 && (
						<Accordion
							expanded={expanded}
							onChange={() => setExpanded(!expanded)}
							sx={{
								mb: 2,
								backgroundColor: "rgba(0, 0, 0, 0.03)",
								boxShadow: 1,
							}}
						>
							<AccordionSummary
								expandIcon={<ExpandMoreIcon />}
								aria-controls="reasoning-content"
								id="reasoning-header"
							>
								<Typography fontWeight="bold">Reasoning</Typography>
							</AccordionSummary>
							<AccordionDetails>
								<ReactMarkdown
									remarkPlugins={[remarkGfm, remarkMath]}
									rehypePlugins={[rehypeKatex]}
									components={{
										math: ({ value }) => (
											<MathJaxContext>
												<MathJax>{`\\[${value}\\]`}</MathJax>
											</MathJaxContext>
										),
										inlineMath: ({ value }) => (
											<MathJaxContext>
												<MathJax>{`\\(${value}\\)`}</MathJax>
											</MathJaxContext>
										),
										code({ node, inline, className, children, ...props }) {
											const match = /language-(\w+)/.exec(className || "");
											const language = match ? match[1] : "";
											return !inline && language && language.trim() !== "" ? (
												<CodeBlock
													code={String(children).replace(/\n$/, "")}
													language={language}
												/>
											) : (
												<code {...props}>{children}</code>
											);
										},
										li: ({ node, checked, ...props }) => {
											if (typeof checked === "boolean") {
												return (
													<li style={{ listStyle: "none" }}>
														<input type="checkbox" readOnly checked={checked} />{" "}
														{props.children}
													</li>
												);
											}
											return <li>{props.children}</li>;
										},
										p: (props) => (
											<p style={{ marginBottom: "0.5em", marginTop: "0.5em" }}>
												{props.children}
											</p>
										),
										table: ({ node, ...props }) => (
											<div style={{ overflowX: "auto" }}>
												<table style={{ borderCollapse: "collapse" }}>
													{props.children}
												</table>
											</div>
										),
										thead: ({ node, ...props }) => (
											<thead style={{ borderBottom: "2px solid #ddd" }}>
												{props.children}
											</thead>
										),
										th: ({ node, ...props }) => (
											<th
												style={{
													padding: "6px 13px",
													border: "1px solid #ddd",
												}}
											>
												{props.children}
											</th>
										),
										td: ({ node, ...props }) => (
											<td
												style={{
													padding: "6px 13px",
													border: "1px solid #ddd",
												}}
											>
												{props.children}
											</td>
										),
										del: ({ node, ...props }) => (
											<del style={{ color: "#666" }}>{props.children}</del>
										),
										a: ({ node, href, ...props }) => (
											// eslint-disable-next-line jsx-a11y/anchor-has-content
											<a
												href={href}
												target="_blank"
												rel="noopener noreferrer"
												{...props}
											/>
										),
										blockquote: ({ node, ...props }) => (
											<blockquote
												style={{
													borderLeft: "4px solid #ccc",
													paddingLeft: "16px",
													margin: "16px 0",
												}}
											>
												{props.children}
											</blockquote>
										),
										hr: ({ node, ...props }) => (
											<hr style={{ margin: "16px 0" }} />
										),
									}}
								>
									{formatContent(
										reasoningSections.join("\n\n"),
										outputTokenCount,
									)}
								</ReactMarkdown>
							</AccordionDetails>
						</Accordion>
					)}

					{/* Current reasoning text - shown expanded while streaming */}
					{currentReasoningText && (
						<Accordion
							expanded={true}
							sx={{
								mb: 2,
								backgroundColor: "rgba(0, 0, 0, 0.03)",
								boxShadow: 1,
							}}
						>
							<AccordionSummary
								expandIcon={<ExpandMoreIcon />}
								aria-controls="current-reasoning-content"
								id="current-reasoning-header"
							>
								<Typography fontWeight="bold">Reasoning</Typography>
							</AccordionSummary>
							<AccordionDetails>
								<ReactMarkdown
									remarkPlugins={[remarkGfm, remarkMath]}
									rehypePlugins={[rehypeKatex]}
									components={{
										math: ({ value }) => (
											<MathJaxContext>
												<MathJax>{`\\[${value}\\]`}</MathJax>
											</MathJaxContext>
										),
										inlineMath: ({ value }) => (
											<MathJaxContext>
												<MathJax>{`\\(${value}\\)`}</MathJax>
											</MathJaxContext>
										),
										code({ node, inline, className, children, ...props }) {
											const match = /language-(\w+)/.exec(className || "");
											const language = match ? match[1] : "";
											return !inline && language && language.trim() !== "" ? (
												<CodeBlock
													code={String(children).replace(/\n$/, "")}
													language={language}
													style={okaidia}
												/>
											) : (
												<code {...props}>{children}</code>
											);
										},
										li: ({ node, checked, ...props }) => {
											if (typeof checked === "boolean") {
												return (
													<li style={{ listStyle: "none" }}>
														<input type="checkbox" readOnly checked={checked} />{" "}
														{props.children}
													</li>
												);
											}
											return <li>{props.children}</li>;
										},
										p: (props) => (
											<p style={{ marginBottom: "0.5em", marginTop: "0.5em" }}>
												{props.children}
											</p>
										),
										table: ({ node, ...props }) => (
											<div style={{ overflowX: "auto" }}>
												<table style={{ borderCollapse: "collapse" }}>
													{props.children}
												</table>
											</div>
										),
										thead: ({ node, ...props }) => (
											<thead style={{ borderBottom: "2px solid #ddd" }}>
												{props.children}
											</thead>
										),
										th: ({ node, ...props }) => (
											<th
												style={{
													padding: "6px 13px",
													border: "1px solid #ddd",
												}}
											>
												{props.children}
											</th>
										),
										td: ({ node, ...props }) => (
											<td
												style={{
													padding: "6px 13px",
													border: "1px solid #ddd",
												}}
											>
												{props.children}
											</td>
										),
										del: ({ node, ...props }) => (
											<del style={{ color: "#666" }}>{props.children}</del>
										),
										a: ({ node, href, ...props }) => (
											// eslint-disable-next-line jsx-a11y/anchor-has-content
											<a
												href={href}
												target="_blank"
												rel="noopener noreferrer"
												{...props}
											/>
										),
										blockquote: ({ node, ...props }) => (
											<blockquote
												style={{
													borderLeft: "4px solid #ccc",
													paddingLeft: "16px",
													margin: "16px 0",
												}}
											>
												{props.children}
											</blockquote>
										),
										hr: ({ node, ...props }) => (
											<hr style={{ margin: "16px 0" }} />
										),
									}}
								>
									{formatContent(currentReasoningText, outputTokenCount)}
								</ReactMarkdown>
							</AccordionDetails>
						</Accordion>
					)}

					{/* Normal text (non-reasoning) */}
					{normalText && (
						<ReactMarkdown
							remarkPlugins={[remarkGfm, remarkMath]}
							rehypePlugins={[rehypeKatex]}
							components={{
								math: ({ value }) => (
									<MathJaxContext>
										<MathJax>{`\\[${value}\\]`}</MathJax>
									</MathJaxContext>
								),
								inlineMath: ({ value }) => (
									<MathJaxContext>
										<MathJax>{`\\(${value}\\)`}</MathJax>
									</MathJaxContext>
								),
								code({ node, inline, className, children, ...props }) {
									const match = /language-(\w+)/.exec(className || "");
									const language = match ? match[1] : "";
									return !inline && language && language.trim() !== "" ? (
										<CodeBlock
											code={String(children).replace(/\n$/, "")}
											language={language}
											style={okaidia}
										/>
									) : (
										<code {...props}>{children}</code>
									);
								},
								li: ({ node, checked, ...props }) => {
									if (typeof checked === "boolean") {
										return (
											<li style={{ listStyle: "none" }}>
												<input type="checkbox" readOnly checked={checked} />{" "}
												{props.children}
											</li>
										);
									}
									return <li>{props.children}</li>;
								},
								p: (props) => (
									<p style={{ marginBottom: "0.5em", marginTop: "0.5em" }}>
										{props.children}
									</p>
								),
								table: ({ node, ...props }) => (
									<div style={{ overflowX: "auto" }}>
										<table style={{ borderCollapse: "collapse" }}>
											{props.children}
										</table>
									</div>
								),
								thead: ({ node, ...props }) => (
									<thead style={{ borderBottom: "2px solid #ddd" }}>
										{props.children}
									</thead>
								),
								th: ({ node, ...props }) => (
									<th style={{ padding: "6px 13px", border: "1px solid #ddd" }}>
										{props.children}
									</th>
								),
								td: ({ node, ...props }) => (
									<td style={{ padding: "6px 13px", border: "1px solid #ddd" }}>
										{props.children}
									</td>
								),
								del: ({ node, ...props }) => (
									<del style={{ color: "#666" }}>{props.children}</del>
								),
								a: ({ node, href, ...props }) => (
									// eslint-disable-next-line jsx-a11y/anchor-has-content
									<a
										href={href}
										target="_blank"
										rel="noopener noreferrer"
										{...props}
									/>
								),
								blockquote: ({ node, ...props }) => (
									<blockquote
										style={{
											borderLeft: "4px solid #ccc",
											paddingLeft: "16px",
											margin: "16px 0",
										}}
									>
										{props.children}
									</blockquote>
								),
								hr: ({ node, ...props }) => <hr style={{ margin: "16px 0" }} />,
							}}
						>
							{formatContent(normalText, outputTokenCount)}
						</ReactMarkdown>
					)}

					{/* If no reasoning has happened, just render the content as before */}
					{!reasoningSections.length &&
						!currentReasoningText &&
						!normalText && (
							<ReactMarkdown
								remarkPlugins={[remarkGfm, remarkMath]}
								rehypePlugins={[rehypeKatex]}
								components={{
									math: ({ value }) => (
										<MathJaxContext>
											<MathJax>{`\\[${value}\\]`}</MathJax>
										</MathJaxContext>
									),
									inlineMath: ({ value }) => (
										<MathJaxContext>
											<MathJax>{`\\(${value}\\)`}</MathJax>
										</MathJaxContext>
									),
									code({ node, inline, className, children, ...props }) {
										const match = /language-(\w+)/.exec(className || "");
										const language = match ? match[1] : "";
										return !inline && language && language.trim() !== "" ? (
											<CodeBlock
												code={String(children).replace(/\n$/, "")}
												language={language}
												style={okaidia}
											/>
										) : (
											<code {...props}>{children}</code>
										);
									},
									li: ({ node, checked, ...props }) => {
										if (typeof checked === "boolean") {
											return (
												<li style={{ listStyle: "none" }}>
													<input type="checkbox" readOnly checked={checked} />{" "}
													{props.children}
												</li>
											);
										}
										return <li>{props.children}</li>;
									},
									p: (props) => (
										<p style={{ marginBottom: "0.5em", marginTop: "0.5em" }}>
											{props.children}
										</p>
									),
									table: ({ node, ...props }) => (
										<div style={{ overflowX: "auto" }}>
											<table style={{ borderCollapse: "collapse" }}>
												{props.children}
											</table>
										</div>
									),
									thead: ({ node, ...props }) => (
										<thead style={{ borderBottom: "2px solid #ddd" }}>
											{props.children}
										</thead>
									),
									th: ({ node, ...props }) => (
										<th
											style={{ padding: "6px 13px", border: "1px solid #ddd" }}
										>
											{props.children}
										</th>
									),
									td: ({ node, ...props }) => (
										<td
											style={{ padding: "6px 13px", border: "1px solid #ddd" }}
										>
											{props.children}
										</td>
									),
									del: ({ node, ...props }) => (
										<del style={{ color: "#666" }}>{props.children}</del>
									),
									a: ({ node, href, ...props }) => (
										// eslint-disable-next-line jsx-a11y/anchor-has-content
										<a
											href={href}
											target="_blank"
											rel="noopener noreferrer"
											{...props}
										/>
									),
									blockquote: ({ node, ...props }) => (
										<blockquote
											style={{
												borderLeft: "4px solid #ccc",
												paddingLeft: "16px",
												margin: "16px 0",
											}}
										>
											{props.children}
										</blockquote>
									),
									hr: ({ node, ...props }) => (
										<hr style={{ margin: "16px 0" }} />
									),
								}}
							>
								{formatContent(messageContent,reasoningContent, outputTokenCount)}
							</ReactMarkdown>
						)}

					{attachments.length > 0 && (
						<Box sx={{ mt: 2 }}>
							{attachments.map((attachment) => (
								<Chip
									key={attachment.s3Key}
									label={attachment.s3Key}
									variant="outlined"
									color="primary"
									size="small"
									sx={{ mr: 1, mb: 1 }}
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
			role,
			showFullMessage,
			handleShowFullMessage,
			reasoningSections,
			currentReasoningText,
			normalText,
			expanded,
		]);

		return (
			<Box
				ref={messageRef}
				className={`chat-message ${role.toLowerCase()}`}
				sx={{
					backgroundColor: isAssistant
						? reactThemeMode === "light"
							? "#f5f5f5"
							: "#1e1e1e"
						: reactThemeMode === "light"
							? "#e3f2fd"
							: "#424242",
					color: isAssistant
						? reactThemeMode === "light"
							? "#000"
							: "#fff"
						: reactThemeMode === "light"
							? "#000"
							: "#fff",
					borderRadius: "10px",
					padding: "10px",
					marginBottom: "10px",
					position: "relative",
					alignSelf: isHuman ? "flex-end" : "flex-start",
					maxWidth: "90%",
				}}
			>
				<Box
					className="message-header"
					sx={{ display: "flex", alignItems: "center", mb: 1 }}
				>
					<Box sx={{ display: "flex", alignItems: "center" }}>
						<MessageHeader role={role} timestamp={timestamp} model={model} />
						{isAssistant && isStreaming && (
							<CircularProgress size={15} sx={{ ml: 1 }} />
						)}
					</Box>

					<Box sx={{ display: "flex", alignItems: "center", ml: "auto" }}>
						{isAssistant && responseTime && (
							<Box className="response-time-wrapper">
								(Response Time: {responseTime}ms)
							</Box>
						)}
						{isHuman && (
							<Tooltip title="Retry" placement="top">
								<IconButton size="small" onClick={handleRefresh}>
									<RefreshIcon fontSize="small" />
								</IconButton>
							</Tooltip>
						)}
					</Box>
				</Box>

				{/* Show error retry button - this is for any error message */}
				{hasError && isLastMessage && (
					<Box sx={{ mb: 2, textAlign: "center" }}>
						<Button
							variant="contained"
							onClick={handleRefresh}
							startIcon={<RefreshIcon />}
							color="primary"
						>
							Retry
						</Button>
					</Box>
				)}

				{renderContent()}

				<Box
					sx={{
						position: "absolute",
						top: 10,
						right: 10,
						display: "flex",
						alignItems: "center",
					}}
				>
					<Tooltip title={copied ? "Copied!" : "Copy text"}>
						<IconButton
							size="small"
							onClick={handleCopyMessage}
							sx={{
								color: copied ? "success.main" : "inherit",
								opacity: 0.7,
								"&:hover": { opacity: 1 },
							}}
						>
							<ContentCopyIcon fontSize="small" />
						</IconButton>
					</Tooltip>
				</Box>
				<Box
					sx={{
						position: "absolute",
						bottom: 10,
						right: 10,
						display: "flex",
						alignItems: "center",
					}}
				>
					<Tooltip title="Scroll to top">
						<IconButton
							size="small"
							onClick={handleScrollToTop}
							sx={{
								opacity: 0.7,
								"&:hover": { opacity: 1 },
							}}
						>
							<KeyboardArrowUpIcon fontSize="small" />
						</IconButton>
					</Tooltip>
				</Box>
			</Box>
		);
	},
);

export default ChatMessage;
