import { useState, type FormEvent } from 'react';
import { ApiError, login, signup } from './api/client';
import type { AuthUser } from './api/types';
import { clearSession, getSessionUser, saveSession } from './auth/session';
import { EmployeePortal } from './portals/EmployeePortal';
import { EngineerDashboard } from './portals/EngineerDashboard';
import { AdminDashboard } from './portals/AdminDashboard';

export function App() {
  const [user, setUser] = useState<AuthUser | null>(() => getSessionUser());
  const [view, setView] = useState<'employee' | 'engineer' | 'admin'>(() => {
    const sessionUser = getSessionUser();
    if (!sessionUser) return 'employee';
    if (sessionUser.role === 'admin') return 'admin';
    return sessionUser.role !== 'employee' ? 'engineer' : 'employee';
  });

  const handleLogin = (newUser: AuthUser) => {
    setUser(newUser);
    if (newUser.role === 'admin') {
      setView('admin');
    } else if (newUser.role !== 'employee') {
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
          {user.role === 'employee' && (
            <button
              className={`nav-button ${view === 'employee' ? 'is-active' : ''}`}
              onClick={() => setView('employee')}
              aria-pressed={view === 'employee'}
            >
              Employee Portal
            </button>
          )}

          {user.role !== 'employee' && user.role !== 'admin' && (
            <button
              className={`nav-button ${view === 'engineer' ? 'is-active' : ''}`}
              onClick={() => setView('engineer')}
              aria-pressed={view === 'engineer'}
            >
              Engineer Dashboard
            </button>
          )}

          {user.role === 'admin' && (
            <button
              className={`nav-button ${view === 'admin' ? 'is-active' : ''}`}
              onClick={() => setView('admin')}
              aria-pressed={view === 'admin'}
            >
              Admin Dashboard
            </button>
          )}

          <div className="user-pill">
            <span className="user-pill-name">
              {user.name || user.email}
            </span>
            <span className="user-pill-role">
              ({user.role}{user.department ? ` • ${user.department}` : ''})
            </span>
          </div>

          <button
            className="nav-button"
            onClick={() => {
              clearSession();
              setUser(null);
            }}
          >
            Sign out
          </button>

        </div>
      </nav>
      <div className="page-frame">
        {view === 'employee' ? (
          <EmployeePortal />
        ) : view === 'admin' ? (
          <AdminDashboard />
        ) : (
          <EngineerDashboard />
        )}
      </div>
    </main>
  );
}

function LoginScreen({ onLogin }: { onLogin: (user: AuthUser) => void }) {
  const [mode, setMode] = useState<'signin' | 'signup'>('signin');

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [department, setDepartment] = useState<'hr' | 'sales' | 'ui_ux' | 'ta'>('hr');

  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  function switchMode(newMode: 'signin' | 'signup') {
    setMode(newMode);
    setError('');
    setPassword('');
    setConfirmPassword('');
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      if (mode === 'signup') {
        if (password !== confirmPassword) {
          setError('Passwords do not match.');
          return;
        }

        if (password.length < 8) {
          setError('Password must be at least 8 characters.');
          return;
        }

        const response = await signup(
          name,
          email,
          password,
          'employee',
          department,
        );

        saveSession(response.access_token, response.user);
        onLogin(response.user);
      } else {
        const response = await login(email, password);

        saveSession(response.access_token, response.user);
        onLogin(response.user);
      }
    } catch (requestError) {
      const msg =
        requestError instanceof ApiError
          ? requestError.message
          : requestError instanceof Error
            ? requestError.message
            : mode === 'signup'
              ? 'Unable to create account.'
              : 'Unable to sign in.';
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-panel">
        <div className="neo-brand-header">
          <div className="neo-brand-emblem">IT</div>
          <div className="neo-brand-info">
            <span className="neo-brand-title">Helpdesk</span>
            <span className="neo-brand-subtitle">Enterprise IT Support</span>
          </div>
        </div>

        <div className="neo-mode-track">
          <button
            type="button"
            className={`neo-mode-tab ${mode === 'signin' ? 'is-active' : ''}`}
            onClick={() => switchMode('signin')}
          >
            Sign in
          </button>

          <button
            type="button"
            className={`neo-mode-tab ${mode === 'signup' ? 'is-active' : ''}`}
            onClick={() => switchMode('signup')}
          >
            Sign up
          </button>
        </div>

        <p className="neo-eyebrow">
          {mode === 'signin' ? 'Secure Access' : 'New Account'}
        </p>

        <h1 className="neo-title">
          {mode === 'signin' ? 'Sign in to support' : 'Create your account'}
        </h1>

        <p className="neo-subtitle">
          {mode === 'signin'
            ? 'Sign in with your corporate Helpdesk credentials.'
            : 'Register your account to access enterprise IT self-service.'}
        </p>

        {mode === 'signin' && (
          <div className="neo-quick-box">
            <span className="neo-quick-title">Quick Demo Login</span>
            <div className="neo-chips-row">
              <button
                type="button"
                className="neo-chip-btn"
                onClick={() => {
                  setEmail('engineer@example.com');
                  setPassword('dev-password');
                }}
              >
                L1 Engineer
              </button>

              <button
                type="button"
                className="neo-chip-btn"
                onClick={() => {
                  setEmail('employee@example.com');
                  setPassword('dev-password');
                }}
              >
                Employee
              </button>

              <button
                type="button"
                className="neo-chip-btn"
                onClick={() => {
                  setEmail('admin@example.com');
                  setPassword('dev-password');
                }}
              >
                Admin
              </button>
            </div>
          </div>
        )}

        <form className="neo-form-group" onSubmit={handleSubmit}>
          {mode === 'signup' && (
            <div className="neo-field">
              <label htmlFor="name">Full name</label>
              <input
                id="name"
                type="text"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="e.g. Jane Doe"
                required
              />
            </div>
          )}

          <div className="neo-field">
            <label htmlFor="email">Email address</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              required
            />
          </div>

          {mode === 'signup' && (
            <div className="neo-field">
              <label htmlFor="department">Department</label>
              <select
                id="department"
                value={department}
                onChange={(event) =>
                  setDepartment(
                    event.target.value as 'hr' | 'sales' | 'ui_ux' | 'ta',
                  )
                }
              >
                <option value="hr">HR</option>
                <option value="sales">Sales</option>
                <option value="ui_ux">UI/UX</option>
                <option value="ta">TA</option>
              </select>
            </div>
          )}

          <div className="neo-field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder={
                mode === 'signup' ? 'Minimum 8 characters' : 'Enter password'
              }
              minLength={mode === 'signup' ? 8 : undefined}
              required
            />
          </div>

          {mode === 'signup' && (
            <div className="neo-field">
              <label htmlFor="confirm-password">Confirm password</label>
              <input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                placeholder="Re-enter password"
                minLength={8}
                required
              />
            </div>
          )}

          {error && (
            <div className="neo-error-banner" role="alert">
              {error}
            </div>
          )}

          <button
            className="neo-submit-btn"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting
              ? mode === 'signup'
                ? 'Creating account...'
                : 'Signing in...'
              : mode === 'signup'
                ? 'Create account'
                : 'Sign in'}
          </button>
        </form>

        <p className="neo-footer-note">
          {mode === 'signin'
            ? "Don't have an account? "
            : 'Already have an account? '}
          <button
            type="button"
            className="neo-switch-link"
            onClick={() =>
              switchMode(mode === 'signin' ? 'signup' : 'signin')
            }
          >
            {mode === 'signin' ? 'Create one' : 'Sign in'}
          </button>
        </p>
      </section>
    </main>
  );
}