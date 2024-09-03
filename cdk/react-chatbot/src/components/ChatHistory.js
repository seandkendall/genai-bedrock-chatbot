import React, { useEffect, useRef, forwardRef, memo } from 'react';
import ChatMessage from './ChatMessage';
import { Box } from '@mui/material';

const ChatHistory = memo(forwardRef(({ messages, selectedMode, setMessages }, ref) => {
  const lastMessageRef = useRef(null);

  useEffect(() => {
    const bedrockSessionId = localStorage.getItem('bedrockSessionId');
    const agentsSessionId = localStorage.getItem('agentsSessionId');

    const bedrockHistory = localStorage.getItem(`bedrockHistory-${bedrockSessionId}`);
    const agentsHistory = localStorage.getItem(`agentsHistory-${agentsSessionId}`);

    if (selectedMode === 'bedrock') {
      if (bedrockHistory) {
        setMessages(JSON.parse(bedrockHistory));
      }
    } else if (selectedMode === 'agents') {
      if (agentsHistory) {
        setMessages(JSON.parse(agentsHistory));
      }
    }
  }, [selectedMode, setMessages]);

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