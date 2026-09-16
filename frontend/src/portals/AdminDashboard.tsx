import React, { useEffect, useState } from 'react';
import { getTickets, ApiError } from '../api/client';
import type { TicketItem } from '../api/types';

export const AdminDashboard: React.FC = () => {
  const [tickets, setTickets] = useState<TicketItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

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

        if (
          err instanceof ApiError &&
          (err.status === 401 || err.status === 403)
        ) {
          setError('Access restricted: Admin role is required.');
        } else if (err instanceof Error) {
          setError(err.message);
        } else {
          setError('Failed to load tickets.');
        }

        setIsLoading(false);
      }
    };

    // Initial load
    loadTickets();

    // Refresh every 7 seconds while the tab is visible
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

  const statusCounts = tickets.reduce<Record<string, number>>((acc, ticket) => {
    acc[ticket.status] = (acc[ticket.status] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="admin-dashboard">
      <h1>Admin Dashboard</h1>

      <p className="page-subtitle">
        System overview and management
      </p>

      {/* Statistics */}
      <div className="stats-row">
        <div className="stat-card">
          <span className="stat-value">
            {tickets.length}
          </span>
          <span className="stat-label">
            Total Tickets
          </span>
        </div>

        <div className="stat-card">
          <span className="stat-value">
            {statusCounts['ESCALATED'] ?? 0}
          </span>
          <span className="stat-label">
            Escalated
          </span>
        </div>

        <div className="stat-card">
          <span className="stat-value">
            {statusCounts['IN_PROGRESS'] ?? 0}
          </span>
          <span className="stat-label">
            In Progress
          </span>
        </div>

        <div className="stat-card">
          <span className="stat-value">
            {statusCounts['RESOLVED'] ?? 0}
          </span>
          <span className="stat-label">
            Resolved
          </span>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="is-error">
          {error}
        </div>
      )}

      {/* Ticket Queue */}
      <div className="panel">
        <h2>Ticket Queue</h2>

        {isLoading ? (
          <div className="empty-state">
            <strong>Loading tickets…</strong>
          </div>
        ) : tickets.length === 0 ? (
          <div className="empty-state">
            <strong>No tickets</strong>
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
                </tr>
              </thead>

              <tbody>
                {tickets.map((ticket) => (
                  <tr key={ticket.id}>
                    <td
                      style={{
                        fontFamily: 'monospace',
                        fontSize: '0.78rem',
                      }}
                    >
                      {ticket.id.slice(0, 8)}…
                    </td>

                    <td title={ticket.title}>
                      {ticket.title}
                    </td>

                    <td>
                      <span
                        className={`badge badge-${ticket.status.toLowerCase()}`}
                      >
                        {ticket.status}
                      </span>
                    </td>

                    <td>
                      {ticket.priority}
                    </td>

                    <td>
                      {ticket.category ?? '—'}
                    </td>
                    <td>
                      {ticket.status === 'ESCALATED'
                        ? 'L1 Engineer'
                        : ticket.status === 'IN_PROGRESS'
                          ? 'L1 Engineer'
                          : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default AdminDashboard;