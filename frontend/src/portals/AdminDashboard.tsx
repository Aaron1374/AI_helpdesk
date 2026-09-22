import React, { useEffect, useState } from 'react';
import { getTickets, getConversationMessages, provisionEngineer, ApiError } from '../api/client';
import type { TicketItem, ChatMessageRecord } from '../api/types';
import { MarkdownRenderer } from '../components/MarkdownRenderer';

export interface AdminDashboardProps {
  isProvisionHeroOpen?: boolean;
  onToggleProvisionHero?: () => void;
}

export const AdminDashboard: React.FC<AdminDashboardProps> = ({
  isProvisionHeroOpen = false,
  onToggleProvisionHero,
}) => {
  const [tickets, setTickets] = useState<TicketItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [searchTerm, setSearchTerm] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  const [currentPage, setCurrentPage] = useState<number>(1);
  const ticketsPerPage = 10;

  const [inspectedTicket, setInspectedTicket] = useState<TicketItem | null>(null);
  const [inspectedMessages, setInspectedMessages] = useState<ChatMessageRecord[]>([]);
  const [isInspectLoading, setIsInspectLoading] = useState<boolean>(false);

  const [isAnalyticsExpanded, setIsAnalyticsExpanded] = useState<boolean>(true);
  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState<boolean>(false);

  // Provision Engineer state
  const [isInternalProvisionOpen, setIsInternalProvisionOpen] = useState<boolean>(false);
  const [engFirstName, setEngFirstName] = useState<string>('');
  const [engLastName, setEngLastName] = useState<string>('');
  const [engEmail, setEngEmail] = useState<string>('');
  const [engPassword, setEngPassword] = useState<string>('');
  const [engRole, setEngRole] = useState<'l1' | 'l2' | 'support_lead'>('l1');
  const [engDepartment, setEngDepartment] = useState<string>('engineering');
  const [provisionError, setProvisionError] = useState<string>('');
  const [provisionSuccess, setProvisionSuccess] = useState<string>('');
  const [isProvisioning, setIsProvisioning] = useState<boolean>(false);
  const [isPasswordRulesVisible, setIsPasswordRulesVisible] = useState<boolean>(false);

  const isProvisionActive = isProvisionHeroOpen || isInternalProvisionOpen;
  const toggleProvision = onToggleProvisionHero || (() => setIsInternalProvisionOpen(!isInternalProvisionOpen));

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
      if (!document.hidden) {
        loadTickets();
      }
    }, 7000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const handleRefresh = async () => {
    if (isRefreshing) return;

    setIsRefreshing(true);

    try {
      const ticketList = await getTickets();
      setTickets(ticketList);
      setError(null);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        setError('Access restricted: Admin role is required.');
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to refresh tickets.');
      }
    } finally {
      setIsRefreshing(false);
    }
  };

  const sortedTickets = [...tickets].reverse();

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

  const totalCount = sortedTickets.length;

  const toPercentage = (count: number, total: number): number =>
    total > 0 ? Math.round((count / total) * 100) : 0;

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
    'Application',
  ];

  const normalizeCategory = (cat: string | null | undefined): string => {
    if (!cat) return 'General Support';

    const c = cat.toLowerCase().replace(/_/g, ' ').trim();

    if (c === 'access') return 'Access';
    if (c === 'network') return 'Network';
    if (c === 'hardware') return 'Hardware';
    if (c === 'software') return 'Software';
    if (c === 'email') return 'Email';
    if (c === 'security' || c === 'security incident') {
      return 'Security';
    }
    if (c === 'application' || c === 'app') {
      return 'Application';
    }
    if (c === 'general support' || c === 'general') {
      return 'General Support';
    }

    return c.replace(/\b\w/g, (l) => l.toUpperCase());
  };

  const categoryCounts = sortedTickets.reduce<Record<string, number>>((acc, t) => {
    const cat = normalizeCategory(t.category);

    acc[cat] = (acc[cat] || 0) + 1;

    return acc;
  }, {});

  const allCategoryKeys = Array.from(
    new Set([...ALL_IT_CATEGORIES, ...Object.keys(categoryCounts)]),
  );

  const sortedCategories = allCategoryKeys
    .map((cat) => [cat, categoryCounts[cat] || 0] as [string, number])
    .sort((a, b) => b[1] - a[1]);

  const categoryColors = [
    '#0f4c47',
    '#3b5998',
    '#1e6b37',
    '#e05638',
    '#d97706',
    '#6366f1',
    '#64748b',
    '#0284c7',
  ];

  const conicSlices = sortedCategories.map(([cat, count], idx) => {
    const pct = toPercentage(count, totalCount);

    const color = categoryColors[idx % categoryColors.length];

    return {
      cat,
      count,
      pct,
      color,
    };
  });

  let accumulatedPct = 0;

  const activeConicSlices = conicSlices
    .filter((s) => s.count > 0)
    .map((s) => {
      const startPct = accumulatedPct;

      accumulatedPct += (s.count / totalCount) * 100;

      const endPct = accumulatedPct;

      return {
        ...s,
        startPct,
        endPct,
      };
    });

  const conicGradientStyle =
    activeConicSlices.length > 0
      ? activeConicSlices.map((s) => `${s.color} ${s.startPct}% ${s.endPct}%`).join(', ')
      : '#e2e8f0 0% 100%';

  const resolvedCount = (statusCounts['RESOLVED'] || 0) + (statusCounts['CLOSED'] || 0);

  const escalatedCount = statusCounts['ESCALATED'] || 0;

  const aiResolutionPct = toPercentage(resolvedCount, totalCount);

  const escalationPct = toPercentage(escalatedCount, totalCount);

  const statusColors: Record<string, string> = {
    ESCALATED: '#e05638',
    IN_PROGRESS: '#0f4c47',
    RESOLVED: '#1e6b37',
    CLOSED: '#64748b',
    NEW: '#3b5998',
  };

  const filteredTickets = sortedTickets.filter((ticket) => {
    const normalizedSearch = searchTerm.trim().toLowerCase();

    const matchesSearch =
      !normalizedSearch ||
      ticket.id.toLowerCase().includes(normalizedSearch) ||
      ticket.title.toLowerCase().includes(normalizedSearch) ||
      (ticket.category || '').toLowerCase().includes(normalizedSearch) ||
      ticket.status.toLowerCase().includes(normalizedSearch) ||
      ticket.priority.toLowerCase().includes(normalizedSearch);

    const matchesStatus =
      statusFilter === 'ALL' || ticket.status === statusFilter;

    const matchesCategory =
      categoryFilter === 'ALL' || normalizeCategory(ticket.category) === categoryFilter;

    return matchesSearch && matchesStatus && matchesCategory;
  });

  const totalPages = Math.max(1, Math.ceil(filteredTickets.length / ticketsPerPage));

  const startIndex = (currentPage - 1) * ticketsPerPage;

  const endIndex = startIndex + ticketsPerPage;

  const paginatedTickets = filteredTickets.slice(startIndex, endIndex);

  useEffect(() => {
    setCurrentPage((page) => Math.min(page, totalPages));
  }, [totalPages]);

  const handleExportCsv = () => {
    if (filteredTickets.length === 0) return;

    const escapeCsvValue = (value: string | number | null | undefined) =>
      `"${String(value ?? '').replace(/"/g, '""')}"`;

    const getOwner = (ticket: TicketItem): string => {
      if (ticket.status === 'ESCALATED' || ticket.status === 'IN_PROGRESS') {
        return 'L1 Engineer';
      }

      return 'AI Agent';
    };

    const headers = [
      'Ticket ID',
      'Title',
      'Status',
      'Priority',
      'Category',
      'Owner',
      'Conversation ID',
    ];

    const rows = filteredTickets.map((ticket) => [
      ticket.id,
      ticket.title,
      ticket.status,
      ticket.priority,
      ticket.category ?? '',
      getOwner(ticket),
      ticket.conversation_id ?? '',
    ]);

    const csvContent = [headers, ...rows]
      .map((row) => row.map(escapeCsvValue).join(','))
      .join('\r\n');

    const blob = new Blob([`\uFEFF${csvContent}`], {
      type: 'text/csv;charset=utf-8;',
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');

    link.href = url;
    link.download = `tickets-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const isEngFirstNameValid = !engFirstName || /^[a-zA-Z]+$/.test(engFirstName.trim());
  const isEngLastNameValid = !engLastName || /^[a-zA-Z]+$/.test(engLastName.trim());

  const engPasswordRules = [
    { id: 'length', label: 'Minimum 8 characters', met: engPassword.length >= 8 },
    { id: 'uppercase', label: 'At least 1 uppercase letter (A-Z)', met: /[A-Z]/.test(engPassword) },
    { id: 'lowercase', label: 'At least 1 lowercase letter (a-z)', met: /[a-z]/.test(engPassword) },
    { id: 'number', label: 'At least 1 number (0-9)', met: /[0-9]/.test(engPassword) },
    { id: 'special', label: 'At least 1 special character (! @ # $ % ^ & *)', met: /[!@#$%^&*]/.test(engPassword) },
    {
      id: 'userEmail',
      label: 'Must not contain engineer name or email',
      met: engPassword.length > 0 &&
        !(engFirstName.trim() && engPassword.toLowerCase().includes(engFirstName.trim().toLowerCase())) &&
        !(engLastName.trim() && engPassword.toLowerCase().includes(engLastName.trim().toLowerCase())) &&
        !(engEmail.trim() && engPassword.toLowerCase().includes(engEmail.trim().toLowerCase())),
    },
    {
      id: 'commonPw',
      label: 'Must not use common passwords',
      met: engPassword.length > 0 &&
        !['password', 'password123', 'password123!', 'pass1234!', '12345678', 'qwertyuiop', 'admin123!'].some(
          (cp) => engPassword.toLowerCase() === cp || engPassword.toLowerCase().includes(cp),
        ),
    },
  ];

  const handleProvisionEngineerSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setProvisionError('');
    setProvisionSuccess('');

    if (!engFirstName.trim() || !/^[a-zA-Z]+$/.test(engFirstName.trim())) {
      setProvisionError('First Name must contain only English letters with no spaces or special characters.');
      return;
    }

    if (!engLastName.trim() || !/^[a-zA-Z]+$/.test(engLastName.trim())) {
      setProvisionError('Last Name must contain only English letters with no spaces or special characters.');
      return;
    }

    const unmet = engPasswordRules.find((rule) => !rule.met);
    if (unmet) {
      setProvisionError(`Password rule failed: ${unmet.label}`);
      return;
    }

    setIsProvisioning(true);

    try {
      const res = await provisionEngineer(engFirstName, engLastName, engEmail, engPassword, engRole, engDepartment);
      setProvisionSuccess(`Successfully provisioned engineer account for ${res.user.name} (${res.user.email})!`);
      setEngFirstName('');
      setEngLastName('');
      setEngEmail('');
      setEngPassword('');
    } catch (err) {
      if (err instanceof ApiError) {
        setProvisionError(err.message);
      } else if (err instanceof Error) {
        setProvisionError(err.message);
      } else {
        setProvisionError('Failed to provision engineer account.');
      }
    } finally {
      setIsProvisioning(false);
    }
  };

  return (
    <div className="admin-dashboard">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div>
          <h1 style={{ margin: 0 }}>Admin Dashboard</h1>
          <p className="page-subtitle" style={{ margin: '6px 0 0 0' }}>
            Enterprise analytics, conversation auditing, and system operations
          </p>
        </div>
      </div>

      {/* PROVISION ENGINEER HERO BANNER */}
      {isProvisionActive && (
        <div className="admin-provision-hero" id="admin-provision-hero">
          <div className="admin-provision-hero-header">
            <div className="admin-provision-hero-title">
              <h2>⚡ Provision Engineer Account</h2>
              <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--muted)' }}>
                Create verified IT support engineer credentials with department roles.
              </p>
            </div>
            <button
              type="button"
              className="secondary-button"
              onClick={toggleProvision}
              style={{ fontSize: '0.85rem', padding: '5px 14px' }}
            >
              ✕ Close Hero
            </button>
          </div>

          {provisionSuccess && (
            <div
              className="neo-error-banner"
              style={{
                background: '#dcfce7',
                color: '#15803d',
                borderColor: '#bbf7d0',
                marginBottom: '14px',
              }}
            >
              ✓ {provisionSuccess}
            </div>
          )}
          {provisionError && (
            <div className="neo-error-banner" style={{ marginBottom: '14px' }}>
              {provisionError}
            </div>
          )}

          <form onSubmit={handleProvisionEngineerSubmit} className="provision-form-grid">
            <div className="name-fields-row" style={{ gridColumn: 'span 2' }}>
              <div className="neo-field">
                <label>First Name</label>
                <input
                  type="text"
                  value={engFirstName}
                  onChange={(e) => setEngFirstName(e.target.value)}
                  placeholder="e.g. Alex"
                  required
                />
                {!isEngFirstNameValid && (
                  <span className="field-hint error-hint">
                    English letters only (no spaces or numbers).
                  </span>
                )}
              </div>

              <div className="neo-field">
                <label>Last Name</label>
                <input
                  type="text"
                  value={engLastName}
                  onChange={(e) => setEngLastName(e.target.value)}
                  placeholder="e.g. Smith"
                  required
                />
                {!isEngLastNameValid && (
                  <span className="field-hint error-hint">
                    English letters only (no spaces or numbers).
                  </span>
                )}
              </div>
            </div>

            <div className="neo-field">
              <label>Email Address</label>
              <input
                type="email"
                value={engEmail}
                onChange={(e) => setEngEmail(e.target.value)}
                placeholder="engineer@company.com"
                required
              />
            </div>

            <div className="neo-field">
              <label>Role</label>
              <select value={engRole} onChange={(e) => setEngRole(e.target.value as any)}>
                <option value="l1">L1 Support Engineer</option>
                <option value="l2">L2 Support Engineer</option>
                <option value="support_lead">Support Lead</option>
              </select>
            </div>

            <div className="neo-field">
              <label>Department</label>
              <input
                type="text"
                value={engDepartment}
                onChange={(e) => setEngDepartment(e.target.value)}
                placeholder="engineering"
                required
              />
            </div>

            <div className="neo-field password-field-wrapper">
              <div className="password-label-row">
                <label>Initial Password</label>
                <span
                  className="password-info-trigger"
                  onMouseEnter={() => setIsPasswordRulesVisible(true)}
                  onMouseLeave={() => setIsPasswordRulesVisible(false)}
                >
                  ⓘ Requirements
                </span>
              </div>
              <input
                type="password"
                value={engPassword}
                onChange={(e) => setEngPassword(e.target.value)}
                onFocus={() => setIsPasswordRulesVisible(true)}
                onBlur={() => setIsPasswordRulesVisible(false)}
                onMouseEnter={() => setIsPasswordRulesVisible(true)}
                onMouseLeave={() => setIsPasswordRulesVisible(false)}
                placeholder="Strong initial password"
                required
              />
              {isPasswordRulesVisible && (
                <div className="password-rules-popover">
                  <div className="password-rules-header">Password Requirements</div>
                  <ul className="password-rules-list">
                    {engPasswordRules.map((rule) => {
                      const isMet = engPassword.length > 0 ? rule.met : false;
                      return (
                        <li key={rule.id} className={`rule-item ${isMet ? 'is-satisfied' : ''}`}>
                          <span className="rule-icon">{isMet ? '✓' : '•'}</span>
                          <span className="rule-label">{rule.label}</span>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}
            </div>

            <div style={{ gridColumn: 'span 2', textAlign: 'right', marginTop: '10px' }}>
              <button
                type="submit"
                className="neo-submit-btn"
                  disabled={isProvisioning}
                  style={{ width: 'auto', padding: '10px 24px' }}
                >
                  {isProvisioning ? 'Provisioning Account...' : 'Provision Engineer Account'}
                </button>
              </div>
            </form>
          </div>
        )}

      <div className="admin-analytics-panel">
        <div className="admin-analytics-header">
          <div className="admin-analytics-title">
            <h2>Operational Analytics & Metrics</h2>
          </div>

          <button
            type="button"
            className="secondary-button"
            style={{
              fontSize: '0.8rem',
              padding: '4px 12px',
              minHeight: 'auto',
            }}
            onClick={() => setIsAnalyticsExpanded(!isAnalyticsExpanded)}
          >
            {isAnalyticsExpanded ? 'Hide Analytics ▲' : 'Show Analytics ▲'}
          </button>
        </div>

        {isAnalyticsExpanded && (
          <div className="admin-analytics-body">
            <div className="stats-row" style={{ margin: 0 }}>
              <div className="stat-card">
                <span className="stat-value">{tickets.length}</span>

                <span className="stat-label">Total Tickets</span>
              </div>

              <div className="stat-card">
                <span
                  className="stat-value"
                  style={{
                    color: '#e05638',
                  }}
                >
                  {statusCounts['ESCALATED'] ?? 0}
                </span>

                <span className="stat-label">Escalated</span>
              </div>

              <div className="stat-card">
                <span
                  className="stat-value"
                  style={{
                    color: '#0f4c47',
                  }}
                >
                  {statusCounts['IN_PROGRESS'] ?? 0}
                </span>

                <span className="stat-label">In Progress</span>
              </div>

              <div className="stat-card">
                <span
                  className="stat-value"
                  style={{
                    color: '#1e6b37',
                  }}
                >
                  {statusCounts['RESOLVED'] ?? 0}
                </span>

                <span className="stat-label">Resolved</span>
              </div>
            </div>

            <section className="admin-charts-grid" aria-label="Analytics Graphs">
              {/* STATUS BREAKDOWN */}
              <div className="chart-card">
                <div
                  className="chart-card-header"
                  style={{
                    marginBottom: '8px',
                  }}
                >
                  <h3 className="chart-card-title">Status Breakdown</h3>

                  <span className="chart-card-badge">{tickets.length} Total</span>
                </div>

                <div className="chart-bars-list" style={{ gap: '8px' }}>
                  {['ESCALATED', 'IN_PROGRESS', 'RESOLVED', 'CLOSED', 'NEW'].map((status) => {
                    const count = statusCounts[status] || 0;

                    const pct = toPercentage(count, totalCount);

                    return (
                      <div key={status} className="chart-bar-item">
                        <div
                          className="chart-bar-label-row"
                          style={{
                            fontSize: '0.78rem',
                            marginBottom: '2px',
                          }}
                        >
                          <span
                            className={`badge badge-${status.toLowerCase()}`}
                            style={{
                              fontSize: '0.65rem',
                              padding: '1px 6px',
                            }}
                          >
                            {status.replace('_', ' ')}
                          </span>

                          <span>
                            <strong>{count}</strong> ({pct}%)
                          </span>
                        </div>

                        <div
                          className="chart-bar-track"
                          style={{
                            height: '6px',
                          }}
                        >
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

              {/* CATEGORY VOLUME */}
              <div
                className="chart-card"
                style={{
                  cursor: 'pointer',
                }}
                onClick={() => setIsCategoryModalOpen(true)}
              >
                <div className="chart-card-header">
                  <h3 className="chart-card-title">Category Volume</h3>

                  <button
                    type="button"
                    className="secondary-button"
                    style={{
                      fontSize: '0.75rem',
                      padding: '3px 10px',
                      minHeight: 'auto',
                      whiteSpace: 'nowrap',
                    }}
                    onClick={(e) => {
                      e.stopPropagation();

                      setIsCategoryModalOpen(true);
                    }}
                  >
                    Expand
                  </button>
                </div>

                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flex: 1,
                    padding: '10px 0',
                  }}
                >
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
                      <span
                        style={{
                          fontSize: '0.95rem',
                          fontWeight: 700,
                          color: 'var(--ink)',
                        }}
                      >
                        {tickets.length}
                      </span>

                      <span
                        style={{
                          fontSize: '0.62rem',
                          color: 'var(--muted)',
                          textTransform: 'uppercase',
                        }}
                      >
                        Tickets
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* AI VS HUMAN */}
              <div className="chart-card">
                <div className="chart-card-header">
                  <h3 className="chart-card-title">AI vs Human Handoff</h3>

                  <span
                    className="chart-card-badge"
                    style={{
                      background: '#e6f4f2',
                      color: '#0f4c47',
                    }}
                  >
                    {aiResolutionPct}% Autonomous
                  </span>
                </div>

                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    flex: 1,
                    justifyContent: 'space-between',
                  }}
                >
                  <div
                    className="chart-bars-list"
                    style={{
                      gap: '12px',
                      margin: 'auto 0',
                    }}
                  >
                    <div className="chart-bar-item">
                      <div
                        className="chart-bar-label-row"
                        style={{
                          fontSize: '0.78rem',
                          marginBottom: '4px',
                        }}
                      >
                        <span
                          style={{
                            fontWeight: 600,
                          }}
                        >
                          AI Automated Resolution
                        </span>

                        <span
                          style={{
                            color: '#1e6b37',
                            fontWeight: 700,
                          }}
                        >
                          {aiResolutionPct}%
                        </span>
                      </div>

                      <div
                        className="chart-bar-track"
                        style={{
                          height: '8px',
                        }}
                      >
                        <div
                          className="chart-bar-fill"
                          style={{
                            width: `${aiResolutionPct}%`,
                            backgroundColor: '#1e6b37',
                          }}
                        />
                      </div>
                    </div>

                    <div className="chart-bar-item">
                      <div
                        className="chart-bar-label-row"
                        style={{
                          fontSize: '0.78rem',
                          marginBottom: '4px',
                        }}
                      >
                        <span
                          style={{
                            fontWeight: 600,
                          }}
                        >
                          Human Engineer Escalation
                        </span>

                        <span
                          style={{
                            color: '#e05638',
                            fontWeight: 700,
                          }}
                        >
                          {escalationPct}%
                        </span>
                      </div>

                      <div
                        className="chart-bar-track"
                        style={{
                          height: '8px',
                        }}
                      >
                        <div
                          className="chart-bar-fill"
                          style={{
                            width: `${escalationPct}%`,
                            backgroundColor: '#e05638',
                          }}
                        />
                      </div>
                    </div>
                  </div>

                  <div
                    style={{
                      marginTop: 'auto',
                      background: '#f8fafc',
                      padding: '8px 12px',
                      borderRadius: '6px',
                      fontSize: '0.78rem',
                      color: 'var(--muted)',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      border: '1px solid var(--line)',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        gap: '8px',
                      }}
                    >
                      <span>AI Efficiency Index =</span>

                      <strong
                        style={{
                          color: 'var(--ink)',
                        }}
                      >
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
      {error && <div className="is-error">{error}</div>}

      <div className="panel">
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '14px',
            gap: '12px',
            flexWrap: 'wrap',
          }}
        >
          <h2>Incident Queue & Conversation Audit</h2>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              flexWrap: 'wrap',
            }}
          >
            <input
              type="search"
              value={searchTerm}
              placeholder="Search tickets..."
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setCurrentPage(1);
              }}
              aria-label="Search tickets"
              style={{
                width: '220px',
                padding: '7px 10px',
                border: '1px solid var(--line)',
                borderRadius: '6px',
                background: 'var(--paper, #ffffff)',
                color: 'var(--ink)',
                fontSize: '0.82rem',
                outline: 'none',
              }}
            />

            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setCurrentPage(1);
              }}
              aria-label="Filter tickets by status"
              style={{
                minWidth: '130px',
                padding: '7px 10px',
                border: '1px solid var(--line)',
                borderRadius: '6px',
                background: 'var(--paper, #ffffff)',
                color: 'var(--ink)',
                fontSize: '0.82rem',
                cursor: 'pointer',
              }}
            >
              <option value="ALL">All Statuses</option>
              {['NEW', 'ESCALATED', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'].map((status) => (
                <option key={status} value={status}>
                  {status.replace('_', ' ')}
                </option>
              ))}
            </select>

            <select
              value={categoryFilter}
              onChange={(e) => {
                setCategoryFilter(e.target.value);
                setCurrentPage(1);
              }}
              aria-label="Filter tickets by category"
              style={{
                minWidth: '150px',
                padding: '7px 10px',
                border: '1px solid var(--line)',
                borderRadius: '6px',
                background: 'var(--paper, #ffffff)',
                color: 'var(--ink)',
                fontSize: '0.82rem',
                cursor: 'pointer',
              }}
            >
              <option value="ALL">All Categories</option>
              {allCategoryKeys.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>

            <button
              type="button"
              className="secondary-button"
              onClick={handleRefresh}
              disabled={isRefreshing}
              style={{
                fontSize: '0.8rem',
                padding: '7px 11px',
                minHeight: 'auto',
                whiteSpace: 'nowrap',
              }}
            >
              {isRefreshing ? 'Refreshing…' : '↻ Refresh'}
            </button>

            <button
              type="button"
              className="secondary-button"
              onClick={handleExportCsv}
              disabled={filteredTickets.length === 0}
              style={{
                fontSize: '0.8rem',
                padding: '7px 11px',
                minHeight: 'auto',
                whiteSpace: 'nowrap',
              }}
            >
              ↓ Export CSV
            </button>
          </div>
        </div>

        {isLoading ? (
          <div className="empty-state">
            <strong>Loading tickets…</strong>
          </div>
        ) : sortedTickets.length === 0 ? (
          <div className="empty-state">
            <strong>No tickets found</strong>
          </div>
        ) : filteredTickets.length === 0 ? (
          <div className="empty-state">
            <strong>No tickets match the current search and filters.</strong>
          </div>
        ) : (
          <>
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
                    <th
                      style={{
                        textAlign: 'center',
                        width: '50px',
                      }}
                    >
                      Chat
                    </th>
                  </tr>
                </thead>

                <tbody>
                  {/* ONLY THIS IS PAGINATED */}
                  {paginatedTickets.map((ticket) => (
                    <tr key={ticket.id}>
                      <td
                        style={{
                          fontFamily: 'monospace',
                          fontSize: '0.78rem',
                        }}
                      >
                        {ticket.id.slice(0, 8)}…
                      </td>

                      <td
                        title={ticket.title}
                        style={{
                          fontWeight: 600,
                        }}
                      >
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

                      <td
                        style={{
                          textAlign: 'center',
                        }}
                      >
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
                          <span
                            style={{
                              fontSize: '0.8rem',
                              color: 'var(--muted)',
                            }}
                          >
                            —
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginTop: '16px',
                paddingTop: '12px',
                borderTop: '1px solid var(--line)',
              }}
            >
              <span
                style={{
                  fontSize: '0.85rem',
                  color: 'var(--muted)',
                }}
              >
                Showing {startIndex + 1}
                {' – '}
                {Math.min(endIndex, filteredTickets.length)} of {filteredTickets.length}
              </span>

              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <button
                  type="button"
                  className="secondary-button"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
                >
                  ← Previous
                </button>

                <span
                  style={{
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    minWidth: '90px',
                    textAlign: 'center',
                  }}
                >
                  Page {currentPage} of {totalPages}
                </span>

                <button
                  type="button"
                  className="secondary-button"
                  disabled={currentPage >= totalPages}
                  onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
                >
                  Next →
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {inspectedTicket && (
        <div className="admin-inspector-overlay" role="dialog" aria-modal="true">
          <div className="admin-inspector-dialog">
            <div className="admin-inspector-header">
              <div>
                <h3
                  style={{
                    margin: 0,
                    fontSize: '1.1rem',
                    fontWeight: 700,
                  }}
                >
                  Auditing: {inspectedTicket.title}
                </h3>

                <span
                  style={{
                    fontSize: '0.8rem',
                    color: 'var(--muted)',
                  }}
                >
                  Ticket ID: <code>{inspectedTicket.id.slice(0, 8)}</code>
                  {' • '}
                  Status: <code>{inspectedTicket.status}</code>
                </span>
              </div>

              <button
                type="button"
                className="secondary-button"
                style={{
                  fontSize: '0.85rem',
                  padding: '6px 12px',
                  minHeight: 'auto',
                }}
                onClick={() => setInspectedTicket(null)}
              >
                Close Audit
              </button>
            </div>

            <div className="admin-inspector-body">
              {isInspectLoading ? (
                <div
                  className="empty-state"
                  style={{
                    minHeight: '180px',
                  }}
                >
                  <span>Fetching conversation transcript...</span>
                </div>
              ) : inspectedMessages.length === 0 ? (
                <div
                  className="empty-state"
                  style={{
                    minHeight: '180px',
                  }}
                >
                  <strong>No messages found in conversation</strong>
                </div>
              ) : (
                inspectedMessages.map((msg, idx) => {
                  const isEngineer =
                    msg.sender_type === 'SYSTEM' || msg.content.startsWith('[Engineer]');

                  const isUser = msg.sender_type === 'USER';

                  const messageClass = isEngineer ? 'support' : isUser ? 'user' : 'ai';

                  const label = isEngineer
                    ? 'Support Engineer'
                    : isUser
                      ? 'Employee'
                      : 'AI Helpdesk';

                  const cleanContent =
                    isEngineer && msg.content.startsWith('[Engineer] ')
                      ? msg.content.replace('[Engineer] ', '')
                      : msg.content;

                  return (
                    <div key={msg.id || idx} className={`message ${messageClass}`}>
                      <span className="message-label">{label}</span>

                      {isUser ? (
                        <span
                          style={{
                            whiteSpace: 'pre-wrap',
                          }}
                        >
                          {cleanContent}
                        </span>
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

      {isCategoryModalOpen && (
        <div
          className="admin-inspector-overlay"
          role="dialog"
          aria-modal="true"
          onClick={() => setIsCategoryModalOpen(false)}
        >
          <div
            className="admin-inspector-dialog"
            style={{
              maxWidth: '640px',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="admin-inspector-header">
              <div>
                <h3
                  style={{
                    margin: 0,
                    fontSize: '1.1rem',
                    fontWeight: 700,
                  }}
                >
                  Category Volume Distribution
                </h3>

                <span
                  style={{
                    fontSize: '0.8rem',
                    color: 'var(--muted)',
                  }}
                >
                  Total Incidents Analyzed: <strong>{tickets.length}</strong>
                  {' • '}
                  All Categories Breakdown
                </span>
              </div>

              <button
                type="button"
                className="secondary-button"
                style={{
                  fontSize: '0.85rem',
                  padding: '6px 12px',
                  minHeight: 'auto',
                }}
                onClick={() => setIsCategoryModalOpen(false)}
              >
                Close
              </button>
            </div>

            <div
              className="admin-inspector-body"
              style={{
                padding: '24px',
                display: 'flex',
                flexDirection: 'column',
                gap: '20px',
              }}
            >
              {/* LARGE DONUT */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '24px',
                  background: '#f8fafc',
                  padding: '20px',
                  borderRadius: '10px',
                  border: '1px solid var(--line)',
                }}
              >
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
                    boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
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
                    <span
                      style={{
                        fontSize: '1.05rem',
                        fontWeight: 700,
                        color: 'var(--ink)',
                      }}
                    >
                      {tickets.length}
                    </span>

                    <span
                      style={{
                        fontSize: '0.65rem',
                        color: 'var(--muted)',
                        textTransform: 'uppercase',
                      }}
                    >
                      Incidents
                    </span>
                  </div>
                </div>

                <div
                  style={{
                    flex: 1,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                  }}
                >
                  <h4
                    style={{
                      margin: 0,
                      fontSize: '0.95rem',
                      fontWeight: 700,
                      color: 'var(--ink)',
                    }}
                  >
                    Top Category: {sortedCategories[0]?.[0] || 'N/A'}
                  </h4>

                  <p
                    style={{
                      margin: 0,
                      fontSize: '0.82rem',
                      color: 'var(--muted)',
                    }}
                  >
                    Represents {toPercentage(sortedCategories[0]?.[1] || 0, totalCount)}%
                    of total logged support queries.
                  </p>
                </div>
              </div>

              {/* CATEGORY TABLE */}
              <div
                style={{
                  border: '1px solid var(--line)',
                  borderRadius: '8px',
                  overflowY: 'auto',
                  maxHeight: '360px',
                }}
              >
                <table
                  style={{
                    width: '100%',
                    borderCollapse: 'collapse',
                    fontSize: '0.85rem',
                  }}
                >
                  <thead>
                    <tr
                      style={{
                        background: '#f4f8f7',
                        textTransform: 'uppercase',
                        fontSize: '0.75rem',
                        color: 'var(--muted)',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      <th
                        style={{
                          padding: '10px 14px',
                          textAlign: 'left',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        Category
                      </th>

                      <th
                        style={{
                          padding: '10px 14px',
                          textAlign: 'right',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        Incidents
                      </th>

                      <th
                        style={{
                          padding: '10px 14px',
                          textAlign: 'right',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        Share
                      </th>

                      <th
                        style={{
                          padding: '10px 14px',
                          textAlign: 'left',
                          width: '35%',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        Distribution
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {conicSlices.map((slice) => (
                      <tr
                        key={slice.cat}
                        style={{
                          borderTop: '1px solid var(--line)',
                        }}
                      >
                        <td
                          style={{
                            padding: '10px 14px',
                            fontWeight: 600,
                            color: 'var(--ink)',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          <span
                            style={{
                              display: 'inline-block',
                              width: '8px',
                              height: '8px',
                              borderRadius: '50%',
                              backgroundColor: slice.color,
                              marginRight: '8px',
                            }}
                          />

                          {slice.cat}
                        </td>

                        <td
                          style={{
                            padding: '10px 14px',
                            textAlign: 'right',
                            fontWeight: 700,
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {slice.count}
                        </td>

                        <td
                          style={{
                            padding: '10px 14px',
                            textAlign: 'right',
                            color: 'var(--muted)',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {slice.pct}%
                        </td>

                        <td
                          style={{
                            padding: '10px 14px',
                            verticalAlign: 'middle',
                          }}
                        >
                          <div
                            style={{
                              height: '6px',
                              background: '#e2e8f0',
                              borderRadius: '999px',
                              overflow: 'hidden',
                            }}
                          >
                            <div
                              style={{
                                height: '100%',
                                width: `${slice.pct}%`,
                                backgroundColor: slice.color,
                                borderRadius: '999px',
                              }}
                            />
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
