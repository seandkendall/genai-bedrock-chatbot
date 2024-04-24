import React, { useState, useRef, useEffect } from 'react';
import { Box, TextField, IconButton } from '@mui/material';
import { FaPaperPlane } from 'react-icons/fa';

const MessageInput = ({ onSend, disabled }) => {
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

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      handleSend();
      e.preventDefault();
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
        placeholder="Type your message..."
        disabled={disabled}
        multiline
        fullWidth
        variant="outlined"
        sx={{ mr: 2 }}
      />
      <IconButton
        disabled={disabled}
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