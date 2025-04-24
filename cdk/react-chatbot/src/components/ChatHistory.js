import React, { useEffect, useState, useRef, forwardRef, memo } from "react";
import ChatMessage from "./ChatMessage";
import { Box } from "@mui/material";

const ChatHistory = memo(
	forwardRef(
		(
			{
				user,
				messages,
				selectedMode,
				setMessages,
				selectedConversation,
				loadConversationHistory,
				loadConversationList,
				onSend,
				requireConversationLoad,
				setRequireConversationLoad,
				reactThemeMode,
				websocketConnectionId,
				conversationList,
				setIsRefreshingMessage,
				setIsRefreshing,
			},
			ref,
		) => {
			const lastMessageRef = useRef(null);
			const audioRef = useRef(null);
			const [resetTrimmedMessages, setResetTrimmedMessages] = useState(false);

			useEffect(() => {
				if (
					selectedMode?.outputModalities?.includes("SPEECH") &&
					messages.length > 0
				) {
					const lastMessage = messages[messages.length - 1];
					if (lastMessage.role === "assistant" && lastMessage.audioUrl) {
						if (audioRef.current) {
							audioRef.current.src = lastMessage.audioUrl;
							audioRef.current.play().catch((error) => {
								console.error("Error playing audio:", error);
							});
						}
					}
				}
			}, [messages, selectedMode]);

			// biome-ignore lint/correctness/useExhaustiveDependencies: user needed here
			useEffect(() => {
				if (
					requireConversationLoad &&
					websocketConnectionId !== null &&
					selectedConversation?.session_id
				) {
					// Find the most up-to-date conversation from the list
					const currentConversation = conversationList.find(
						(item) => item.session_id === selectedConversation.session_id,
					);

					const chatHistory = localStorage.getItem(
						`chatHistory-${selectedConversation.session_id}`,
					);
					const chatHistoryExists =
						chatHistory !== null &&
						chatHistory &&
						JSON.parse(chatHistory).length > 0;

					if (chatHistoryExists) {
						setIsRefreshingMessage("Loading Previous Conversation");
						setIsRefreshing(true);
						setMessages(JSON.parse(chatHistory));
						setIsRefreshing(false);

						const lastLoadedChatMessage = JSON.parse(chatHistory).slice(-1)[0];
						const lastMessageId =
							lastLoadedChatMessage?.raw_message?.message_id ||
							lastLoadedChatMessage?.message_id;

						if (
							currentConversation &&
							lastMessageId !== currentConversation.last_message_id
						) {
							loadConversationHistory(
								selectedConversation.session_id,
								true,
								lastMessageId,
							);
						}
					} else {
						loadConversationHistory(
							selectedConversation.session_id,
							false,
							null,
						);
					}

					loadConversationList();
					setRequireConversationLoad(false);
				}
			}, [
				requireConversationLoad,
				websocketConnectionId,
				selectedConversation?.session_id,
				conversationList,
				loadConversationHistory,
				loadConversationList,
				setMessages,
				setIsRefreshingMessage,
				setIsRefreshing,
				setRequireConversationLoad,
				user,
			]);

			// biome-ignore lint/correctness/useExhaustiveDependencies: user needed here
			useEffect(() => {
				setResetTrimmedMessages((prev) => !prev);
			}, [selectedConversation, user]);

			return (
				<Box
					ref={ref}
					className="chat-history"
					sx={{
						flex: 1,
						flexGrow: 1,
						paddingLeft: "calc(var(--sidebar-width) + 10px)",
						paddingRight: "10px",
						p: 2,
						overflowY: "auto",
						display: "flex",
						flexDirection: "column",
					}}
				>
					{messages?.map((message, index) => (
						<div
							key={`${message.timestamp || index}-${index}`}
							ref={index === messages.length - 1 ? lastMessageRef : null}
						>
							<ChatMessage
								message={message}
								onSend={onSend}
								isLastMessage={index === messages.length - 1}
								reactThemeMode={reactThemeMode}
								resetTrimmedMessages={resetTrimmedMessages}
								user={user} // Passing user to ChatMessage
							/>
						</div>
					))}
					<div ref={lastMessageRef} />
					{/* Add hidden audio element for speech playback with a caption track */}
					<audio ref={audioRef} style={{ display: "none" }}>
						<track kind="captions" src="" label="English" default />
					</audio>
				</Box>
			);
		},
	),
);

export default ChatHistory;
