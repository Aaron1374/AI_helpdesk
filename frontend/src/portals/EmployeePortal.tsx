import React, { useState } from 'react';
import { ApiError, createConversation, sendMessage } from '../api/client';
import type { WorkflowState } from '../api/types';

export const EmployeePortal: React.FC = () => {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<{sender: string, content: string}[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState('');
  const [activity, setActivity] = useState<string[]>([]);

  const handleSend = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const currentInput = input.trim();
    if (!currentInput || isSending) return;

    setError('');
    setIsSending(true);
    setMessages(prev => [...prev, { sender: 'USER', content: currentInput }]);
    setInput('');

    try {
      const activeConversationId = conversationId ?? (await createConversation()).id;
      if (!conversationId) setConversationId(activeConversationId);
      const response = await sendMessage(activeConversationId, currentInput);
      setMessages(prev => [...prev, ...response.messages]);
      setActivity(buildActivity(response.state));
      if (response.status === 'human_takeover' || response.state?.status === 'human_takeover') {
        setMessages(prev => [...prev, { sender: 'SYSTEM', content: 'An engineer has taken over this conversation. Please wait for their response.' }]);
      }
    } catch (requestError) {
      setMessages(prev => prev.slice(0, -1));
      setInput(currentInput);
      setError(requestError instanceof ApiError ? requestError.message : 'Unable to send your request.');
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="portal">
      <header className="page-heading">
        <p className="eyebrow">Employee support</p>
        <h1>How can we help today?</h1>
        <p className="page-subtitle">Describe the problem in your own words and we will guide you to a resolution.</p>
      </header>
      {error && <div className="is-error" role="alert">{error}</div>}
      <div className="chat-window">
        {messages.length === 0 ? (
          <div className="empty-state">
            <span className="empty-state-icon" aria-hidden="true">?</span>
            <strong>Start with a short description</strong>
            <span>For example: “My VPN stopped connecting this morning.”</span>
          </div>
        ) : messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.sender.toLowerCase()}`}>
            <span className="message-label">{msg.sender}</span>
            <span>{msg.content}</span>
          </div>
        ))}
      </div>
      {activity.length > 0 && (
        <section className="activity-panel" aria-label="Agent activity">
          <div className="activity-heading">
            <span className="activity-dot" aria-hidden="true" />
            <strong>Agent activity</strong>
          </div>
          <ol className="activity-list">
            {activity.map((item) => <li key={item}>{item}</li>)}
          </ol>
        </section>
      )}
      <form className="input-area" onSubmit={handleSend}>
        <input 
          className="text-field"
          value={input} 
          onChange={(e) => setInput(e.target.value)} 
          placeholder="Describe your issue..." 
          disabled={isSending}
        />
        <button className="primary-button" type="submit" disabled={isSending || !input.trim()}>
          {isSending ? 'Working...' : 'Send message'}
        </button>
      </form>
    </div>
  );
};

function buildActivity(state?: WorkflowState): string[] {
  if (!state) return [];
  const items = ['Request received and workflow completed.'];
  if (state.category) items.push(`Classified as ${formatLabel(state.category)}.`);
  if (state.tool_history?.length) items.push(`Diagnostic tools used: ${state.tool_history.join(', ')}.`);
  if (state.evidence?.length) items.push(`${state.evidence.length} evidence item(s) collected.`);
  if (state.escalate || state.status === 'human_takeover') items.push('Escalation policy transferred the conversation to a human engineer.');
  if (state.status && state.status !== 'human_takeover') items.push(`Workflow status: ${formatLabel(state.status)}.`);
  return items;
}

function formatLabel(value: string): string {
  return value.split('_').join(' ');
}
