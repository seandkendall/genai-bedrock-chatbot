import React, { useEffect, useRef, forwardRef, memo } from 'react';
import ChatMessage from './ChatMessage';
import { Box } from '@mui/material';

const ChatHistory = memo(forwardRef(({ user, messages, selectedMode, setMessages, appSessionid, loadConversationHistory,loadConversationList, onSend,requireConversationLoad,setRequireConversationLoad }, ref) => {
  const lastMessageRef = useRef(null);

  useEffect(() => {
      if (requireConversationLoad) {
        // if appSessionid is not null and not empty
        if (appSessionid && appSessionid !== '') {
          console.log(`Loading chat history for session: ${appSessionid}`);
          const chatHistory = localStorage.getItem(`chatHistory-${appSessionid}`);
          setMessages(chatHistory ? JSON.parse(chatHistory) : []);
          loadConversationHistory(appSessionid);
        }else{
          loadConversationList()
        }
        setRequireConversationLoad(false);
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