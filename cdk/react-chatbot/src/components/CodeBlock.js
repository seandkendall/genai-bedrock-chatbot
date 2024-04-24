import React, { useState, memo } from 'react';
import SyntaxHighlighter from 'react-syntax-highlighter';
import { Box, IconButton, Tooltip, Chip } from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import { atomOneDark } from 'react-syntax-highlighter/dist/esm/styles/hljs';

const CodeBlock = memo(({ code, language }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Box sx={{ position: 'relative' }}>
      <SyntaxHighlighter
        language={language}
        style={atomOneDark}
        customStyle={{
          backgroundColor: '#1e1e1e',
          padding: '0.5rem 1rem',
          borderRadius: '0.375rem',
          whiteSpace: 'pre-wrap', // Add this line
        }}
        wrapLines={true}
        showLineNumbers={true}
      >
        {code}
      </SyntaxHighlighter>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          position: 'absolute',
          top: '0.5rem',
          right: '0.5rem',
        }}
      >
        <Chip
          label={language}
          size="small"
          sx={{
            bgcolor: 'rgba(255, 255, 255, 0.1)',
            color: '#858585',
            mr: 1,
          }}
        />
        <Tooltip title={copied ? 'Copied!' : 'Copy Code'} arrow>
          <IconButton
            sx={{
              color: '#fff',
              backgroundColor: 'rgba(255, 255, 255, 0.1)',
              '&:hover': {
                backgroundColor: 'rgba(255, 255, 255, 0.2)',
              },
            }}
            onClick={handleCopy}
            color={copied ? 'success' : 'default'}
          >
            {copied ? <CheckCircleOutlineIcon /> : <ContentCopyIcon />}
          </IconButton>
        </Tooltip>
      </Box>
    </Box>
  );
});

export default CodeBlock;