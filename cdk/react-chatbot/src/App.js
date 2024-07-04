import { marked } from 'marked';
import { websocketUrl } from './variables.js';
import React, { useState, useEffect, useRef, memo, lazy, Suspense } from 'react';
import DOMPurify from 'dompurify';
import Header from './components/Header';
import ChatHistory from './components/ChatHistory';
import MessageInput from './components/MessageInput';
import useTimer from './useTimer';
import './App.css';
import Popup from './components/Popup';
import { Amplify } from 'aws-amplify';
import { fetchAuthSession } from 'aws-amplify/auth';
import { withAuthenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import amplifyConfig from './config.json';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import useWebSocket from 'react-use-websocket';

// hard-coded pricing for now, until amazon releases an API for this
// reference: https://aws.amazon.com/bedrock/pricing/
const modelPrices = {
  'amazon.titan-text-express-v1': {
    pricePer1000InputTokens: 0.0008,
    pricePer1000OutputTokens: 0.0016,
  },
  'amazon.titan-text-lite-v1': {
    pricePer1000InputTokens: 0.0003,
    pricePer1000OutputTokens: 0.0004,
  },
  'anthropic.claude-v2': {
    pricePer1000InputTokens: 0.008,
    pricePer1000OutputTokens: 0.024,
  },
  'anthropic.claude-v2:1': {
    pricePer1000InputTokens: 0.008,
    pricePer1000OutputTokens: 0.024,
  },
  'anthropic.claude-3-sonnet-20240229-v1:0': {
    pricePer1000InputTokens: 0.003,
    pricePer1000OutputTokens: 0.015,
  },
  'anthropic.claude-3-haiku-20240307-v1:0': {
    pricePer1000InputTokens: 0.00025,
    pricePer1000OutputTokens: 0.00125,
  },
  'anthropic.claude-3-opus-20240229-v1:0': {
    pricePer1000InputTokens: 0.015,
    pricePer1000OutputTokens: 0.075,
  },
  'anthropic.claude-instant-v1': {
    pricePer1000InputTokens: 0.0008,
    pricePer1000OutputTokens: 0.0024,
  },
  'mistral.mistral-7b-instruct-v0:2': {
    pricePer1000InputTokens: 0.00015,
    pricePer1000OutputTokens: 0.0002,
  },
  'mistral.mixtral-8x7b-instruct-v0:1': {
    pricePer1000InputTokens: 0.00045,
    pricePer1000OutputTokens: 0.0007,
  },
  'mistral.mistral-large-2402-v1:0': {
    pricePer1000InputTokens: 0.008,
    pricePer1000OutputTokens: 0.024,
  },
};

const SettingsModal = lazy(() => import('./components/SettingsModal'));

async function getCurrentSession() {
  try {
    const { accessToken, idToken } = (await fetchAuthSession()).tokens ?? {};
    return { accessToken, idToken }
  } catch (err) {
    console.log(err);
  }
}

const theme = createTheme({
  palette: {
    mode: 'light',
  },
});

Amplify.configure(amplifyConfig);
marked.setOptions({
  breaks: true,
  gfm: true,
  sanitize: true,
  smartLists: true,
  smartypants: false,
  xhtml: false,
});

const App = memo(({ signOut, user }) => {
  const [messages, setMessages] = useState([]);
  const [isDisabled, setIsDisabled] = useState(false);
  const [selectedMode, setSelectedMode] = useState('bedrock');
  const [responseCompleted, setResponseCompleted] = useState(true);
  const chatHistoryRef = useRef(null);
  const { elapsedTime, startTimer, stopTimer, resetTimer } = useTimer();
  const [showPopup, setShowPopup] = useState(false);
  const [popupMessage, setPopupMessage] = useState('');
  const [popupType, setPopupType] = useState('success');
  const [bedrockHistory, setBedrockHistory] = useState([]);
  const [agentsHistory, setAgentsHistory] = useState([]);
  const [totalInputTokens, setTotalInputTokens] = useState(0);
  const [totalOutputTokens, setTotalOutputTokens] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  // eslint-disable-next-line
  const [retryTimeout, setRetryTimeout] = useState(null);
  const [pricePer1000InputTokens, setPricePer1000InputTokens] = useState(0.00300);
  const [pricePer1000OutputTokens, setPricePer1000OutputTokens] = useState(0.01500);
  // eslint-disable-next-line
  const [monthlyInputTokens, setMonthlyInputTokens] = useState(0)
  // eslint-disable-next-line
  const [monthlyOutputTokens, setMonthlyOutputTokens] = useState(0)
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [reloadPromptConfig, setReloadPromptConfig] = useState(true);
  const [bedrockKnowledgeBaseID, setBedrockKnowledgeBaseID] = useState('');
  const [bedrockAgentsID, setBedrockAgentsID] = useState('');
  const [bedrockAgentsAliasID, setBedrockAgentsAliasID] = useState('');
  const [knowledgebasesOrAgents, setKnowledgebasesOrAgents] = useState('knowledgeBases');
  const [bedrockSessionId, setBedrockSessionId] = useState('');
  const [agentsSessionId, setAgentsSessionId] = useState('');
  const [kbSessionId, setKBSessionId] = useState('');
  const [systemPromptUserOrSystem, setSystemPromptUserOrSystem] = useState('system');
  const [models, setModels] = useState([]);
  const [usedModel, setUsedModel] = useState('');
  const [selectedModel, setSelectedModel] = useState(null);
  const [region, setRegion] = useState(null);

  // Use the useWebSocket hook to manage the WebSocket connection
  // eslint-disable-next-line
  const { sendMessage, lastMessage, readyState } = useWebSocket(websocketUrl, {
    shouldReconnect: (closeEvent) => true, // Automatically reconnect on close
    reconnectInterval: 3000, // Reconnect every 3 seconds
  });
  
  useEffect(() => {
    if (bedrockSessionId !== null) {
      loadModels(bedrockSessionId, 'bedrock');
    }
  }, [bedrockSessionId]);
  // Add this function to update the prices based on the selected model
  const updatePricesFromModel = (selectedModel) => {
    if (selectedModel) {
      const modelId = selectedModel;
      const modelPriceInfo = modelPrices[modelId] || {
        pricePer1000InputTokens: 0.00300,
        pricePer1000OutputTokens: 0.01500,
      };
      setPricePer1000InputTokens(modelPriceInfo.pricePer1000InputTokens);
      setPricePer1000OutputTokens(modelPriceInfo.pricePer1000OutputTokens);
    }else{
      const modelPriceInfo = {
        pricePer1000InputTokens: 0.00300,
        pricePer1000OutputTokens: 0.01500,
      };
      setPricePer1000InputTokens(modelPriceInfo.pricePer1000InputTokens);
      setPricePer1000OutputTokens(modelPriceInfo.pricePer1000OutputTokens);
    }
  };
  useEffect(() => {
    updatePricesFromModel(selectedModel)
  },[selectedModel]);

  useEffect(() => {
    const storedBedrockSessionId = localStorage.getItem('bedrockSessionId');
    const storedAgentsSessionId = localStorage.getItem('agentsSessionId');
    const selMode = localStorage.getItem('selectedMode') || 'bedrock';
    const bedrockHistory = localStorage.getItem(`bedrockHistory-${storedBedrockSessionId}`);
    const agentsHistory = localStorage.getItem(`agentsHistory-${storedAgentsSessionId}`);
    const kbSessionId = localStorage.getItem(`kbSessionId`);
    const storedPricePer1000InputTokens = localStorage.getItem(`pricePer1000InputTokens`);
    const storedPricePer1000OutputTokens = localStorage.getItem(`pricePer1000OutputTokens`);

    // Set the price per 1000 tokens from localStorage if available, otherwise use the default values
    setPricePer1000InputTokens(storedPricePer1000InputTokens);
    setPricePer1000OutputTokens(storedPricePer1000OutputTokens);
    setKBSessionId(kbSessionId)
    const storedBedrockHistory = isValidJSON(bedrockHistory) && Array.isArray(JSON.parse(bedrockHistory))
      ? JSON.parse(bedrockHistory)
      : [];
    const storedAgentsHistory = isValidJSON(agentsHistory) && Array.isArray(JSON.parse(agentsHistory))
      ? JSON.parse(agentsHistory)
      : [];
    const currentDate = new Date().toDateString();
    const storedInputTokens = isValidJSON(localStorage.getItem(`inputTokens-${currentDate}`))
      ? JSON.parse(localStorage.getItem(`inputTokens-${currentDate}`))
      : 0;
    const storedOutputTokens = isValidJSON(localStorage.getItem(`outputTokens-${currentDate}`))
      ? JSON.parse(localStorage.getItem(`outputTokens-${currentDate}`))
      : 0;

    setBedrockHistory(storedBedrockHistory);
    setAgentsHistory(storedAgentsHistory);
    setTotalInputTokens(storedInputTokens);
    setTotalOutputTokens(storedOutputTokens);

    if (storedBedrockSessionId) {
      setBedrockSessionId(storedBedrockSessionId);
      if (selMode === 'bedrock' && (storedBedrockHistory === null || storedBedrockHistory.length === 0)) {
        loadConversationHistory(storedBedrockSessionId, 'bedrock');
      } else if (selMode === 'bedrock') {
        if (Array.isArray(storedBedrockHistory)) {
          setMessages(storedBedrockHistory);
        }
      }
    } else if (selMode === 'bedrock') {
      const newSessionId = generateSessionId();
      setBedrockSessionId(newSessionId);
      localStorage.setItem('bedrockSessionId', newSessionId);
    }

    if (storedAgentsSessionId) {
      setAgentsSessionId(storedAgentsSessionId);
      if (selMode === 'agents' && (storedAgentsHistory === null || storedAgentsHistory.length === 0)) {
        loadConversationHistory(storedAgentsSessionId, 'agents');
      } else if (selMode === 'agents') {
        if (Array.isArray(storedAgentsHistory)) {
          setMessages(storedAgentsHistory);
        }
      }
    } else if (selMode === 'agents') {
      const newSessionId = generateSessionId();
      setAgentsSessionId(newSessionId);
      localStorage.setItem('agentsSessionId', newSessionId);
    }
    setSelectedMode(selMode);

    const storedBedrockKnowledgeBaseID = localStorage.getItem('bedrockKnowledgeBaseID');
    const storedBedrockAgentsID = localStorage.getItem('bedrockAgentsID');
    const storedBedrockAgentsAliasID = localStorage.getItem('bedrockAgentsAliasID');
    const storedKnowledgebasesOrAgents = localStorage.getItem('knowledgebasesOrAgents');

    if (storedBedrockKnowledgeBaseID) {
      setBedrockKnowledgeBaseID(storedBedrockKnowledgeBaseID);
    }

    if (storedBedrockAgentsID) {
      setBedrockAgentsID(storedBedrockAgentsID);
    }

    if (storedBedrockAgentsAliasID) {
      setBedrockAgentsAliasID(storedBedrockAgentsAliasID);
    }

    if (storedKnowledgebasesOrAgents) {
      setKnowledgebasesOrAgents(storedKnowledgebasesOrAgents);
    }
  }, []);

  const isValidJSON = (str) => {
    try {
      JSON.parse(str);
    } catch (e) {
      return false;
    }
    return true;
  };

  const generateSessionId = () => {
    return user.username + '-' + Math.random().toString(36).substring(2, 8);
  };

  const handleModeChange = (newMode) => {
    setMessages([]);
    if (newMode === 'agents') {
      if (!agentsSessionId) {
        const newSessionId = generateSessionId();
        setAgentsSessionId(newSessionId);
        localStorage.setItem('agentsSessionId', newSessionId);
      }
      setMessages(agentsHistory);
    } else if (newMode === 'bedrock') {
      if (!bedrockSessionId) {
        const newSessionId = generateSessionId();
        setBedrockSessionId(newSessionId);
        localStorage.setItem('bedrockSessionId', newSessionId);
      }
      setMessages(bedrockHistory);
    } else {
      console.log('unknown new mode: ' + newMode)
    }
    setSelectedMode(newMode);
    localStorage.setItem('selectedMode', newMode);
    scrollToBottom();
  };
  const loadModels = async (sessionId, mode) => {
    const { accessToken, idToken } = await getCurrentSession()
    const data = {
      action: 'config',
      subaction: 'load_models',
      session_id: sessionId,
      selectedMode: mode,
      idToken: idToken + '',
      accessToken: accessToken + '',
      knowledgebasesOrAgents: knowledgebasesOrAgents,
    };
    sendMessage(JSON.stringify(data));
  }
  const loadConversationHistory = async (sessionId, mode, history = []) => {
    const { accessToken, idToken } = await getCurrentSession()
    const data = {
      type: 'load',
      session_id: sessionId,
      kb_session_id: kbSessionId,
      selectedMode: mode,
      idToken: idToken + '',
      accessToken: accessToken + '',
      knowledgebasesOrAgents: knowledgebasesOrAgents,
    };

    sendMessage(JSON.stringify(data));
  };

  useEffect(() => {
    if (lastMessage !== null) {
      const message = JSON.parse(lastMessage.data);
      if (message.type === 'conversation_history') {
        const messageChunk = convertRuleToHuman(JSON.parse(message.chunk));
        setMessages((prevMessages) => [...prevMessages, ...messageChunk]);
      }
    }
  }, [lastMessage, sendMessage]);

  const handleError = (errormessage) => {
    let popupMsg = 'Sorry, We encountered an issue, Please try resubmitting your message.'
    if (errormessage.includes('allow-listed')) {
      popupMsg = errormessage
    } else if (errormessage.includes('throttlingException')) {
      popupMsg = 'Sorry, We encountered a Throttling issue, Please try resubmitting your message.'
    }
    setIsDisabled(false);
    stopTimer();
    setPopupMessage(popupMsg);
    setPopupType('error');
    setTimeout(() => setShowPopup(false), 3000);
    setShowPopup(true);
    console.error('WebSocket error:', errormessage);
  };

  const onSend = async (message) => {
    setIsDisabled(true);
    setResponseCompleted(false);
    setIsLoading(true);
    resetTimer();
    startTimer();

    const sanitizedMessage = DOMPurify.sanitize(message);

    let currentSessionId = selectedMode === 'bedrock' ? bedrockSessionId : agentsSessionId;

    if (!selectedModel) {
      handleError('You have not requested access to a model in Bedrock. You can do so by visiting this link:https://'+region+'.console.aws.amazon.com/bedrock/home?region='+region+'#/modelaccess')
    }else{
      const { accessToken, idToken } = await getCurrentSession()
      const data = {
        prompt: sanitizedMessage,
        session_id: currentSessionId,
        kb_session_id: kbSessionId,
        selectedMode: selectedMode,
        model: selectedModel,
        idToken: idToken + '',
        accessToken: accessToken + '',
        knowledgebasesOrAgents: knowledgebasesOrAgents,
        reloadPromptConfig: reloadPromptConfig,
        systemPromptUserOrSystem: systemPromptUserOrSystem
      };
      data.model = selectedModel;
      const currentTime = new Date();
      const messageWithTime = {
        role: 'user',
        content: message,
        timestamp: currentTime.toLocaleString(),
      };

      setMessages((prevMessages) => [
        ...prevMessages,
        messageWithTime,
        {
          role: 'assistant',
          content: '',
          isStreaming: true,
          timestamp: null,
        },
      ]);

      scrollToBottom();

      sendMessage(JSON.stringify(data));
      setReloadPromptConfig(false);

    }
  };

  useEffect(() => {
    if (lastMessage !== null) {
      const message = JSON.parse(lastMessage.data);

      // Handle session ID updates from the server
      if (message.kb_session_id && (!kbSessionId || (kbSessionId && kbSessionId !== message.kb_session_id))) {
        // Skip updating the session if the response contains a specific error message
        if (message && message.delta && message.delta.text) {
          const textValue = message.delta.text;
          if (
            textValue.includes('Sorry, I am unable to assist you with this request') ||
            textValue.includes('Sorry, I cannot Answer')
          ) {
            console.log('Sorry, I am unable to assist you with this request.');
          } else {
            setKBSessionId(message.kb_session_id);
            localStorage.setItem('kbSessionId', message.kb_session_id);
          }
        }
      }

      if (typeof message === 'string' && message.includes('You have not been allow-listed for this application')) {
        handleError(message);
      } else if (message.type === 'message_start') {
        const model = message?.['message'].model
        setUsedModel(model)
        updateMessages(message);
      } else if (message.type === 'content_block_delta') {
        updateMessages(message);
      } else if (message.type === 'message_stop') {
        updateMessages(message);
        updateMessagesOnStop(message);
        setIsDisabled(false);
        setResponseCompleted(true);
        setIsLoading(false);
        scrollToBottom();
      } else if (message.type === 'error' || message.message === 'Internal server error') {
        updateMessages({ delta: { text: message.error || message.message } })
        handleError(message.error || message.message);
        setIsDisabled(false);
        setResponseCompleted(true);
        setIsLoading(false);
        scrollToBottom();
      } else if (message.type === 'load_models') {
        setModels(message.models)
      } else {
        if (typeof message === 'object' && message !== null) {
          const messageString = JSON.stringify(message);
          if (!messageString.includes('Message Received')) {
            console.log('Uncaught String Message:');
            console.log(messageString);
          }
        } else if (typeof message === 'string') {
          if (!message.includes('Message Received')) {
            console.log('Uncaught String Message:');
            console.log(message);
          }
        } else {
          console.log('Uncaught Message (non-string, non-object):');
          console.log(message);
        }
      }
    }
  }, [lastMessage]);

  const updateMessages = (message) => {
    // console.log('message:', message)
    if (message && message.delta && message.delta.text) {
      setMessages((prevMessages) => {
        const updatedMessages = [...prevMessages];
        const lastIndex = updatedMessages.length - 1;
        const lastMessage = updatedMessages[lastIndex];
        if (lastMessage && lastMessage.role === 'assistant') {
          const newContent = lastMessage.content + message.delta.text;
          updatedMessages[lastIndex] = {
            ...lastMessage,
            content: newContent,
          };
        }
        return updatedMessages;
      });
    }
  };

  const updateMessagesOnStop = (messageStop) => {
    setMessages((prevMessages) => {
      const updatedMessages = [...prevMessages];
      const lastIndex = updatedMessages.length - 1;
      const invocationMetrics = messageStop?.['amazon-bedrock-invocationMetrics'] || null; // Handle the case when 'amazon-bedrock-invocationMetrics' is not present
      const inputTokenCount = invocationMetrics ? invocationMetrics.inputTokenCount : 0;
      const outputTokenCount = invocationMetrics ? invocationMetrics.outputTokenCount : 0;
      const tokenidentifier = invocationMetrics ? invocationMetrics.inputTokenCount + '' + invocationMetrics.outputTokenCount + '' + invocationMetrics.invocationLatency + '' + invocationMetrics.firstByteLatency : 'R' + Math.floor(Math.random() * 1000000);

      const currentDate = new Date().toDateString();
      const existingInputTokens = isValidJSON(localStorage.getItem(`inputTokens-${currentDate}`))
        ? JSON.parse(localStorage.getItem(`inputTokens-${currentDate}`))
        : 0;
      const existingOutputTokens = isValidJSON(localStorage.getItem(`outputTokens-${currentDate}`))
        ? JSON.parse(localStorage.getItem(`outputTokens-${currentDate}`))
        : 0;
      const lastStoredTokenIdentifier = isValidJSON(localStorage.getItem('lastTokenIdentifier'))
        ? JSON.parse(localStorage.getItem('lastTokenIdentifier'))
        : '';

      if (tokenidentifier === lastStoredTokenIdentifier) {
        return updatedMessages;
      } else {
        localStorage.setItem('lastTokenIdentifier', tokenidentifier);
        console.log('inputTokens:', inputTokenCount)
        console.log('outputTokens:', outputTokenCount)

        updatedMessages[lastIndex] = {
          ...updatedMessages[lastIndex],
          isStreaming: false,
          timestamp: new Date().toLocaleString(),
          model: usedModel,
          outputTokenCount: outputTokenCount,
          inputTokenCount: inputTokenCount,
        };

        const newInputTokens = existingInputTokens + inputTokenCount;
        const newOutputTokens = existingOutputTokens + outputTokenCount;

        localStorage.setItem(`inputTokens-${currentDate}`, newInputTokens.toString());
        localStorage.setItem(`outputTokens-${currentDate}`, newOutputTokens.toString());

        setTotalInputTokens(newInputTokens);
        setTotalOutputTokens(newOutputTokens);

        if (selectedMode === 'bedrock') {
          localStorage.setItem(`bedrockHistory-${bedrockSessionId}`, JSON.stringify(updatedMessages));
        } else if (selectedMode === 'agents') {
          localStorage.setItem(`agentsHistory-${agentsSessionId}`, JSON.stringify(updatedMessages));
        }
        return updatedMessages;
      }
    });
    scrollToBottom();
  };

  const onClearConversation = () => {
    setMessages([]);
    setKBSessionId('')
    const newSessionId = generateSessionId();
    if (selectedMode === 'bedrock') {
      setBedrockHistory([]);
      const bedrockSessionId = localStorage.getItem('bedrockSessionId');
      localStorage.removeItem(`bedrockHistory-${bedrockSessionId}`);
      setBedrockSessionId(newSessionId);
      localStorage.setItem('bedrockSessionId', newSessionId);
    } else {
      setAgentsHistory([]);
      const agentsSessionId = localStorage.getItem('agentsSessionId');
      localStorage.removeItem(`agentsHistory-${agentsSessionId}`);
      setAgentsSessionId(newSessionId);
      localStorage.setItem('agentsSessionId', newSessionId);
    }

    setPopupMessage('Conversation Cleared');
    setPopupType('success');
    setShowPopup(true);
    setTimeout(() => setShowPopup(false), 3000);
  };

  const scrollToBottom = () => {
    const documentHeight = Math.max(
      document.body.scrollHeight,
      document.documentElement.scrollHeight,
      document.body.offsetHeight,
      document.documentElement.offsetHeight,
      document.body.clientHeight,
      document.documentElement.clientHeight
    );

    window.scrollTo({
      top: documentHeight,
      behavior: 'auto',
    });
  };

  const handleOpenSettingsModal = () => {
    setShowSettingsModal(true);
  };

  const handleCloseSettingsModal = () => {
    setShowSettingsModal(false);
  };

  const handleSaveSettings = (newKnowledgebasesOrAgents) => {
    localStorage.setItem('bedrockKnowledgeBaseID', bedrockKnowledgeBaseID);
    localStorage.setItem('bedrockAgentsID', bedrockAgentsID);
    localStorage.setItem('bedrockAgentsAliasID', bedrockAgentsAliasID);
    localStorage.setItem('knowledgebasesOrAgents', knowledgebasesOrAgents);
    setKnowledgebasesOrAgents(newKnowledgebasesOrAgents);
    handleCloseSettingsModal();
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <div className="app">
        <Header
          disabled={isDisabled || isLoading}
          bedrockSessionId={bedrockSessionId}
          agentsSessionId={agentsSessionId}
          kbSessionId={kbSessionId}
          handleOpenSettingsModal={handleOpenSettingsModal}
          signOut={signOut}
          onClearConversation={onClearConversation}
          timerVisible={!responseCompleted}
          timerValue={elapsedTime}
          selectedMode={selectedMode}
          onModeChange={handleModeChange}
          showPopup={showPopup}
          setShowPopup={setShowPopup}
          popupMessage={popupMessage}
          popupType={popupType}
          totalInputTokens={totalInputTokens}
          totalOutputTokens={totalOutputTokens}
          isLoading={isLoading}
          pricePer1000InputTokens={pricePer1000InputTokens}
          pricePer1000OutputTokens={pricePer1000OutputTokens}
          monthlyInputTokens={monthlyInputTokens}
          monthlyOutputTokens={monthlyOutputTokens}
          knowledgebasesOrAgents={knowledgebasesOrAgents}
          selectedModel={selectedModel}
        />
        <div className="chat-history" ref={chatHistoryRef}>
          <ChatHistory messages={messages} selectedMode={selectedMode} setMessages={setMessages} />
        </div>
        <MessageInput onSend={onSend} disabled={isDisabled || isLoading} /> {/* Disable MessageInput when loading or disabled */}
        {showPopup && <Popup message={popupMessage}
          type={popupType}
          onClose={() => setShowPopup(false)}
          showPopup={showPopup}
          setShowPopup={setShowPopup} />}
        <Suspense fallback={<div>Loading...</div>}>
          <SettingsModal
            open={showSettingsModal}
            onClose={handleCloseSettingsModal}
            onSave={handleSaveSettings}
            bedrockKnowledgeBaseID={bedrockKnowledgeBaseID}
            setBedrockKnowledgeBaseID={setBedrockKnowledgeBaseID}
            bedrockAgentsID={bedrockAgentsID}
            knowledgebasesOrAgents={knowledgebasesOrAgents}
            setBedrockAgentsID={setBedrockAgentsID}
            bedrockAgentsAliasID={bedrockAgentsAliasID}
            setBedrockAgentsAliasID={setBedrockAgentsAliasID}
            setPricePer1000InputTokens={setPricePer1000InputTokens}
            pricePer1000InputTokens={pricePer1000InputTokens}
            setPricePer1000OutputTokens={setPricePer1000OutputTokens}
            pricePer1000OutputTokens={pricePer1000OutputTokens}
            setKnowledgebasesOrAgents={setKnowledgebasesOrAgents}
            user={user}
            websocketUrl={websocketUrl}
            getCurrentSession={getCurrentSession}
            systemPromptUserOrSystem={systemPromptUserOrSystem}
            setSystemPromptUserOrSystem={setSystemPromptUserOrSystem}
            setReloadPromptConfig={setReloadPromptConfig}
            models={models}
            selectedModel={selectedModel}
            setSelectedModel={setSelectedModel}
            setRegion={setRegion}
          />
        </Suspense>
      </div>
    </ThemeProvider>
  );
});

function convertRuleToHuman(jsonArray) {
  return jsonArray.map(item => {
    if (item.rule === 'user') {
      return { ...item, rule: 'Human' };
    } else if (item.rule === 'assistant') {
      return { ...item, rule: 'Assistant' };
    }
    return item;
  });
}

const AuthenticatedApp = withAuthenticator(App);

export default AuthenticatedApp;