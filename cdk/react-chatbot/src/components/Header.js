import React, { useState } from 'react';
import { AppBar, Toolbar, Typography, Box, IconButton, Menu, MenuItem, Switch, Tooltip } from '@mui/material';
import { tooltipClasses } from '@mui/material/Tooltip';
import { styled } from '@mui/material/styles';
import { FaSignOutAlt, FaInfoCircle, FaCog, FaBroom } from 'react-icons/fa';
import Popup from './Popup';
import useMediaQuery from '@mui/material/useMediaQuery';

const NoMaxWidthTooltip = styled(({ className, ...props }) => (
  <Tooltip {...props} classes={{ popper: className }} />
))({
  [`& .${tooltipClasses.tooltip}`]: {
    maxWidth: 'none',
  },
});

const Header = ({
  bedrockSessionId,
  agentsSessionId,
  kbSessionId,
  signOut,
  onClearConversation,
  timerVisible,
  timerValue,
  selectedMode,
  onModeChange,
  showPopup,
  setShowPopup,
  popupMessage,
  popupType,
  disabled,
  totalInputTokens,
  totalOutputTokens,
  handleOpenSettingsModal,
  pricePer1000InputTokens,
  pricePer1000OutputTokens,
  monthlyInputTokens,
  monthlyOutputTokens,
  knowledgebasesOrAgents,
  selectedModel
}) => {
  const [anchorEl, setAnchorEl] = React.useState(null);
  const [showInfoTooltip, setShowInfoTooltip] = useState(false);
  const isMobile = useMediaQuery('(max-width:600px)');

  const handleMenuOpen = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const formatTimer = (value) => {
    return `${value} ms`;
  };

  const handleInfoTooltipOpen = () => {
    setShowInfoTooltip(true);
  };

  const handleInfoTooltipClose = () => {
    setShowInfoTooltip(false);
  };
  const calculateDailyCost = () => {
    const dailyCost = (totalOutputTokens * (pricePer1000OutputTokens/1000)) + (totalInputTokens * (pricePer1000InputTokens/1000));
    return dailyCost.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
  }
  const calculateMonthlyCost = () => {
    const dailyCost = (monthlyOutputTokens * (pricePer1000OutputTokens/1000)) + (monthlyInputTokens * (pricePer1000InputTokens/1000));
    return dailyCost.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
  }

  const getHeaderLabel = () => {
    if (knowledgebasesOrAgents === 'knowledgeBases') {
      return isMobile ? 'KB' : 'KnowledgeBases';
    } else if (knowledgebasesOrAgents === 'agents') {
      return isMobile ? 'AG' : 'Agents';
    } else {
      return isMobile ? 'BR' : 'Bedrock';
    }
  };

  return (
    <AppBar position="sticky">
      <Toolbar>
        <Typography variant={isMobile ? 'body1' : 'h6'} component="div" sx={{ flexGrow: 1, display: 'flex', alignItems: 'center' }}>
          {isMobile ? 'AWS' : 'AWS Bedrock Chat'}
          <NoMaxWidthTooltip
            title={
              <Box>
                <Typography>Solution Designed and Built by Sean Kendall</Typography>
                <Typography>Active Model: {selectedModel}</Typography>
                <Typography>Bedrock Session ID: {bedrockSessionId}</Typography>
                <Typography>Agents Session ID: {agentsSessionId}</Typography>
                {kbSessionId && <Typography>KnowledgeBase Session ID: {kbSessionId}</Typography>}
                <Typography>Total Input/Output Tokens (Bedrock only): {totalInputTokens}/{totalOutputTokens}</Typography>
                <Typography>Bedrock Cost (Today): { calculateDailyCost()} USD</Typography>
                {monthlyInputTokens > 0 && <Typography>Bedrock Cost (Current Month): { calculateMonthlyCost()} USD</Typography>}
              </Box>
            }
            open={showInfoTooltip}
            onOpen={handleInfoTooltipOpen}
            onClose={handleInfoTooltipClose}
            arrow
          >
            <IconButton color="inherit" sx={{ ml: 1 }}>
              <FaInfoCircle />
            </IconButton>
          </NoMaxWidthTooltip>
        </Typography>

        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          {!isMobile && timerVisible && <Typography variant="body2" mr={2}>{formatTimer(timerValue)}</Typography>}
          <Box sx={{ display: 'flex', alignItems: 'center', mr: 2 }}>
            <Typography variant="body2" mr={1}>{isMobile ? 'BR' : 'Bedrock'}</Typography>
            <Switch
              checked={selectedMode === 'agents'}
              onChange={() => onModeChange(selectedMode === 'bedrock' ? 'agents' : 'bedrock')}
              disabled={disabled}
              color="warning"
            />
            <Typography variant="body2" ml={1}>{getHeaderLabel()}</Typography>
          </Box>
          <IconButton color="inherit" onClick={handleOpenSettingsModal}>
            <FaCog />
          </IconButton>
          <IconButton color="inherit" onClick={onClearConversation} disabled={disabled}>
            <FaBroom />
          </IconButton>
          <IconButton color="inherit" onClick={handleMenuOpen} disabled={disabled}>
            <FaSignOutAlt />
          </IconButton>
          <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={handleMenuClose}
          >
            <MenuItem onClick={signOut}>Sign Out</MenuItem>
          </Menu>
        </Box>
      </Toolbar>
      {showPopup && <Popup message={popupMessage} type={popupType} onClose={() => setShowPopup(false)} />}
    </AppBar>
  );
};

export default Header;