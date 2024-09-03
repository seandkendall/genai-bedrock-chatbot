import React, { useState, useEffect, useCallback } from 'react';
import { Tooltip, Modal, Box, Typography, TextField, Button, Grid, Paper, Link, Switch, FormControl, RadioGroup, Radio, FormControlLabel, IconButton, InputLabel, Select, MenuItem } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { FaInfoCircle } from 'react-icons/fa';
import useWebSocket from 'react-use-websocket';

const SettingsModal = ({
    open,
    onClose,
    onSave,
    bedrockKnowledgeBaseID,
    setBedrockKnowledgeBaseID,
    bedrockAgentsID,
    setBedrockAgentsID,
    bedrockAgentsAliasID,
    setBedrockAgentsAliasID,
    setPricePer1000InputTokens,
    pricePer1000InputTokens,
    setPricePer1000OutputTokens,
    pricePer1000OutputTokens,
    knowledgebasesOrAgents,
    setKnowledgebasesOrAgents,
    user,
    websocketUrl,
    getCurrentSession,
    systemPromptUserOrSystem,
    setSystemPromptUserOrSystem,
    setReloadPromptConfig,
    models,
    selectedModel,
    setSelectedModel,
    setRegion,
    imageModel,
    setImageModel,
    stylePreset,
    setStylePreset,
    heightWidth,
    setHeightWidth,
}) => {
    const theme = useTheme();
    const [error, setError] = useState('');
    const [showInfoTooltip, setShowInfoTooltip] = useState(false);
    const [configLoaded, setConfigLoaded] = useState(false);

    const [localState, setLocalState] = useState({
        bedrockKnowledgeBaseID,
        bedrockAgentsID,
        bedrockAgentsAliasID,
        pricePer1000InputTokens,
        pricePer1000OutputTokens,
        knowledgebasesOrAgents,
        selectedModel,
        systemPrompt: {
            system: '',
            user: '',
        },
        systemPromptType: systemPromptUserOrSystem,
        imageModel: localStorage.getItem('imageModel') || 'amazon.titan-image-generator-v2:0',
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

    const handleImageModelChange = useCallback((event) => {
        const newImageModel = event.target.value;
        setLocalState(prevState => ({
            ...prevState,
            imageModel: newImageModel,
            heightWidth: '1024x1024', // Reset height/width when model changes
        }));
        localStorage.setItem('imageModel', newImageModel);
    }, []);

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

    const getDefaultModel = useCallback((models) => {
        const defaultModel = models.find(
            (model) => model.modelId === 'anthropic.claude-3-sonnet-20240229-v1:0'
        );
        if (defaultModel) return defaultModel;
        const anthropicModel = models.find((model) => model.providerName === 'Anthropic');
        if (anthropicModel) return anthropicModel;
        return models.length > 0 ? models[0] : null;
    }, []);

    const handleModelChange = useCallback((event) => {
        const selectedModelId = event.target.value;
        const selectedModel = models.find((model) => model.modelId === selectedModelId);
        if (selectedModel) {
            console.log('handleModelChange: Setting New Model As : ' + selectedModel.modelId);
            updateLocalState('selectedModel', selectedModel.modelId);
        }
    }, [models, updateLocalState]);

    const handleSystemPromptChange = useCallback((event) => {
        const { name, value } = event.target;
        setLocalState(prevState => ({
            ...prevState,
            systemPrompt: {
                ...prevState.systemPrompt,
                [name]: value,
            },
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
        if (!selectedModel) {
            const defaultModel = getDefaultModel(models);
            if (defaultModel) {
                console.log('DefaultModel: setting default model as: ' + defaultModel.modelId);
                updateLocalState('selectedModel', defaultModel.modelId);
                setSelectedModel(defaultModel.modelId);
            }
        }
        if (!imageModel) {
            const defaultImageModel = localStorage.getItem('imageModel') || 'amazon.titan-image-generator-v2:0';
            setLocalState(prevState => ({
                ...prevState,
                imageModel: defaultImageModel,
            }));
            setImageModel(defaultImageModel);
        }
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
    }, [models, selectedModel, heightWidth, stylePreset, imageModel, getDefaultModel, setSelectedModel, updateLocalState, setHeightWidth, setImageModel, setStylePreset]);

    useEffect(() => {
        const storedOption = localStorage.getItem('knowledgebasesOrAgents');
        if (storedOption) {
            updateLocalState('knowledgebasesOrAgents', storedOption);
        }
        if (!configLoaded) {
            loadConfig('system');
            loadConfig('user');
            setConfigLoaded(true);
        }
    }, [configLoaded, loadConfig, updateLocalState]);

    useEffect(() => {
        setReloadPromptConfig(true);
    }, [localState.systemPrompt, localState.systemPromptType, setReloadPromptConfig]);

    const handleOptionChange = useCallback((knowledgebasesOrAgents) => {
        updateLocalState('knowledgebasesOrAgents', knowledgebasesOrAgents);
        localStorage.setItem('knowledgebasesOrAgents', knowledgebasesOrAgents);
    }, [updateLocalState]);

    const updateSystemPrompt = useCallback((configType, newPrompt) => {
        updateLocalState('systemPrompt', prevState => ({
            ...prevState,
            [configType]: newPrompt,
        }));
    }, [updateLocalState]);

    useEffect(() => {
        if (lastMessage !== null) {
            try {
                const response = JSON.parse(lastMessage.data);
                if (response) {
                    if (response.config_type === 'system') {
                        updateLocalState('bedrockKnowledgeBaseID', response.bedrockKnowledgeBaseID || bedrockKnowledgeBaseID);
                        updateLocalState('bedrockAgentsID', response.bedrockAgentsID || bedrockAgentsID);
                        updateLocalState('bedrockAgentsAliasID', response.bedrockAgentsAliasID || bedrockAgentsAliasID);
                        updateLocalState('pricePer1000InputTokens', response.pricePer1000InputTokens || pricePer1000InputTokens);
                        updateLocalState('pricePer1000OutputTokens', response.pricePer1000OutputTokens || pricePer1000OutputTokens);
                        updateLocalState('pricePer1000OutputTokens', response.pricePer1000OutputTokens || pricePer1000OutputTokens);
                        console.log('updating system response.systemPrompt: '+response.systemPrompt)
                        updateLocalState('systemPrompt.system', response.systemPrompt || '')
                        setRegion(response.region || 'us-west-2');
                        if (response.modelId) {
                            updateLocalState('selectedModel', response.modelId);
                            setSelectedModel(response.modelId);
                        }
                        updateSystemPrompt('system', response.systemPrompt ?? localState.systemPrompt.system);
                    } else if (response.config_type === 'user') {
                        const newImageModel = response.imageModel || 'amazon.titan-image-generator-v2:0';
                        const newStylePreset = response.stylePreset || 'photographic';
                        const newHeightWidth = response.heightWidth || '1024x1024';
                        updateLocalState('bedrockKnowledgeBaseID', response.bedrockKnowledgeBaseID || bedrockKnowledgeBaseID);
                        updateLocalState('bedrockAgentsID', response.bedrockAgentsID || bedrockAgentsID);
                        updateLocalState('bedrockAgentsAliasID', response.bedrockAgentsAliasID || bedrockAgentsAliasID);
                        updateLocalState('pricePer1000InputTokens', response.pricePer1000InputTokens || pricePer1000InputTokens);
                        updateLocalState('pricePer1000OutputTokens', response.pricePer1000OutputTokens || pricePer1000OutputTokens);
                        console.log('updating user response.systemPrompt: '+response.systemPrompt)
                        updateLocalState('systemPrompt.user', response.systemPrompt || '')
                        updateLocalState('imageModel', newImageModel);
                        updateLocalState('stylePreset', newStylePreset);
                        updateLocalState('heightWidth', newHeightWidth);
                        localStorage.setItem('imageModel', newImageModel);
                        setImageModel(newImageModel)
                        localStorage.setItem('stylePreset', newStylePreset);
                        setStylePreset(newStylePreset)
                        localStorage.setItem('heightWidth', newHeightWidth);
                        setHeightWidth(newHeightWidth)

                        updateSystemPrompt('user', response.systemPrompt ?? localState.systemPrompt.user);
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
    }, [lastMessage, bedrockAgentsAliasID, bedrockAgentsID, bedrockKnowledgeBaseID, pricePer1000InputTokens, pricePer1000OutputTokens, setRegion, setSelectedModel, updateSystemPrompt, updateLocalState]);

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
                    systemPrompt: configType === 'system' ? localState.systemPrompt.system : localState.systemPrompt.user,
                },
            };
            sendMessage(JSON.stringify(data));
        } catch (error) {
            console.error('Error saving configuration:', error);
            setError('Failed to save configuration. Please try again.');
        }
    }, [getCurrentSession, sendMessage, user.username, localState.systemPrompt]);


    const handleSave = useCallback(() => {
        if ((localState.bedrockAgentsID && !localState.bedrockAgentsAliasID) || (!localState.bedrockAgentsID && localState.bedrockAgentsAliasID)) {
            setError('If you enter a Bedrock Agents ID, you must also enter a Bedrock Agents Alias ID, and vice versa.');
        } else {
            setError('');
            setBedrockKnowledgeBaseID(localState.bedrockKnowledgeBaseID);
            setBedrockAgentsID(localState.bedrockAgentsID);
            setBedrockAgentsAliasID(localState.bedrockAgentsAliasID);
            setPricePer1000InputTokens(localState.pricePer1000InputTokens);
            setPricePer1000OutputTokens(localState.pricePer1000OutputTokens);
            setKnowledgebasesOrAgents(localState.knowledgebasesOrAgents);
            setSelectedModel(localState.selectedModel);

            // Update image-related 
            setImageModel(localState.imageModel);
            setStylePreset(localState.stylePreset);
            setHeightWidth(localState.heightWidth);
            localStorage.setItem('imageModel', localState.imageModel);
            localStorage.setItem('stylePreset', localState.stylePreset);
            localStorage.setItem('heightWidth', localState.heightWidth);

            saveConfig('system', {
                bedrockKnowledgeBaseID: localState.bedrockKnowledgeBaseID,
                bedrockAgentsID: localState.bedrockAgentsID,
                bedrockAgentsAliasID: localState.bedrockAgentsAliasID,
                systemPrompt: localState.systemPrompt,
                modelId: localState.selectedModel || null,
            });

            saveConfig('user', {
                systemPrompt: localState.systemPrompt,
                imageModel: localState.imageModel,
                stylePreset: localState.imageModel === 'stability.stable-diffusion-xl-v1' ? localState.stylePreset : null,
                heightWidth: localState.heightWidth,
            });

            onSave(localState.knowledgebasesOrAgents);
            onClose();
        }
    }, [localState, setBedrockKnowledgeBaseID, setBedrockAgentsID, setBedrockAgentsAliasID, setPricePer1000InputTokens, setPricePer1000OutputTokens, setKnowledgebasesOrAgents, setSelectedModel, setImageModel, setStylePreset, setHeightWidth, saveConfig, onSave, onClose]);

    const isFormValid = useCallback(() => {
        return !(localState.bedrockAgentsID && !localState.bedrockAgentsAliasID) && !(!localState.bedrockAgentsID && localState.bedrockAgentsAliasID);
    }, [localState.bedrockAgentsID, localState.bedrockAgentsAliasID]);

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
        <Modal open={open} onClose={onClose}>
            <Box sx={modalStyle}>
                <Typography variant="h6" component="h2">
                    Settings
                </Typography>
                <FormControl fullWidth margin="normal">
                    <InputLabel id="model-select-label">Model</InputLabel>
                    <Select
                        labelId="model-select-label"
                        id="model-select"
                        value={localState.selectedModel}
                        onChange={handleModelChange}
                        label="Select a model"
                    >
                        {models.map((model) => (
                            <MenuItem key={model.modelId} value={model.modelId}>
                                {model.providerName} - {model.modelName} ({model.modelId})
                            </MenuItem>
                        ))}
                    </Select>
                </FormControl>

                <FormControl component="fieldset" margin="normal">
                    <RadioGroup
                        row
                        aria-label="knowledgebases-or-agents"
                        name="knowledgebasesOrAgents"
                        value={localState.knowledgebasesOrAgents}
                        onChange={(e) => handleOptionChange(e.target.value)}
                    >
                        <FormControlLabel value="knowledgeBases" control={<Radio />} label="Knowledge Bases" />
                        <FormControlLabel value="agents" control={<Radio />} label="Agents" />
                    </RadioGroup>
                </FormControl>

                {localState.knowledgebasesOrAgents === 'knowledgeBases' && (
                    <Tooltip title="Enter the Bedrock Knowledge Base ID" arrow>
                        <TextField
                            label="Bedrock Knowledge Base ID"
                            value={localState.bedrockKnowledgeBaseID}
                            onChange={(e) => updateLocalState('bedrockKnowledgeBaseID', e.target.value)}
                            fullWidth
                            margin="normal"
                        />
                    </Tooltip>
                )}

                {localState.knowledgebasesOrAgents === 'agents' && (
                    <>
                        <Tooltip title="Enter the Bedrock Agents ID" arrow>
                            <TextField
                                label="Bedrock Agents ID"
                                value={localState.bedrockAgentsID}
                                onChange={(e) => updateLocalState('bedrockAgentsID', e.target.value)}
                                fullWidth
                                margin="normal"
                            />
                        </Tooltip>
                        <Tooltip title="Enter the Bedrock Agents Alias ID" arrow>
                            <TextField
                                label="Bedrock Agents Alias ID"
                                value={localState.bedrockAgentsAliasID}
                                onChange={(e) => updateLocalState('bedrockAgentsAliasID', e.target.value)}
                                fullWidth
                                margin="normal"
                            />
                        </Tooltip>
                    </>
                )}

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

                <Box sx={{ display: 'flex', alignItems: 'center', marginTop: theme.spacing(2) }}>
                    <Typography variant="h6">
                        Backend Prompt:
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
                        label={`${localState.systemPromptType === 'user' ? 'User' : 'System'} Prompt`}
                        multiline
                        rows={4}
                        value={localState.systemPrompt[localState.systemPromptType]}
                        onChange={handleSystemPromptChange}
                        name={localState.systemPromptType}
                        fullWidth
                        margin="normal"
                    />
                </Tooltip>

                <Typography variant="h6" style={{ marginTop: theme.spacing(2) }}>
                    Image Generation Settings
                </Typography>

                <FormControl fullWidth margin="normal">
                    <InputLabel id="image-model-select-label">Image Model</InputLabel>
                    <Select
                        labelId="image-model-select-label"
                        id="image-model-select"
                        value={localState.imageModel}
                        onChange={handleImageModelChange}
                        label="Image Model"
                    >
                        <MenuItem value="amazon.titan-image-generator-v2:0">Amazon Titan Image Generator v1</MenuItem>
                        <MenuItem value="stability.stable-diffusion-xl-v1">Stability AI Stable Diffusion XL v1</MenuItem>
                    </Select>
                </FormControl>

                {localState.imageModel === 'stability.stable-diffusion-xl-v1' && (
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
                        {(localState.imageModel === 'amazon.titan-image-generator-v2:0' ? titanImageSizes : stabilityDiffusionSizes).map(size => (
                            <MenuItem key={size} value={size}>
                                {formatSizeLabel(size)}
                            </MenuItem>
                        ))}
                    </Select>
                </FormControl>

                {error && (
                    <Typography color="error" style={{ marginTop: theme.spacing(2) }}>
                        {error}
                    </Typography>
                )}

                <Box sx={{ display: 'flex', justifyContent: 'flex-end', marginTop: theme.spacing(2) }}>
                    <Button onClick={onClose} style={{ marginRight: theme.spacing(1) }}>
                        Cancel
                    </Button>
                    <Button onClick={handleSave} variant="contained" color="primary" disabled={!isFormValid()}>
                        Save
                    </Button>
                </Box>
            </Box>
        </Modal>
    );
};

export default SettingsModal;