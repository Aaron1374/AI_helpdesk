import { useState, type FormEvent } from 'react';
import { ApiError, login } from './api/client';
import type { AuthUser } from './api/types';
import { clearSession, getSessionUser, saveSession } from './auth/session';
import { EmployeePortal } from './portals/EmployeePortal';
import { EngineerDashboard } from './portals/EngineerDashboard';

export function App() {
  const [view, setView] = useState<'employee' | 'engineer'>('employee');
  const [user, setUser] = useState<AuthUser | null>(() => getSessionUser());

  if (!user) return <LoginScreen onLogin={setUser} />;

  return (
    <main className="app-shell">
      <nav className="topbar" aria-label="Portal navigation">
        <div className="brand-lockup">
          <span className="brand-mark">IT</span>
          <span>Helpdesk</span>
        </div>
        <div className="nav-actions">
          <button
            className={`nav-button ${view === 'employee' ? 'is-active' : ''}`}
            onClick={() => setView('employee')}
            aria-pressed={view === 'employee'}
          >
            Employee Portal
          </button>
          <button
            className={`nav-button ${view === 'engineer' ? 'is-active' : ''}`}
            onClick={() => setView('engineer')}
            aria-pressed={view === 'engineer'}
          >
            Engineer Dashboard
          </button>
          <button className="nav-button" onClick={() => { clearSession(); setUser(null); }}>
            Sign out
          </button>
        </div>
      </nav>
      <div className="page-frame">
        {view === 'employee' ? <EmployeePortal /> : <EngineerDashboard />}
      </div>
    </main>
  );
}

function LoginScreen({ onLogin }: { onLogin: (user: AuthUser) => void }) {
  const [email, setEmail] = useState('employee@example.com');
  const [password, setPassword] = useState('dev-password');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);
    try {
      const response = await login(email, password);
      saveSession(response.access_token, response.user);
      onLogin(response.user);
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : 'Unable to sign in.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-panel">
        <div className="brand-lockup login-brand"><span className="brand-mark">IT</span><span>Helpdesk</span></div>
        <p className="eyebrow">Secure access</p>
        <h1>Sign in to support</h1>
        <p className="page-subtitle">Use your helpdesk account to start a conversation with the support agent.</p>
        <form className="login-form" onSubmit={handleSubmit}>
          <label htmlFor="email">Email</label>
          <input id="email" className="text-field" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          <label htmlFor="password">Password</label>
          <input id="password" className="text-field" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          {error && <div className="is-error" role="alert">{error}</div>}
          <button className="primary-button login-submit" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </section>
    </main>
  );
}