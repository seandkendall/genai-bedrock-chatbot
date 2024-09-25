import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Tooltip, Modal, Box, Typography, TextField, Button, Link, Switch, FormControl, IconButton, InputLabel, Select, MenuItem } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { FaInfoCircle } from 'react-icons/fa';
import useWebSocket from 'react-use-websocket';

const SettingsModal = ({
    onClose,
    onSave,
    showSettingsModal,
    setPricePer1000InputTokens,
    pricePer1000InputTokens,
    setPricePer1000OutputTokens,
    pricePer1000OutputTokens,
    user,
    websocketUrl,
    getCurrentSession,
    systemPromptUserOrSystem,
    setSystemPromptUserOrSystem,
    setReloadPromptConfig,
    stylePreset,
    setStylePreset,
    heightWidth,
    setHeightWidth,
    onModeChange,
    selectedMode
}) => {
    const theme = useTheme();
    const [error, setError] = useState('');
    const [showInfoTooltip, setShowInfoTooltip] = useState(false);
    const [configLoaded, setConfigLoaded] = useState(false);

    const [localState, setLocalState] = useState({
        pricePer1000InputTokens,
        pricePer1000OutputTokens,
        selectedMode,
        userSystemPrompt: '',
        systemSystemPrompt: '',
        systemPromptType: systemPromptUserOrSystem,
        stylePreset: localStorage.getItem('stylePreset') || 'photographic',
        heightWidth: localStorage.getItem('heightWidth') || '1024x1024',
    });
    const updateLocalState = useCallback((key, value) => {
        setLocalState(prevState => {
            if (key.includes('.')) {
                const [parentKey, childKey] = key.split('.');
                return {
                    ...prevState,
                    [parentKey]: {
                        ...prevState[parentKey],
                        [childKey]: value
                    }
                };
            }
            return {
                ...prevState,
                [key]: value
            };
        });
    }, []);

    const stylePresets = [
        '3d-model', 'analog-film', 'anime', 'cinematic', 'comic-book', 'digital-art',
        'enhance', 'fantasy-art', 'isometric', 'line-art', 'low-poly', 'modeling-compound',
        'neon-punk', 'origami', 'photographic', 'pixel-art', 'tile-texture'
    ];

    const stabilityDiffusionSizes = [
        '1024x1024', '1152x896', '1216x832', '1344x768', '1536x640',
        '640x1536', '768x1344', '832x1216', '896x1152'
    ];

    const titanImageSizes = [
        '1024x1024', '768x768', '512x512', '768x1152', '384x576', '1152x768', '576x384',
        '768x1280', '384x640', '1280x768', '640x384', '896x1152', '448x576', '1152x896',
        '576x448', '768x1408', '384x704', '1408x768', '704x384', '640x1408', '320x704',
        '1408x640', '704x320', '1152x640', '1173x640'
    ];

    const handleStylePresetChange = useCallback((event) => {
        const newStylePreset = event.target.value;
        setLocalState(prevState => ({
            ...prevState,
            stylePreset: newStylePreset,
        }));
        localStorage.setItem('stylePreset', newStylePreset);
    }, []);

    const handleHeightWidthChange = useCallback((event) => {
        const newHeightWidth = event.target.value;
        setLocalState(prevState => ({
            ...prevState,
            heightWidth: newHeightWidth,
        }));
        localStorage.setItem('heightWidth', newHeightWidth);
    }, []);

    const formatSizeLabel = useCallback((size) => {
        const [height, width] = size.split('x');
        return `${height}(H) x ${width}(W)`;
    }, []);

    const handleSystemPromptChange = useCallback((event) => {
        const { name, value } = event.target;
        setLocalState(prevState => ({
            ...prevState,
            [name]: value,
        }));
    }, []);

    const handleSystemPromptTypeChange = useCallback((event) => {
        const value = event.target.checked ? 'user' : 'system';
        updateLocalState('systemPromptType', value);
        setSystemPromptUserOrSystem(value);
        localStorage.setItem('systemPromptUserOrSystem', value);
    }, [setSystemPromptUserOrSystem, updateLocalState]);

    const { sendMessage, lastMessage } = useWebSocket(websocketUrl, {
        shouldReconnect: (closeEvent) => true,
        reconnectInterval: 3000,
    });

    const loadConfig = useCallback(async (configType) => {
        try {
            const { accessToken, idToken } = await getCurrentSession();
            const data = {
                action: 'config',
                subaction: 'load',
                config_type: configType,
                user: configType === 'user' ? user.username : 'system',
                idToken: idToken + '',
                accessToken: accessToken + '',
            };
            sendMessage(JSON.stringify(data));
        } catch (error) {
            console.error('Error loading configuration:', error);
            setError('Failed to load configuration. Please try again.');
        }
    }, [getCurrentSession, sendMessage, user.username]);

    useEffect(() => {
        if (!stylePreset) {
            const defaultStylePreset = localStorage.getItem('stylePreset') || 'photographic';
            setLocalState(prevState => ({
                ...prevState,
                stylePreset: defaultStylePreset,
            }));
            setStylePreset(defaultStylePreset);
        }
        if (!heightWidth) {
            const defaultHeightWidth = localStorage.getItem('heightWidth') || '1024x1024';
            updateLocalState('defaultHeightWidth', defaultHeightWidth);
            setHeightWidth(defaultHeightWidth);
        }
    }, [heightWidth, stylePreset, updateLocalState, setHeightWidth, setStylePreset,]);

    useEffect(() => {
        if (!configLoaded) {
            loadConfig('system');
            loadConfig('user');
            setConfigLoaded(true);
        }
    }, [configLoaded, loadConfig, updateLocalState]);

    useEffect(() => {
        setReloadPromptConfig(true);
    }, [localState.systemPrompt, localState.systemPromptType, setReloadPromptConfig]);

    const updateSystemPrompt = useCallback((configType, newPrompt) => {
        updateLocalState('systemPrompt', prevState => ({
            ...prevState,
            [configType]: newPrompt,
        }));
    }, [updateLocalState]);

    const usePrevious = (value, initialValue) => {
        const ref = useRef(initialValue);
        useEffect(() => {
            ref.current = value;
        });
        return ref.current;
    };

    const prevLastMessage = usePrevious(lastMessage, null);

    useEffect(() => {
        if (lastMessage !== null && lastMessage !== prevLastMessage) {
            try {
                const response = JSON.parse(lastMessage.data);
                if (response) {
                    if (response.config_type === 'system') {
                        updateLocalState('pricePer1000InputTokens', response.pricePer1000InputTokens || pricePer1000InputTokens);
                        updateLocalState('pricePer1000OutputTokens', response.pricePer1000OutputTokens || pricePer1000OutputTokens);
                        updateLocalState('pricePer1000OutputTokens', response.pricePer1000OutputTokens || pricePer1000OutputTokens);
                        updateLocalState('systemSystemPrompt', response.systemPrompt || '');
                        updateSystemPrompt('system', response.systemPrompt ?? localState.systemSystemPrompt);
                    } else if (response.config_type === 'user') {
                        const newStylePreset = response.stylePreset || 'photographic';
                        const newHeightWidth = response.heightWidth || '1024x1024';
                        updateLocalState('pricePer1000InputTokens', response.pricePer1000InputTokens || pricePer1000InputTokens);
                        updateLocalState('pricePer1000OutputTokens', response.pricePer1000OutputTokens || pricePer1000OutputTokens);
                        updateLocalState('userSystemPrompt', response.systemPrompt || '');
                        const newSystemPromptUserOrSystem = response.systemPromptUserOrSystem || 'system';
                        updateLocalState('systemPromptType', newSystemPromptUserOrSystem);
                        setSystemPromptUserOrSystem(newSystemPromptUserOrSystem);

                        updateLocalState('stylePreset', newStylePreset);
                        localStorage.setItem('stylePreset', newStylePreset);
                        setStylePreset(newStylePreset)

                        updateLocalState('heightWidth', newHeightWidth);
                        localStorage.setItem('heightWidth', newHeightWidth);
                        setHeightWidth(newHeightWidth)

                    } else if (response.message === 'Config saved successfully') {
                        console.log('Configuration saved successfully');
                    } else {
                        console.log('Other settings response:', response);
                    }
                }
            } catch (error) {
                console.error('Error processing WebSocket message:', error);
                setError('Failed to process server response. Please try again.');
            }
        }
    }, [
        lastMessage,
        prevLastMessage,
        pricePer1000InputTokens,
        pricePer1000OutputTokens,
        updateSystemPrompt,
        updateLocalState,
        setStylePreset,
        setHeightWidth,
        localState.systemSystemPrompt,
    ]);

    const saveConfig = useCallback(async (configType, config) => {
        try {
            const { accessToken, idToken } = await getCurrentSession();
            const data = {
                action: 'config',
                subaction: 'save',
                config_type: configType,
                user: configType === 'user' ? user.username : undefined,
                idToken: idToken + '',
                accessToken: accessToken + '',
                config: {
                    ...config,
                    systemPrompt: configType === 'system' ? localState.systemSystemPrompt : localState.userSystemPrompt
                },
            };
            sendMessage(JSON.stringify(data));
        } catch (error) {
            console.error('Error saving configuration:', error);
            setError('Failed to save configuration. Please try again.');
        }
    }, [getCurrentSession, sendMessage, user.username, localState.systemSystemPrompt, localState.userSystemPrompt]);


    const handleSave = useCallback(() => {
        setError('');
        setPricePer1000InputTokens(localState.pricePer1000InputTokens);
        setPricePer1000OutputTokens(localState.pricePer1000OutputTokens);
        onModeChange(selectedMode)

        // Update image-related 
        setStylePreset(localState.stylePreset);
        setHeightWidth(localState.heightWidth);
        localStorage.setItem('stylePreset', localState.stylePreset);
        localStorage.setItem('heightWidth', localState.heightWidth);

        saveConfig('system', {
            systemPrompt: localState.systemSystemPrompt,
        });

        saveConfig('user', {
            systemPrompt: localState.userSystemPrompt,
            stylePreset: localState.stylePreset,
            heightWidth: localState.heightWidth,
            systemPromptUserOrSystem: localState.systemPromptType,
        });

        onSave();
        onClose();
    }, [localState,
        setPricePer1000InputTokens,
        setPricePer1000OutputTokens,
        setStylePreset,
        setHeightWidth,
        saveConfig,
        onSave,
        onClose,
        onModeChange,
        selectedMode]);

    const modalStyle = {
        position: 'absolute',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        width: '80vw',
        bgcolor: 'background.paper',
        border: '2px solid #000',
        boxShadow: 24,
        maxHeight: '80vh',
        padding: theme.spacing(2),
        overflowY: 'auto',
    };
    const handleInfoTooltipOpen = () => {
        setShowInfoTooltip(true);
    };

    const handleInfoTooltipClose = () => {
        setShowInfoTooltip(false);
    };

    return (
        <Modal open={showSettingsModal} onClose={onClose}>
            <Box sx={modalStyle}>
                <Typography variant="h6" component="h2">
                    Settings
                </Typography>

                <Tooltip title="Enter the price per 1000 input tokens" arrow>
                    <TextField
                        label="Price per 1000 Input Tokens"
                        value={localState.pricePer1000InputTokens}
                        onChange={(e) => updateLocalState('pricePer1000InputTokens', e.target.value)}
                        fullWidth
                        margin="normal"
                        type="number"
                    />
                </Tooltip>

                <Tooltip title="Enter the price per 1000 output tokens" arrow>
                    <TextField
                        label="Price per 1000 Output Tokens"
                        value={localState.pricePer1000OutputTokens}
                        onChange={(e) => updateLocalState('pricePer1000OutputTokens', e.target.value)}
                        fullWidth
                        margin="normal"
                        type="number"
                    />
                </Tooltip>

                <Typography variant="body2" color="textSecondary" style={{ marginTop: theme.spacing(1) }}>
                    Bedrock pricing found here:{' '}
                    <Link href="https://aws.amazon.com/bedrock/pricing/" target="_blank" rel="noopener noreferrer">
                        https://aws.amazon.com/bedrock/pricing/
                    </Link>
                </Typography>

                {selectedMode && selectedMode.category === "Bedrock Models" && (
                    <Typography variant="h6" style={{ marginTop: theme.spacing(2) }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', marginTop: theme.spacing(2) }}>
                            <Typography variant="h6">
                                Bedrock Backend Prompt (Doesn't apply with KB or Agents):
                            </Typography>
                            <Tooltip
                                title="Add a Backend Prompt to direct the chatbot to give you better answers such as:
                        'You are a developer and system architect helping design well architected code 
                        for a modern event-driven application'"
                                placement="right"
                                open={showInfoTooltip}
                                onOpen={handleInfoTooltipOpen}
                                onClose={handleInfoTooltipClose}
                                arrow
                            >
                                <IconButton color="inherit" sx={{ ml: 1 }}>
                                    <FaInfoCircle />
                                </IconButton>
                            </Tooltip>
                        </Box>
                        <Box sx={{ display: 'flex', alignItems: 'center' }}>
                            <Typography variant="body1" sx={{ marginRight: 1 }}>System</Typography>
                            <Switch
                                checked={localState.systemPromptType === 'user'}
                                onChange={handleSystemPromptTypeChange}
                                color="primary"
                            />
                            <Typography variant="body1" sx={{ marginLeft: 1 }}>User</Typography>
                        </Box>


                        <Tooltip title={`Enter the ${localState.systemPromptType === 'user' ? 'User' : 'System'} Prompt`} arrow>
                            <TextField
                                label="System Prompt"
                                multiline
                                rows={4}
                                value={localState.systemSystemPrompt}
                                onChange={handleSystemPromptChange}
                                name="systemSystemPrompt"
                                fullWidth
                                margin="normal"
                                style={{ display: localState.systemPromptType !== 'user' ? 'block' : 'none' }}
                            />
                            <TextField
                                label="User Prompt"
                                multiline
                                rows={4}
                                value={localState.userSystemPrompt}
                                onChange={handleSystemPromptChange}
                                name="userSystemPrompt"
                                fullWidth
                                margin="normal"
                                style={{ display: localState.systemPromptType === 'user' ? 'block' : 'none' }}
                            />
                        </Tooltip>
                    </Typography>
                )}
                {selectedMode && selectedMode.category && selectedMode.category.includes("Image") && selectedMode.modelId.includes('stable-diffusion-xl-v1') && (
                    <>
                        <Typography variant="h6" style={{ marginTop: theme.spacing(2) }}>Image Generation Settings:</Typography>
                        {selectedMode.modelId.includes('stable-diffusion-xl-v1') && (
                            <FormControl fullWidth margin="normal">
                                <InputLabel id="style-preset-select-label">Stability AI Style</InputLabel>
                                <Select
                                    labelId="style-preset-select-label"
                                    id="style-preset-select"
                                    value={localState.stylePreset}
                                    onChange={handleStylePresetChange}
                                    label="Stability AI Style"
                                >
                                    {stylePresets.map(style => (
                                        <MenuItem key={style} value={style}>
                                            {style}
                                        </MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                        )}
                        <FormControl fullWidth margin="normal">
                            <InputLabel id="height-width-select-label">Height x Width</InputLabel>
                            <Select
                                labelId="height-width-select-label"
                                id="height-width-select"
                                value={localState.heightWidth}
                                onChange={handleHeightWidthChange}
                                label="Height x Width"
                            >
                                {(selectedMode && selectedMode.category && selectedMode.model && selectedMode.modelId && selectedMode.category.includes("Images") && selectedMode.modelId === 'amazon.titan-image-generator-v2:0' ? titanImageSizes : stabilityDiffusionSizes).map(size => (
                                    <MenuItem key={size} value={size}>
                                        {formatSizeLabel(size)}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    </>
                )}
                {error && (
                    <Typography color="error" style={{ marginTop: theme.spacing(2) }}>
                        {error}
                    </Typography>
                )}

                <Box sx={{ display: 'flex', justifyContent: 'flex-end', marginTop: theme.spacing(2) }}>
                    <Button onClick={onClose} style={{ marginRight: theme.spacing(1) }}>
                        Cancel
                    </Button>
                    <Button onClick={handleSave} variant="contained" color="primary">
                        Save
                    </Button>
                </Box>
            </Box>
        </Modal>
    );
};

export default SettingsModal;