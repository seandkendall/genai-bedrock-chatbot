import { marked } from 'marked';
import { websocketUrl } from './variables.js';
import React, { useState, useEffect, useRef, memo, lazy, Suspense } from 'react';
import DOMPurify from 'dompurify';
import Header from './components/Header';
import ChatHistory from './components/ChatHistory';
import MessageInput from './components/MessageInput';
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
  'mistral.mistral-large-2402-v1:0': {
    pricePer1000InputTokens: 0.004,
    pricePer1000OutputTokens: 0.012,
  },
  'mistral.mistral-large-2407-v1:0': {
    pricePer1000InputTokens: 0.003,
    pricePer1000OutputTokens: 0.009,
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
  const [selectedMode, setSelectedMode] = useState(null);
  const [responseCompleted, setResponseCompleted] = useState(true);
  const chatHistoryRef = useRef(null);
  // const { elapsedTime, startTimer, stopTimer, resetTimer } = useTimer();
  const [showPopup, setShowPopup] = useState(false);
  const [popupMessage, setPopupMessage] = useState('');
  const [popupType, setPopupType] = useState('success');
  const [chatHistory, setChatHistory] = useState([]);
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
  
  // Lists of models, KBs, Agents, prompt flows
  const [bedrockAgents, setBedrockAgents] = useState([]);
  const [bedrockKnowledgeBases, setBedrockKnowledgeBases] = useState([]);
  const [models, setModels] = useState([]);
  const [imageModels, setImageModels] = useState([]);
  const [promptFlows, setPromptFlows] = useState([]);
  
  const [appSessionid, setAppSessionId] = useState('');
  const [kbSessionId, setKBSessionId] = useState('');
  const [systemPromptUserOrSystem, setSystemPromptUserOrSystem] = useState('system');
  const [usedModel, setUsedModel] = useState('');
  const [region, setRegion] = useState(null);
  const [stylePreset, setStylePreset] = useState('photographic');
  const [heightWidth, setHeightWidth] = useState('1024x1024');

  const [selectedKbMode, onSelectedKbMode] = useState(null);



  // Use the useWebSocket hook to manage the WebSocket connection
  // eslint-disable-next-line
  const { sendMessage, lastMessage, readyState } = useWebSocket(websocketUrl, {
    shouldReconnect: (closeEvent) => true, // Automatically reconnect on close
    reconnectInterval: 3000, // Reconnect every 3 seconds
  });

  

  useEffect(() => {
    loadConfigSubaction('load_models,load_prompt_flows,load_knowledge_bases,load_agents');
  },[]);

  // Add this function to update the prices based on the selected model
  const updatePricesFromModel = () => {
    if (selectedMode && selectedMode.model && selectedMode.modelId) {
      const modelId = selectedMode && selectedMode.model && selectedMode.modelId;
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
    updatePricesFromModel()
  },[selectedMode]);
  

  
  useEffect(() => {
    const kbSessionId = localStorage.getItem(`kbSessionId`);
    setKBSessionId(kbSessionId)
    const storedPricePer1000InputTokens = localStorage.getItem(`pricePer1000InputTokens`);
    setPricePer1000InputTokens(storedPricePer1000InputTokens);
    const storedPricePer1000OutputTokens = localStorage.getItem(`pricePer1000OutputTokens`);
    setPricePer1000OutputTokens(storedPricePer1000OutputTokens);
    
    const currentDate = new Date().toDateString();
    const storedInputTokens = isValidJSON(localStorage.getItem(`inputTokens-${currentDate}`))
      ? JSON.parse(localStorage.getItem(`inputTokens-${currentDate}`))
      : 0;
    const storedOutputTokens = isValidJSON(localStorage.getItem(`outputTokens-${currentDate}`))
      ? JSON.parse(localStorage.getItem(`outputTokens-${currentDate}`))
      : 0;

    setTotalInputTokens(storedInputTokens);
    setTotalOutputTokens(storedOutputTokens);
  }, []);

  const isValidJSON = (str) => {
    try {
      JSON.parse(str);
    } catch (e) {
      return false;
    }
    return true;
  };

  const handleModeChange = (newMode) => {
    setMessages([]);
    setSelectedMode(newMode);
    scrollToBottom();
  };

  const loadConfigSubaction = async (subaction) => {
    const { accessToken, idToken } = await getCurrentSession()
    const data = {
      action: 'config',
      subaction: subaction,
      idToken: idToken + '',
      accessToken: accessToken + '',
    };
    sendMessage(JSON.stringify(data));
  }

  const loadConversationHistory = async (sessId) => {
    if (models && selectedMode && (appSessionid || sessId)){
      const { accessToken, idToken } = await getCurrentSession()
      const data = {
        type: 'load',
        session_id: sessId? sessId : appSessionid,
        kb_session_id: kbSessionId,
        selectedMode: selectedMode,
        idToken: idToken + '',
        accessToken: accessToken + '',
      };
      sendMessage(JSON.stringify(data));
    }
  };

  const clearConversationHistory = async () => {
    if (models && selectedMode && appSessionid){
      const { accessToken, idToken } = await getCurrentSession()
      const data = {
        type: 'clear_conversation',
        session_id: appSessionid,
        kb_session_id: kbSessionId,
        selectedMode: selectedMode,
        idToken: idToken + '',
        accessToken: accessToken + '',
      };
      sendMessage(JSON.stringify(data));
    }
  };
  
  function mergeMessages(existingMessages, newMessages) {
    const mergedMessages = [...existingMessages];
  
    for (const newMessage of newMessages) {
      const existingMessageIndex = mergedMessages.findIndex(
        (message) =>
          message.message_id === newMessage.message_id ||
          (newMessage.message_id && !message.message_id)
      );
  
      if (existingMessageIndex === -1) {
        mergedMessages.push(newMessage);
      } else {
        mergedMessages[existingMessageIndex] = {
          ...mergedMessages[existingMessageIndex],
          ...newMessage,
        };
      }
    }
  
    return mergedMessages;
  }

  useEffect(() => {
    if (lastMessage !== null) {
      const message = JSON.parse(lastMessage.data);
      if (message.type === 'conversation_history') {
        const messageChunk = convertRuleToHuman(JSON.parse(message.chunk));
        setMessages((prevMessages) => mergeMessages(prevMessages?prevMessages:[], messageChunk));
      }
    }
  }, [lastMessage, sendMessage]);

  const handleError = (errormessage) => {
    let popupMsg = 'Sorry, We encountered an issue, Please try resubmitting your message.'
    if (errormessage.includes('allow-listed') || errormessage.includes('You have not requested access to a model in Bedrock')) {
      popupMsg = errormessage
    } else if (errormessage.includes('throttlingException')) {
      popupMsg = 'Sorry, We encountered a Throttling issue, Please try resubmitting your message.'
    } else if (errormessage.includes('AUP or AWS Responsible AI')) {
      popupMsg = 'This request has been blocked by our content filters because the generated image(s) may conflict our AUP or AWS Responsible AI Policy. please try again'
    } 
    setIsDisabled(false);
    // stopTimer();
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
    // resetTimer();
    // startTimer();

    const sanitizedMessage = DOMPurify.sanitize(message);
    // generate random 8 character alpha/numeric message id
    const randomMessageId = Math.random().toString(36).substring(2, 10);
    if (selectedMode.category === 'Bedrock Image Models') {
      generateImage(sanitizedMessage,randomMessageId);
      return;
    }

    const { accessToken, idToken } = await getCurrentSession()
    const message_timestamp = new Date().toISOString();
    const data = {
      prompt: sanitizedMessage,
      message_id: randomMessageId,
      timestamp: message_timestamp,
      session_id: appSessionid,
      kb_session_id: kbSessionId,
      selectedMode: selectedMode,
      idToken: idToken + '',
      accessToken: accessToken + '',
      reloadPromptConfig: reloadPromptConfig,
      systemPromptUserOrSystem: systemPromptUserOrSystem
    };
    if(selectedMode.knowledgeBaseId){
      //add selectedKbMode to data
      data.selectedKbMode = selectedKbMode;
    }
    const messageWithTime = {
      role: 'user',
      content: message,
      message_id: randomMessageId,
      timestamp: message_timestamp,
    };
    setMessages((prevMessages) => [
      ...prevMessages? prevMessages: [],
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
  };

  const generateImage = async (prompt, randomMessageId) => {
    setIsDisabled(true);
    setResponseCompleted(false);
    setIsLoading(true);
    // resetTimer();
    // startTimer();
  
    const { accessToken, idToken } = await getCurrentSession();
    const message_timestamp = new Date().toISOString()
    const data = {
      prompt: prompt,
      message_id: randomMessageId,
      timestamp: message_timestamp,
      session_id: appSessionid,
      selectedMode: selectedMode,
      idToken: idToken + '',
      accessToken: accessToken + '',
      stylePreset: stylePreset,
      heightWidth: heightWidth,
    };
  
    const currentTime = new Date();
    const messageWithTime = {
      role: 'user',
      content: `Generating Image of: ${prompt}`,
      message_id: randomMessageId,
      timestamp: currentTime.toISOString()
    };
    setMessages((prevMessages) => [
      ...prevMessages? prevMessages: [],
      messageWithTime,
      {
        role: 'assistant',
        content: `Generating Image of: *${prompt}* with model: *${selectedMode.modelName}*. Please wait..`,
        isStreaming: true,
        timestamp: null,
        model: selectedMode.modelName,
        isImage: false,
        imageAlt: prompt
      },
    ]);
  
    scrollToBottom();
  
    sendMessage(JSON.stringify(data));
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
        updateMessagesOnStop({});
        handleError(message.error || message.message);
        setIsDisabled(false);
        setResponseCompleted(true);
        setIsLoading(false);
        scrollToBottom();
      } else if (message.type === 'image_generated') {
        setMessages((prevMessages) => {
          const updatedMessages = [...prevMessages? prevMessages: []];
          const lastIndex = updatedMessages.length - 1;
          updatedMessages[lastIndex] = {
            ...updatedMessages[lastIndex],
            content: message.image_url,
            prompt: message.prompt,
            message_id: message.message_id,
            isStreaming: false,
            isImage: true,
            model: message.modelId,
            outputTokenCount: 0,
            inputTokenCount: 0,
            timestamp: message.timestamp
          };
          return updatedMessages;
        });
      } else if (message.type === 'load_response') {
        if(message.load_models)
          if(message.load_models.text_models)
            setModels(message.load_models.text_models)
          if(message.load_models.image_models)
            setImageModels(message.load_models.image_models)
        if(message.load_knowledge_bases && message.load_knowledge_bases.knowledge_bases)
          setBedrockKnowledgeBases(message.load_knowledge_bases.knowledge_bases)
        if(message.load_agents && message.load_agents.agents)
          setBedrockAgents(message.load_agents.agents)
        if(message.load_prompt_flows && message.load_prompt_flows.prompt_flows)
          setPromptFlows(message.load_prompt_flows.prompt_flows)
      } else if (message.type === 'conversation_history') {
        // Do nothing, UseEffect will handle this 
      } else {
        if (typeof message === 'object' && message !== null) {
          const messageString = JSON.stringify(message);
          if (!messageString.includes('Message Received')) {
            console.log('Uncaught String Message 1:');
            console.log(messageString);
          }
        } else if (typeof message === 'string') {
          if (!message.includes('Message Received')) {
            console.log('Uncaught String Message 2:');
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
    //if message starts with the text "\nBot: " then strip this from the message
    if (message && message.delta && message.delta.text && message.delta.text.startsWith('\nBot: ')) {
      message.delta.text = message.delta.text.substring(6);
    }
    if (message && message.delta && message.delta.text) {
      setMessages((prevMessages) => {

        const updatedMessages = [...prevMessages? prevMessages: []];
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
      const updatedMessages = [...prevMessages? prevMessages: []];
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
        // console.log('inputTokens:', inputTokenCount)
        // console.log('outputTokens:', outputTokenCount)

        updatedMessages[lastIndex] = {
          ...updatedMessages[lastIndex],
          isStreaming: false,
          timestamp: new Date().toISOString(),
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
        
        localStorage.setItem(`chatHistory-${appSessionid}`, JSON.stringify(updatedMessages));
        return updatedMessages;
      }
    });
    scrollToBottom();
  };

  const onClearConversation = () => {
    setMessages([]);
    clearConversationHistory()
    setKBSessionId('')
    localStorage.removeItem('kbSessionId');
    localStorage.removeItem(`chatHistory-${appSessionid}`)
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

  const handleSaveSettings = () => {
    handleCloseSettingsModal();
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <div className="app">
        <Header
          disabled={isDisabled || isLoading}
          appSessionid={appSessionid}
          kbSessionId={kbSessionId}
          setKBSessionId={setKBSessionId}
          handleOpenSettingsModal={handleOpenSettingsModal}
          signOut={signOut}
          onClearConversation={onClearConversation}
          selectedMode={selectedMode}
          onModeChange={handleModeChange}
          showPopup={showPopup}
          setShowPopup={setShowPopup}
          popupMessage={popupMessage}
          popupType={popupType}
          totalInputTokens={totalInputTokens}
          totalOutputTokens={totalOutputTokens}
          pricePer1000InputTokens={pricePer1000InputTokens}
          pricePer1000OutputTokens={pricePer1000OutputTokens}
          monthlyInputTokens={monthlyInputTokens}
          monthlyOutputTokens={monthlyOutputTokens}
          bedrockAgents={bedrockAgents}
          bedrockKnowledgeBases={bedrockKnowledgeBases}
          models={models}
          imageModels={imageModels}
          promptFlows={promptFlows}
          selectedKbMode={selectedKbMode}
          onSelectedKbMode={onSelectedKbMode}
        />
        <div className="chat-history" ref={chatHistoryRef}>
          <ChatHistory user={user} messages={messages} selectedMode={selectedMode} setMessages={setMessages} appSessionid={appSessionid} setAppSessionId={setAppSessionId} loadConversationHistory={loadConversationHistory} />
        </div>
        <MessageInput onSend={onSend} disabled={isDisabled || isLoading} selectedMode={selectedMode} selectedKbMode={selectedKbMode} /> 
        {showPopup && <Popup message={popupMessage}
          type={popupType}
          onClose={() => setShowPopup(false)}
          showPopup={showPopup}
          setShowPopup={setShowPopup} />}
        <Suspense fallback={<div>Loading...</div>}>
          <SettingsModal
            onClose={handleCloseSettingsModal}
            onSave={handleSaveSettings}
            showSettingsModal={showSettingsModal}
            setPricePer1000InputTokens={setPricePer1000InputTokens}
            pricePer1000InputTokens={pricePer1000InputTokens}
            setPricePer1000OutputTokens={setPricePer1000OutputTokens}
            pricePer1000OutputTokens={pricePer1000OutputTokens}
            user={user}
            websocketUrl={websocketUrl}
            getCurrentSession={getCurrentSession}
            systemPromptUserOrSystem={systemPromptUserOrSystem}
            setSystemPromptUserOrSystem={setSystemPromptUserOrSystem}
            setReloadPromptConfig={setReloadPromptConfig}
            setRegion={setRegion}
            stylePreset={stylePreset}
            setStylePreset={setStylePreset}
            heightWidth={heightWidth}
            setHeightWidth={setHeightWidth}
            onModeChange={handleModeChange}
            selectedMode={selectedMode}
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