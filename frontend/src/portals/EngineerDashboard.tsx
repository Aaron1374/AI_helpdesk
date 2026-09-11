import React, { useState, useEffect, useRef, useCallback } from 'react';
import { MarkdownRenderer } from '../components/MarkdownRenderer';
import {
  getTickets,
  getSimilarTickets,
  getConversationMessages,
  takeoverConversation,
  resolveTicket,
  sendMessage,
  ApiError,
} from '../api/client';
import type { TicketItem, SimilarIncident, ChatMessageRecord } from '../api/types';

export const EngineerDashboard: React.FC = () => {
  const [tickets, setTickets] = useState<TicketItem[]>([]);
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [conversationMessages, setConversationMessages] = useState<ChatMessageRecord[]>([]);
  const [similarTickets, setSimilarTickets] = useState<Record<string, SimilarIncident[]>>({});
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [replyInput, setReplyInput] = useState<string>('');
  const [isSending, setIsSending] = useState<boolean>(false);
  const [isActionLoading, setIsActionLoading] = useState<boolean>(false);

  const consoleBodyRef = useRef<HTMLDivElement | null>(null);

  const selectedTicket = tickets.find((t) => t.id === selectedTicketId) ?? null;

  const scrollToBottom = (smooth = false) => {
    if (consoleBodyRef.current) {
      if (smooth) {
        consoleBodyRef.current.scrollTo({
          top: consoleBodyRef.current.scrollHeight,
          behavior: 'smooth',
        });
      } else {
        consoleBodyRef.current.scrollTop = consoleBodyRef.current.scrollHeight;
      }
    }
  };

  // Load ticket list
  const loadTickets = useCallback(async (quiet = false) => {
    if (!quiet) setIsLoading(true);
    try {
      const ticketList = await getTickets();
      setTickets(ticketList);
      if (ticketList.length > 0 && !selectedTicketId) {
        setSelectedTicketId(ticketList[0].id);
      }
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        setError('Access restricted: An engineer or support role is required to view the Engineer Dashboard.');
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to load tickets.');
      }
    } finally {
      if (!quiet) setIsLoading(false);
    }
  }, [selectedTicketId]);

  // Initial load and periodic ticket list sync
  useEffect(() => {
    loadTickets();
    const interval = setInterval(() => {
      if (!document.hidden) loadTickets(true);
    }, 7000);
    return () => clearInterval(interval);
  }, [loadTickets]);

  // Load messages & similar tickets for selected ticket
  useEffect(() => {
    if (!selectedTicket || !selectedTicket.conversation_id) {
      setConversationMessages([]);
      return;
    }

    let isMounted = true;
    const convId = selectedTicket.conversation_id;

    const fetchMessages = async () => {
      try {
        const msgs = await getConversationMessages(convId);
        if (isMounted) setConversationMessages(msgs);
      } catch {
        // Non-blocking
      }
    };

    fetchMessages();

    // Fetch similar incidents if not loaded yet
    if (!similarTickets[selectedTicket.id]) {
      getSimilarTickets(selectedTicket.id)
        .then((sim) => {
          if (isMounted) setSimilarTickets((prev) => ({ ...prev, [selectedTicket.id]: sim }));
        })
        .catch(() => {});
    }

    // Auto-poll messages for the active conversation when tab is visible
    const interval = setInterval(() => {
      if (!document.hidden) fetchMessages();
    }, 5000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [selectedTicket?.id, selectedTicket?.conversation_id, selectedTicket, similarTickets]);

  const prevMsgCountRef = useRef<number>(0);

  useEffect(() => {
    if (conversationMessages.length !== prevMsgCountRef.current) {
      const isFirst = prevMsgCountRef.current === 0;
      prevMsgCountRef.current = conversationMessages.length;
      if (isFirst) {
        scrollToBottom(false);
      } else if (consoleBodyRef.current) {
        const { scrollTop, scrollHeight, clientHeight } = consoleBodyRef.current;
        const isNearBottom = scrollHeight - scrollTop - clientHeight < 150;
        if (isNearBottom) {
          scrollToBottom(true);
        }
      }
    }
  }, [conversationMessages]);

  const handleTakeover = async () => {
    if (!selectedTicket?.conversation_id) return;
    setIsActionLoading(true);
    setActionNotice(null);
    try {
      await takeoverConversation(selectedTicket.conversation_id);
      setActionNotice('Conversation taken over. You can now chat live with the employee.');
      await loadTickets(true);
      const msgs = await getConversationMessages(selectedTicket.conversation_id);
      setConversationMessages(msgs);
    } catch (err) {
      setActionNotice(err instanceof Error ? `Takeover failed: ${err.message}` : 'Takeover failed.');
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleResolve = async () => {
    if (!selectedTicket) return;
    setIsActionLoading(true);
    setActionNotice(null);
    try {
      await resolveTicket(selectedTicket.id);
      setActionNotice(`Ticket marked as RESOLVED.`);
      await loadTickets(true);
    } catch (err) {
      setActionNotice(err instanceof Error ? `Resolve failed: ${err.message}` : 'Resolve failed.');
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleSendReply = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = replyInput.trim();
    if (!text || !selectedTicket?.conversation_id || isSending) return;

    setIsSending(true);
    setReplyInput('');
    try {
      await sendMessage(selectedTicket.conversation_id, text);
      const msgs = await getConversationMessages(selectedTicket.conversation_id);
      setConversationMessages(msgs);
    } catch (err) {
      setReplyInput(text);
      setActionNotice(err instanceof Error ? `Send failed: ${err.message}` : 'Failed to send reply.');
    } finally {
      setIsSending(false);
    }
  };

  const getBadgeClass = (status: string) => {
    switch (status.toUpperCase()) {
      case 'ESCALATED':
        return 'badge-escalated';
      case 'IN_PROGRESS':
        return 'badge-in-progress';
      case 'RESOLVED':
      case 'CLOSED':
        return 'badge-resolved';
      default:
        return 'badge-new';
    }
  };

  return (
    <div className="engineer-dashboard">
      <header className="page-heading dashboard-heading">
        <p className="eyebrow">Operations & Live Triage</p>
        <h1>Engineer dashboard</h1>
        <p className="page-subtitle">Review escalated incidents, chat live with employees, and resolve tickets.</p>
      </header>

      {actionNotice && (
        <div className="is-success" role="status" style={{ marginBottom: '1rem' }}>
          {actionNotice}
        </div>
      )}

      {error ? (
        <div className="empty-state panel-empty is-error" role="alert">
          <strong>Access Notice</strong>
          <span>{error}</span>
        </div>
      ) : isLoading ? (
        <div className="empty-state panel-empty">
          <strong>Loading dashboard...</strong>
          <span>Fetching tickets and incident history.</span>
        </div>
      ) : (
        <div className="dashboard-grid">
          {/* Left Column: Ticket Queue */}
          <aside className="queue-panel" aria-label="Ticket Queue">
            <div className="queue-header">
              <h3>Incident Queue</h3>
              <span className="queue-count">{tickets.length} Tickets</span>
            </div>

            {tickets.length === 0 ? (
              <div className="empty-state panel-empty" style={{ minHeight: '180px' }}>
                <strong>Queue clear</strong>
                <span>No tickets pending engineer review.</span>
              </div>
            ) : (
              tickets.map((ticket) => (
                <div
                  key={ticket.id}
                  className={`queue-card ${selectedTicketId === ticket.id ? 'is-active' : ''}`}
                  onClick={() => setSelectedTicketId(ticket.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setSelectedTicketId(ticket.id);
                    }
                  }}
                  role="button"
                  tabIndex={0}
                >
                  <div className="queue-card-title">{ticket.title}</div>
                  <div className="queue-card-footer">
                    <span className={`status-badge ${getBadgeClass(ticket.status)}`}>{ticket.status}</span>
                    <span>{ticket.conversation_id ? 'Chat active' : 'No chat'}</span>
                  </div>
                </div>
              ))
            )}
          </aside>

          {/* Right Column: Live Chat & Incident Console */}
          <main className="chat-console-panel" aria-label="Live Chat Console">
            {selectedTicket ? (
              <>
                <div className="console-header">
                  <div className="console-title-wrap">
                    <h2 className="console-title">{selectedTicket.title}</h2>
                    <div className="console-meta">
                      Ticket ID: <code>{selectedTicket.id.slice(0, 8)}</code> • Conversation:{' '}
                      <code>{selectedTicket.conversation_id ? selectedTicket.conversation_id.slice(0, 8) : 'None'}</code>
                    </div>
                  </div>
                  <div className="console-actions">
                    <span className={`status-badge ${getBadgeClass(selectedTicket.status)}`}>
                      {selectedTicket.status}
                    </span>
                    {selectedTicket.status === 'ESCALATED' && (
                      <button
                        className="primary-button"
                        style={{ padding: '8px 14px', fontSize: '0.85rem' }}
                        onClick={handleTakeover}
                        disabled={isActionLoading}
                      >
                        {isActionLoading ? 'Taking over...' : 'Take Over Chat'}
                      </button>
                    )}
                    {selectedTicket.status === 'IN_PROGRESS' && (
                      <button
                        className="success-button"
                        onClick={handleResolve}
                        disabled={isActionLoading}
                      >
                        {isActionLoading ? 'Resolving...' : 'Mark Resolved'}
                      </button>
                    )}
                  </div>
                </div>

                {/* Similar Incidents Summary */}
                {similarTickets[selectedTicket.id] && similarTickets[selectedTicket.id].length > 0 && (
                  <div style={{ padding: '10px 20px', background: '#f8fbfa', borderBottom: '1px solid var(--line)', fontSize: '0.82rem' }}>
                    <strong>Similar Incidents:</strong>{' '}
                    {similarTickets[selectedTicket.id]?.map((sim, i) => (
                      <span key={i} style={{ marginRight: '10px', color: 'var(--teal-dark)' }}>
                        • {sim.title} ({sim.status ?? 'RESOLVED'})
                        {typeof sim.similarity === 'number' && sim.similarity > 0 && (
                          <small style={{ marginLeft: '4px', opacity: 0.85 }}>
                            [Score: {(sim.similarity * 100).toFixed(1)}%]
                          </small>
                        )}
                      </span>
                    ))}
                  </div>
                )}

                {/* Transcript Body */}
                <div className="console-body" ref={consoleBodyRef}>
                  {conversationMessages.length === 0 ? (
                    <div className="empty-state" style={{ minHeight: '200px' }}>
                      <strong>No messages in conversation</strong>
                      <span>When the employee sends messages, they will appear here.</span>
                    </div>
                  ) : (
                    conversationMessages.map((msg, idx) => {
                      const isEngineer = msg.sender_type === 'SYSTEM' || msg.content.startsWith('[Engineer]');
                      const isUser = msg.sender_type === 'USER';
                      const messageClass = isEngineer ? 'support' : isUser ? 'user' : 'ai';
                      const label = isEngineer ? 'Support Engineer' : isUser ? 'Employee' : 'AI Helpdesk';
                      const displayContent = isEngineer && msg.content.startsWith('[Engineer] ')
                        ? msg.content.replace('[Engineer] ', '')
                        : msg.content;

                      return (
                        <div key={msg.id || idx} className={`message ${messageClass}`}>
                          <span className="message-label">{label}</span>
                          <MarkdownRenderer content={displayContent} />
                        </div>
                      );
                    })
                  )}
                </div>

                {/* Reply Footer */}
                <div className="console-footer">
                  <form className="console-input-form" onSubmit={handleSendReply}>
                    <input
                      className="text-field"
                      value={replyInput}
                      onChange={(e) => setReplyInput(e.target.value)}
                      placeholder={
                        selectedTicket.status === 'ESCALATED'
                          ? 'Click "Take Over Chat" above to respond directly...'
                          : 'Type your message to the employee...'
                      }
                      disabled={isSending || !selectedTicket.conversation_id}
                    />
                    <button
                      className="primary-button"
                      type="submit"
                      disabled={isSending || !replyInput.trim() || !selectedTicket.conversation_id}
                    >
                      {isSending ? 'Sending...' : 'Send'}
                    </button>
                  </form>
                </div>
              </>
            ) : (
              <div className="empty-state panel-empty">
                <strong>No ticket selected</strong>
                <span>Select a ticket from the left panel to inspect its messages and chat live.</span>
              </div>
            )}
          </main>
        </div>
      )}
    </div>
  );
};
