import React, { useEffect, useState, useMemo } from 'react';
import useTimer from '../useTimer'
import { AppBar, Toolbar, Typography, Box, IconButton, Menu, MenuItem, Select, Tooltip, InputLabel, FormControl } from '@mui/material';
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
  disabled,
  appSessionid,
  kbSessionId,
  setKBSessionId,
  handleOpenSettingsModal,
  signOut,
  onClearConversation,
  selectedMode,
  onModeChange,
  showPopup,
  setShowPopup,
  popupMessage,
  popupType,
  totalInputTokens,
  totalOutputTokens,
  pricePer1000InputTokens,
  pricePer1000OutputTokens,
  monthlyInputTokens,
  monthlyOutputTokens,
  bedrockAgents,
  bedrockKnowledgeBases,
  models,
  imageModels,
  promptFlows,
  selectedKbMode,
  onSelectedKbMode
}) => {
  const [anchorEl, setAnchorEl] = React.useState(null);

  const [showInfoTooltip, setShowInfoTooltip] = useState(false);
  const { elapsedTime, startTimer, stopTimer, resetTimer } = useTimer();
  const isMobile = useMediaQuery('(max-width:600px)');

  // load selectedMode from local storage
  useEffect(() => {
    if (selectedMode === null) {
      let savedOption;
      try {
        // Attempt to parse the JSON string from localStorage
        savedOption = JSON.parse(localStorage.getItem('selectedMode'));
      } catch (error) {
        localStorage.removeItem('selectedMode')
      }
      if (savedOption) {
        onModeChange(savedOption);
      }
    }
    if (selectedKbMode === null) {
      let savedKbOption;
      try {
        // Attempt to parse the JSON string from 
        savedKbOption = JSON.parse(localStorage.getItem('selectedKbMode'));
      } catch (error) {
        localStorage.removeItem('selectedKbMode')
      }
      if (savedKbOption) {
        onSelectedKbMode(savedKbOption)
      }
    }
  }, []);

  //start and stop header timer
  useEffect(() => {
    if (disabled) {
      startTimer();
    } else {
      stopTimer();
      resetTimer();
    }
  }, [disabled]);

  const onSelectedModeChange = (event) => {
    if (event && event.target && event.target.value) {
      const [category, modeSelector] = event.target.value.split('%');
      let selectedObject = null;
      switch (category) {
        case 'Bedrock Models':
          selectedObject = models.find((item) => item.mode_selector === modeSelector);
          selectedObject.category = category;
          break;
        case 'Bedrock Image Models':
          selectedObject = imageModels.find((item) => item.mode_selector === modeSelector);
          selectedObject.category = category;
          break;
        case 'Bedrock KnowledgeBases':
          selectedObject = bedrockKnowledgeBases.find((item) => item.mode_selector === modeSelector);
          selectedObject.category = category;
          break;
        case 'Bedrock Agents':
          selectedObject = bedrockAgents.find((item) => item.mode_selector === modeSelector);
          selectedObject.category = category;
          break;
        case 'Bedrock Prompt Flows':
          selectedObject = promptFlows.find((item) => item.mode_selector === modeSelector);
          selectedObject.category = category;
          break;
        default:
          break;
      }
      if (selectedObject) {
        onModeChange(selectedObject);
        localStorage.setItem('selectedMode', JSON.stringify(selectedObject));
      }
    }
  };

  const onSelectedKbModeChange = (event) => {
    if (event && event.target && event.target.value) {
      const [category, modeSelector] = event.target.value.split('%');
      let selectedObject = null;
      switch (category) {
        case 'Bedrock Models':
          selectedObject = models.find((item) => item.mode_selector === modeSelector);
          selectedObject.category = category;
          break;
        default:
          break;
      }
      if (selectedObject) {
        onSelectedKbMode(selectedObject);
        localStorage.setItem('selectedKbMode', JSON.stringify(selectedObject));
        setKBSessionId('')
        localStorage.removeItem('kbSessionId');

      }
    }
  };

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
    const dailyCost = (totalOutputTokens * (pricePer1000OutputTokens / 1000)) + (totalInputTokens * (pricePer1000InputTokens / 1000));
    return dailyCost.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
  }
  const calculateMonthlyCost = () => {
    const dailyCost = (monthlyOutputTokens * (pricePer1000OutputTokens / 1000)) + (monthlyInputTokens * (pricePer1000InputTokens / 1000));
    return dailyCost.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
  }

  const getHeaderLabel = () => {
    if (selectedMode) {
      switch (selectedMode.category) {
        case 'Bedrock Models':
          return selectedMode.modelName;
        case 'Bedrock Image Models':
          return selectedMode.modelName;
        case 'Bedrock KnowledgeBases':
          return selectedMode.knowledgeBaseId;
        case 'Bedrock Agents':
          return selectedMode.agentAliasId;
        case 'Bedrock Prompt Flow':
          return selectedMode.id;
        default:
          return isMobile ? 'BR' : 'Bedrock';
      }
    }
    return '';
  };

  const selectOptions = useMemo(() => [
    { title: 'Bedrock Models', data: models },
    { title: 'Bedrock Image Models', data: imageModels },
    { title: 'Bedrock KnowledgeBases', data: bedrockKnowledgeBases },
    { title: 'Bedrock Agents', data: bedrockAgents },
    { title: 'Bedrock Prompt Flows', data: promptFlows }
  ], [models, imageModels, bedrockKnowledgeBases, bedrockAgents, promptFlows]);
  const kbModelOptions = useMemo(() => [
    { title: 'Bedrock Models', data: models },
  ], [models]);

  return (
    <AppBar position="sticky">
      <Toolbar>
        <Typography variant={isMobile ? 'body1' : 'h6'} component="div" sx={{ flexGrow: 1, display: 'flex', alignItems: 'center' }}>
          {isMobile ? 'AWS' : 'AWS Bedrock Chat'}
          <NoMaxWidthTooltip
            title={
              <Box>
                <Typography>Solution Designed and Built by Sean Kendall</Typography>
                <Typography>Active Model/Mode: {getHeaderLabel()}</Typography>
                <Typography>App Session ID: {appSessionid}</Typography>
                {kbSessionId && <Typography>KnowledgeBase Session ID: {kbSessionId}</Typography>}
                <Typography>Total Input/Output Tokens (Bedrock only): {totalInputTokens}/{totalOutputTokens}</Typography>
                <Typography>Bedrock Cost (Today): {calculateDailyCost()} USD</Typography>
                {monthlyInputTokens > 0 && <Typography>Bedrock Cost (Current Month): {calculateMonthlyCost()} USD</Typography>}
                <Typography></Typography>
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
          {!isMobile && disabled && <Typography variant="body2" mr={2}>{formatTimer(elapsedTime)}</Typography>}
          <>
            <FormControl sx={{ m: 1, minWidth: 120 }}>
              <InputLabel id="mode-select-label" sx={{ color: 'white' }}>Bedrock Chatbot Model</InputLabel>
              <Select
                id="mode-select"
                labelId="mode-select-label"
                value={selectedMode ? selectedMode.category + '%' + selectedMode.mode_selector : 'DEFAULT'}
                onChange={onSelectedModeChange}
                label="Bedrock Chatbot Model"
                sx={{
                  '& .MuiOutlinedInput-notchedOutline': {
                    borderColor: 'white',
                  },
                  '& .MuiSvgIcon-root': {
                    color: 'white',
                  },
                  color: 'white',
                }}
              >
                <MenuItem value="DEFAULT" >
                  Select a Model
                </MenuItem>
                {selectOptions.flatMap(({ title, data }) =>
                  data.length > 0 ? [
                    <MenuItem key={`title-${title}`} value={title} disabled>
                      {title}
                    </MenuItem>,
                    ...data.map((item) => (
                      <MenuItem value={`${title}%${item.mode_selector}`} >
                        {(() => {
                          switch (title) {
                            case 'Bedrock Models':
                              return item.modelName;
                            case 'Bedrock Image Models':
                              return item.modelName;
                            case 'Bedrock KnowledgeBases':
                              return item.name;
                            case 'Bedrock Agents':
                              return item.agentAliasName;
                            case 'Bedrock Prompt Flows':
                              return item.name;
                            default:
                              return 'Unknown';
                          }
                        })()}
                      </MenuItem>
                    ))
                  ] : [])}
              </Select>
            </FormControl>
            {selectedMode && selectedMode.knowledgeBaseId && (
              <FormControl sx={{ m: 1, minWidth: 120 }}>
                <InputLabel id="kbmode-select-label" sx={{ color: 'white' }}>KnowledgeBase Model</InputLabel>
                <Select
                  id="kbmode-select"
                  labelId="kbmode-select-label"
                  value={selectedKbMode ? selectedKbMode.category + '%' + selectedKbMode.mode_selector : 'DEFAULT'}
                  onChange={onSelectedKbModeChange}
                  label="KnowledgeBase Model"
                  sx={{
                    '& .MuiOutlinedInput-notchedOutline': {
                      borderColor: 'white',
                    },
                    '& .MuiSvgIcon-root': {
                      color: 'white',
                    },
                    color: 'white',
                  }}
                >
                  <MenuItem value="DEFAULT" >
                    Select a Model
                  </MenuItem>
                  {kbModelOptions.flatMap(({ title, data }) =>
                    data.length > 0 ? [
                      ...data.map((item) => (
                        <MenuItem value={`${title}%${item.mode_selector}`} >
                          {(() => {
                            switch (title) {
                              case 'Bedrock Models':
                                return item.modelName;
                              default:
                                return 'Unknown';
                            }
                          })()}
                        </MenuItem>
                      ))
                    ] : [])}
                </Select>
              </FormControl>
            )}

          </>

          <IconButton color="inherit" onClick={() => handleOpenSettingsModal()}>
            <FaCog />
          </IconButton>
          <IconButton color="inherit" onClick={onClearConversation} disabled={disabled || (!selectedMode) || (selectedMode.category === "Bedrock KnowledgeBases") && !selectedKbMode}>
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