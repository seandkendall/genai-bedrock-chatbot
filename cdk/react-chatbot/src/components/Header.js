import React, { useEffect, useState, useMemo } from 'react';
import useTimer from '../useTimer'
import { AppBar, Toolbar, CircularProgress, Typography, Box, IconButton, Menu, MenuItem, Select, Tooltip, InputLabel, FormControl } from '@mui/material';
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
  kbModels,
  imageModels,
  promptFlows,
  selectedKbMode,
  onSelectedKbMode,
  triggerModelScan,
  isRefreshing,
}) => {
  const [anchorEl, setAnchorEl] = React.useState(null);

  const [showInfoTooltip, setShowInfoTooltip] = useState(false);
  const { elapsedTime, startTimer, stopTimer, resetTimer } = useTimer();
  const isMobile = useMediaQuery('(max-width:600px)');

  // load selectedMode from local storage
  // biome-ignore lint/correctness/useExhaustiveDependencies: Dependencies not needed
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
  // biome-ignore lint/correctness/useExhaustiveDependencies: Dependencies not needed
  useEffect(() => {
    if (disabled) {
      startTimer();
    } else {
      stopTimer();
      resetTimer();
    }
  }, [disabled]);

  const truncateText = (text, maxLength) => {
    return text.length > maxLength ? `${text.substring(0, maxLength)}...` : text;
  };
  
  const renderSelectOptions = (options, maxLength) => {
    return options.flatMap(({ title, data }) =>
      data.length > 0 ? [
        <MenuItem key={`title-${title}`} value={title} disabled>{title}</MenuItem>,
        ...data.map((item) => (
          <MenuItem key={`${title}%${item.mode_selector}`} value={`${title}%${item.mode_selector}`}>
            {truncateText((() => {
              switch (title) {
                case 'Bedrock Models':
                  return `${item.providerName} ${item.modelName}`;
                case 'Bedrock Image Models':
                  return `${item.providerName} ${item.modelName}`;
                case 'Bedrock KnowledgeBases':
                  return item.name;
                case 'Bedrock Agents':
                  return `${item.agent_name} (${item.agentAliasName})`;
                case 'Bedrock Prompt Flows':
                  return item.name;
                default:
                  return 'Unknown';
              }
            })(), maxLength)}
          </MenuItem>
        ))
      ] : []
    );
  };



  const onSelectedModeChange = (event) => {
    if (event?.target?.value) {
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
        case 'RELOAD':
          triggerModelScan();
          selectedObject = null;
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
    {
      title: 'Bedrock Models',
      data: (models ? models : JSON.parse(localStorage.getItem('local-models')))
        .filter(item => item.is_active === true || !('is_active' in item))
    },
    {
      title: 'Bedrock Image Models',
      data: (imageModels ? imageModels : JSON.parse(localStorage.getItem('local-image-models')))
        .filter(item => item.is_active === true || !('is_active' in item))
    },
    {
      title: 'Bedrock KnowledgeBases',
      data: (bedrockKnowledgeBases ? bedrockKnowledgeBases : JSON.parse(localStorage.getItem('local-bedrock-knowledge-bases')))
        .filter(item => item.is_active === true || !('is_active' in item))
    },
    {
      title: 'Bedrock Agents',
      data: (bedrockAgents ? bedrockAgents : JSON.parse(localStorage.getItem('local-bedrock-agents')))
        .filter(item => item.is_active === true || !('is_active' in item))
    },
    {
      title: 'Bedrock Prompt Flows',
      data: (promptFlows ? promptFlows : JSON.parse(localStorage.getItem('local-prompt-flows')))
        .filter(item => item.is_active === true || !('is_active' in item))
    }
  ], [models, imageModels, bedrockKnowledgeBases, bedrockAgents, promptFlows]);

  const kbModelOptions = useMemo(() => [
    {
      title: 'Bedrock Models',
      data: (models ? models : JSON.parse(localStorage.getItem('local-models')))
        .filter(item =>
          kbModels.some(model => model.modelId === item.modelId) &&
          (item.is_active === true || !('is_active' in item))
        )
    },
  ], [models, kbModels]);



  return (
    <>
      <AppBar position="sticky">
        <Toolbar>
          <Typography variant={isMobile ? 'body1' : 'h6'} component="div" sx={{ flexGrow: 1, display: 'flex', alignItems: 'center' }}>
            {isMobile ? 'AWS' : 'AWS Bedrock KendallChat'}
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
                <InputLabel id="mode-select-label" sx={{ color: 'white' }}>{isMobile ? 'Model' : 'Bedrock Chatbot Model'}</InputLabel>
                <Select
                  id="mode-select"
                  labelId="mode-select-label"
                  value={selectedMode ? selectedMode.category + '%' + selectedMode.mode_selector : 'DEFAULT'}
                  onChange={onSelectedModeChange}
                  label={isMobile ? 'Model' : 'Bedrock Chatbot Model'}
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
                    <em>{isMobile ? 'Model' : 'Select a Model'}</em>
                  </MenuItem>
                  {renderSelectOptions(selectOptions, isMobile ? 20 : 50)}
                  <MenuItem value="RELOAD" >
                    <em>{isMobile ? 'Reload' : 'Reload Models (~60 seconds)'}</em>
                  </MenuItem>
                </Select>
              </FormControl>
              {selectedMode && selectedMode.knowledgeBaseId && (
                <FormControl sx={{ m: 1, minWidth: 120 }}>
                  <InputLabel id="kbmode-select-label" sx={{ color: 'white' }}>{isMobile ? 'KBModel' : 'KnowledgeBase Model'}</InputLabel>
                  <Select
                    id="kbmode-select"
                    labelId="kbmode-select-label"
                    value={selectedKbMode ? selectedKbMode.category + '%' + selectedKbMode.mode_selector : 'DEFAULT'}
                    onChange={onSelectedKbModeChange}
                    label={isMobile ? 'KBModel' : 'KnowledgeBase Model'}
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
                      <em>{isMobile ? 'Model' : 'Select a Model'}</em>
                    </MenuItem>
                    {renderSelectOptions(kbModelOptions, isMobile ? 20 : 50)}
                  </Select>
                </FormControl>
              )}

            </>

            <IconButton color="inherit" onClick={() => handleOpenSettingsModal()}>
              <FaCog />
            </IconButton>
            <IconButton color="inherit" onClick={onClearConversation} disabled={disabled || (!selectedMode) || (selectedMode.category === "Bedrock KnowledgeBases" && !selectedKbMode)}>
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
      {isRefreshing && (
        <Box
          sx={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 9999,
          }}
        >
          <CircularProgress size={60} thickness={4} sx={{ color: 'white' }} />
          <Typography variant="h6" sx={{ color: 'white', mt: 2 }}>
            Loading Models
          </Typography>
          <Typography variant="body1" sx={{ color: 'white', mt: 1 }}>
            Please wait, this could take a minute...
          </Typography>
        </Box>
      )}
      {showPopup && <Popup message={popupMessage} type={popupType} onClose={() => setShowPopup(false)} />}
    </>
  );
};

export default Header;