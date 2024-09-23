import React, { useEffect, useRef, forwardRef, memo } from 'react';
import ChatMessage from './ChatMessage';
import { Box } from '@mui/material';

const ChatHistory = memo(forwardRef(({ user, messages, selectedMode, setMessages, appSessionid, setAppSessionId,loadConversationHistory }, ref) => {
  const lastMessageRef = useRef(null);

  useEffect(() => {
    if (selectedMode) {
      let sessionId = user.username;
      if (selectedMode.category === 'Bedrock Agents') {
        sessionId = sessionId + '-agents-'+selectedMode.agentAliasId;
      } else if (selectedMode.category === 'Bedrock KnowledgeBases') {
        sessionId = sessionId + '-kb-'+selectedMode.knowledgeBaseId;
      } else if (selectedMode.category === 'Bedrock Prompt Flow') {
        sessionId = sessionId + '-pflow-'+selectedMode.id;
      } else if (selectedMode.category === 'Bedrock Models') {
        sessionId = sessionId + '-model-'+selectedMode.modelId;
      } else if (selectedMode.category === 'Bedrock Image Models') {
        sessionId = sessionId + '-image-'+selectedMode.modelId;
      }
      setAppSessionId(sessionId)
      const chatHistory = localStorage.getItem(`chatHistory-${sessionId}`);
      setMessages(JSON.parse(chatHistory));
      loadConversationHistory(`chatHistory-${sessionId}`);
    }
  }, [selectedMode,user,appSessionid]);

  return (
    <Box sx={{ flex: 1, p: 2, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
      {messages && Array.isArray(messages) && messages.map((message, index) => (
        <div key={index} ref={lastMessageRef}>
          <ChatMessage
            {...message}
            imageAlt={message.imageAlt || ''}
            isImage={message.isImage || false}
            prompt={message.prompt || ''}
          />
        </div>
      ))}
    </Box>
  );
}));

export default ChatHistory;