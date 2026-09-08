import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  ApiError,
  createConversation,
  sendMessage,
  getConversationMessages,
  getConversations,
  closeConversation,
} from '../api/client';
import type { WorkflowState, ChatMessageRecord, ConversationItem } from '../api/types';

export const EmployeePortal: React.FC = () => {
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(() => {
    const stored = sessionStorage.getItem('employee_active_conv');
    return stored === 'new' ? null : stored;
  });
  const [messages, setMessages] = useState<ChatMessageRecord[]>([]);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isClosing, setIsClosing] = useState(false);
  const [isLoadingList, setIsLoadingList] = useState(false);
  const [error, setError] = useState('');
  const [activity, setActivity] = useState<string[]>([]);
  const [isHumanTakeover, setIsHumanTakeover] = useState(false);

  const chatWindowRef = useRef<HTMLDivElement | null>(null);
  const prevCountRef = useRef<number>(0);

  const scrollToBottom = (smooth = false) => {
    if (chatWindowRef.current) {
      if (smooth) {
        chatWindowRef.current.scrollTo({
          top: chatWindowRef.current.scrollHeight,
          behavior: 'smooth',
        });
      } else {
        chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight;
      }
    }
  };

  // 1. Fetch user's past conversations
  const loadConversations = useCallback(async (quiet = false) => {
    if (!quiet) setIsLoadingList(true);
    try {
      const list = await getConversations();
      setConversations(list);

      const stored = sessionStorage.getItem('employee_active_conv');
      if (stored === 'new') {
        setActiveConversationId(null);
      } else if (stored) {
        const found = list.find((c) => c.id === stored);
        if (found) {
          setActiveConversationId(found.id);
        } else {
          const openConv = list.find((c) => c.status !== 'CLOSED' && c.ticket_status !== 'CLOSED');
          if (openConv) {
            setActiveConversationId(openConv.id);
            sessionStorage.setItem('employee_active_conv', openConv.id);
          } else {
            setActiveConversationId(null);
            sessionStorage.setItem('employee_active_conv', 'new');
          }
        }
      } else {
        const openConv = list.find((c) => c.status !== 'CLOSED' && c.ticket_status !== 'CLOSED');
        if (openConv) {
          setActiveConversationId(openConv.id);
          sessionStorage.setItem('employee_active_conv', openConv.id);
        } else {
          setActiveConversationId(null);
          sessionStorage.setItem('employee_active_conv', 'new');
        }
      }
    } catch {
      // Non-blocking
    } finally {
      if (!quiet) setIsLoadingList(false);
    }
  }, []);

  useEffect(() => {
    loadConversations();
    const interval = setInterval(() => {
      if (!document.hidden) loadConversations(true);
    }, 8000);
    return () => clearInterval(interval);
  }, [loadConversations]);

  // 2. Fetch messages for selected conversation
  useEffect(() => {
    if (!activeConversationId) {
      setMessages([]);
      setIsHumanTakeover(false);
      prevCountRef.current = 0;
      return;
    }

    let isMounted = true;
    const fetchLatest = async () => {
      try {
        const history = await getConversationMessages(activeConversationId);
        if (isMounted) {
          setMessages(history);
          const hasEngineerMsg = history.some(
            (m) => m.sender_type === 'SYSTEM' || m.content.startsWith('[Engineer]')
          );
          setIsHumanTakeover(hasEngineerMsg);
        }
      } catch {
        // Non-blocking
      }
    };

    fetchLatest();
    const interval = setInterval(() => {
      if (!document.hidden) fetchLatest();
    }, 4000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [activeConversationId]);

  // Handle internal chat container scrolling when messages change
  useEffect(() => {
    if (messages.length !== prevCountRef.current) {
      const isFirstLoad = prevCountRef.current === 0;
      prevCountRef.current = messages.length;
      if (isFirstLoad) {
        scrollToBottom(false);
      } else if (chatWindowRef.current) {
        const { scrollTop, scrollHeight, clientHeight } = chatWindowRef.current;
        const isNearBottom = scrollHeight - scrollTop - clientHeight < 150;
        if (isNearBottom) {
          scrollToBottom(true);
        }
      }
    }
  }, [messages]);

  const handleSelectConversation = (convId: string) => {
    setActiveConversationId(convId);
    sessionStorage.setItem('employee_active_conv', convId);
    setActivity([]);
    setError('');
    prevCountRef.current = 0;
  };

  const handleNewChat = () => {
    setActiveConversationId(null);
    sessionStorage.setItem('employee_active_conv', 'new');
    setMessages([]);
    setActivity([]);
    setError('');
    prevCountRef.current = 0;
  };

  const handleEndConversation = async () => {
    if (!activeConversationId || isClosing) return;
    if (!window.confirm('Are you sure you want to end this support conversation?')) return;

    setIsClosing(true);
    setError('');
    try {
      await closeConversation(activeConversationId);
      const updated = await getConversationMessages(activeConversationId);
      setMessages(updated);
      await loadConversations(true);
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : 'Unable to end conversation.');
    } finally {
      setIsClosing(false);
    }
  };

  const handleSend = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const currentInput = input.trim();
    if (!currentInput || isSending) return;

    setError('');
    setIsSending(true);
    setInput('');

    try {
      let targetConvId = activeConversationId;
      if (!targetConvId) {
        const newConv = await createConversation();
        targetConvId = newConv.id;
        setActiveConversationId(newConv.id);
        sessionStorage.setItem('employee_active_conv', newConv.id);
      }

      const response = await sendMessage(targetConvId, currentInput);
      setActivity(buildActivity(response.state));
      if (response.status === 'human_takeover' || response.state?.status === 'human_takeover') {
        setIsHumanTakeover(true);
      }

      // Refresh messages & conversation list
      const updated = await getConversationMessages(targetConvId);
      setMessages(updated);
      await loadConversations(true);
    } catch (requestError) {
      setInput(currentInput);
      setError(requestError instanceof ApiError ? requestError.message : 'Unable to send your request.');
    } finally {
      setIsSending(false);
    }
  };

  const getStatusBadge = (conv: ConversationItem) => {
    if (conv.status === 'CLOSED' || conv.ticket_status === 'CLOSED') {
      return <span className="status-badge badge-closed">Closed</span>;
    }
    const status = (conv.ticket_status || conv.status || 'ACTIVE').toUpperCase();
    switch (status) {
      case 'RESOLVED':
        return <span className="status-badge badge-resolved">Resolved</span>;
      case 'IN_PROGRESS':
        return <span className="status-badge badge-in-progress">In Progress</span>;
      case 'ESCALATED':
        return <span className="status-badge badge-escalated">Escalated</span>;
      default:
        return <span className="status-badge badge-new">{conv.owner_type === 'HUMAN' ? 'Support' : 'AI Active'}</span>;
    }
  };

  const activeConvDetails = conversations.find((c) => c.id === activeConversationId);
  const isCurrentConvClosed = activeConvDetails?.status === 'CLOSED' || activeConvDetails?.ticket_status === 'CLOSED';

  return (
    <div className="portal">
      <header className="page-heading" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <p className="eyebrow">Employee support</p>
          <h1>How can we help today?</h1>
          <p className="page-subtitle">Describe the problem in your own words and our AI assistant or engineer will assist you.</p>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          {activeConversationId && !isCurrentConvClosed && (
            <button
              type="button"
              className="danger-button"
              onClick={handleEndConversation}
              disabled={isClosing}
              title="End this active conversation"
            >
              {isClosing ? 'Ending...' : 'End Conversation'}
            </button>
          )}
          {activeConversationId && (
            <button
              type="button"
              className="secondary-button"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
              onClick={handleNewChat}
            >
              + Start New Chat
            </button>
          )}
        </div>
      </header>

      {error && <div className="is-error" role="alert" style={{ marginBottom: '1rem' }}>{error}</div>}

      {isHumanTakeover && !isCurrentConvClosed && (
        <div className="is-success" role="status" style={{ marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: 'var(--teal)' }} />
          An L1 Support Engineer is in the chat and assisting you live.
        </div>
      )}

      {/* Main Single-Column Chat Window */}
      <div className="chat-window" ref={chatWindowRef}>
        {activeConvDetails && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '12px', borderBottom: '1px solid var(--line)', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--ink)' }}>
              {activeConvDetails.title}
            </span>
            <div>{getStatusBadge(activeConvDetails)}</div>
          </div>
        )}

        {messages.length === 0 ? (
          <div className="empty-state">
            <span className="empty-state-icon" aria-hidden="true">?</span>
            <strong>Start with a short description</strong>
            <span>For example: “My VPN stopped connecting this morning.” or “I have no sound on my laptop.”</span>
          </div>
        ) : (
          messages.map((msg, idx) => {
            const isEngineer = msg.sender_type === 'SYSTEM' || msg.content.startsWith('[Engineer]');
            const isUser = msg.sender_type === 'USER';
            const messageClass = isEngineer ? 'support' : isUser ? 'user' : 'ai';
            const label = isEngineer ? 'Support Engineer' : isUser ? 'You' : 'AI Helpdesk';

            return (
              <div key={msg.id || idx} className={`message ${messageClass}`}>
                <span className="message-label">{label}</span>
                <span style={{ whiteSpace: 'pre-wrap' }}>
                  {isEngineer && msg.content.startsWith('[Engineer] ')
                    ? msg.content.replace('[Engineer] ', '')
                    : msg.content}
                </span>
              </div>
            );
          })
        )}
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

      {isCurrentConvClosed ? (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', background: '#f8fafc', border: '1px solid var(--line)', borderRadius: '8px', marginTop: '14px', flexWrap: 'wrap', gap: '10px' }}>
          <span style={{ fontSize: '0.9rem', color: 'var(--muted)' }}>
            This conversation has been ended. You can review the messages above or start a new request.
          </span>
          <button type="button" className="primary-button" onClick={handleNewChat}>
            + Start New Chat
          </button>
        </div>
      ) : (
        <form className="input-area" onSubmit={handleSend}>
          <input
            className="text-field"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              isHumanTakeover
                ? 'Type your reply to the engineer...'
                : activeConversationId
                ? 'Reply or ask a follow-up question...'
                : 'Describe your issue...'
            }
            disabled={isSending}
          />
          <button
            className="primary-button"
            type="submit"
            disabled={isSending || !input.trim()}
          >
            {isSending ? 'Sending...' : 'Send message'}
          </button>
        </form>
      )}

      {/* History Section Down Below */}
      <section className="history-section" aria-label="Conversation History">
        <div className="history-header">
          <div>
            <h2>Past Conversations</h2>
            <p style={{ margin: '4px 0 0', fontSize: '0.9rem', color: 'var(--muted)' }}>
              Click any past chat to view its message history and status.
            </p>
          </div>
          <button
            type="button"
            className="primary-button"
            style={{ fontSize: '0.85rem', padding: '8px 16px', minHeight: 'auto' }}
            onClick={handleNewChat}
          >
            + New Request
          </button>
        </div>

        {isLoadingList && conversations.length === 0 ? (
          <div className="empty-state panel-empty" style={{ minHeight: '140px' }}>
            <span>Loading your past conversations...</span>
          </div>
        ) : conversations.length === 0 ? (
          <div className="empty-state panel-empty" style={{ minHeight: '140px' }}>
            <strong>No past conversations</strong>
            <span>Your support requests will appear here.</span>
          </div>
        ) : (
          <div className="history-grid">
            {conversations.map((conv) => (
              <div
                key={conv.id}
                className={`history-card ${activeConversationId === conv.id ? 'is-active' : ''}`}
                onClick={() => handleSelectConversation(conv.id)}
                role="button"
                tabIndex={0}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
                  <div className="history-card-title">{conv.title}</div>
                  {getStatusBadge(conv)}
                </div>
                <div className="history-card-preview">{conv.preview}</div>
                <div className="history-card-footer">
                  <span>{conv.message_count} {conv.message_count === 1 ? 'message' : 'messages'}</span>
                  <span>{conv.created_at ? new Date(conv.created_at).toLocaleDateString() : ''}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
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
