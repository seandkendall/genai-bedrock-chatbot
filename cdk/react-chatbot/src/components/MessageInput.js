import React, { useState, useRef, useEffect } from 'react';
import { Box, TextField, IconButton, Tooltip } from '@mui/material';
import { FaPaperPlane } from 'react-icons/fa';

const MessageInput = ({ onSend, disabled }) => {
  const [message, setMessage] = useState('');
  const [tooltipOpen, setTooltipOpen] = useState(false);
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
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

  const handleMouseMove = (event) => {
    setMousePosition({ x: event.clientX, y: event.clientY });
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
      <Tooltip
        title="Generate an image by prefixing your message with 'Image:'. Example: 'Image: Dogs'"
        open={tooltipOpen}
        followCursor
        PopperProps={{
          anchorEl: {
            getBoundingClientRect: () => ({
              top: mousePosition.y,
              left: mousePosition.x,
              right: mousePosition.x,
              bottom: mousePosition.y,
              width: 0,
              height: 0,
            }),
          },
        }}
      >
        <TextField
          inputRef={inputRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          onMouseEnter={() => setTooltipOpen(true)}
          onMouseLeave={() => setTooltipOpen(false)}
          onMouseMove={handleMouseMove}
          placeholder="Type your message..."
          disabled={disabled}
          multiline
          fullWidth
          variant="outlined"
          sx={{ mr: 2 }}
        />
      </Tooltip>
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