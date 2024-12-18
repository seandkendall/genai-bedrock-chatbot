import React, { useEffect, useRef, forwardRef, memo } from 'react';
import ChatMessage from './ChatMessage';
import { Box } from '@mui/material';

const ChatHistory = memo(forwardRef(({ user, messages, selectedMode, setMessages, appSessionid, loadConversationHistory,loadConversationList, onSend,requireConversationLoad,setRequireConversationLoad,setAppSessionId,selectedChatId,reactThemeMode,websocketConnectionId }, ref) => {
  const lastMessageRef = useRef(null);

  useEffect(() => {
      if (requireConversationLoad && websocketConnectionId !== null) {
        if (appSessionid && appSessionid !== '') {
          const chatHistory = localStorage.getItem(`chatHistory-${appSessionid}`);
          setMessages(chatHistory ? JSON.parse(chatHistory) : []);
          loadConversationHistory(appSessionid);
        }else{
          setAppSessionId(
            `session-${Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15)}`,
          );
        }
        if (requireConversationLoad){
          loadConversationList()
          setRequireConversationLoad(false);
        }
      }
  }, [selectedMode, user, appSessionid,websocketConnectionId]);
  
  useEffect(() => {
    lastMessageRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <Box ref={ref} className="chat-history" sx={{ flex: 1, flexGrow: 1, paddingLeft: 'calc(var(--sidebar-width) + 10px)', paddingRight: '10px', p: 2, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
      {messages?.map((message, index) => (
        <div key={message.id || index} >
          <ChatMessage
            {...message}
            imageAlt={message.imageAlt || ''}
            isImage={message.isImage || false}
            isVideo={message.isVideo || false}
            prompt={message.prompt || ''}
            onSend={onSend}
            isLastMessage={index === messages.length - 1}
            reactThemeMode={reactThemeMode}
          />
        </div>
      ))}
      <div ref={lastMessageRef} />
    </Box>
  );

}));

export default ChatHistory;