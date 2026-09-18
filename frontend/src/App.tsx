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

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              marginLeft: '0.5rem',
              background: '#f1f5f9',
              padding: '0.3rem 0.7rem',
              borderRadius: '6px',
              fontSize: '0.8rem'
            }}
          >
            <span style={{ color: '#334155', fontWeight: 600 }}>
              {user.email}
            </span>
            <span style={{ color: '#64748b' }}>
              ({user.role})
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
  const [role, setRole] = useState<'employee' | 'engineer' | 'admin'>('employee');
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
          role,
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
      setError(
        requestError instanceof ApiError
          ? requestError.message
          : mode === 'signup'
            ? 'Unable to create account.'
            : 'Unable to sign in.',
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-panel">

        <div className="brand-lockup login-brand">
          <span className="brand-mark">IT</span>
          <span>Helpdesk</span>
        </div>

        <div
          style={{
            display: 'flex',
            gap: '0.5rem',
            marginBottom: '1.5rem',
          }}
        >
          <button
            type="button"
            className={`nav-button ${mode === 'signin' ? 'is-active' : ''}`}
            onClick={() => switchMode('signin')}
          >
            Sign in
          </button>

          <button
            type="button"
            className={`nav-button ${mode === 'signup' ? 'is-active' : ''}`}
            onClick={() => switchMode('signup')}
          >
            Sign up
          </button>
        </div>

        <p className="eyebrow">
          {mode === 'signin' ? 'Secure access' : 'Create account'}
        </p>

        <h1>
          {mode === 'signin'
            ? 'Sign in to support'
            : 'Create your account'}
        </h1>

        <p className="page-subtitle">
          {mode === 'signin'
            ? 'Sign in with your Helpdesk credentials.'
            : 'Create an account to access the IT Helpdesk.'}
        </p>

        {mode === 'signin' && (
          <div
            style={{
              display: 'flex',
              gap: '0.5rem',
              marginBottom: '1rem',
              flexWrap: 'wrap',
            }}
          >
            <button
              type="button"
              className="nav-button"
              style={{
                fontSize: '0.8rem',
                padding: '0.35rem 0.6rem',
              }}
              onClick={() => {
                setEmail('engineer@example.com');
                setPassword('dev-password');
              }}
            >
              L1 Engineer
            </button>

            <button
              type="button"
              className="nav-button"
              style={{
                fontSize: '0.8rem',
                padding: '0.35rem 0.6rem',
              }}
              onClick={() => {
                setEmail('employee@example.com');
                setPassword('dev-password');
              }}
            >
              Employee
            </button>

            <button
              type="button"
              className="nav-button"
              style={{
                fontSize: '0.8rem',
                padding: '0.35rem 0.6rem',
              }}
              onClick={() => {
                setEmail('admin@example.com');
                setPassword('dev-password');
              }}
            >
              Admin
            </button>
          </div>
        )}

        <form className="login-form" onSubmit={handleSubmit}>

          {mode === 'signup' && (
            <>
              <label htmlFor="name">Full name</label>

              <input
                id="name"
                className="text-field"
                type="text"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Enter your full name"
                required
              />
            </>
          )}

          <label htmlFor="email">Email</label>

          <input
            id="email"
            className="text-field"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            required
          />

          {mode === 'signup' && (
            <>
              <label htmlFor="role">Account type</label>

              <select
                id="role"
                className="text-field"
                value={role}
                onChange={(event) =>
                  setRole(
                    event.target.value as
                      | 'employee'
                      | 'engineer'
                      | 'admin',
                  )
                }
              >
                <option value="employee">Employee</option>
                <option value="engineer">Engineer</option>
                <option value="admin">Admin</option>
              </select>
            </>
          )}

         {mode === 'signup' && (
  <>
    <label htmlFor="department">Department</label>

    <select
      id="department"
      className="text-field"
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
  </>
)}


          <label htmlFor="password">Password</label>

          <input
            id="password"
            className="text-field"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder={
              mode === 'signup'
                ? 'Minimum 8 characters'
                : 'Enter your password'
            }
            minLength={mode === 'signup' ? 8 : undefined}
            required
          />

          {mode === 'signup' && (
            <>
              <label htmlFor="confirm-password">
                Confirm password
              </label>

              <input
                id="confirm-password"
                className="text-field"
                type="password"
                value={confirmPassword}
                onChange={(event) =>
                  setConfirmPassword(event.target.value)
                }
                placeholder="Re-enter your password"
                minLength={8}
                required
              />
            </>
          )}

          {error && (
            <div className="is-error" role="alert">
              {error}
            </div>
          )}

          <button
            className="primary-button login-submit"
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

        <p
          style={{
            marginTop: '1rem',
            textAlign: 'center',
            fontSize: '0.85rem',
            color: '#64748b',
          }}
        >
          {mode === 'signin'
            ? "Don't have an account? "
            : 'Already have an account? '}

          <button
            type="button"
            onClick={() =>
              switchMode(
                mode === 'signin' ? 'signup' : 'signin',
              )
            }
            style={{
              border: 'none',
              background: 'none',
              padding: 0,
              cursor: 'pointer',
              fontWeight: 600,
              color: '#2563eb',
            }}
          >
            {mode === 'signin'
              ? 'Create one'
              : 'Sign in'}
          </button>
        </p>

      </section>
    </main>
  );
}