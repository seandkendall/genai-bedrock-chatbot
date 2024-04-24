import React, { useState } from 'react';
import { Typography, Tooltip } from '@mui/material';

const MessageHeader = ({ role, timestamp, model }) => {
  const [showTooltip, setShowTooltip] = useState(false);

  const handleMouseEnter = () => {
    setShowTooltip(true);
  };

  const handleMouseLeave = () => {
    setShowTooltip(false);
  };

  const formatTimestamp = (timestamp, model) => {
    const date = new Date(timestamp);
    if (model)
      return date.toLocaleString()+' ('+model+')';
    return date.toLocaleString();
  };

  const formatRole = (role) => {
    if(role === 'user') {
      return 'Human';
    }else if(role === 'assistant') {
        return 'Assistant';
    }
    return role;
  };

  return (
    <Tooltip
      open={showTooltip}
      title={formatTimestamp(timestamp,model)}
      arrow
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <Typography variant="subtitle2" fontWeight="bold">
        {formatRole(role)}
      </Typography>
    </Tooltip>
  );
};

export default MessageHeader;