import React, { useState, useEffect } from 'react';

export const EngineerDashboard: React.FC = () => {
  const [tickets, setTickets] = useState<{id: string, title: string, status: string, conversation_id: string | null}[]>([]);
  const [similarTickets, setSimilarTickets] = useState<Record<string, {title: string, content: string, status: string}[]>>({});

  useEffect(() => {
    // Fetch escalated tickets
    const fetchTickets = async () => {
      try {
        const response = await fetch('/api/tickets', {
          headers: { 'Authorization': 'Bearer DUMMY_ENGINEER_TOKEN' }
        });
        if (response.ok) {
          const data = await response.json();
          setTickets(data);
          
          // Fetch similar incidents for each ticket
          for (const ticket of data) {
            fetch(`/api/tickets/${ticket.id}/similar`, {
              headers: { 'Authorization': 'Bearer DUMMY_ENGINEER_TOKEN' }
            })
            .then(res => res.json())
            .then(similarData => {
              setSimilarTickets(prev => ({...prev, [ticket.id]: similarData}));
            })
            .catch(err => console.error(err));
          }
        }
      } catch (e) {
        console.error(e);
      }
    };
    fetchTickets();
  }, []);

  const handleTakeover = async (id: string, convId: string | null) => {
    if (!convId) {
      alert('No conversation associated with this ticket.');
      return;
    }
    try {
      await fetch(`/api/conversations/${convId}/takeover`, {
        method: 'POST',
        headers: { 'Authorization': 'Bearer DUMMY_ENGINEER_TOKEN' }
      });
      alert('Conversation taken over by engineer.');
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="engineer-dashboard">
      <h1>Engineer Dashboard</h1>
      <div className="ticket-list">
        {tickets.map(ticket => (
          <div key={ticket.id} className="ticket-item">
            <span>{ticket.title} ({ticket.status})</span>
            
            <div className="similar-incidents">
              <h4>Similar Incidents:</h4>
              {similarTickets[ticket.id] && similarTickets[ticket.id].length > 0 ? (
                <ul>
                  {similarTickets[ticket.id].map((sim, idx) => (
                    <li key={idx}>{sim.title} ({sim.status})</li>
                  ))}
                </ul>
              ) : (
                <p>No similar incidents found.</p>
              )}
            </div>

            {ticket.status === 'ESCALATED' && (
              <button onClick={() => handleTakeover(ticket.id, ticket.conversation_id)}>Take Over</button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
