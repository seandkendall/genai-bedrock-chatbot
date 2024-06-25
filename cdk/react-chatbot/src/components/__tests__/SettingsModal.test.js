import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import SettingsModal from '../SettingsModal';

// Mock dependencies and props
jest.mock('react-use-websocket', () => ({
  __esModule: true,
  default: () => ({
    sendMessage: jest.fn(),
    lastMessage: null,
  }),
}));

const mockProps = {
  open: true,
  onClose: jest.fn(),
  onSave: jest.fn(),
  bedrockKnowledgeBaseID: '',
  setBedrockKnowledgeBaseID: jest.fn(),
  bedrockAgentsID: '',
  setBedrockAgentsID: jest.fn(),
  bedrockAgentsAliasID: '',
  setBedrockAgentsAliasID: jest.fn(),
  setPricePer1000InputTokens: jest.fn(),
  pricePer1000InputTokens: '',
  setPricePer1000OutputTokens: jest.fn(),
  pricePer1000OutputTokens: '',
  knowledgebasesOrAgents: 'knowledgeBases',
  setKnowledgebasesOrAgents: jest.fn(),
  user: { username: 'testUser' },
  websocketUrl: 'ws://localhost:8000',
  getCurrentSession: jest.fn(),
  systemPromptUserOrSystem: 'system',
  setSystemPromptUserOrSystem: jest.fn(),
  setReloadPromptConfig: jest.fn(),
  models: [
    { modelId: 'model1', providerName: 'Provider 1', modelName: 'Model 1' },
    { modelId: 'model2', providerName: 'Provider 2', modelName: 'Model 2' },
  ],
  selectedModel: null,
  setSelectedModel: jest.fn(),
  setRegion: jest.fn(),
};

describe('SettingsModal', () => {
  test('renders without crashing', () => {
    render(<SettingsModal {...mockProps} />);
  });

  test('calls onClose when Cancel button is clicked', () => {
    render(<SettingsModal {...mockProps} />);
    const cancelButton = screen.getByText('Cancel');
    fireEvent.click(cancelButton);
    expect(mockProps.onClose).toHaveBeenCalled();
  });

  // Add more tests for other functionality
});