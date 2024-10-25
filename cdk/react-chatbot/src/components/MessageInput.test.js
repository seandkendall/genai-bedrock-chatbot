import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MessageInput, { getPlaceholderText, sanitizeFileName } from './MessageInput';

jest.mock('axios');
describe('getPlaceholderText function', () => {
  it('returns default message when no mode is selected', () => {
    const result = getPlaceholderText(null, null);
    expect(result).toBe("Select a Model, Agent, KnowledgeBase or PromptFlow in the Header");
  });

  it('returns default message when selectedMode is empty', () => {
    const result = getPlaceholderText({}, null);
    expect(result).toBe("Select a Model, Agent, KnowledgeBase or PromptFlow in the Header");
  });

  it('returns KB message when Bedrock KnowledgeBases is selected without KB mode', () => {
    const selectedMode = { category: 'Bedrock KnowledgeBases' };
    const result = getPlaceholderText(selectedMode, null);
    expect(result).toBe("Select a Model for your KnowledgeBase in the Header");
  });

  it('returns default input message for other cases', () => {
    const selectedMode = { category: 'Other' };
    const result = getPlaceholderText(selectedMode, {});
    expect(result).toBe("Type your message...");
  });
});

describe('sanitizeFileName function', () => {
  it('removes special characters and spaces from filename', () => {
    const result = sanitizeFileName('My File Name!@#.txt');
    expect(result).toMatch(/^[a-z0-9]{6}-MyFileName\.txt$/);
  });

  it('preserves allowed special characters', () => {
    const result = sanitizeFileName('File-Name_(1)[2].pdf');
    expect(result).toMatch(/^[a-z0-9]{6}-[a-zA-Z0-9_\-()[\]]+\.[a-zA-Z]{3}$/);
  });

  it('handles filenames without extensions', () => {
    const result = sanitizeFileName('NoExtensionFile');
    expect(result).toMatch(/^[a-z0-9]{6}-[a-zA-Z0-9_\-()[\]]+\.[a-zA-Z]{3}$/);
  });

  it('handles filenames with multiple dots', () => {
    const result = sanitizeFileName('file.name.with.dots.txt');
    expect(result).toMatch(/^[a-z0-9]{6}-filenamewithdots\.txt$/);
  });

  it('generates different prefixes for each call', () => {
    const result1 = sanitizeFileName('test.txt');
    const result2 = sanitizeFileName('test.txt');
    expect(result1).not.toBe(result2);
  });
});

describe('MessageInput Component', () => {
  const mockOnSend = jest.fn();
  const mockGetCurrentSession = jest.fn(() => Promise.resolve({ accessToken: 'mockToken', idToken: 'mockIdToken' }));

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the input field and buttons', () => {
    render(<MessageInput onSend={jest.fn()} getCurrentSession={jest.fn()} selectedMode={{}} />);

    expect(screen.getByRole('textbox')).toBeInTheDocument();
    expect(screen.getByLabelText('Attach file')).toBeInTheDocument();
    expect(screen.getByLabelText('Send message')).toBeInTheDocument();
  });

  it('disables input and buttons when disabled prop is true', () => {
    render(<MessageInput onSend={jest.fn()} disabled={true} getCurrentSession={jest.fn()} selectedMode={{}} />);

    expect(screen.getByRole('textbox')).toBeDisabled();
    expect(screen.getByLabelText('Attach file')).toBeDisabled();
    expect(screen.getByLabelText('Send message')).toBeDisabled();
  });

  it('allows typing in the input field', async () => {
    render(<MessageInput onSend={mockOnSend} getCurrentSession={mockGetCurrentSession} selectedMode={{}} />);

    const input = screen.getByRole('textbox');
    await userEvent.type(input, 'Hello, world!');

    expect(input).toHaveValue('Hello, world!');
  });

  it('calls onSend when send button is clicked', async () => {
    render(<MessageInput onSend={mockOnSend} getCurrentSession={mockGetCurrentSession} selectedMode={{}} />);

    const input = screen.getByRole('textbox');
    await userEvent.type(input, 'Test message');

    const sendButton = screen.getByLabelText('Send message');
    await userEvent.click(sendButton);

    expect(mockOnSend).toHaveBeenCalledWith('Test message', []);
  });
});