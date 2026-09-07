import React, { useState } from 'react';

export const EmployeePortal: React.FC = () => {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<{sender: string, content: string}[]>([]);

  const handleSend = async () => {
    if (!input) return;
    
    // Add user message immediately
    setMessages(prev => [...prev, { sender: 'USER', content: input }]);
    const currentInput = input;
    setInput('');

    try {
      // In a real app, we'd create a conversation first or use an existing ID
      const response = await fetch('/api/conversations/123e4567-e89b-12d3-a456-426614174000/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: currentInput })
      });
      
      if (response.ok) {
        const data = await response.json();
        setMessages(prev => [...prev, ...data.messages]);
      }
    } catch (error) {
      console.error("Failed to send message", error);
    }
  };

  return (
    <div className="portal">
      <h1>Employee Portal - IT Helpdesk</h1>
      <div className="chat-window">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.sender.toLowerCase()}`}>
            <strong>{msg.sender}:</strong> {msg.content}
          </div>
        ))}
      </div>
      <div className="input-area">
        <input 
          value={input} 
          onChange={(e) => setInput(e.target.value)} 
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Describe your issue..." 
        />
        <button onClick={handleSend}>Send</button>
      </div>
    </div>
  );
};
