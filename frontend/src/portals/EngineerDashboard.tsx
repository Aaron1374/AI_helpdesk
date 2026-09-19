import React, { useState, useEffect, useRef, useCallback } from 'react';
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
import { MarkdownRenderer } from '../components/MarkdownRenderer';


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

  // New states for queue tabs and real-time escalation pop-up alert
  const [queueTab, setQueueTab] = useState<'active' | 'history'>('active');
  const [escalationAlert, setEscalationAlert] = useState<TicketItem | null>(null);
  const knownEscalatedIdsRef = useRef<Set<string>>(new Set());
  const isInitialLoadRef = useRef<boolean>(true);

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

      // Real-time Escalation Pop-Up Detection
      const currentEscalated = ticketList.filter((t) => t.status === 'ESCALATED');
      if (!isInitialLoadRef.current) {
        const newlyEscalated = currentEscalated.find((t) => !knownEscalatedIdsRef.current.has(t.id));
        if (newlyEscalated) {
          setEscalationAlert(newlyEscalated);
        }
      } else {
        isInitialLoadRef.current = false;
      }
      knownEscalatedIdsRef.current = new Set(currentEscalated.map((t) => t.id));

      setTickets(ticketList);
      if (ticketList.length > 0 && !selectedTicketId) {
        // Select newest ticket initially
        const newest = [...ticketList].reverse().find((t) => t.status !== 'RESOLVED' && t.status !== 'CLOSED') || ticketList[ticketList.length - 1];
        setSelectedTicketId(newest.id);
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
    }, 5000);
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

  // Scroll to bottom ONLY when a new message comes through or on initial conversation load
  useEffect(() => {
    if (conversationMessages.length > prevMsgCountRef.current) {
      const isFirst = prevMsgCountRef.current === 0;
      prevMsgCountRef.current = conversationMessages.length;
      scrollToBottom(!isFirst);
    } else if (conversationMessages.length < prevMsgCountRef.current) {
      prevMsgCountRef.current = conversationMessages.length;
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
      if (selectedTicket.conversation_id) {
        const msgs = await getConversationMessages(selectedTicket.conversation_id);
        setConversationMessages(msgs);
      }
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

    const tempMsgId = `temp-eng-${Date.now()}`;
    const tempMsg: ChatMessageRecord = {
      id: tempMsgId,
      sender_type: 'SYSTEM',
      content: `[Engineer] ${text}`,
      created_at: new Date().toISOString(),
    };
    setConversationMessages((prev) => [...prev, tempMsg]);

    try {
      await sendMessage(selectedTicket.conversation_id, text);
      const msgs = await getConversationMessages(selectedTicket.conversation_id);
      setConversationMessages(msgs);
    } catch (err) {
      setConversationMessages((prev) => prev.filter((m) => m.id !== tempMsgId));
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

  // Sort tickets newest-first
  const sortedTickets = [...tickets].reverse();
  const activeTickets = sortedTickets.filter((t) => t.status !== 'RESOLVED' && t.status !== 'CLOSED');
  const historyTickets = sortedTickets.filter((t) => t.status === 'RESOLVED' || t.status === 'CLOSED');
  const displayedTickets = queueTab === 'active' ? activeTickets : historyTickets;

  return (
    <div className="engineer-dashboard">
      <header className="page-heading dashboard-heading">
        <p className="eyebrow">Operations & Live Triage</p>
        <h1>Engineer dashboard</h1>
        <p className="page-subtitle">Review escalated incidents, chat live with employees, and resolve tickets.</p>
      </header>

      {/* Simple Escalation Alert Banner */}
      {escalationAlert && (
        <div className="escalation-alert-banner" role="alert">
          <div className="escalation-alert-content">
            <span className="escalation-alert-badge">New Escalated Request</span>
            <strong>{escalationAlert.title}</strong>
            <span className="escalation-alert-meta">
              Category: <code>{escalationAlert.category || 'General Support'}</code> • Priority: <code>{escalationAlert.priority || 'MEDIUM'}</code>
            </span>
          </div>
          <div className="escalation-alert-actions">
            <button
              type="button"
              className="primary-button"
              style={{ fontSize: '0.85rem', padding: '8px 16px', minHeight: 'auto' }}
              onClick={() => {
                setSelectedTicketId(escalationAlert.id);
                setQueueTab('active');
                setEscalationAlert(null);
              }}
            >
              View & Take Over
            </button>
            <button
              type="button"
              className="secondary-button"
              style={{ fontSize: '0.85rem', padding: '8px 14px', minHeight: 'auto', background: 'transparent', border: '1px solid var(--line)', color: 'var(--muted)' }}
              onClick={() => setEscalationAlert(null)}
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

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
              <span className="queue-count">{displayedTickets.length} Tickets</span>
            </div>

            {/* Active vs History Tab Controls */}
            <div className="queue-tab-bar" role="tablist">
              <button
                type="button"
                className={`queue-tab-btn ${queueTab === 'active' ? 'is-active' : ''}`}
                onClick={() => setQueueTab('active')}
                role="tab"
                aria-selected={queueTab === 'active'}
              >
                Active Queue ({activeTickets.length})
              </button>
              <button
                type="button"
                className={`queue-tab-btn ${queueTab === 'history' ? 'is-active' : ''}`}
                onClick={() => setQueueTab('history')}
                role="tab"
                aria-selected={queueTab === 'history'}
              >
                History ({historyTickets.length})
              </button>
            </div>

            {displayedTickets.length === 0 ? (
              <div className="empty-state panel-empty" style={{ minHeight: '180px' }}>
                <strong>{queueTab === 'active' ? 'Active queue clear' : 'No ticket history'}</strong>
                <span>{queueTab === 'active' ? 'No open tickets pending engineer review.' : 'Resolved & closed tickets will appear here.'}</span>
              </div>
            ) : (
              displayedTickets.map((ticket) => (
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
                    <span className={`status-badge badge-${ticket.priority?.toLowerCase() || 'medium'}`} style={{marginLeft: '4px'}}>{ticket.priority || 'MEDIUM'}</span>
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
                    {selectedTicket.priority_rationale && (
                      <div className="console-meta" style={{ marginTop: '6px', color: 'var(--text-light)' }}>
                        <strong>AI Rationale:</strong> {selectedTicket.priority_rationale}
                      </div>
                    )}
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
                    {(selectedTicket.status === 'IN_PROGRESS' || selectedTicket.status === 'ESCALATED') && (
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
                      const cleanContent = isEngineer && msg.content.startsWith('[Engineer] ')
                        ? msg.content.replace('[Engineer] ', '')
                        : msg.content;


                      return (
                        <div key={msg.id || idx} className={`message ${messageClass}`}>
                          <span className="message-label">{label}</span>
                          {isUser ? (
                            <span style={{ whiteSpace: 'pre-wrap' }}>{cleanContent}</span>
                          ) : (
                            <MarkdownRenderer content={cleanContent} />
                          )}
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
                          ? 'Click "Take Over Chat" above to enable messaging...'
                          : selectedTicket.status === 'RESOLVED' || selectedTicket.status === 'CLOSED'
                            ? 'This ticket is closed.'
                            : 'Type your message to the employee...'
                      }
                      disabled={isSending || selectedTicket.status !== 'IN_PROGRESS' || !selectedTicket.conversation_id}
                    />
                    <button
                      className="primary-button"
                      type="submit"
                      disabled={
                        isSending ||
                        selectedTicket.status !== 'IN_PROGRESS' ||
                        !replyInput.trim() ||
                        !selectedTicket.conversation_id
                      }
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
