import React, { useState, useRef, useEffect } from 'react';
import { Box, TextField, IconButton } from '@mui/material';
import { FaPaperPlane } from 'react-icons/fa';

const MessageInput = ({ onSend, disabled, selectedMode, selectedKbMode }) => {
  const [message, setMessage] = useState('');
  const inputRef = useRef(null);

  useEffect(() => {
    if (!disabled && inputRef.current) {
      inputRef.current.focus();
    }
  }, [disabled]);

  const handleSend = () => {
    if (message.trim()) {
      onSend(message.trim());
      setMessage('');
    } else {
      console.log('no content');
      setMessage('');
    }
  };
  const getPlaceholderText = () => {
    if (!selectedMode || !selectedMode.category) {
      return "Select a Model, Agent, KnowledgeBase or PromptFlow in the Header";
    }
    return (selectedMode && selectedMode.category && selectedMode.category === 'Bedrock KnowledgeBases' && !selectedKbMode) ? "Select a Model for your KnowledgeBase in the Header" : "Type your message..."
  }
  const isDisabled = () => {
    return disabled || !selectedMode || (selectedMode && selectedMode.category && selectedMode.category === 'Bedrock KnowledgeBases' && !selectedKbMode)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      handleSend();
      e.preventDefault();
    } else if (e.key === 'Tab') {
      e.preventDefault();
      const { selectionStart, selectionEnd } = e.target;
      const newMessage = message.substring(0, selectionStart) + '\t' + message.substring(selectionEnd);
      setMessage(newMessage);
      setTimeout(() => {
        e.target.selectionStart = e.target.selectionEnd = selectionStart + 1;
      }, 0);
    }
  };


  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        p: 2,
        bgcolor: 'background.paper',
        position: 'sticky',
        bottom: 0,
        boxShadow: '0 -2px 4px rgba(0, 0, 0, 0.1)',
      }}
    >
      <TextField
        inputRef={inputRef}
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={getPlaceholderText()}
        disabled={isDisabled()}
        multiline
        fullWidth
        variant="outlined"
        inputProps={
          selectedMode && selectedMode.category && selectedMode.category === 'Bedrock Image Models'
            ? { maxLength: 512 }
            : {}
        }
        sx={{ mr: 2 }}
      />
      <IconButton
        disabled={isDisabled()}
        color="primary"
        onClick={handleSend}
        aria-label="Send message"
      >
        <FaPaperPlane />
      </IconButton>
    </Box>
  );
};

export default MessageInput;