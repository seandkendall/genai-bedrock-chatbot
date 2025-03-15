/* eslint-disable react-hooks/exhaustive-deps */
import React, { useEffect, useRef, forwardRef, memo } from "react";
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

			// biome-ignore lint/correctness/useExhaustiveDependencies: <explanation>
			useEffect(() => {
				if (requireConversationLoad && websocketConnectionId !== null) {
					if (selectedConversation?.session_id) {
						// Reload conversation from conversation list (for the most up to date attributes)
						selectedConversation = conversationList.find(
							(item) => item.session_id === selectedConversation.session_id,
						);

						const chatHistory = localStorage.getItem(
							`chatHistory-${selectedConversation?.session_id}`,
						);
						const chatHistoryExists =
							chatHistory !== null &&
							chatHistory &&
							JSON.parse(chatHistory).length > 0;
						// get last element of JSON.parse(chatHistory)
						let lastLoadedChatMessage = null;
						if (chatHistoryExists) {
							//SDK TODO  does this work?
							setIsRefreshingMessage("Loading Previous Conversation");
							setIsRefreshing(true);
							setMessages(chatHistory ? JSON.parse(chatHistory) : []);
							setIsRefreshing(false);
							//SDK TODO  does this wrk?
							// console.log("SDK chatHistory:");
							// console.log(JSON.parse(chatHistory));
							// console.log("SDK chatHistory DONE");
							lastLoadedChatMessage = JSON.parse(chatHistory).slice(-1)[0];
							console.log("lastLoadedChatMessage:")
							console.log(lastLoadedChatMessage)
							if (lastLoadedChatMessage?.raw_message?.message_id) {
								lastLoadedChatMessage.message_id =
									lastLoadedChatMessage?.raw_message?.message_id;
							}
							// console.log("SDK lastLoadedChatMessage:");
							// console.log(lastLoadedChatMessage);
							// console.log("SDK lastLoadedChatMessage DONE");
							// console.log(
							// 	`SDK ChatHistory.js (chatHistoryExists) - lastLoadedChatMessage.message_id: ${lastLoadedChatMessage.message_id}  selectedConversation.last_message_id: ${selectedConversation.last_message_id}`,
							// );
							console.log(`lastLoadedChatMessage.message_id: ${lastLoadedChatMessage.message_id} (${lastLoadedChatMessage?.message_id})` )
							if (
								lastLoadedChatMessage.message_id !==
								selectedConversation.last_message_id
							) {
								console.log("Loading Chat History");
								loadConversationHistory(
									selectedConversation?.session_id,
									chatHistoryExists,
									lastLoadedChatMessage?.message_id,
								);
							} else {
								console.log("Chat History already loaded");
							}
						} else {
							console.log(
								`SDK ChatHistory.js (NOT chatHistoryExists) - lastLoadedChatMessage?.message_id: ${lastLoadedChatMessage?.message_id}`,
							);
							console.log("SDK990: Loading Chat History for selectedConversation",selectedConversation);
							loadConversationHistory(
								selectedConversation?.session_id,
								chatHistoryExists,
								lastLoadedChatMessage?.message_id,
							);
						}
					}
					// console.log(
					// 	"SDK ChatHistory.js  - Loading Conversation List {loadConversationList()} ",
					// );
					loadConversationList();
					setRequireConversationLoad(false);
				}
			}, [
				selectedMode,
				user,
				selectedConversation?.session_id,
				websocketConnectionId,
			]);

			// biome-ignore lint/correctness/useExhaustiveDependencies: <explanation>
			useEffect(() => {
				lastMessageRef.current?.scrollIntoView({ behavior: "smooth" });
			}, [messages]);

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
						<div key={message.id || index}>
							<ChatMessage
								message={message}
								onSend={onSend}
								isLastMessage={index === messages.length - 1}
								reactThemeMode={reactThemeMode}
							/>
						</div>
					))}
					<div ref={lastMessageRef} />
				</Box>
			);
		},
	),
);

export default ChatHistory;
