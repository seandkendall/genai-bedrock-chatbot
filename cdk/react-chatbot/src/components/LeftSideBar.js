import React from 'react';
import { Box, Typography, IconButton, List, ListItem, ListItemText, CircularProgress } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';

const LeftSideBar = ({ handleNewChat, handleDeleteChat, conversationList,conversationListLoading, selectedChatId, setSelectedChatId, setAppSessionId, setRequireConversationLoad,handleModeChange,getModeObjectFromModelID,kbSessionId, setKBSessionId }) => {

  const handleSelectChat = (sessionId,selectedModelId) => {
    console.log(`SDK: Selected chat session: ${sessionId}, model: ${selectedModelId}`);
    setRequireConversationLoad(true)
    setSelectedChatId(sessionId);
    setAppSessionId(sessionId);
    const selMode = getModeObjectFromModelID(selectedModelId);
    console.log(`SDK: Selected mode: ${selMode}`);
    console.log(selMode)
    //For KnowledgeBases, if a kbSessionID Exists for this AppSession, then load it
    if (selMode.category === "Bedrock KnowledgeBases") {
      if (localStorage.getItem(`kbSessionId-${sessionId}`)) {
        setKBSessionId(localStorage.getItem(`kbSessionId-${sessionId}`));
      }
    }
    if(selMode)
      handleModeChange(selMode)
  };
  

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', position: 'relative' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', p: 2 }}>
        <Typography variant="h6">Chats</Typography>
        <IconButton onClick={handleNewChat}>
          <AddIcon />
        </IconButton>
      </Box>
      <List className="left-sidebar" sx={{ flexGrow: 1, overflowY: 'auto' }}>
        {conversationList.map((conversation) => (
          <ListItem
            key={conversation.session_id}
            onClick={() => handleSelectChat(conversation.session_id,conversation.selected_model_id)}
            className={selectedChatId === conversation.session_id ? 'Mui-selected' : ''}
            secondaryAction={
              <IconButton
                edge="end"
                aria-label="delete"
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeleteChat(conversation.session_id);
                }}
              >
                <DeleteIcon />
              </IconButton>
            }
          >
            <ListItemText
              primary={conversation.title}
              secondary={new Date(conversation.last_modified_date).toLocaleString()}
            />
          </ListItem>
        ))}
      </List>
      {conversationListLoading && (
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 1,
          }}
        >
          <CircularProgress size={40} thickness={4} sx={{ color: 'white' }} />
          <Typography variant="body1" sx={{ color: 'white', mt: 2 }}>
            Loading chats...
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default LeftSideBar;