import React, { useEffect, useState } from 'react';
import { getTickets, getConversationMessages, ApiError } from '../api/client';
import type { TicketItem, ChatMessageRecord } from '../api/types';
import { MarkdownRenderer } from '../components/MarkdownRenderer';

export const AdminDashboard: React.FC = () => {
  const [tickets, setTickets] = useState<TicketItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Inspector modal state
  const [inspectedTicket, setInspectedTicket] = useState<TicketItem | null>(null);
  const [inspectedMessages, setInspectedMessages] = useState<ChatMessageRecord[]>([]);
  const [isInspectLoading, setIsInspectLoading] = useState<boolean>(false);

  useEffect(() => {
    let cancelled = false;

    const loadTickets = async () => {
      try {
        const ticketList = await getTickets();
        if (cancelled) return;
        setTickets(ticketList);
        setIsLoading(false);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          setError('Access restricted: Admin role is required.');
        } else if (err instanceof Error) {
          setError(err.message);
        } else {
          setError('Failed to load tickets.');
        }
        setIsLoading(false);
      }
    };

    loadTickets();
    const interval = setInterval(() => {
      if (!document.hidden) loadTickets();
    }, 7000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  // Analytics expandable state
  const [isAnalyticsExpanded, setIsAnalyticsExpanded] = useState<boolean>(true);
  const [showAllCategories, setShowAllCategories] = useState<boolean>(false);
  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState<boolean>(false);

  const handleInspect = async (ticket: TicketItem) => {
    if (!ticket.conversation_id) return;
    setInspectedTicket(ticket);
    setIsInspectLoading(true);
    setInspectedMessages([]);
    try {
      const msgs = await getConversationMessages(ticket.conversation_id);
      setInspectedMessages(msgs);
    } catch {
      // Non-blocking
    } finally {
      setIsInspectLoading(false);
    }
  };

  const sortedTickets = [...tickets].reverse();

  // Metrics computation for charts
  const totalCount = sortedTickets.length || 1;
  const statusCounts = sortedTickets.reduce<Record<string, number>>((acc, t) => {
    acc[t.status] = (acc[t.status] || 0) + 1;
    return acc;
  }, {});

  const ALL_IT_CATEGORIES = [
    'Network',
    'General Support',
    'Access',
    'Hardware',
    'Software',
    'Email',
    'Security',
    'Application'
  ];

  const normalizeCategory = (cat: string | null | undefined): string => {
    if (!cat) return 'General Support';
    const c = cat.toLowerCase().replace(/_/g, ' ').trim();
    if (c === 'access') return 'Access';
    if (c === 'network') return 'Network';
    if (c === 'hardware') return 'Hardware';
    if (c === 'software') return 'Software';
    if (c === 'email') return 'Email';
    if (c === 'security' || c === 'security incident') return 'Security';
    if (c === 'application' || c === 'app') return 'Application';
    if (c === 'general support' || c === 'general') return 'General Support';
    return c.replace(/\b\w/g, l => l.toUpperCase());
  };

  const categoryCounts = sortedTickets.reduce<Record<string, number>>((acc, t) => {
    const cat = normalizeCategory(t.category);
    acc[cat] = (acc[cat] || 0) + 1;
    return acc;
  }, {});

  const allCategoryKeys = Array.from(new Set([...ALL_IT_CATEGORIES, ...Object.keys(categoryCounts)]));

  const sortedCategories = allCategoryKeys
    .map(cat => [cat, categoryCounts[cat] || 0] as [string, number])
    .sort((a, b) => b[1] - a[1]);

  const categoryColors = [
    '#0f4c47', // Deep Teal
    '#3b5998', // Indigo Blue
    '#1e6b37', // Emerald Green
    '#e05638', // Soft Coral
    '#d97706', // Amber/Orange
    '#6366f1', // Indigo/Violet
    '#64748b', // Slate
    '#0284c7', // Sky Blue
  ];

  const conicSlices = sortedCategories.map(([cat, count], idx) => {
    const pct = Math.round((count / totalCount) * 100);
    const color = categoryColors[idx % categoryColors.length];
    return { cat, count, pct, color };
  });

  // For conic gradient pie chart, compute slice angles from active categories
  let accumulatedPct = 0;
  const activeConicSlices = conicSlices
    .filter(s => s.count > 0)
    .map(s => {
      const startPct = accumulatedPct;
      accumulatedPct += (s.count / totalCount) * 100;
      const endPct = accumulatedPct;
      return { ...s, startPct, endPct };
    });

  const conicGradientStyle = activeConicSlices.length > 0
    ? activeConicSlices.map(s => `${s.color} ${s.startPct}% ${s.endPct}%`).join(', ')
    : '#e2e8f0 0% 100%';

  const resolvedCount = (statusCounts['RESOLVED'] || 0) + (statusCounts['CLOSED'] || 0);
  const escalatedCount = statusCounts['ESCALATED'] || 0;
  const aiResolutionPct = Math.round((resolvedCount / totalCount) * 100);
  const escalationPct = Math.round((escalatedCount / totalCount) * 100);

  const statusColors: Record<string, string> = {
    ESCALATED: '#e05638',
    IN_PROGRESS: '#0f4c47',
    RESOLVED: '#1e6b37',
    CLOSED: '#64748b',
    NEW: '#3b5998',
  };

  return (
    <div className="admin-dashboard">
      <h1>Admin Dashboard</h1>
      <p className="page-subtitle">
        Enterprise analytics, conversation auditing, and system operations
      </p>

      {/* Unified Collapsible Operational Analytics & Metrics Section */}
      <div className="admin-analytics-panel">
        <div className="admin-analytics-header">
          <div className="admin-analytics-title">
            <h2>Operational Analytics & Metrics</h2>
          </div>
          <button
            type="button"
            className="secondary-button"
            style={{ fontSize: '0.8rem', padding: '4px 12px', minHeight: 'auto' }}
            onClick={() => setIsAnalyticsExpanded(!isAnalyticsExpanded)}
          >
            {isAnalyticsExpanded ? 'Hide Analytics ▲' : 'Show Analytics ▲'}
          </button>
        </div>

        {isAnalyticsExpanded && (
          <div className="admin-analytics-body">
            {/* Top Level Summary Statistics */}
            <div className="stats-row" style={{ margin: 0 }}>
              <div className="stat-card">
                <span className="stat-value">{tickets.length}</span>
                <span className="stat-label">Total Tickets</span>
              </div>
              <div className="stat-card">
                <span className="stat-value" style={{ color: '#e05638' }}>
                  {statusCounts['ESCALATED'] ?? 0}
                </span>
                <span className="stat-label">Escalated</span>
              </div>
              <div className="stat-card">
                <span className="stat-value" style={{ color: '#0f4c47' }}>
                  {statusCounts['IN_PROGRESS'] ?? 0}
                </span>
                <span className="stat-label">In Progress</span>
              </div>
              <div className="stat-card">
                <span className="stat-value" style={{ color: '#1e6b37' }}>
                  {statusCounts['RESOLVED'] ?? 0}
                </span>
                <span className="stat-label">Resolved</span>
              </div>
            </div>

            {/* Visual Analytics & Graphical Charts Section */}
            <section className="admin-charts-grid" aria-label="Analytics Graphs">
              {/* Chart 1: Status Distribution */}
              <div className="chart-card">
                <div className="chart-card-header" style={{ marginBottom: '8px' }}>
                  <h3 className="chart-card-title">Status Breakdown</h3>

                  <span className="chart-card-badge">{tickets.length} Total</span>
                </div>
                <div className="chart-bars-list" style={{ gap: '8px' }}>
                  {['ESCALATED', 'IN_PROGRESS', 'RESOLVED', 'CLOSED', 'NEW'].map((status) => {
                    const count = statusCounts[status] || 0;
                    const pct = Math.round((count / totalCount) * 100);
                    return (
                      <div key={status} className="chart-bar-item">
                        <div className="chart-bar-label-row" style={{ fontSize: '0.78rem', marginBottom: '2px' }}>
                          <span className={`badge badge-${status.toLowerCase()}`} style={{ fontSize: '0.65rem', padding: '1px 6px' }}>
                            {status.replace('_', ' ')}
                          </span>
                          <span><strong>{count}</strong> ({pct}%)</span>
                        </div>
                        <div className="chart-bar-track" style={{ height: '6px' }}>
                          <div
                            className="chart-bar-fill"
                            style={{
                              width: `${pct}%`,
                              backgroundColor: statusColors[status] || 'var(--teal)',
                            }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Chart 2: Category Distribution - Donut Pie Chart */}
              <div
                className="chart-card"
                style={{ cursor: 'pointer' }}
                onClick={() => setIsCategoryModalOpen(true)}
              >
                <div className="chart-card-header">
                  <h3 className="chart-card-title">Category Volume</h3>
                  <button
                    type="button"
                    className="secondary-button"
                    style={{ fontSize: '0.75rem', padding: '3px 10px', minHeight: 'auto', whiteSpace: 'nowrap' }}
                    onClick={(e) => {
                      e.stopPropagation();
                      setIsCategoryModalOpen(true);
                    }}
                  >
                    Expand
                  </button>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1, padding: '10px 0' }}>
                  {/* Centered Graphical Donut Pie */}
                  <div
                    className="pie-chart-donut"
                    style={{
                      width: '120px',
                      height: '120px',
                      borderRadius: '50%',
                      background: `conic-gradient(${conicGradientStyle})`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      position: 'relative',
                      boxShadow: '0 3px 10px rgba(0,0,0,0.08)',
                    }}
                  >
                    {/* Donut Center Hole */}
                    <div
                      style={{
                        width: '66px',
                        height: '66px',
                        borderRadius: '50%',
                        background: 'var(--paper, #ffffff)',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.08)',
                      }}
                    >
                      <span style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--ink)' }}>
                        {tickets.length}
                      </span>
                      <span style={{ fontSize: '0.62rem', color: 'var(--muted)', textTransform: 'uppercase' }}>
                        Tickets
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Chart 3: AI Automation vs Human Handoff */}
              <div className="chart-card">
                <div className="chart-card-header">
                  <h3 className="chart-card-title">AI vs Human Handoff</h3>
                  <span className="chart-card-badge" style={{ background: '#e6f4f2', color: '#0f4c47' }}>
                    {aiResolutionPct}% Autonomous
                  </span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', flex: 1, justifyContent: 'space-between' }}>
                  <div className="chart-bars-list" style={{ gap: '12px', margin: 'auto 0' }}>
                    <div className="chart-bar-item">
                      <div className="chart-bar-label-row" style={{ fontSize: '0.78rem', marginBottom: '4px' }}>
                        <span style={{ fontWeight: 600 }}>AI Automated Resolution</span>
                        <span style={{ color: '#1e6b37', fontWeight: 700 }}>{aiResolutionPct}%</span>
                      </div>
                      <div className="chart-bar-track" style={{ height: '8px' }}>
                        <div
                          className="chart-bar-fill"
                          style={{ width: `${aiResolutionPct}%`, backgroundColor: '#1e6b37' }}
                        />
                      </div>
                    </div>

                    <div className="chart-bar-item">
                      <div className="chart-bar-label-row" style={{ fontSize: '0.78rem', marginBottom: '4px' }}>
                        <span style={{ fontWeight: 600 }}>Human Engineer Escalation</span>
                        <span style={{ color: '#e05638', fontWeight: 700 }}>{escalationPct}%</span>
                      </div>
                      <div className="chart-bar-track" style={{ height: '8px' }}>
                        <div
                          className="chart-bar-fill"
                          style={{ width: `${escalationPct}%`, backgroundColor: '#e05638' }}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Summary metric pill */}
                  <div style={{
                    marginTop: 'auto',
                    background: '#f8fafc',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    fontSize: '0.78rem',
                    color: 'var(--muted)',
                    display: 'flex',
                    justify: 'space-between',
                    alignItems: 'center',
                    border: '1px solid var(--line)'
                  }}>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <span>AI Efficiency Index =</span>
                      <strong style={{ color: 'var(--ink)' }}>
                        {resolvedCount} Solved / {totalCount} Total
                      </strong>
                    </div>
                  </div>
                </div>
              </div>
            </section>
          </div>
        )}
      </div>

      {/* Error */}
      {error && <div className="is-error">{error}</div>}

      {/* Ticket Queue & Live Audit Table */}
      <div className="panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <h2>Incident Queue & Conversation Audit</h2>
          <span style={{ fontSize: '0.85rem', color: 'var(--muted)' }}></span>
        </div>

        {isLoading ? (
          <div className="empty-state">
            <strong>Loading tickets…</strong>
          </div>
        ) : sortedTickets.length === 0 ? (
          <div className="empty-state">
            <strong>No tickets found</strong>
          </div>
        ) : (
          <div className="table-wrapper">
            <table className="ticket-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Title</th>
                  <th>Status</th>
                  <th>Priority</th>
                  <th>Category</th>
                  <th>Owner</th>
                  <th style={{ textAlign: 'center', width: '50px' }}>Chat</th>
                </tr>
              </thead>
              <tbody>
                {sortedTickets.map((ticket) => (
                  <tr key={ticket.id}>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>
                      {ticket.id.slice(0, 8)}…
                    </td>
                    <td title={ticket.title} style={{ fontWeight: 600 }}>
                      {ticket.title}
                    </td>
                    <td>
                      <span className={`badge badge-${ticket.status.toLowerCase()}`}>
                        {ticket.status}
                      </span>
                    </td>
                    <td>{ticket.priority}</td>
                    <td>{ticket.category ?? '—'}</td>
                    <td>
                      {ticket.status === 'ESCALATED' || ticket.status === 'IN_PROGRESS'
                        ? 'L1 Engineer'
                        : 'AI Agent'}
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      {ticket.conversation_id ? (
                        <button
                          type="button"
                          className="admin-inspect-btn"
                          title="Inspect Chat Transcript"
                          aria-label="Inspect Chat Transcript"
                          onClick={() => handleInspect(ticket)}
                        >
                          ⊙
                        </button>
                      ) : (
                        <span style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Conversation Overlook Audit Modal */}
      {inspectedTicket && (
        <div className="admin-inspector-overlay" role="dialog" aria-modal="true">
          <div className="admin-inspector-dialog">
            <div className="admin-inspector-header">
              <div>
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700 }}>
                  Auditing: {inspectedTicket.title}
                </h3>
                <span style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>
                  Ticket ID: <code>{inspectedTicket.id.slice(0, 8)}</code> • Status: <code>{inspectedTicket.status}</code>
                </span>
              </div>
              <button
                type="button"
                className="secondary-button"
                style={{ fontSize: '0.85rem', padding: '6px 12px', minHeight: 'auto' }}
                onClick={() => setInspectedTicket(null)}
              >
                Close Audit
              </button>
            </div>

            <div className="admin-inspector-body">
              {isInspectLoading ? (
                <div className="empty-state" style={{ minHeight: '180px' }}>
                  <span>Fetching conversation transcript...</span>
                </div>
              ) : inspectedMessages.length === 0 ? (
                <div className="empty-state" style={{ minHeight: '180px' }}>
                  <strong>No messages found in conversation</strong>
                </div>
              ) : (
                inspectedMessages.map((msg, idx) => {
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
          </div>
        </div>
      )}
      {/* Category Volume Deep-Dive Popup Modal */}
      {isCategoryModalOpen && (
        <div className="admin-inspector-overlay" role="dialog" aria-modal="true" onClick={() => setIsCategoryModalOpen(false)}>
          <div className="admin-inspector-dialog" style={{ maxWidth: '640px' }} onClick={(e) => e.stopPropagation()}>
            <div className="admin-inspector-header">
              <div>
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700 }}>
                  Category Volume Distribution
                </h3>
                <span style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>
                  Total Incidents Analyzed: <strong>{tickets.length}</strong> • All Categories Breakdown
                </span>
              </div>
              <button
                type="button"
                className="secondary-button"
                style={{ fontSize: '0.85rem', padding: '6px 12px', minHeight: 'auto' }}
                onClick={() => setIsCategoryModalOpen(false)}
              >
                Close
              </button>
            </div>

            <div className="admin-inspector-body" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* Large Donut Chart & Overview */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '24px', background: '#f8fafc', padding: '20px', borderRadius: '10px', border: '1px solid var(--line)' }}>
                <div
                  style={{
                    width: '140px',
                    height: '140px',
                    borderRadius: '50%',
                    background: `conic-gradient(${conicGradientStyle})`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    boxShadow: '0 4px 12px rgba(0,0,0,0.08)'
                  }}
                >
                  <div
                    style={{
                      width: '76px',
                      height: '76px',
                      borderRadius: '50%',
                      background: '#ffffff',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <span style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--ink)' }}>
                      {tickets.length}
                    </span>
                    <span style={{ fontSize: '0.65rem', color: 'var(--muted)', textTransform: 'uppercase' }}>
                      Incidents
                    </span>
                  </div>
                </div>

                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: 'var(--ink)' }}>
                    Top Category: {sortedCategories[0]?.[0] || 'N/A'}
                  </h4>
                  <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--muted)' }}>
                    Represents {Math.round(((sortedCategories[0]?.[1] || 0) / totalCount) * 100)}% of total logged support queries.
                  </p>
                </div>
              </div>

              {/* Full Category Table Breakdown */}
              <div style={{ border: '1px solid var(--line)', borderRadius: '8px', overflowY: 'auto', maxHeight: '360px' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                  <thead>
                    <tr style={{ background: '#f4f8f7', textTransform: 'uppercase', fontSize: '0.75rem', color: 'var(--muted)', whiteSpace: 'nowrap' }}>
                      <th style={{ padding: '10px 14px', textAlign: 'left', whiteSpace: 'nowrap' }}>Category</th>
                      <th style={{ padding: '10px 14px', textAlign: 'right', whiteSpace: 'nowrap' }}>Incidents</th>
                      <th style={{ padding: '10px 14px', textAlign: 'right', whiteSpace: 'nowrap' }}>Share</th>
                      <th style={{ padding: '10px 14px', textAlign: 'left', width: '35%', whiteSpace: 'nowrap' }}>Distribution</th>
                    </tr>
                  </thead>
                  <tbody>
                    {conicSlices.map((slice) => (
                      <tr key={slice.cat} style={{ borderTop: '1px solid var(--line)' }}>
                        <td style={{ padding: '10px 14px', fontWeight: 600, color: 'var(--ink)', whiteSpace: 'nowrap' }}>
                          <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: slice.color, marginRight: '8px' }} />
                          {slice.cat}
                        </td>
                        <td style={{ padding: '10px 14px', textAlign: 'right', fontWeight: 700, whiteSpace: 'nowrap' }}>
                          {slice.count}
                        </td>
                        <td style={{ padding: '10px 14px', textAlign: 'right', color: 'var(--muted)', whiteSpace: 'nowrap' }}>
                          {slice.pct}%
                        </td>
                        <td style={{ padding: '10px 14px', verticalAlign: 'middle' }}>
                          <div style={{ height: '6px', background: '#e2e8f0', borderRadius: '999px', overflow: 'hidden' }}>
                            <div style={{ height: '100%', width: `${slice.pct}%`, backgroundColor: slice.color, borderRadius: '999px' }} />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminDashboard;