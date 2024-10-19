import React, { memo } from 'react';
import { Box, Typography, CircularProgress, IconButton, Tooltip, Chip } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import ReactMarkdown from 'react-markdown';
import { okaidia } from 'react-syntax-highlighter/dist/esm/styles/prism';
import CodeBlock from './CodeBlock';
import MessageHeader from './MessageHeader';

const ChatMessage = memo(({ raw_message, onSend, isLastMessage, role, content, responseTime, isStreaming, timestamp, outputTokenCount, model, isImage, imageAlt, prompt, ...otherProps }) => {
  const hasError = raw_message && raw_message.error && raw_message.error.trim() !== '';
  let messageContent = '';
  let attachments = [];

  if (hasError) {
    messageContent = raw_message.error;
  } else if (Array.isArray(content)) {
    content.forEach(item => {
      if (item.text) {
        messageContent += item.text + ' ';
      }
      if (item.image) {
        const s3KeyName = reformatFilename(item.image.s3source.s3key)
        attachments.push({ type: 'image', s3Key: s3KeyName });
        
      }
      if (item.document) {
        const s3KeyName = reformatFilename(item.document.s3source.s3key)
        attachments.push({ type: 'document', s3Key: s3KeyName });
      }
    });
    messageContent = messageContent.trim();
  } else {
    messageContent = content;
  }

  const handleRefresh = () => {
    onSend(null, null, true);
  };

  const renderContent = () => {
    if (isImage) {
      return (
        <>
          <Typography>Generated Image of: {prompt}</Typography>
          <img
            src={messageContent}
            alt={imageAlt || 'Generated image'}
            style={{ maxWidth: '100%', height: 'auto' }}
          />
        </>
      );
    }

    return (
      <>
        <ReactMarkdown
          components={{
            code({ node, inline, className, children, ...props }) {
              const match = /language-(\w+)/.exec(className || '');
              const language = match ? match[1] : '';

              return !inline && language && language.trim() !== '' ? (
                <CodeBlock code={String(children).trim()} language={language} style={okaidia} />
              ) : (
                <code className={className}>{children}</code>
              );
            },
            li: (props) => (
              <Typography
                component="li"
                variant="body1"
                sx={{
                  lineHeight: 1,
                  '&::marker': {
                    fontSize: '1.2rem',
                    fontWeight: 'bold',
                  },
                }}
                {...props}
              />
            ),
            p: (props) => <Typography component="p" variant="body1" whiteSpace="pre-wrap" {...props} />,
          }}
        >
          {formatContent(messageContent, outputTokenCount)}
        </ReactMarkdown>
        {attachments.length > 0 && (
          <Box mt={2} display="flex" flexWrap="wrap" gap={1}>
            {attachments.map((attachment, index) => {
              return (
                <Chip
                  key={index}
                  label={attachment.s3Key}
                  color={attachment.type === 'image' ? 'primary' : 'success'}
                  size="small"
                />
              );
            })}
          </Box>
        )}
      </>
    );
  };

  return (
    <Box
      sx={{
        width: '99%',
        maxWidth: '99%',
        mb: 2,
        p: 2,
        borderRadius: 2,
        position: 'relative',
        alignSelf: (role === 'Human' || role === 'user') ? 'flex-end' : 'flex-start',
        bgcolor: hasError ? '#FFCCCB' : (role === 'Human' || role === 'user') ? 'grey.200' : 'background.paper',
        boxShadow: (role === 'Assistant' || role === 'assistant') ? '0 1px 2px rgba(0, 0, 0, 0.1)' : 'none',
        userSelect: 'text',
      }}
    >
      <Box display="flex" alignItems="center" justifyContent="space-between">
        <Box display="flex" alignItems="center">
          <MessageHeader role={role} timestamp={timestamp} model={model} />
          {(role === 'Assistant' || role === 'assistant') && (
            <>
              {isStreaming && (
                <Box ml={1}>
                  <CircularProgress size="1rem" color="inherit" />
                </Box>
              )}
              {responseTime && (
                <Typography variant="body2" ml={1} color="text.secondary">
                  (Response Time: {responseTime}ms)
                </Typography>
              )}
            </>
          )}
        </Box>
        {(hasError && isLastMessage) && (
          <Tooltip title="Send the previous message again" arrow>
            <IconButton
              onClick={handleRefresh}
              size="small"
              sx={{ position: 'absolute', top: 8, right: 8 }}
            >
              <RefreshIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
      </Box>
      <Box mt={1}>{renderContent()}</Box>
    </Box>
  );
});

export default ChatMessage;

function formatContent(content, outputTokenCount) {
  if (outputTokenCount && outputTokenCount >= 4096) {
    let contentslice = content.slice(-100).trim();
    return content + "\n\n---\n**This response was too large and may have been cut short. If you would like to see the rest of this response, ask me this:** \n\n\nI did not receive your full last response. please re-send me the remainder of the final response starting from the text: \n\n\"" + contentslice + "\"";
  }
  return content;
}

function reformatFilename(filename) {
  if (filename.includes('/'))
    filename = filename.split('/').pop();
  const parts = filename.split('-');
  if (parts.length > 1) {
    return parts.slice(1).join('-');
  }
  return filename;
}