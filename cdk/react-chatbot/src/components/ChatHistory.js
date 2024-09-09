import React, { useEffect, useRef, forwardRef, memo } from 'react';
import ChatMessage from './ChatMessage';
import { Box } from '@mui/material';

const ChatHistory = memo(forwardRef(({ messages, selectedMode, setMessages,selectedPromptFlow,knowledgebasesOrAgents }, ref) => {
  const lastMessageRef = useRef(null);

  useEffect(() => {
    const sessionId = localStorage.getItem(`${selectedMode}SessionId`);
    const chatHistory = localStorage.getItem(`chatHistory-${sessionId}${selectedMode === 'bedrock'? '':knowledgebasesOrAgents}${selectedPromptFlow?selectedPromptFlow.id:''}`);
    setMessages(JSON.parse(chatHistory));
  }, [selectedMode, setMessages,selectedPromptFlow,knowledgebasesOrAgents]);

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