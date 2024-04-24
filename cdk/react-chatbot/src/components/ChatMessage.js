import React, { memo } from 'react';
import { Box, Typography, CircularProgress } from '@mui/material';
import ReactMarkdown from 'react-markdown';
import { okaidia } from 'react-syntax-highlighter/dist/esm/styles/prism';
import CodeBlock from './CodeBlock';
import MessageHeader from './MessageHeader';

const ChatMessage = memo(({ role, content, responseTime, isStreaming, timestamp, outputTokenCount, model }) => {
  const renderContent = () => (
    <ReactMarkdown
      components={{
        code({ node, inline, className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || '');
          const language = match ? match[1] : '';

          // Render code blocks with syntax highlighting
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
        // Add this new component for handling new-line characters
        p: (props) => <Typography component="p" variant="body1" whiteSpace="pre-wrap" {...props} />,
      }}
    >
      {formatContent(content, outputTokenCount)}
    </ReactMarkdown>
  );

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
        bgcolor: (role === 'Human' || role === 'user') ? 'grey.200' : 'background.paper',
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