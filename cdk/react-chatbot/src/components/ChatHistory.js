import React, { useEffect, useRef, forwardRef, memo } from 'react';
import ChatMessage from './ChatMessage';
import { Box } from '@mui/material';

const ChatHistory = memo(forwardRef(({ user, messages, selectedMode, setMessages, appSessionid, setAppSessionId, loadConversationHistory, onSend }, ref) => {
  const lastMessageRef = useRef(null);
  const loadedSessionId = useRef(null);

  useEffect(() => {
    if (selectedMode) {
      let sessionId = user.username;
      if (selectedMode.category === 'Bedrock Agents') {
        sessionId = `${sessionId}-agents-${selectedMode.agentAliasId}`;
      } else if (selectedMode.category === 'Bedrock KnowledgeBases') {
        sessionId = `${sessionId}-kb-${selectedMode.knowledgeBaseId}`;
      } else if (selectedMode.category === 'Bedrock Prompt Flow') {
        sessionId = `${sessionId}-pflow-${selectedMode.id}`;
      } else if (selectedMode.category === 'Bedrock Models') {
        sessionId = `${sessionId}-model-${selectedMode.modelId}`;
      } else if (selectedMode.category === 'Bedrock Image Models') {
        sessionId = `${sessionId}-image-${selectedMode.modelId}`;
      }
      if (sessionId !== appSessionid)
        setAppSessionId(sessionId);

      // Check if sessionId is different from loadedSessionId
      if (sessionId !== loadedSessionId.current) {
        console.log(`Loading chat history for session: ${sessionId}`);
        const chatHistory = localStorage.getItem(`chatHistory-${sessionId}`);
        setMessages(chatHistory ? JSON.parse(chatHistory) : []);
        // Update loadedSessionId with the new sessionId
        loadedSessionId.current = sessionId;
        loadConversationHistory(sessionId);
      }
    }
  }, [selectedMode, user, appSessionid]);

  return (
    <Box sx={{ flex: 1, p: 2, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
      {messages?.map((message, index) => (
        <div key={message.id || index} ref={lastMessageRef}>
          <ChatMessage
            {...message}
            imageAlt={message.imageAlt || ''}
            isImage={message.isImage || false}
            prompt={message.prompt || ''}
            onSend={onSend}
            isLastMessage={index === messages.length - 1}
          />
        </div>
      ))}
    </Box>
  );

}));

export default ChatHistory;