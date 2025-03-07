/* eslint-disable react-hooks/exhaustive-deps */
import { websocketUrl } from "./variables.js";
import React, {
	useState,
	useEffect,
	useRef,
	memo,
	lazy,
	Suspense,
} from "react";
import axios from "axios";
import DOMPurify from "dompurify";
import Header from "./components/Header";
import ChatHistory from "./components/ChatHistory";
import MessageInput from "./components/MessageInput";
import LeftSideBar from "./components/LeftSideBar";
import "./App.css";
import Popup from "./components/Popup";
import { Amplify } from "aws-amplify";
import { fetchAuthSession } from "aws-amplify/auth";
import { withAuthenticator } from "@aws-amplify/ui-react";
import "@aws-amplify/ui-react/styles.css";
import amplifyConfig from "./config.json";
import { createTheme, ThemeProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import { Box, useMediaQuery } from "@mui/material";
import useWebSocket from "react-use-websocket";
import { modelPrices } from "./modelPrices.js";

const SettingsModal = lazy(() => import("./components/SettingsModal"));

async function getCurrentSession() {
	try {
		const { accessToken, idToken } = (await fetchAuthSession()).tokens ?? {};
		return { accessToken, idToken };
	} catch (err) {
		console.log(err);
	}
}

Amplify.configure(amplifyConfig);

const App = memo(({ signOut, user, awsRum }) => {
	const [partialMessages, setPartialMessages] = useState([]);
	const [region, setRegion] = useState("");
	const [websocketConnectionId, setWebsocketConnectionId] = useState(null);
	const [reactThemeMode, setReactThemeMode] = useState(
		localStorage.getItem("react_theme_mode") || "light",
	);
	const [firstLoad, setFirstLoad] = useState(true);
	const [messages, setMessages] = useState([]);
	const [messagesProcessing, setMessagesProcessing] = useState(false);
	const [uploadedFileNames, setUploadedFileNames] = useState([]);
	const [conversationList, setConversationList] = useState(
		localStorage.getItem("load_conversation_list")
			? JSON.parse(localStorage.getItem("load_conversation_list"))
			: [],
	);
	const [conversationListLoading, setConversationListLoading] = useState(false);

	const [selectedConversation, setSelectedConversation] = useState(() => {
		const storedValue = localStorage.getItem("selectedConversation");
		if (storedValue) {
			try {
				const storedValueJson = JSON.parse(storedValue);
				return storedValueJson;
			} catch (error) {
				// If parsing fails, remove the invalid value from localStorage
				localStorage.removeItem("selectedConversation");
				console.warn(
					"Invalid JSON in localStorage, removed 'selectedConversation'",
				);
			}
		}
		return {
			session_id: `session-${Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15)}`,
		};
	});

	const [requireConversationLoad, setRequireConversationLoad] = useState(true);
	const [isDisabled, setIsDisabled] = useState(false);
	const [selectedMode, setSelectedMode] = useState(() => {
		const storedValue = localStorage.getItem("selectedMode");
		if (storedValue) {
			try {
				return JSON.parse(storedValue);
			} catch (error) {
				// If parsing fails, remove the invalid value from localStorage
				localStorage.removeItem("selectedMode");
				console.warn("Invalid JSON in localStorage, removed 'selectedMode'");
			}
		}
		return ""; // Default value if nothing in localStorage or if parsing fails
	});
	const [selectedTitleGenerationMode, setSelectedTitleGenerationMode] =
		useState(null);
	const [selectedTitleGenerationTheme, setSelectedTitleGenerationTheme] =
		useState(localStorage.getItem("title_generation_theme") || "");
	const chatHistoryRef = useRef(null);
	const [showPopup, setShowPopup] = useState(false);
	const [popupMessage, setPopupMessage] = useState("");
	const [popupType, setPopupType] = useState("success");
	const [totalInputTokens, setTotalInputTokens] = useState(0);
	const [totalOutputTokens, setTotalOutputTokens] = useState(0);
	const [isLoading, setIsLoading] = useState(false);
	const [pricePer1000InputTokens, setPricePer1000InputTokens] = useState(0.003);
	const [pricePer1000OutputTokens, setPricePer1000OutputTokens] =
		useState(0.015);
	// eslint-disable-next-line
	const [monthlyInputTokens, setMonthlyInputTokens] = useState(0);
	// eslint-disable-next-line
	const [monthlyOutputTokens, setMonthlyOutputTokens] = useState(0);
	const [showSettingsModal, setShowSettingsModal] = useState(false);
	const [reloadPromptConfig, setReloadPromptConfig] = useState(true);

	// Lists of models, KBs, Agents, prompt flows
	const [bedrockAgents, setBedrockAgents] = useState(
		localStorage.getItem("local-bedrock-agents")
			? JSON.parse(localStorage.getItem("local-bedrock-agents"))
			: [],
	); //local-bedrock-agents
	const [bedrockKnowledgeBases, setBedrockKnowledgeBases] = useState(
		localStorage.getItem("local-bedrock-knowledge-bases")
			? JSON.parse(localStorage.getItem("local-bedrock-knowledge-bases"))
			: [],
	); //local-bedrock-knowledge-bases
	const [models, setModels] = useState(
		localStorage.getItem("local-models")
			? JSON.parse(localStorage.getItem("local-models"))
			: [],
	); //local-models
	const [imageModels, setImageModels] = useState(
		localStorage.getItem("local-image-models")
			? JSON.parse(localStorage.getItem("local-image-models"))
			: [],
	); //local-image-models
	const [videoModels, setVideoModels] = useState(
		localStorage.getItem("local-video-models")
			? JSON.parse(localStorage.getItem("local-video-models"))
			: [],
	); //local-video-models
	const [importedModels, setImportedModels] = useState(
		localStorage.getItem("local-imported-models")
			? JSON.parse(localStorage.getItem("local-imported-models"))
			: [],
	); //local-imported-models
	const [promptFlows, setPromptFlows] = useState(
		localStorage.getItem("local-prompt-flows")
			? JSON.parse(localStorage.getItem("local-prompt-flows"))
			: [],
	); //local-prompt-flows
	const [modelsLoaded, setModelsLoaded] = useState(false);
	const [expandedCategories, setExpandedCategories] = useState({});
	const [kbSessionId, setKBSessionId] = useState("");
	const [systemPromptUserOrSystem, setSystemPromptUserOrSystem] =
		useState("system");
	const [usedModel, setUsedModel] = useState("");
	const [stylePreset, setStylePreset] = useState("photographic");
	const [heightWidth, setHeightWidth] = useState("1024x1024");
	// chatbotTitle will be loaded from local storage(chatbot_title) if it exists, otherwise it will be set to 'AWS Bedrock KendallChat'
	const [chatbotTitle, setChatbotTitle] = useState(
		localStorage.getItem("chatbot_title") || "AWS Bedrock KendallChat",
	);

	const [selectedKbMode, onSelectedKbMode] = useState(null);
	const [previousSentMessage, setPreviousSentMessage] = useState({});
	const [isRefreshing, setIsRefreshing] = useState(false);
	const [isRefreshingMessage, setIsRefreshingMessage] =
		useState("Loading Models");
	const [attachments, setAttachments] = useState([]);
	const [allowlist, setAllowList] = useState(null);
	const messageInputRef = useRef(null);

	const [sidebarWidth, setSidebarWidth] = useState(250);
	const [isDragging, setIsDragging] = useState(false);
	const isMobile = useMediaQuery("(max-width:600px)");

	// Use the useWebSocket hook to manage the WebSocket connection
	// eslint-disable-next-line
	const { sendMessage, lastMessage, readyState, getWebSocket } = useWebSocket(
		websocketUrl,
		{
			shouldReconnect: (closeEvent) => true,
			reconnectAttempts: Number.POSITIVE_INFINITY, // Keep trying to reconnect
			reconnectInterval: (attemptNumber) =>
				Math.min(1000 * 2 ** attemptNumber, 30000), // Exponential backoff up to 30 seconds
		},
	);
	// biome-ignore lint/correctness/useExhaustiveDependencies: <explanation>
	useEffect(() => {
		if (readyState === WebSocket.OPEN) {
			sendMessage(JSON.stringify({ type: "ping" }));
		}
	}, [readyState, getWebSocket]);

	useEffect(() => {
		const interval = setInterval(() => {
			if (readyState === WebSocket.OPEN) {
				// Send a "ping" message every 3 minutes (180,000 milliseconds)
				sendMessage(JSON.stringify({ type: "ping" }));
			}
		}, 180000); // 3 minutes = 180000 milliseconds

		// Cleanup interval on component unmount
		return () => clearInterval(interval);
	}, [readyState, sendMessage]);

	//persist models to local storage if changed
	useEffect(() => {
		if (models && models.length > 0)
			localStorage.setItem("local-models", JSON.stringify(models));
	}, [models]);
	//persist image models to local storage if changed
	useEffect(() => {
		if (imageModels && imageModels.length > 0)
			localStorage.setItem("local-image-models", JSON.stringify(imageModels));
	}, [imageModels]);
	useEffect(() => {
		if (videoModels && videoModels.length > 0)
			localStorage.setItem("local-video-models", JSON.stringify(videoModels));
	}, [videoModels]);
	useEffect(() => {
		if (importedModels && importedModels.length > 0)
			localStorage.setItem(
				"local-imported-models",
				JSON.stringify(importedModels),
			);
	}, [importedModels]);

	//persist prompt flows to local storage if changed
	useEffect(() => {
		if (promptFlows && promptFlows.length > 0)
			localStorage.setItem("local-prompt-flows", JSON.stringify(promptFlows));
	}, [promptFlows]);

	//persist bedrockAgents to local storage if changed
	useEffect(() => {
		if (bedrockAgents && bedrockAgents.length > 0)
			localStorage.setItem(
				"local-bedrock-agents",
				JSON.stringify(bedrockAgents),
			);
	}, [bedrockAgents]);

	//persist bedrockKnowledgeBases to local storage if changed
	useEffect(() => {
		if (bedrockKnowledgeBases && bedrockKnowledgeBases.length > 0)
			localStorage.setItem(
				"local-bedrock-knowledge-bases",
				JSON.stringify(bedrockKnowledgeBases),
			);
	}, [bedrockKnowledgeBases]);

	useEffect(() => {
		if (websocketConnectionId) {
			loadConfigSubaction(
				"load_models,load_prompt_flows,load_knowledge_bases,load_agents",
			);
		}
	}, [websocketConnectionId]);

	// biome-ignore lint/correctness/useExhaustiveDependencies: only watch messages
	useEffect(() => {
		// if messages has > 0 elements, print to console
		if (messages.length > 0 && !messagesProcessing) {
			//Remove any error messages and the cooresponding message before (which is the user message) only for persistence
			const filteredMessages = messages.filter((message, index, array) => {
				if (
					index > 0 &&
					message.raw_message &&
					message.raw_message.type === "error"
				) {
					// Skip this message and the previous one
					return false;
				}
				if (
					index < array.length - 1 &&
					array[index + 1].raw_message &&
					array[index + 1].raw_message.type === "error"
				) {
					// Skip this message as it's followed by an error
					return false;
				}
				return true;
			});
			localStorage.setItem(
				`chatHistory-${selectedConversation?.session_id}`,
				JSON.stringify(filteredMessages),
			);
		}
	}, [messages]);

	const getModeObjectFromModelID = (category, selectedModelId) => {
		let selectedObject = null;
		if (
			category === "Bedrock Models" ||
			category === "Imported Models" ||
			category === "Bedrock KnowledgeBases"
		) {
			selectedObject = models.find((item) => item.modelId === selectedModelId);
			if (!selectedObject) {
				selectedObject = models.find(
					(item) => item.modelArn === selectedModelId,
				);
			}
		} else if (category === "Bedrock Image Models") {
			selectedObject = imageModels.find(
				(item) => item.modelId === selectedModelId,
			);
			if (!selectedObject) {
				selectedObject = imageModels.find(
					(item) => item.modelArn === selectedModelId,
				);
			}
		} else if (category === "Bedrock Video Models") {
			selectedObject = videoModels.find(
				(item) => item.modelId === selectedModelId,
			);
			if (!selectedObject) {
				selectedObject = videoModels.find(
					(item) => item.modelArn === selectedModelId,
				);
			}
		} else if (category === "Imported Models") {
			selectedObject = importedModels.find(
				(item) => item.modelId === selectedModelId,
			);
			if (!selectedObject) {
				selectedObject = importedModels.find(
					(item) => item.modelArn === selectedModelId,
				);
			}
		} else if (category === "Prompt Flows") {
			selectedObject = promptFlows.find(
				(item) => item.flowAliasId === selectedModelId,
			);
		} else if (category === "Bedrock Agents") {
			selectedObject = bedrockAgents.find(
				(item) => item.agentAliasId === selectedModelId,
			);
		}
		return selectedObject;
	};

	const handleSelectChat = (conversation) => {
		if (isDisabled) {
			return;
		}
		setRequireConversationLoad(true);
		setSelectedConversation(conversation);
		if (conversation) {
			localStorage.setItem(
				"selectedConversation",
				JSON.stringify(conversation),
			);
		}
		const selMode = getModeObjectFromModelID(
			conversation.category,
			conversation.selected_model_id,
		);
		if (conversation.selected_knowledgebase_id && conversation.kb_session_id) {
			setKBSessionId(conversation.kb_session_id);
			const selectedObject = bedrockKnowledgeBases.find(
				(model) =>
					model.knowledgeBaseId === conversation.selected_knowledgebase_id,
			);
			onSelectedKbMode(selMode);
			setExpandedCategories((prev) => {
				return {
					...Object.keys(prev).reduce((acc, key) => {
						acc[key] = false;
						return acc;
					}, {}),
					[selectedObject.category]: true,
				};
			});
			handleModeChange(selectedObject, true);
			localStorage.setItem("selectedKbMode", JSON.stringify(selectedObject));
			localStorage.setItem(
				`kbSessionId-${conversation.sessionId}`,
				conversation.kb_session_id,
			);
		} else if (selMode) {
			setExpandedCategories((prev) => {
				return {
					...Object.keys(prev).reduce((acc, key) => {
						acc[key] = false;
						return acc;
					}, {}),
					[selMode.category]: true,
				};
			});

			handleModeChange(selMode, true);
		}
	};
	// biome-ignore lint/correctness/useExhaustiveDependencies: Not needed
	useEffect(() => {
		if (selectedConversation) {
			handleSelectChat(selectedConversation);
		}
	}, [selectedConversation]);
	const triggerInfoErrorPopupMessage = (msgText, type) => {
		setPopupMessage(msgText);
		setPopupType(type);
		setShowPopup(true);
	};
	const localSignOut = () => {
		localStorage.clear();
		signOut();
	};
	// Add this function to update the prices based on the selected model
	const updatePricesFromModel = () => {
		if (selectedMode?.modelId) {
			const modelId = selectedMode?.modelId;
			const modelPriceInfo = modelPrices[modelId] || {
				pricePer1000InputTokens: 0.003,
				pricePer1000OutputTokens: 0.015,
			};
			setPricePer1000InputTokens(modelPriceInfo.pricePer1000InputTokens);
			setPricePer1000OutputTokens(modelPriceInfo.pricePer1000OutputTokens);
		} else {
			const modelPriceInfo = {
				pricePer1000InputTokens: 0.003,
				pricePer1000OutputTokens: 0.015,
			};
			setPricePer1000InputTokens(modelPriceInfo.pricePer1000InputTokens);
			setPricePer1000OutputTokens(modelPriceInfo.pricePer1000OutputTokens);
		}
	};

	// biome-ignore lint/correctness/useExhaustiveDependencies:
	useEffect(() => {
		updatePricesFromModel();
	}, [selectedMode]);

	useEffect(() => {
		const kbSessionId = localStorage.getItem("kbSessionId");
		setKBSessionId(kbSessionId);
		const storedPricePer1000InputTokens = localStorage.getItem(
			"pricePer1000InputTokens",
		);
		setPricePer1000InputTokens(storedPricePer1000InputTokens);
		const storedPricePer1000OutputTokens = localStorage.getItem(
			"pricePer1000OutputTokens",
		);
		setPricePer1000OutputTokens(storedPricePer1000OutputTokens);

		const currentDate = new Date().toDateString();
		const storedInputTokens = isValidJSON(
			localStorage.getItem(`inputTokens-${currentDate}`),
		)
			? JSON.parse(localStorage.getItem(`inputTokens-${currentDate}`))
			: 0;
		const storedOutputTokens = isValidJSON(
			localStorage.getItem(`outputTokens-${currentDate}`),
		)
			? JSON.parse(localStorage.getItem(`outputTokens-${currentDate}`))
			: 0;

		setTotalInputTokens(storedInputTokens);
		setTotalOutputTokens(storedOutputTokens);
	}, []);

	const isValidJSON = (str) => {
		try {
			JSON.parse(str);
		} catch (e) {
			return false;
		}
		return true;
	};

	const scrollToBottom = () => {
		window.scrollTo({
			top: document.documentElement.scrollHeight,
			behavior: "smooth",
		});

		setTimeout(() => {
			requestAnimationFrame(() => {
				if (messageInputRef.current) {
					messageInputRef.current.focus();
				}
			});
		}, 200);
	};

	const handleModeChange = (newMode, chatSelectedByUser) => {
		if (!chatSelectedByUser) {
			if (
				selectedMode &&
				newMode &&
				(selectedMode.output_type !== newMode.output_type ||
					selectedMode.category !== newMode.category ||
					selectedMode.knowledgeBaseId !== newMode.knowledgeBaseId)
			) {
				const selectedOutputType = selectedMode.output_type
					? selectedMode.output_type.charAt(0).toUpperCase() +
						selectedMode.output_type.slice(1).toLowerCase()
					: "unknown";
				const newOutputType = newMode.output_type
					? newMode.output_type.charAt(0).toUpperCase() +
						newMode.output_type.slice(1).toLowerCase()
					: "unknown";
				// if selectedOutputType is null or empty or equal to unknown
				if (!selectedOutputType || selectedOutputType === "Unknown") {
					triggerInfoErrorPopupMessage(
						"I have created a new chat for you.",
						"success",
					);
				} else {
					triggerInfoErrorPopupMessage(
						`You were currently interacting with a model capable of outputting ${selectedOutputType} and are now switching to an output type of ${newOutputType}. I have created a new chat for you.`,
						"success",
					);
				}
				handleNewChat();
			}
		}
		if (newMode) {
			setSelectedMode(newMode);
			localStorage.setItem("selectedMode", JSON.stringify(newMode));
		}
		setTimeout(scrollToBottom, 0);
	};

	const loadConfigSubaction = async (subaction) => {
		const { accessToken, idToken } = await getCurrentSession();
		const data = {
			action: "config",
			subaction: subaction,
			idToken: `${idToken}`,
			accessToken: `${accessToken}`,
		};
		sendMessage(JSON.stringify(data));
		awsRum.recordEvent("chatbot_websocket_call", {
			action: "loadConfigSubaction",
			data: data,
		});
	};

	const triggerModelScan = async () => {
		setIsRefreshingMessage("Loading Models");
		setIsRefreshing(true);
		try {
			const { accessToken, idToken } = await getCurrentSession();
			const data = {
				action: "model-scan-request",
				idToken: `${idToken}`,
				accessToken: `${accessToken}`,
			};
			sendMessageViaRest(data, "/rest/model-scan-request", "triggerModelScan");
		} catch (error) {
			console.error("Error refreshing models:", error);
		}
	};
	const triggerModelScanFinished = async () => {
		loadConfigSubaction(
			"load_models,load_prompt_flows,load_knowledge_bases,load_agents,modelscan",
		);
	};

	const loadConversationList = async (selected_session_id = null) => {
		// if firstLoad is true and conversationList is not null empty
		if (firstLoad && conversationList.length > 0) {
			setFirstLoad(false);
		} else {
			if (firstLoad) {
				setFirstLoad(false);
			}
			setConversationListLoading(true);
		}
		const { accessToken, idToken } = await getCurrentSession();
		const data = {
			type: "load_conversation_list",
			selectedSessionId: selected_session_id,
			idToken: `${idToken}`,
			accessToken: `${accessToken}`,
		};
		sendMessageViaRest(data, "/rest/send-message", "loadConversationList");
	};

	const loadConversationHistory = async (
		sessId,
		chatHistoryExists,
		lastLoadedChatMessageId,
	) => {
		// if (chatHistoryExists) {
		// 	return;
		// }
		if (
			models &&
			selectedMode &&
			(selectedConversation?.session_id || sessId)
		) {
			if (!chatHistoryExists) {
				setIsRefreshingMessage("Loading Previous Conversation");
				setIsRefreshing(true);
			}
			const { accessToken, idToken } = await getCurrentSession();
			const data = {
				type: "load",
				session_id: sessId ? sessId : selectedConversation?.session_id,
				last_loaded_message_id: lastLoadedChatMessageId,
				kb_session_id: kbSessionId,
				selected_mode: selectedMode,
				idToken: `${idToken}`,
				accessToken: `${accessToken}`,
			};
			sendMessageViaRest(data, "/rest/send-message", "loadConversationHistory");
		}
	};

	const clearConversationHistory = async (session_id) => {
		localStorage.removeItem(`chatHistory-${session_id}`);
		const { accessToken, idToken } = await getCurrentSession();
		const data = {
			type: "clear_conversation",
			session_id: session_id,
			kb_session_id: kbSessionId,
			selected_mode: selectedMode,
			idToken: `${idToken}`,
			accessToken: `${accessToken}`,
		};
		sendMessageViaRest(data, "/rest/send-message", "clearConversationHistory");
	};

	// biome-ignore lint/correctness/useExhaustiveDependencies: Not Needed
	useEffect(() => {
		if (!lastMessage) return;
		try {
			const message = JSON.parse(lastMessage.data);
			const message_temp_cache = [];
			if (message.type !== "conversation_history") return;
			const current_chunk = message.current_chunk || 1;
			const last_message = message.last_message;
			let messageChunk = JSON.parse(message.chunk);
			if (messageChunk.msg_partial) {
				const allMessages = [...partialMessages, messageChunk];
				if (messageChunk.msg_partial_last_chunk) {
					let newMessageChunk;
					for (const currentPartialMessage of allMessages) {
						if (!newMessageChunk) {
							newMessageChunk = currentPartialMessage;
						} else {
							newMessageChunk.content = `${currentPartialMessage.content}${newMessageChunk.content}`;
						}
					}
					messageChunk = newMessageChunk;
				} else {
					setPartialMessages(allMessages);
					return;
				}
			}
			if (partialMessages.length > 0) setPartialMessages([]);
			messageChunk = convertRoleToHuman(messageChunk);
			for (const item of messageChunk) {
				if (item.message_stop_reason) {
					handleMaxTokenMessage(item);
				}
			}

			message_temp_cache.push(...messageChunk);
			if (last_message) {
				setMessagesProcessing(false);
			} else if (!messagesProcessing) {
				setMessagesProcessing(true);
			}
			setMessages((prevMessages) =>
				current_chunk === 1 ? messageChunk : [...prevMessages, ...messageChunk],
			);
			if (last_message) {
				setIsRefreshing(false);
				setTimeout(scrollToBottom, 0);
				message_temp_cache.length = 0;
			}
		} catch (error) {
			console.error("Error processing message:", error);
		}
		// Remove messages from dependency array since it causes infinite loop
	}, [lastMessage]);

	const handleError = (message) => {
		const errormessage =
			typeof message === "string" ? message : message.error || message.message;

		let popupMsg =
			"Sorry, we encountered an issue. Please try resubmitting your message.";

		if (
			errormessage.includes("allow-listed") ||
			errormessage.includes(
				"You have not requested access to a model in Bedrock",
			)
		) {
			popupMsg = errormessage;
			triggerInfoErrorPopupMessage(popupMsg, "error");
		} else if (
			errormessage.includes("throttlingException") ||
			errormessage.includes("ThrottlingException")
		) {
			triggerInfoErrorPopupMessage(
				"Sorry, we encountered a throttling issue. Please try resubmitting your message.",
				"error",
			);
		} else if (errormessage.includes("AUP or AWS Responsible AI")) {
			triggerInfoErrorPopupMessage(
				"This request has been blocked by our content filters because the generated image(s) may conflict with our AUP or AWS Responsible AI Policy. Please try again.",
				"error",
			);
		} else {
			triggerInfoErrorPopupMessage(popupMsg, "error");
		}

		setIsDisabled(false);
		console.error("WebSocket error:", popupMsg);
	};

	function reformat_attachments(attachments) {
		return attachments.map((attachment) => {
			if (attachment.type.startsWith("image"))
				return { image: { s3source: { s3key: attachment.url } } };
			if (attachment.type.startsWith("video"))
				return { video: { s3source: { s3key: attachment.url } } };
			return { document: { s3source: { s3key: attachment.url } } };
		});
	}

	const sendMessageViaRest = async (data, endpoint, action) => {
		awsRum.recordEvent("chatbot_rest_call", {
			action: action,
			endpoint: endpoint,
			data: data,
		});
		try {
			const { accessToken, idToken } = await getCurrentSession();
			await axios.post(
				endpoint,
				{
					...data,
					session_id: selectedConversation?.session_id,
					connection_id: websocketConnectionId,
					access_token: accessToken,
				},
				{
					headers: {
						Authorization: `Bearer ${idToken}`,
						"Content-Type": "application/json",
					},
				},
			);
			// const { url, fields } = response.data;
		} catch (error) {
			console.error("Error sending message:", error);
			throw error;
		}
	};

	const onSend = async (
		message,
		attachments,
		retryPreviousMessage,
		truncated,
	) => {
		let newConversationSessionId;
		if (!selectedConversation || !selectedConversation.session_id) {
			setRequireConversationLoad(false);
			newConversationSessionId = `session-${Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15)}`;
			const newConvo = { session_id: newConversationSessionId };
			setSelectedConversation(newConvo);
			localStorage.setItem("selectedConversation", JSON.stringify(newConvo));
		}

		if (retryPreviousMessage) {
			message = previousSentMessage.message;
			attachments = previousSentMessage.attachments;
		} else {
			setPreviousSentMessage({ message: message, attachments: attachments });
		}

		setIsLoading(true);

		const sanitizedMessage = DOMPurify.sanitize(message);
		const randomMessageId = Math.random().toString(36).substring(2, 10);

		if (selectedMode.category === "Bedrock Image Models") {
			generateImage(sanitizedMessage, randomMessageId, attachments);
			return;
		}
		if (selectedMode.category === "Bedrock Video Models") {
			const video_helper_image_model_id =
				selectedMode?.video_helper_image_model_id;
			generateVideo(
				sanitizedMessage,
				randomMessageId,
				attachments,
				video_helper_image_model_id,
			);
			return;
		}

		const { accessToken, idToken } = await getCurrentSession();
		const message_timestamp = new Date().toISOString();
		const timezone = Intl.DateTimeFormat("en-US", {
			timeZoneName: "short",
			timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
		})
			.formatToParts(new Date())
			.find((part) => part.type === "timeZoneName").value;

		const data = {
			prompt: sanitizedMessage,
			type: "chat",
			message_id: randomMessageId,
			timestamp: message_timestamp,
			timestamp_local_timezone: timezone,
			session_id: newConversationSessionId
				? newConversationSessionId
				: selectedConversation?.session_id,
			kb_session_id: kbSessionId,
			selected_mode: selectedMode,
			titleGenModel: selectedTitleGenerationMode,
			titleGenTheme: selectedTitleGenerationTheme,
			idToken: `${idToken}`,
			accessToken: `${accessToken}`,
			reloadPromptConfig: reloadPromptConfig,
			systemPromptUserOrSystem: systemPromptUserOrSystem,
			attachments: await Promise.all(
				attachments
					.map(async (file) => {
						try {
							return {
								name: file.name,
								type: file.type,
								url: file.url,
							};
						} catch (error) {
							console.error("Error processing file:", file.name, error);
							return null;
						}
					})
					.filter(Boolean),
			),
		};

		if (selectedMode.knowledgeBaseId) {
			//add selectedKbMode to data
			data.selectedKbMode = selectedKbMode;
		}
		const reformatted_attachments = reformat_attachments(attachments);
		let truncated_message = "";
		if (truncated) {
			truncated_message =
				"\n\n* Max message size is 250MB. Your input has been truncated to this size. *";
		}
		const messageWithTime = {
			role: "user",
			content: [
				{
					text: message
						? `${message}${truncated_message || ""}`
						: truncated_message || "",
				},
				...reformatted_attachments,
			],
			message_id: randomMessageId,
			timestamp: message_timestamp,
		};
		setMessages((prevMessages) => [
			...(prevMessages ? prevMessages : []),
			messageWithTime,
			{
				role: "assistant",
				content: "",
				isStreaming: true,
				isVideoStreaming: false,
				timestamp: null,
			},
		]);

		setTimeout(scrollToBottom, 0);
		sendMessageViaRest(data, "/rest/send-message", "chatMessage");
		setReloadPromptConfig(false);
	};

	const generateImage = async (prompt, randomMessageId, attachments) => {
		setIsLoading(true);
		let newConversationSessionId;
		if (!selectedConversation || !selectedConversation.session_id) {
			setRequireConversationLoad(false);
			newConversationSessionId = `session-${Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15)}`;
			const newConvo = { session_id: newConversationSessionId };
			setSelectedConversation(newConvo);
			localStorage.setItem("selectedConversation", JSON.stringify(newConvo));
		}

		const { accessToken, idToken } = await getCurrentSession();
		const message_timestamp = new Date().toISOString();
		const data = {
			prompt: prompt,
			message_id: randomMessageId,
			timestamp: message_timestamp,
			session_id: newConversationSessionId
				? newConversationSessionId
				: selectedConversation?.session_id,
			selected_mode: selectedMode,
			idToken: `${idToken}`,
			accessToken: `${accessToken}`,
			stylePreset: stylePreset,
			heightWidth: heightWidth,
		};

		const currentTime = new Date();
		const messageWithTime = {
			role: "user",
			content: `Generate an Image of: ${prompt}`,
			message_id: randomMessageId,
			timestamp: currentTime.toISOString(),
		};
		setMessages((prevMessages) => [
			...(prevMessages ? prevMessages : []),
			messageWithTime,
			{
				role: "assistant",
				content: `Generating Image of: *${prompt}* with model: *${selectedMode.modelName}*. Please wait.. `,
				isStreaming: true,
				isVideoStreaming: false,
				timestamp: null,
				model: selectedMode.modelName,
				isImage: false,
				isVideo: false,
				imageAlt: prompt,
			},
		]);

		setTimeout(scrollToBottom, 0);
		sendMessageViaRest(data, "/rest/send-message", "generateImageRequest");
	};

	const generateVideo = async (
		prompt,
		randomMessageId,
		attachments,
		video_helper_image_model_id,
	) => {
		setIsLoading(true);
		let newConversationSessionId;
		if (!selectedConversation || !selectedConversation.session_id) {
			setRequireConversationLoad(false);
			newConversationSessionId = `session-${Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15)}`;
			const newConvo = { session_id: newConversationSessionId };
			setSelectedConversation(newConvo);
			localStorage.setItem("selectedConversation", JSON.stringify(newConvo));
		}

		const { accessToken, idToken } = await getCurrentSession();
		const message_timestamp = new Date().toISOString();
		const data = {
			prompt: prompt,
			video_helper_image_model_id: video_helper_image_model_id,
			message_id: randomMessageId,
			timestamp: message_timestamp,
			session_id: newConversationSessionId
				? newConversationSessionId
				: selectedConversation?.session_id,
			selected_mode: selectedMode,
			idToken: `${idToken}`,
			accessToken: `${accessToken}`,
			attachments: await Promise.all(
				attachments
					.map(async (file) => {
						try {
							return {
								name: file.name,
								type: file.type,
								url: file.url,
							};
						} catch (error) {
							console.error("Error processing file:", file.name, error);
							return null;
						}
					})
					.filter(Boolean),
			),
		};

		const currentTime = new Date();
		const reformatted_attachments = reformat_attachments(attachments);
		const messageWithTime = {
			role: "user",
			content: [
				{ text: `Generate a Video of: ${prompt}.` },
				...reformatted_attachments,
			],
			message_id: randomMessageId,
			timestamp: currentTime.toISOString(),
		};
		setMessages((prevMessages) => [
			...(prevMessages ? prevMessages : []),
			messageWithTime,
			{
				role: "assistant",
				content: `Generating Video of: *${prompt}* with model: *${selectedMode.modelName}*. Please wait... \n\rThis could take 3 - 5 Minutes... `,
				isStreaming: true,
				isVideoStreaming: false,
				timestamp: null,
				model: selectedMode.modelName,
				isImage: false,
				isVideo: false,
				imageAlt: prompt,
			},
		]);

		setTimeout(scrollToBottom, 0);
		sendMessageViaRest(data, "/rest/send-message", "generateVideoRequest");
	};

	// biome-ignore lint/correctness/useExhaustiveDependencies:
	useEffect(() => {
		if (lastMessage !== null) {
			const message = JSON.parse(lastMessage.data);

			// Handle session ID updates from the server
			if (
				message.kb_session_id &&
				(!kbSessionId || (kbSessionId && kbSessionId !== message.kb_session_id))
			) {
				// Skip updating the session if the response contains a specific error message
				if (message && message.delta && message.delta.text) {
					const textValue = message.delta.text;
					if (
						textValue.includes(
							"Sorry, I am unable to assist you with this request",
						) ||
						textValue.includes("Sorry, I cannot Answer")
					) {
						console.log("Sorry, I am unable to assist you with this request.");
					} else {
						setKBSessionId(message.kb_session_id);
						localStorage.setItem(
							`kbSessionId-${selectedConversation?.session_id}`,
							message.kb_session_id,
						);
					}
				}
			}

			if (
				typeof message === "string" &&
				message.includes("You have not been allow-listed for this application")
			) {
				handleError(message);
			} else if (message.type === "message_title") {
				// Do nothing
			} else if (
				message.type === "message_start" &&
				selectedConversation.session_id === message.session_id
			) {
				if (isRefreshing) {
					setIsRefreshing(false);
				}
				const model = message?.message?.model;
				setUsedModel(model);
				updateMessages(message);
			} else if (
				message.type === "content_block_delta" &&
				selectedConversation.session_id === message.session_id
			) {
				if (isRefreshing) {
					setIsRefreshing(false);
				}
				updateMessages(message);
			} else if (
				message.type === "message_stop" &&
				selectedConversation.session_id === message.session_id
			) {
				if (isRefreshing) {
					setIsRefreshing(false);
				}
				updateMessages(message);
				updateMessagesOnStop(message);
				setIsDisabled(false);
				setIsLoading(false);
				setTimeout(scrollToBottom, 0);
				if (message.new_conversation) {
					loadConversationList(message.session_id);
				}
			} else if (
				(message.type === "error" ||
					message.message === "Internal server error") &&
				selectedConversation.session_id === message.session_id
			) {
				if (isRefreshing) {
					setIsRefreshing(false);
				}
				if (
					message.error &&
					(message.error.includes("throttlingException") ||
						message.error.includes("ThrottlingException"))
				) {
					message.error =
						"Oops! Looks like we're experiencing a 'traffic jam' on the Amazon Bedrock superhighway. Our AI is currently doing the digital equivalent of honking its horn and tapping its foot impatiently. \n\r\n\rPlease give it another shot - our AI is eager to chat with you! If this keeps happening, it might be time to sweet-talk your IT team into upgrading our 'digital express lane' by purchasing some fancy 'Provisioned Throughput' from Amazon Bedrock. \n\r\n\rRemember, good things come to those who wait... but faster things come to those with better throughput!";
				}
				updateMessagesOnStop(message);
				handleError(message);
				setIsDisabled(false);
				setIsLoading(false);
				setTimeout(scrollToBottom, 0);
			} else if (
				message.type === "video_generated" &&
				selectedConversation.session_id === message.session_id
			) {
				if (isRefreshing) {
					setIsRefreshing(false);
				}
				setMessages((prevMessages) => {
					const updatedMessages = [...(prevMessages ? prevMessages : [])];
					const lastIndex = updatedMessages.length - 1;
					updatedMessages[lastIndex] = {
						...updatedMessages[lastIndex],
						content: message.video_url,
						prompt: message.prompt,
						message_id: message.message_id,
						isStreaming: false,
						isVideoStreaming: true,
						isImage: false,
						isVideo: true,
						model: message.modelId,
						outputTokenCount: 0,
						inputTokenCount: 0,
						timestamp: message.timestamp,
						raw_message: message,
					};
					return updatedMessages;
				});
			} else if (
				message.type === "image_generated" &&
				selectedConversation.session_id === message.session_id
			) {
				if (isRefreshing) {
					setIsRefreshing(false);
				}
				setMessages((prevMessages) => {
					const updatedMessages = [...(prevMessages ? prevMessages : [])];
					const lastIndex = updatedMessages.length - 1;
					updatedMessages[lastIndex] = {
						...updatedMessages[lastIndex],
						content: message.image_url,
						prompt: message.prompt,
						message_id: message.message_id,
						isStreaming: false,
						isVideoStreaming: false,
						isImage: true,
						isVideo: false,
						model: message.modelId,
						outputTokenCount: 0,
						inputTokenCount: 0,
						timestamp: message.timestamp,
						raw_message: message,
					};
					return updatedMessages;
				});
			} else if (message.type === "load_response") {
				if (message.load_models)
					if (message.load_models.text_models)
						setModels(filter_active_models(message.load_models.text_models));
				if (message.load_models.image_models)
					setImageModels(
						filter_active_models(message.load_models.image_models),
					);
				if (message.load_models.video_models)
					setVideoModels(
						filter_active_models(message.load_models.video_models),
					);
				if (message.load_models.imported_models)
					setImportedModels(message.load_models.imported_models);
				if (message.load_knowledge_bases?.knowledge_bases)
					setBedrockKnowledgeBases(
						message.load_knowledge_bases.knowledge_bases,
					);
				if (message.load_agents?.agents)
					setBedrockAgents(message.load_agents.agents);
				if (message.load_prompt_flows?.prompt_flows)
					setPromptFlows(message.load_prompt_flows.prompt_flows);
				if (message.modelscan === true) setIsRefreshing(false);

				setModelsLoaded(true);
			} else if (message.type === "conversation_history") {
				// Do nothing, UseEffect will handle this
				// to find this code, search for:
				// if (message.type !== "conversation_history") return;
			} else if (message.type === "load_conversation_list") {
				setConversationList(message.conversation_list);
				// save message.conversation_list in local storage
				if (message.conversation_list) {
					localStorage.setItem(
						"load_conversation_list",
						JSON.stringify(message.conversation_list),
					);
				}

				if (message.selected_session_id) {
					const selectedConversation = message.conversation_list.find(
						(conversation) =>
							conversation.session_id === message.selected_session_id,
					);
					setSelectedConversation(selectedConversation);
					localStorage.setItem(
						"selectedConversation",
						JSON.stringify(selectedConversation),
					);
				}

				setConversationListLoading(false);
			} else if (message.type === "modelscan") {
				triggerModelScanFinished();
			} else {
				if (typeof message === "object" && message !== null) {
					const messageString = JSON.stringify(message);
					if (messageString.includes("pong")) {
						// log current time and connectionId
						// console.log(`pong received at ${new Date().toISOString()} with connection_id: ${message?.connection_id}`)
						message.connection_id &&
							setWebsocketConnectionId(message.connection_id);
					} else if (messageString.includes("model_not_ready")) {
						console.log("Model Not Ready");
						triggerInfoErrorPopupMessage(
							"Custom Model Starting. Please wait while we retry",
							"success",
						);
					} else if (messageString.includes("no_conversation_to_load")) {
						setIsRefreshing(false);
					} else if (messageString.includes('"type":"citation_data')) {
						console.log("Citation Data", messageString);
					} else if (messageString.includes("Access Token has expired")) {
						try {
							localSignOut();
						} catch (error) {
							console.error("Error signing out: ", error);
						}
					} else if (!messageString.includes("Message Received")) {
						console.log("Uncaught String Message 1:");
						console.log(messageString);
						if (isRefreshing) setIsRefreshing(false);
					}
				} else if (typeof message === "string") {
					if (message.includes("no_conversation_to_load")) {
						setIsRefreshing(false);
					} else if (!message.includes("Message Received")) {
						if (isRefreshing) setIsRefreshing(false);
						console.log("Uncaught String Message 2:");
						console.log(message);
					}
				} else {
					console.log("Uncaught Message (non-string, non-object):");
					console.log(message);
					if (isRefreshing) setIsRefreshing(false);
				}
			}
		}
	}, [lastMessage]);

	const updateMessages = (message) => {
		handleMaxTokenMessage(message);
		if (message?.delta?.text) {
			setMessages((prevMessages) => {
				const updatedMessages = [...(prevMessages ? prevMessages : [])];
				const lastIndex = updatedMessages.length - 1;
				const lastMessage = updatedMessages[lastIndex];
				if (lastMessage && !lastMessage.content) {
					lastMessage.content = "";
				}
				if (lastMessage && lastMessage.role === "assistant") {
					const newContent = message.delta?.text
						? lastMessage.content + message.delta.text
						: message.error
							? message.error
							: "no content";
					updatedMessages[lastIndex] = {
						...lastMessage,
						content: newContent,
						raw_message: message,
					};
				}
				return updatedMessages;
			});
		}
	};

	function handleMaxTokenMessage(message) {
		if (message.message_stop_reason) {
			let max_token_message;
			if (message.message_stop_reason === "max_tokens") {
				const needs_code_end = message.needs_code_end;
				if (message?.amazon_bedrock_invocation_metrics?.outputTokenCount) {
					// if needs_code_end is true, then prepend ``` to max_token_message
					if (needs_code_end) {
						max_token_message = `\`\`\`\n\rThe response from this model has reached the maximum size. Max Size: ${message.amazon_bedrock_invocation_metrics.outputTokenCount} Tokens.`;
					} else {
						max_token_message = ` The response from this model has reached the maximum size. Max Size: ${message.amazon_bedrock_invocation_metrics.outputTokenCount} Tokens`;
					}
				} else {
					max_token_message =
						"The response from this model has reached the maximum size.";
				}
				if (message.delta?.text) {
					message.delta.text = `${message.delta.text} \n\r\n\r${max_token_message}`;
				} else if (message.content) {
					message.content.push({ text: `\n\r\n\r${max_token_message}` });
				} else {
					message.delta = { text: `\n\r\n\r${max_token_message}` };
					message.content = [{ text: `\n\r\n\r${max_token_message}` }];
				}
			}
		}
	}

	function replaceKey(obj) {
		if (Array.isArray(obj)) {
			return obj.map((item) => replaceKey(item));
		}
		if (typeof obj === "object" && obj !== null) {
			return Object.fromEntries(
				Object.entries(obj).map(([key, value]) => [
					key === "amazon-bedrock-invocationMetrics"
						? "amazon_bedrock_invocation_metrics"
						: key,
					replaceKey(value),
				]),
			);
		}
		return obj;
	}

	const updateMessagesOnStop = (messageStop) => {
		setMessagesProcessing(false);
		setMessages((prevMessages) => {
			const updatedMessages = [...(prevMessages ? prevMessages : [])];
			const lastIndex = updatedMessages.length - 1;
			const messageStopReplaced = replaceKey(messageStop);

			const invocationMetrics =
				messageStopReplaced?.amazon_bedrock_invocation_metrics || null; // Handle the case when 'amazon-bedrock-invocationMetrics' is not present
			const inputTokenCount = invocationMetrics
				? invocationMetrics.inputTokenCount
				: 0;
			const outputTokenCount = invocationMetrics
				? invocationMetrics.outputTokenCount
				: 0;
			const tokenidentifier = invocationMetrics
				? `${invocationMetrics.inputTokenCount || ""}_${invocationMetrics.outputTokenCount || ""}_${invocationMetrics.invocationLatency || ""}_${invocationMetrics.firstByteLatency || ""}`
				: `R${Math.floor(Math.random() * 1000000)}`;

			const currentDate = new Date().toDateString();
			const existingInputTokens = isValidJSON(
				localStorage.getItem(`inputTokens-${currentDate}`),
			)
				? JSON.parse(localStorage.getItem(`inputTokens-${currentDate}`))
				: 0;
			const existingOutputTokens = isValidJSON(
				localStorage.getItem(`outputTokens-${currentDate}`),
			)
				? JSON.parse(localStorage.getItem(`outputTokens-${currentDate}`))
				: 0;
			const lastStoredTokenIdentifier = isValidJSON(
				localStorage.getItem("lastTokenIdentifier"),
			)
				? JSON.parse(localStorage.getItem("lastTokenIdentifier"))
				: "";

			if (tokenidentifier === lastStoredTokenIdentifier) return updatedMessages;

			localStorage.setItem("lastTokenIdentifier", tokenidentifier);
			updatedMessages[lastIndex] = {
				...updatedMessages[lastIndex],
				isStreaming: false,
				isVideoStreaming: false,
				timestamp: new Date().toISOString(),
				model: usedModel,
				outputTokenCount: outputTokenCount,
				inputTokenCount: inputTokenCount,
				raw_message: messageStopReplaced,
			};

			const newInputTokens = existingInputTokens + inputTokenCount;
			const newOutputTokens = existingOutputTokens + outputTokenCount;

			localStorage.setItem(
				`inputTokens-${currentDate}`,
				newInputTokens.toString(),
			);
			localStorage.setItem(
				`outputTokens-${currentDate}`,
				newOutputTokens.toString(),
			);

			setTotalInputTokens(newInputTokens);
			setTotalOutputTokens(newOutputTokens);
			return updatedMessages;
		});
		setTimeout(scrollToBottom, 0);
	};

	const handleOpenSettingsModal = () => {
		setShowSettingsModal(true);
	};

	const handleCloseSettingsModal = () => {
		setShowSettingsModal(false);
	};

	const handleSaveSettings = () => {
		handleCloseSettingsModal();
	};
	// Code Supporting SideBar
	const handleNewChat = () => {
		setRequireConversationLoad(false);
		setMessages([]);
		setAttachments([]);
		setUploadedFileNames([]);
		setSelectedConversation({});
		localStorage.removeItem("selectedConversation");
		setSelectedConversation({
			session_id: `session-${Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15)}`,
		});
	};

	const handleDeleteChat = (chatId) => {
		//Show Message to user, telling them the chat was deleted
		triggerInfoErrorPopupMessage("Chat/Conversation Deleted", "success");
		//logic for handling the current loaded chat
		if (selectedConversation.session_id === chatId) {
			localStorage.removeItem(`kbSessionId-${selectedConversation.session_id}`);
			setSelectedConversation({});
			localStorage.removeItem("selectedConversation");
			setSelectedConversation({
				session_id: `session-${Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15)}`,
			});
			setMessages([]);
			setUploadedFileNames([]);
			setAttachments([]);
			setKBSessionId("");
		}
		//delete the chat
		clearConversationHistory(chatId);
		// remove conversation matching chatId from conversationList
		setConversationList(
			conversationList.filter(
				(conversation) => conversation.session_id !== chatId,
			),
		);
		localStorage.setItem(
			"load_conversation_list",
			JSON.stringify(
				conversationList.filter(
					(conversation) => conversation.session_id !== chatId,
				),
			),
		);
	};

	const handleMouseDown = (e) => {
		setIsDragging(true);
	};

	const handleMouseUp = () => {
		setIsDragging(false);
	};

	const handleMouseMove = (e) => {
		if (isDragging) {
			const newWidth = Math.max(
				200,
				Math.min(e.clientX, window.innerWidth - 200),
			);
			setSidebarWidth(newWidth);
			document.documentElement.style.setProperty(
				"--sidebar-width",
				`${newWidth}px`,
			);
		}
	};

	// biome-ignore lint/correctness/useExhaustiveDependencies: <explanation>
	useEffect(() => {
		if (isDragging) {
			document.addEventListener("mousemove", handleMouseMove);
			document.addEventListener("mouseup", handleMouseUp);
		} else {
			document.removeEventListener("mousemove", handleMouseMove);
			document.removeEventListener("mouseup", handleMouseUp);
		}
		return () => {
			document.removeEventListener("mousemove", handleMouseMove);
			document.removeEventListener("mouseup", handleMouseUp);
		};
	}, [isDragging]);
	// End of Code Supporting SideBar

	const reactThemePropviderTheme = createTheme({
		palette: {
			mode: reactThemeMode,
		},
	});

	return (
		<ThemeProvider theme={reactThemePropviderTheme}>
			<CssBaseline />
			<div className="app">
				<Header
					disabled={isDisabled || isLoading}
					selectedConversation={selectedConversation}
					kbSessionId={kbSessionId}
					setKBSessionId={setKBSessionId}
					handleOpenSettingsModal={handleOpenSettingsModal}
					signOut={localSignOut}
					selectedMode={selectedMode}
					handleModeChange={handleModeChange}
					showPopup={showPopup}
					setShowPopup={setShowPopup}
					popupMessage={popupMessage}
					popupType={popupType}
					totalInputTokens={totalInputTokens}
					totalOutputTokens={totalOutputTokens}
					pricePer1000InputTokens={pricePer1000InputTokens}
					pricePer1000OutputTokens={pricePer1000OutputTokens}
					monthlyInputTokens={monthlyInputTokens}
					monthlyOutputTokens={monthlyOutputTokens}
					bedrockAgents={bedrockAgents}
					bedrockKnowledgeBases={bedrockKnowledgeBases}
					models={models}
					imageModels={imageModels}
					videoModels={videoModels}
					importedModels={importedModels}
					promptFlows={promptFlows}
					selectedKbMode={selectedKbMode}
					onSelectedKbMode={onSelectedKbMode}
					triggerModelScan={triggerModelScan}
					isRefreshing={isRefreshing}
					isRefreshingMessage={isRefreshingMessage}
					user={user}
					allowlist={allowlist}
					modelsLoaded={modelsLoaded}
					chatbotTitle={chatbotTitle}
					isMobile={isMobile}
					expandedCategories={expandedCategories}
					setExpandedCategories={setExpandedCategories}
					region={region}
				/>
				<Box sx={{ display: "flex", height: "calc(100vh - 64px)" }}>
					<Box
						sx={{
							width: isMobile ? 0 : sidebarWidth,
							flexShrink: 0,
							transition: "width 0.3s",
							borderRight: "1px solid",
							borderColor: "divider",
							overflow: "hidden",
							overflowY: "auto",
							position: "relative",
						}}
					>
						<LeftSideBar
							handleNewChat={handleNewChat}
							handleDeleteChat={handleDeleteChat}
							conversationList={conversationList}
							handleSelectChat={handleSelectChat}
							conversationListLoading={conversationListLoading}
							selectedConversation={selectedConversation}
							isDisabled={isDisabled}
							reactThemeMode={reactThemeMode}
						/>
						<div className="resizer" onMouseDown={handleMouseDown} />
					</Box>
					<Box
						sx={{
							width: "4px",
							cursor: "ew-resize",
							backgroundColor: "divider",
						}}
						onMouseDown={handleMouseDown}
					/>
					<Box
						sx={{
							flexGrow: 1,
							display: "flex",
							width: `calc(100% - ${sidebarWidth}px)`,
							flexDirection: "column",
						}}
					>
						<div className="chat-history" ref={chatHistoryRef}>
							<ChatHistory
								user={user}
								messages={messages}
								selectedMode={selectedMode}
								setMessages={setMessages}
								selectedConversation={selectedConversation}
								loadConversationHistory={loadConversationHistory}
								loadConversationList={loadConversationList}
								onSend={onSend}
								requireConversationLoad={requireConversationLoad}
								setRequireConversationLoad={setRequireConversationLoad}
								reactThemeMode={reactThemeMode}
								websocketConnectionId={websocketConnectionId}
								conversationList={conversationList}
							/>
						</div>
						<MessageInput
							selectedConversation={selectedConversation}
							onSend={onSend}
							disabled={isDisabled || isLoading}
							setIsDisabled={setIsDisabled}
							selectedMode={selectedMode}
							selectedKbMode={selectedKbMode}
							sendMessage={sendMessage}
							getCurrentSession={getCurrentSession}
							attachments={attachments}
							setAttachments={setAttachments}
							setIsRefreshing={setIsRefreshing}
							setIsRefreshingMessage={setIsRefreshingMessage}
							ref={messageInputRef}
							uploadedFileNames={uploadedFileNames}
							setUploadedFileNames={setUploadedFileNames}
						/>
					</Box>
				</Box>
				{showPopup && (
					<Popup
						message={popupMessage}
						type={popupType}
						onClose={() => setShowPopup(false)}
						showPopup={showPopup}
						setShowPopup={setShowPopup}
					/>
				)}
				<Suspense fallback={<div>Loading...</div>}>
					<SettingsModal
						onClose={handleCloseSettingsModal}
						onSave={handleSaveSettings}
						showSettingsModal={showSettingsModal}
						setPricePer1000InputTokens={setPricePer1000InputTokens}
						pricePer1000InputTokens={pricePer1000InputTokens}
						setPricePer1000OutputTokens={setPricePer1000OutputTokens}
						pricePer1000OutputTokens={pricePer1000OutputTokens}
						user={user}
						websocketUrl={websocketUrl}
						getCurrentSession={getCurrentSession}
						systemPromptUserOrSystem={systemPromptUserOrSystem}
						setSystemPromptUserOrSystem={setSystemPromptUserOrSystem}
						setReloadPromptConfig={setReloadPromptConfig}
						stylePreset={stylePreset}
						setStylePreset={setStylePreset}
						heightWidth={heightWidth}
						setHeightWidth={setHeightWidth}
						handleModeChange={handleModeChange}
						selectedMode={selectedMode}
						setAllowList={setAllowList}
						chatbotTitle={chatbotTitle}
						setChatbotTitle={setChatbotTitle}
						selectedTitleGenerationMode={selectedTitleGenerationMode}
						setSelectedTitleGenerationMode={setSelectedTitleGenerationMode}
						selectedTitleGenerationTheme={selectedTitleGenerationTheme}
						setSelectedTitleGenerationTheme={setSelectedTitleGenerationTheme}
						models={models}
						setRegion={setRegion}
						reactThemeMode={reactThemeMode}
						setReactThemeMode={setReactThemeMode}
					/>
				</Suspense>
			</div>
		</ThemeProvider>
	);
});

function convertRoleToHuman(input) {
	// Convert single object to array if needed
	const jsonArray = Array.isArray(input) ? input : [input];

	return jsonArray.map((item) => {
		if (item.role === "user") {
			return {
				...item,
				role: "Human",
			};
		}
		if (item.role === "assistant") {
			return {
				...item,
				role: "Assistant",
			};
		}
		return item;
	});
}
function filter_active_models(models) {
	return models.filter((model) => model.is_active === true);
}

const AuthenticatedApp = withAuthenticator(App);

export default AuthenticatedApp;
