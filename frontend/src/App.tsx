import { useState, type FormEvent } from 'react';
import { ApiError, login } from './api/client';
import type { AuthUser } from './api/types';
import { clearSession, getSessionUser, saveSession } from './auth/session';
import { EmployeePortal } from './portals/EmployeePortal';
import { EngineerDashboard } from './portals/EngineerDashboard';

export function App() {
  const [user, setUser] = useState<AuthUser | null>(() => getSessionUser());
  const [view, setView] = useState<'employee' | 'engineer'>(() => {
    const sessionUser = getSessionUser();
    return sessionUser && sessionUser.role !== 'employee' ? 'engineer' : 'employee';
  });

  const handleLogin = (newUser: AuthUser) => {
    setUser(newUser);
    if (newUser.role !== 'employee') {
      setView('engineer');
    } else {
      setView('employee');
    }
  };

  if (!user) return <LoginScreen onLogin={handleLogin} />;

  const isSupportRole = user.role !== 'employee';

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
          {isSupportRole && (
            <button
              className={`nav-button ${view === 'engineer' ? 'is-active' : ''}`}
              onClick={() => setView('engineer')}
              aria-pressed={view === 'engineer'}
            >
              Engineer Dashboard
            </button>
          )}

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginLeft: '0.5rem', background: '#f1f5f9', padding: '0.3rem 0.7rem', borderRadius: '6px', fontSize: '0.8rem' }}>
            <span style={{ color: '#334155', fontWeight: 600 }}>{user.email}</span>
            <span style={{ color: '#64748b' }}>({user.role})</span>
          </div>

          <button className="nav-button" onClick={() => { clearSession(); setUser(null); }}>
            Sign out
          </button>
        </div>
      </nav>
      <div className="page-frame">
        {view === 'employee' || !isSupportRole ? (
          <EmployeePortal />
        ) : (
          <EngineerDashboard />
        )}
      </div>
    </main>
  );
}

function LoginScreen({ onLogin }: { onLogin: (user: AuthUser) => void }) {
  const [email, setEmail] = useState('engineer@example.com');
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
        <p className="page-subtitle">Select a demo account or sign in with your credentials.</p>

        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="nav-button"
            style={{ fontSize: '0.8rem', padding: '0.35rem 0.6rem' }}
            onClick={() => { setEmail('engineer@example.com'); setPassword('dev-password'); }}
          >
            L1 Engineer
          </button>
          <button
            type="button"
            className="nav-button"
            style={{ fontSize: '0.8rem', padding: '0.35rem 0.6rem' }}
            onClick={() => { setEmail('employee@example.com'); setPassword('dev-password'); }}
          >
            Employee
          </button>
          <button
            type="button"
            className="nav-button"
            style={{ fontSize: '0.8rem', padding: '0.35rem 0.6rem' }}
            onClick={() => { setEmail('admin@example.com'); setPassword('dev-password'); }}
          >
            Admin
          </button>
        </div>

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