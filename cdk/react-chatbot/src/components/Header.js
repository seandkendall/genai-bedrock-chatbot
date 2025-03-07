/* eslint-disable react-hooks/exhaustive-deps */
import React, { useEffect, useState, useMemo } from "react";
import useTimer from "../useTimer";
import {
	AppBar,
	Toolbar,
	CircularProgress,
	Typography,
	Box,
	Link,
	Button,
	IconButton,
	Menu,
	MenuItem,
	Select,
	Tooltip,
	InputLabel,
	FormControl,
} from "@mui/material";
import { tooltipClasses } from "@mui/material/Tooltip";
import { styled } from "@mui/material/styles";
import { FaSignOutAlt, FaInfoCircle, FaCog } from "react-icons/fa";
import { ExpandMore, ExpandLess } from "@mui/icons-material";
import Popup from "./Popup";
import "./Header.css";

const NoMaxWidthTooltip = styled(({ className, ...props }) => (
	<Tooltip {...props} classes={{ popper: className }} />
))({
	[`& .${tooltipClasses.tooltip}`]: {
		maxWidth: "none",
	},
});

const Header = ({
	disabled,
	selectedConversation,
	kbSessionId,
	setKBSessionId,
	handleOpenSettingsModal,
	signOut,
	selectedMode,
	handleModeChange,
	showPopup,
	setShowPopup,
	popupMessage,
	popupType,
	totalInputTokens,
	totalOutputTokens,
	pricePer1000InputTokens,
	pricePer1000OutputTokens,
	monthlyInputTokens,
	monthlyOutputTokens,
	bedrockAgents,
	bedrockKnowledgeBases,
	models,
	imageModels,
	videoModels,
	importedModels,
	promptFlows,
	selectedKbMode,
	onSelectedKbMode,
	triggerModelScan,
	isRefreshing,
	isRefreshingMessage,
	user,
	allowlist,
	modelsLoaded,
	chatbotTitle,
	isMobile,
	expandedCategories,
	setExpandedCategories,
	region,
}) => {
	const [anchorEl, setAnchorEl] = React.useState(null);

	const [showInfoTooltip, setShowInfoTooltip] = useState(false);
	const [dropdownOpen, setDropdownOpen] = useState(false);
	const { elapsedTime, startTimer, stopTimer, resetTimer } = useTimer();

	//start and stop header timer
	// biome-ignore lint/correctness/useExhaustiveDependencies: Dependencies not needed
	useEffect(() => {
		if (disabled) {
			startTimer();
		} else {
			stopTimer();
			resetTimer();
		}
	}, [disabled]);

	const truncateText = (text, maxLength) => {
		return text.length > maxLength
			? `${text.substring(0, maxLength)}...`
			: text;
	};

	const isUserAllowed = () => {
		if (!allowlist || !user?.signInDetails?.loginId) return true;

		const userEmail = user.signInDetails.loginId.toLowerCase();
		// Ensure allowlist is a string before calling split
		const allowedPatterns =
			typeof allowlist === "string"
				? allowlist
						.toLowerCase()
						.split(",")
						.map((pattern) => pattern.trim())
				: [];

		return allowedPatterns.some((pattern) => userEmail.includes(pattern));
	};

	const toggleCategory = (event, category, forceOpen) => {
		if (event) {
			event.preventDefault();
			event.stopPropagation();
		}

		setExpandedCategories((prev) => {
			const currentState = prev[category];

			if (forceOpen || (!currentState && !prev[category])) {
				// If forceOpen is true or the category doesn't exist and we're setting it to true
				return {
					...Object.keys(prev).reduce((acc, key) => {
						acc[key] = false;
						return acc;
					}, {}),
					[category]: true,
				};
			}
			if (currentState) {
				// If the category is currently true, set it to false
				return {
					...prev,
					[category]: false,
				};
			}
			// If the category is currently false, set it to true and all others to false
			return {
				...Object.keys(prev).reduce((acc, key) => {
					acc[key] = false;
					return acc;
				}, {}),
				[category]: true,
			};
		});
	};

	const renderSelectOptions = (options, maxLength) => {
		return options.flatMap(({ title, data }) =>
			data.length > 0
				? [
						<MenuItem
							key={`header-${title}`}
							value={`header-${title}`}
							onClick={(event) => toggleCategory(event, title, false)}
							sx={{
								fontWeight: "bold",
								display: "flex",
								justifyContent: "space-between",
								alignItems: "center",
								"&:hover": {
									backgroundColor: "rgba(0, 0, 0, 0.04)",
								},
							}}
						>
							{title}
							{/* ExpandLess onClick, do nothing, disable actions */}
							{expandedCategories[title] ? (
								<ExpandLess onClick={(event) => event.preventDefault()} />
							) : (
								<ExpandMore onClick={(event) => event.preventDefault()} />
							)}
						</MenuItem>,
						...(expandedCategories[title]
							? data.map((item) => (
									<MenuItem
										key={`${title}%${item.mode_selector}`}
										value={`${title}%${item.mode_selector}`}
										sx={{ pl: 4 }}
									>
										{truncateText(
											(() => {
												switch (title) {
													case "Bedrock Models":
														return isMobile
															? `${item.modelName}`
															: `${item.providerName} ${item.modelName}`;
													case "Bedrock Image Models":
														return isMobile
															? `${item.modelName}`
															: `${item.providerName} ${item.modelName}`;
													case "Bedrock Video Models":
														return isMobile
															? `${item.modelName}`
															: `${item.providerName} ${item.modelName}`;
													case "Imported Models":
														return isMobile
															? `${item.modelName}`
															: `${item.providerName} ${item.modelName}`;
													case "Bedrock KnowledgeBases":
														return item.name;
													case "Bedrock Agents":
														return isMobile
															? `${item.agentAliasName}`
															: `${item.agent_name} (${item.agentAliasName})`;
													case "Bedrock Prompt Flows":
														return item.name;
													default:
														return "Unknown";
												}
											})(),
											maxLength,
										)}
									</MenuItem>
								))
							: []),
					]
				: [],
		);
	};

	const renderSelectOptionsKB = (options, maxLength) => {
		return options.flatMap(({ title, data }) =>
			data.length > 0
				? [
						<MenuItem key={`title-${title}`} value={title} disabled>
							{title}
						</MenuItem>,
						...data.map((item) => (
							<MenuItem
								key={`${title}%${item.mode_selector}`}
								value={`${title}%${item.mode_selector}`}
							>
								{truncateText(
									(() => {
										switch (title) {
											case "Bedrock Models":
												if (isMobile) {
													return `${item.modelName}`;
												}
												return `${item.providerName} ${item.modelName}`;
											case "Bedrock Image Models":
												if (isMobile) {
													return `${item.modelName}`;
												}
												return `${item.providerName} ${item.modelName}`;
											case "Bedrock KnowledgeBases":
												return item.name;
											case "Bedrock Agents":
												if (isMobile) {
													return `${item.agentAliasName}`;
												}
												return `${item.agent_name} (${item.agentAliasName})`;
											case "Bedrock Prompt Flows":
												return item.name;
											default:
												return "Unknown";
										}
									})(),
									maxLength,
								)}
							</MenuItem>
						)),
					]
				: [],
		);
	};

	const onSelectedModeChange = (event) => {
		const value = event.target.value;
		if (value.startsWith("header-")) {
			// Category headers are handled by toggleCategory, so we don't need to do anything here
			return;
		}
		setDropdownOpen(false);
		if (value) {
			const [category, modeSelector] = value.split("%");
			let selectedObject = null;
			switch (category) {
				case "Bedrock Models":
					selectedObject = models.find(
						(item) => item.mode_selector === modeSelector,
					);
					break;
				case "Bedrock Image Models":
					selectedObject = imageModels.find(
						(item) => item.mode_selector === modeSelector,
					);
					break;
				case "Bedrock Video Models":
					selectedObject = videoModels.find(
						(item) => item.mode_selector === modeSelector,
					);
					break;
				case "Imported Models":
					selectedObject = importedModels.find(
						(item) => item.mode_selector === modeSelector,
					);
					break;
				case "Bedrock KnowledgeBases":
					selectedObject = bedrockKnowledgeBases.find(
						(item) => item.mode_selector === modeSelector,
					);
					break;
				case "Bedrock Agents":
					selectedObject = bedrockAgents.find(
						(item) => item.mode_selector === modeSelector,
					);
					break;
				case "Bedrock Prompt Flows":
					selectedObject = promptFlows.find(
						(item) => item.mode_selector === modeSelector,
					);
					break;
				case "RELOAD":
					triggerModelScan();
					selectedObject = null;
					break;
				default:
					break;
			}
			if (selectedObject) {
				handleModeChange(selectedObject, false);
				localStorage.setItem("selectedMode", JSON.stringify(selectedObject));
			}
		}
	};

	const onSelectedKbModeChange = (event) => {
		if (event && event.target && event.target.value) {
			const [category, modeSelector] = event.target.value.split("%");
			let selectedObject = null;
			switch (category) {
				case "Bedrock Models":
					selectedObject = models.find(
						(item) => item.mode_selector === modeSelector,
					);
					break;
				default:
					break;
			}
			if (selectedObject) {
				onSelectedKbMode(selectedObject);
				localStorage.setItem("selectedKbMode", JSON.stringify(selectedObject));
				setKBSessionId("");
				localStorage.removeItem(
					`kbSessionId-${selectedConversation?.session_id}`,
				);
			}
		}
	};

	const handleMenuOpen = (event) => {
		setAnchorEl(event.currentTarget);
	};

	const handleMenuClose = () => {
		setAnchorEl(null);
	};

	const formatTimer = (value) => {
		if (value < 1000) {
			return `${value} ms`;
		}
		if (value < 60000) {
			// Less than 60 seconds
			return `${(value / 1000).toFixed(1)} s`;
		}
		const totalSeconds = Math.floor(value / 1000);
		const minutes = Math.floor(totalSeconds / 60);
		const seconds = totalSeconds % 60;
		return `${minutes}:${seconds.toString().padStart(2, "0")}`;
	};

	const handleInfoTooltipOpen = () => {
		setShowInfoTooltip(true);
	};

	const handleInfoTooltipClose = () => {
		setShowInfoTooltip(false);
	};

	const calculateDailyCost = () => {
		const dailyCost =
			totalOutputTokens * (pricePer1000OutputTokens / 1000) +
			totalInputTokens * (pricePer1000InputTokens / 1000);
		return dailyCost.toLocaleString("en-US", {
			style: "currency",
			currency: "USD",
		});
	};

	const calculateMonthlyCost = () => {
		const dailyCost =
			monthlyOutputTokens * (pricePer1000OutputTokens / 1000) +
			monthlyInputTokens * (pricePer1000InputTokens / 1000);
		return dailyCost.toLocaleString("en-US", {
			style: "currency",
			currency: "USD",
		});
	};

	const getHeaderLabelExtended = () => {
		if (selectedMode) {
			switch (selectedMode.category) {
				case "Bedrock Models":
					return `${selectedMode.modelName} (${selectedMode.modelId})`;
				case "Bedrock Image Models":
					return `${selectedMode.modelName} (${selectedMode.modelId})`;
				case "Bedrock Video Models":
					return `${selectedMode.modelName} (${selectedMode.modelId})`;
				case "Imported Models":
					return `${selectedMode.modelName} (${selectedMode.modelId})`;
				case "Bedrock KnowledgeBases":
					return selectedMode.knowledgeBaseId;
				case "Bedrock Agents":
					return selectedMode.agentAliasId;
				case "Bedrock Prompt Flows":
					return selectedMode.id;
				default:
					return isMobile ? "BR" : "Bedrock";
			}
		}
		return "";
	};

	const selectOptions = useMemo(
		() => [
			{
				title: "Bedrock Models",
				data: (models
					? models
					: JSON.parse(localStorage.getItem("local-models"))
				).filter((item) => item.is_active === true || !("is_active" in item)),
			},
			{
				title: "Bedrock Image Models",
				data: (imageModels
					? imageModels
					: JSON.parse(localStorage.getItem("local-image-models"))
				).filter((item) => item.is_active === true || !("is_active" in item)),
			},
			{
				title: "Bedrock Video Models",
				data: (videoModels
					? videoModels
					: JSON.parse(localStorage.getItem("local-video-models"))
				).filter((item) => item.is_active === true || !("is_active" in item)),
			},
			{
				title: "Imported Models",
				data: (importedModels
					? importedModels
					: JSON.parse(localStorage.getItem("local-imported-models"))
				).filter((item) => item.is_active === true || !("is_active" in item)),
			},
			{
				title: "Bedrock KnowledgeBases",
				data: (bedrockKnowledgeBases
					? bedrockKnowledgeBases
					: JSON.parse(localStorage.getItem("local-bedrock-knowledge-bases"))
				).filter((item) => item.is_active === true || !("is_active" in item)),
			},
			{
				title: "Bedrock Agents",
				data: (bedrockAgents
					? bedrockAgents
					: JSON.parse(localStorage.getItem("local-bedrock-agents"))
				).filter((item) => item.is_active === true || !("is_active" in item)),
			},
			{
				title: "Bedrock Prompt Flows",
				data: (promptFlows
					? promptFlows
					: JSON.parse(localStorage.getItem("local-prompt-flows"))
				).filter((item) => item.is_active === true || !("is_active" in item)),
			},
		],
		[
			models,
			imageModels,
			videoModels,
			importedModels,
			bedrockKnowledgeBases,
			bedrockAgents,
			promptFlows,
		],
	);

	const kbModelOptions = useMemo(
		() => [
			{
				title: "Bedrock Models",
				data: (models
					? models
					: JSON.parse(localStorage.getItem("local-models"))
				).filter(
					(item) =>
						models.some((model) => model.modelId === item.modelId) &&
						item.is_kb_model === true &&
						(item.is_active === true || !("is_active" in item)),
				),
			},
		],
		[models],
	);

	return (
		<>
			<AppBar position="sticky">
				<Toolbar>
					<Typography
						variant={isMobile ? "body1" : "h6"}
						component="div"
						className="header-title"
						sx={{ flexGrow: 1, display: "flex", alignItems: "center" }}
					>
						{isMobile
							? chatbotTitle.substring(0, 3).toUpperCase()
							: chatbotTitle}
						<NoMaxWidthTooltip
							title={
								<Box>
									<Typography>
										Solution Designed and Built by Sean Kendall
									</Typography>
									{user?.signInDetails?.loginId && (
										<Typography>
											User: {user?.signInDetails?.loginId}
											{user?.userId && user?.userId.length > 1 && (
												<> ({user?.userId})</>
											)}
										</Typography>
									)}
									{region && (
										<Typography>Deployment Region: {region}</Typography>
									)}
									<Typography>
										Active Model/Mode: {getHeaderLabelExtended()}
									</Typography>
									<Typography>
										App Session ID: {selectedConversation?.session_id}
									</Typography>
									{kbSessionId && (
										<Typography>
											KnowledgeBase Session ID: {kbSessionId}
										</Typography>
									)}
									<Typography>
										Total Input/Output Tokens (Bedrock only): {totalInputTokens}
										/{totalOutputTokens}
									</Typography>
									<Typography>
										Bedrock Cost (Today): {calculateDailyCost()} USD
									</Typography>
									{monthlyInputTokens > 0 && (
										<Typography>
											Bedrock Cost (Current Month): {calculateMonthlyCost()} USD
										</Typography>
									)}
									<Typography> </Typography>
								</Box>
							}
							open={showInfoTooltip}
							onOpen={handleInfoTooltipOpen}
							onClose={handleInfoTooltipClose}
							arrow
						>
							<IconButton color="inherit" sx={{ ml: 1 }}>
								<FaInfoCircle />
							</IconButton>
						</NoMaxWidthTooltip>
					</Typography>
					<Box sx={{ display: "flex", alignItems: "center" }}>
						{!isMobile && disabled && (
							<Typography variant="body2" mr={2}>
								{formatTimer(elapsedTime)}
							</Typography>
						)}
						<>
							<FormControl sx={{ m: 1, minWidth: 120 }}>
								<InputLabel id="mode-select-label" sx={{ color: "white" }}>
									{isMobile ? "Model" : "Bedrock Chatbot Model"}
								</InputLabel>
								<Select
									id="mode-select"
									labelId="mode-select-label"
									disabled={disabled || (allowlist && !isUserAllowed())}
									value={
										selectedMode
											? `${selectedMode.category}%${selectedMode.mode_selector}`
											: "DEFAULT"
									}
									onChange={onSelectedModeChange}
									labels={isMobile ? "Model" : "Bedrock Chatbot Models"}
									label={
										selectedMode
											? `${selectedMode.category}%${selectedMode.mode_selector}`
											: "DEFAULT"
									}
									open={dropdownOpen}
									onOpen={(event) => {
										setDropdownOpen(true);
									}}
									onClose={(event) => {
										if (
											event.target
												.getAttribute("data-value")
												?.startsWith("header-") ||
											event.target.localName === "path"
										) {
											event.preventDefault();
										} else {
											if (event?.target?.role === null) {
												toggleCategory(null, selectedMode.category, true);
											}
											setDropdownOpen(false);
										}
									}}
									sx={{
										"& .MuiOutlinedInput-notchedOutline": {
											borderColor: "white",
										},
										"& .MuiSvgIcon-root": {
											color: "white",
										},
										color: "white",
									}}
								>
									<MenuItem value="DEFAULT">
										<em>{isMobile ? "Model" : "Select a Model"}</em>
									</MenuItem>
									{renderSelectOptions(selectOptions, isMobile ? 20 : 50)}
									<MenuItem value="RELOAD">
										<em>
											{isMobile ? "Reload" : "Reload Models (~60 seconds)"}
										</em>
									</MenuItem>
								</Select>
							</FormControl>
							{selectedMode?.knowledgeBaseId && (
								<FormControl sx={{ m: 1, minWidth: 120 }}>
									<InputLabel id="kbmode-select-label" sx={{ color: "white" }}>
										{isMobile ? "KBModel" : "KnowledgeBase Model"}
									</InputLabel>
									<Select
										id="kbmode-select"
										labelId="kbmode-select-label"
										disabled={disabled || (allowlist && !isUserAllowed())}
										value={
											selectedKbMode
												? `${selectedKbMode.category}%${selectedKbMode.mode_selector}`
												: "DEFAULT"
										}
										onChange={onSelectedKbModeChange}
										label={isMobile ? "KBModel" : "KnowledgeBase Model"}
										sx={{
											"& .MuiOutlinedInput-notchedOutline": {
												borderColor: "white",
											},
											"& .MuiSvgIcon-root": {
												color: "white",
											},
											color: "white",
										}}
									>
										<MenuItem value="DEFAULT">
											<em>{isMobile ? "Model" : "Select a Model"}</em>
										</MenuItem>
										{renderSelectOptionsKB(kbModelOptions, isMobile ? 20 : 50)}
									</Select>
								</FormControl>
							)}
						</>

						<IconButton
							color="inherit"
							onClick={() => handleOpenSettingsModal()}
						>
							<FaCog />
						</IconButton>
						<IconButton
							color="inherit"
							onClick={handleMenuOpen}
							disabled={disabled}
						>
							<FaSignOutAlt />
						</IconButton>
						<Menu
							anchorEl={anchorEl}
							open={Boolean(anchorEl)}
							onClose={handleMenuClose}
						>
							<MenuItem onClick={signOut}>Sign Out</MenuItem>
						</Menu>
					</Box>
				</Toolbar>
				{showPopup && (
					<Popup
						message={popupMessage}
						type={popupType}
						onClose={() => setShowPopup(false)}
					/>
				)}
			</AppBar>
			{modelsLoaded &&
				(!models || models.length === 0) &&
				(!videoModels || videoModels.length === 0) &&
				(!importedModels || importedModels.length === 0) &&
				(!imageModels || imageModels.length === 0) && (
					<Box
						sx={{
							width: "100%",
							backgroundColor: "#f44336",
							color: "white",
							padding: "12px",
							textAlign: "center",
						}}
					>
						<Typography>
							No models are currently active. Enable models by visiting the{" "}
							<Link
								href="https://console.aws.amazon.com/bedrock/home#/modelaccess"
								target="_blank"
								rel="noopener noreferrer"
								sx={{ color: "white", textDecoration: "underline" }}
							>
								Amazon Bedrock Model Access page
							</Link>
						</Typography>

						<Typography>
							Already enabled Models?{" "}
							<Button
								onClick={triggerModelScan}
								variant="contained"
								color="primary"
								sx={{
									backgroundColor: "white",
									color: "#f44336",
									"&:hover": {
										backgroundColor: "#e0e0e0",
									},
								}}
							>
								Refresh Model List
							</Button>
						</Typography>
						<Typography>
							After Refresh, it may take up to 15 minutes for the cache to
							clear, before you start to see models in the dropdown. Now would
							be a perfect time for a coffee ☕️.
						</Typography>
					</Box>
				)}

			{user &&
				allowlist &&
				user?.signInDetails?.loginId &&
				!isUserAllowed() && (
					<Box
						sx={{
							width: "100%",
							backgroundColor: "#f44336",
							color: "white",
							padding: "12px",
							textAlign: "center",
						}}
					>
						<Typography>
							You have not been allow-listed for this application. Your email
							must match one of the allowed values: {allowlist}
						</Typography>
					</Box>
				)}
			{isRefreshing && (
				<Box
					sx={{
						position: "fixed",
						top: 0,
						left: 0,
						width: "100%",
						height: "100%",
						backgroundColor: "rgba(0, 0, 0, 0.7)",
						display: "flex",
						flexDirection: "column",
						justifyContent: "center",
						alignItems: "center",
						zIndex: 9999,
					}}
				>
					<CircularProgress size={60} thickness={4} sx={{ color: "white" }} />
					<Typography variant="h6" sx={{ color: "white", mt: 2 }}>
						{isRefreshingMessage}
					</Typography>
					<Typography variant="body1" sx={{ color: "white", mt: 1 }}>
						Please wait...
					</Typography>
				</Box>
			)}
			{showPopup && (
				<Popup
					message={popupMessage}
					type={popupType}
					onClose={() => setShowPopup(false)}
				/>
			)}
		</>
	);
};

export default Header;
