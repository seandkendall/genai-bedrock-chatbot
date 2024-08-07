import React, { useState, useEffect, useCallback } from 'react';
import { Tooltip } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { FaInfoCircle } from 'react-icons/fa';
import {
    Modal,
    Box,
    Typography,
    TextField,
    Button,
    Grid,
    Paper,
    Link,
    Switch,
    FormControl,
    RadioGroup,
    Radio,
    FormControlLabel,
    IconButton,
    InputLabel,
    Select,
    MenuItem,
    
} from '@mui/material';
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
}) => {
    const theme = useTheme();
    const [error, setError] = useState('');
    const [showInfoTooltip, setShowInfoTooltip] = useState(false);

    // Local state variables for form fields
    const [localBedrockKnowledgeBaseID, setLocalBedrockKnowledgeBaseID] = useState(bedrockKnowledgeBaseID);
    const [localBedrockAgentsID, setLocalBedrockAgentsID] = useState(bedrockAgentsID);
    const [localBedrockAgentsAliasID, setLocalBedrockAgentsAliasID] = useState(bedrockAgentsAliasID);
    const [localPricePer1000InputTokens, setLocalPricePer1000InputTokens] = useState(pricePer1000InputTokens);
    const [localPricePer1000OutputTokens, setLocalPricePer1000OutputTokens] = useState(pricePer1000OutputTokens);
    const [localKnowledgebasesOrAgents, setLocalKnowledgebasesOrAgents] = useState(knowledgebasesOrAgents);
    const [localSelectedModel, setLocalSelectedModel] = useState(selectedModel);

    const [systemPrompt, setSystemPrompt] = useState({
        system: '',
        user: '',
    });
    const [systemPromptType, setSystemPromptType] = useState(systemPromptUserOrSystem);
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

    const getDefaultModel = (models) => {
        const defaultModel = models.find(
            (model) => model.modelId === 'anthropic.claude-3-sonnet-20240229-v1:0'
        );

        if (defaultModel) {
            return defaultModel;
        }

        // If not, check for any Anthropic model
        const anthropicModel = models.find((model) => model.providerName === 'Anthropic');

        if (anthropicModel) {
            return anthropicModel;
        }

        // If no Anthropic model, return the first available model
        if (models.length > 0) {
            return models[0];
        }
        // If no models are available, return null
        return null;
    };
    const handleModelChange = (event) => {
        const selectedModelId = event.target.value;
        const selectedModel = models.find((model) => model.modelId === selectedModelId);
        if (selectedModel) {
            console.log('handleModelChange: Setting New Model As : ' + selectedModel.modelId);
            setLocalSelectedModel(selectedModel.modelId);
        }
    };

    const handleSystemPromptChange = (event) => {
        const { value } = event.target;
        setSystemPrompt((prevState) => ({
            ...prevState,
            [systemPromptType]: value,
        }));
    };

    const [configLoaded, setConfigLoaded] = useState(false);

    const handleSystemPromptTypeChange = (event) => {
        const value = event.target.checked ? 'user' : 'system';
        setSystemPromptType(value);
        setSystemPromptUserOrSystem(value); // Update the prop value
        localStorage.setItem('systemPromptUserOrSystem', value); // Store in local storage
    };
    const { sendMessage, lastMessage } = useWebSocket(websocketUrl, {
        shouldReconnect: (closeEvent) => true,
        reconnectInterval: 3000,
    });

    const loadConfig = useCallback(
        async (configType) => {
            const { accessToken, idToken } = await getCurrentSession();
            const data = {
                action: 'config',
                subaction: 'load',
                config_type: configType,
                user: configType === 'user' ? user.username : 'system',
                idToken: idToken + '',
                accessToken: accessToken + '',
            };
            console.log('sending a message for settings')
            sendMessage(JSON.stringify(data));
        },
        [getCurrentSession, sendMessage, user.username]
    );
    useEffect(() => {
        if (!selectedModel) {
            const defaultModel = getDefaultModel(models);
            if (defaultModel) {
                console.log('DefaultModel: setting default model as: ' + defaultModel.modelId);
                setLocalSelectedModel(defaultModel.modelId);
                setSelectedModel(defaultModel.modelId);
            }
        }
    }, [models, selectedModel]);


    useEffect(() => {
        const storedOption = localStorage.getItem('knowledgebasesOrAgents');
        if (storedOption) {
            setLocalKnowledgebasesOrAgents(storedOption);
        }

        if (configLoaded === false) {
            loadConfig('system');
            loadConfig('user');
            setConfigLoaded(true);
        }
    }, [configLoaded, loadConfig, setKnowledgebasesOrAgents]);

    useEffect(() => {
        setReloadPromptConfig(true);
    }, [systemPrompt, systemPromptType, setReloadPromptConfig]);

    const handleOptionChange = (knowledgebasesOrAgents) => {
        setLocalKnowledgebasesOrAgents(knowledgebasesOrAgents);
        localStorage.setItem('knowledgebasesOrAgents', knowledgebasesOrAgents);
    };

    const updateSystemPrompt = useCallback(
        (configType, newPrompt) => {
            setSystemPrompt((prevState) => ({
                ...prevState,
                [configType]: newPrompt,
            }));
        },
        [setSystemPrompt]
    );

    // config loading logic from websocket 
    useEffect(() => {
        if (lastMessage !== null) {
            const response = JSON.parse(lastMessage.data);
            if (response) {
                if (response.config_type === 'system') {
                    setLocalBedrockKnowledgeBaseID(response.bedrockKnowledgeBaseID || bedrockKnowledgeBaseID);
                    setLocalBedrockAgentsID(response.bedrockAgentsID || bedrockAgentsID);
                    setLocalBedrockAgentsAliasID(response.bedrockAgentsAliasID || bedrockAgentsAliasID);
                    setLocalPricePer1000InputTokens(response.pricePer1000InputTokens || pricePer1000InputTokens);
                    setLocalPricePer1000OutputTokens(response.pricePer1000OutputTokens || pricePer1000OutputTokens);
                    setRegion(response.region || 'us-west-2')
                    if (response.modelId) {
                        console.log('setting model as : ' + response.modelId)
                        setLocalSelectedModel(response.modelId)
                        setSelectedModel(response.modelId)
                    }

                    setSystemPrompt((prevState) => ({
                        ...prevState,
                        system: response.systemPrompt !== null && response.systemPrompt !== undefined ? response.systemPrompt : prevState.system,
                    }));
                    updateSystemPrompt(
                        'system',
                        response.systemPrompt !== null && response.systemPrompt !== undefined
                            ? response.systemPrompt
                            : systemPrompt.system
                    );
                } else if (response.config_type === 'user') {
                    updateSystemPrompt(
                        'user',
                        response.systemPrompt !== null && response.systemPrompt !== undefined
                            ? response.systemPrompt
                            : systemPrompt.user
                    );
                } else if (response.message === 'Config saved successfully') {
                    // NoOp: Save Success 
                } else {
                    console.log('other settings response');
                    console.log(response);
                }
            } else {
                if (response.body && response.body.error) {
                    console.error('Error loading configuration:', response.body.error);
                } else {
                    console.error('Error loading configuration:', response);
                }
            }
        }
    }, [
        lastMessage,
        bedrockAgentsAliasID,
        bedrockAgentsID,
        bedrockKnowledgeBaseID,
        pricePer1000InputTokens,
        pricePer1000OutputTokens,
        setBedrockAgentsAliasID,
        setBedrockAgentsID,
        setBedrockKnowledgeBaseID,
        setPricePer1000InputTokens,
        setPricePer1000OutputTokens,
        updateSystemPrompt,
    ]);
    const saveConfig = async (configType, config) => {
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
                systemPrompt: configType === 'system' ? systemPrompt.system : systemPrompt.user,
            },
        };
        sendMessage(JSON.stringify(data));
    };

    const handleSave = () => {
        if ((localBedrockAgentsID && !localBedrockAgentsAliasID) || (!localBedrockAgentsID && localBedrockAgentsAliasID)) {
            setError('If you enter a Bedrock Agents ID, you must also enter a Bedrock Agents Alias ID, and vice versa.');
        } else {
            setError('');
            setBedrockKnowledgeBaseID(localBedrockKnowledgeBaseID);
            setBedrockAgentsID(localBedrockAgentsID);
            setBedrockAgentsAliasID(localBedrockAgentsAliasID);
            setPricePer1000InputTokens(localPricePer1000InputTokens);
            setPricePer1000OutputTokens(localPricePer1000OutputTokens);
            setKnowledgebasesOrAgents(localKnowledgebasesOrAgents);
            setSelectedModel(localSelectedModel);

            saveConfig('system', {
                bedrockKnowledgeBaseID: localBedrockKnowledgeBaseID,
                bedrockAgentsID: localBedrockAgentsID,
                bedrockAgentsAliasID: localBedrockAgentsAliasID,
                systemPrompt,
                modelId: localSelectedModel ? localSelectedModel : null,
            });
            saveConfig('user', {
                systemPrompt,
            });
            onSave(localKnowledgebasesOrAgents);
        }
    };

    const isFormValid = () => {
        return !(localBedrockAgentsID && !localBedrockAgentsAliasID) && !((!localBedrockAgentsID && localBedrockAgentsAliasID));
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
                <Typography variant="h6" component="h2">
                    &nbsp;
                </Typography>
                <Grid container spacing={2}>
                    <Grid item xs={12}>
                        <Paper elevation={3}>
                            <Grid container spacing={2} alignItems="center" padding={2}>
                                <Grid item xs={12}>
                                    <FormControl fullWidth>
                                        <InputLabel>Model</InputLabel>
                                        <Select value={localSelectedModel ? localSelectedModel : ''} onChange={handleModelChange}>
                                            <MenuItem value="">Select a model</MenuItem>
                                            {models.map((model) => (
                                                <MenuItem key={model.modelId} value={model.modelId}>
                                                    {model.providerName} - {model.modelName} ({model.modelId})
                                                </MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>
                                </Grid>
                                <Grid item xs={12}>
                                    <FormControl component="fieldset">
                                        <RadioGroup
                                            row
                                            value={localKnowledgebasesOrAgents}
                                            onChange={(e) => handleOptionChange(e.target.value)}
                                        >
                                            <FormControlLabel
                                                value="knowledgeBases"
                                                control={<Radio />}
                                                label="Knowledge Bases"
                                            />
                                            <FormControlLabel
                                                value="agents"
                                                control={<Radio />}
                                                label="Agents"
                                            />
                                        </RadioGroup>
                                    </FormControl>
                                </Grid>
                                {localKnowledgebasesOrAgents === 'knowledgeBases' && (
                                    <Grid item xs={12}>
                                        <TextField
                                            label="Bedrock Knowledge Base ID"
                                            value={localBedrockKnowledgeBaseID || ''}
                                            onChange={(e) => setLocalBedrockKnowledgeBaseID(e.target.value)}
                                            fullWidth
                                        />
                                    </Grid>
                                )}
                                {localKnowledgebasesOrAgents === 'agents' && (
                                    <>
                                        <Grid item xs={12}>
                                            <TextField
                                                label="Bedrock Agents ID"
                                                value={localBedrockAgentsID || ''}
                                                onChange={(e) => setLocalBedrockAgentsID(e.target.value)}
                                                fullWidth
                                            />
                                        </Grid>
                                        <Grid item xs={12}>
                                            <TextField
                                                label="Bedrock Agents Alias ID"
                                                value={localBedrockAgentsAliasID || ''}
                                                onChange={(e) => setLocalBedrockAgentsAliasID(e.target.value)}
                                                fullWidth
                                            />
                                        </Grid>
                                    </>
                                )}
                                <Grid item xs={12}>
                                    <TextField
                                        label="Price per 1000 Input Tokens"
                                        value={localPricePer1000InputTokens || ''}
                                        onChange={(e) => setLocalPricePer1000InputTokens(e.target.value)}
                                        fullWidth
                                    />
                                </Grid>
                                <Grid item xs={12}>
                                    <TextField
                                        label="Price per 1000 Output Tokens"
                                        value={localPricePer1000OutputTokens || ''}
                                        onChange={(e) => setLocalPricePer1000OutputTokens(e.target.value)}
                                        fullWidth
                                    />
                                </Grid>
                                <Grid item xs={12}>
                                    <Typography variant="body2">
                                        Bedrock pricing found here:{' '}
                                        <Link href="https://aws.amazon.com/bedrock/pricing/" target="_blank" rel="noopener">
                                            https://aws.amazon.com/bedrock/pricing/
                                        </Link>
                                    </Typography>
                                </Grid>
                                <Grid item xs={12}>
                                    <Grid container spacing={2} alignItems="center">
                                        <Grid item>
                                            <Typography>Backend Prompt:</Typography>
                                        </Grid>
                                        <Grid item>
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
                                        </Grid>
                                    </Grid>
                                    <Grid container spacing={2} alignItems="center">
                                        <Grid item>
                                            <Typography>System</Typography>
                                        </Grid>
                                        <Grid item>
                                            <Switch
                                                checked={systemPromptType === 'user'}
                                                onChange={handleSystemPromptTypeChange}
                                                color="primary"
                                            />
                                        </Grid>
                                        <Grid item>
                                            <Typography>User</Typography>
                                        </Grid>
                                    </Grid>
                                    <TextField
                                        multiline
                                        rows={4}
                                        value={systemPrompt[systemPromptType] ?? ''}
                                        onChange={handleSystemPromptChange}
                                        fullWidth
                                    />
                                </Grid>
                            </Grid>
                        </Paper>
                    </Grid>
                </Grid>
                {error && (
                    <Box mt={2}>
                        <Typography variant="body2" color="error">
                            {error}
                        </Typography>
                    </Box>
                )}
                <Grid container spacing={2} justifyContent="flex-end" mt={2}>
                    <Grid item>
                        <Button onClick={onClose}>Cancel</Button>
                    </Grid>
                    <Grid item>
                        <Button
                            variant="contained"
                            color="primary"
                            onClick={handleSave}
                            disabled={!isFormValid()}
                        >
                            Save
                        </Button>
                    </Grid>
                </Grid>
            </Box>
        </Modal>
    );
};

// eslint-disable-next-line
const modalStyle = {
    position: 'absolute',
    top: '50%',
    left: '50%',
    transform: 'translate(-50%, -50%)',
    width: 400,
    bgcolor: 'background.paper',
    border: '2px solid #000',
    boxShadow: 24,
    p: 4,
};

export default SettingsModal;