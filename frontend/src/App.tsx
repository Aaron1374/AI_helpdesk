import { useState, type FormEvent } from 'react';
import { ApiError, login, signup, changePassword } from './api/client';
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

  const [isChangePasswordOpen, setIsChangePasswordOpen] = useState(false);
  const [isAdminProvisionOpen, setIsAdminProvisionOpen] = useState(false);

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
            <>
              <button
                className={`nav-button ${view === 'admin' ? 'is-active' : ''}`}
                onClick={() => setView('admin')}
                aria-pressed={view === 'admin'}
              >
                Admin Dashboard
              </button>

              <button
                className="nav-button nav-button-primary"
                onClick={() => {
                  setView('admin');
                  setIsAdminProvisionOpen((prev) => !prev);
                }}
              >
                + Provision Engineer
              </button>
            </>
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
            onClick={() => setIsChangePasswordOpen(true)}
          >
            Change Password
          </button>

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
          <AdminDashboard
            isProvisionHeroOpen={isAdminProvisionOpen}
            onToggleProvisionHero={() => setIsAdminProvisionOpen((prev) => !prev)}
          />
        ) : (
          <EngineerDashboard />
        )}
      </div>

      {isChangePasswordOpen && (
        <ChangePasswordModal onClose={() => setIsChangePasswordOpen(false)} />
      )}
    </main>
  );
}

function ChangePasswordModal({ onClose }: { onClose: () => void }) {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [isPasswordRulesVisible, setIsPasswordRulesVisible] = useState(false);

  const passwordRules = [
    { id: 'length', label: 'Minimum 8 characters', met: newPassword.length >= 8 },
    { id: 'uppercase', label: 'At least 1 uppercase letter (A-Z)', met: /[A-Z]/.test(newPassword) },
    { id: 'lowercase', label: 'At least 1 lowercase letter (a-z)', met: /[a-z]/.test(newPassword) },
    { id: 'number', label: 'At least 1 number (0-9)', met: /[0-9]/.test(newPassword) },
    { id: 'special', label: 'At least 1 special character (! @ # $ % ^ & *)', met: /[!@#$%^&*]/.test(newPassword) },
    {
      id: 'commonPw',
      label: 'Must not use common passwords',
      met: newPassword.length > 0 &&
        !['password', 'password123', 'password123!', 'pass1234!', '12345678', 'qwertyuiop', 'admin123!'].some(
          (cp) => newPassword.toLowerCase() === cp || newPassword.toLowerCase().includes(cp),
        ),
    },
  ];

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setSuccess('');

    if (newPassword !== confirmPassword) {
      setError('New passwords do not match.');
      return;
    }

    const unmet = passwordRules.find((r) => !r.met);
    if (unmet) {
      setError(`Password rule failed: ${unmet.label}`);
      return;
    }

    setIsSubmitting(true);

    try {
      const res = await changePassword(currentPassword, newPassword);
      setSuccess(res.message || 'Password updated successfully!');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to change password.');
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="admin-inspector-overlay" role="dialog" aria-modal="true">
      <div className="admin-inspector-dialog" style={{ maxWidth: '480px' }}>
        <div className="admin-inspector-header">
          <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700 }}>Change Password</h3>
          <button type="button" className="secondary-button" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="admin-inspector-body" style={{ padding: '20px' }}>
          {success && (
            <div className="neo-error-banner" style={{ background: '#dcfce7', color: '#15803d', borderColor: '#bbf7d0', marginBottom: '14px' }}>
              ✓ {success}
            </div>
          )}
          {error && <div className="neo-error-banner" style={{ marginBottom: '14px' }}>{error}</div>}

          <form className="neo-form-group" onSubmit={handleSubmit}>
            <div className="neo-field">
              <label htmlFor="current-pw">Current Password</label>
              <input
                id="current-pw"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Enter current password"
                required
              />
            </div>

            <div className="neo-field password-field-wrapper">
              <div className="password-label-row">
                <label htmlFor="new-pw">New Password</label>
                <span
                  className="password-info-trigger"
                  onMouseEnter={() => setIsPasswordRulesVisible(true)}
                  onMouseLeave={() => setIsPasswordRulesVisible(false)}
                >
                  ⓘ Requirements
                </span>
              </div>
              <input
                id="new-pw"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                onFocus={() => setIsPasswordRulesVisible(true)}
                onBlur={() => setIsPasswordRulesVisible(false)}
                onMouseEnter={() => setIsPasswordRulesVisible(true)}
                onMouseLeave={() => setIsPasswordRulesVisible(false)}
                placeholder="Enter new strong password"
                required
              />
              {isPasswordRulesVisible && (
                <div className="password-rules-popover">
                  <div className="password-rules-header">Password Requirements</div>
                  <ul className="password-rules-list">
                    {passwordRules.map((rule) => {
                      const isMet = newPassword.length > 0 ? rule.met : false;
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

            <div className="neo-field">
              <label htmlFor="confirm-new-pw">Confirm New Password</label>
              <input
                id="confirm-new-pw"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter new password"
                required
              />
            </div>

            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '12px' }}>
              <button type="button" className="secondary-button" onClick={onClose}>
                Cancel
              </button>
              <button type="submit" className="neo-submit-btn" style={{ width: 'auto', padding: '9px 20px' }} disabled={isSubmitting}>
                {isSubmitting ? 'Updating...' : 'Update Password'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

function LoginScreen({ onLogin }: { onLogin: (user: AuthUser) => void }) {
  const [mode, setMode] = useState<'signin' | 'signup'>('signin');

  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [department, setDepartment] = useState<'hr' | 'sales' | 'ui_ux' | 'ta'>('hr');

  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [isPasswordRulesVisible, setIsPasswordRulesVisible] = useState(false);

  function switchMode(newMode: 'signin' | 'signup') {
    setMode(newMode);
    setError('');
    setPassword('');
    setConfirmPassword('');
  }

  const isFirstNameValid = !firstName || /^[a-zA-Z]+$/.test(firstName.trim());
  const isLastNameValid = !lastName || /^[a-zA-Z]+$/.test(lastName.trim());

  const passwordRules = [
    { id: 'length', label: 'Minimum 8 characters', met: password.length >= 8 },
    { id: 'uppercase', label: 'At least 1 uppercase letter (A-Z)', met: /[A-Z]/.test(password) },
    { id: 'lowercase', label: 'At least 1 lowercase letter (a-z)', met: /[a-z]/.test(password) },
    { id: 'number', label: 'At least 1 number (0-9)', met: /[0-9]/.test(password) },
    { id: 'special', label: 'At least 1 special character (! @ # $ % ^ & *)', met: /[!@#$%^&*]/.test(password) },
    {
      id: 'userEmail',
      label: 'Must not contain your name or email',
      met: password.length > 0 &&
        !(firstName.trim() && password.toLowerCase().includes(firstName.trim().toLowerCase())) &&
        !(lastName.trim() && password.toLowerCase().includes(lastName.trim().toLowerCase())) &&
        !(email.trim() && password.toLowerCase().includes(email.trim().toLowerCase())),
    },
    {
      id: 'commonPw',
      label: 'Must not use common passwords (e.g. Password123!)',
      met: password.length > 0 &&
        !['password', 'password123', 'password123!', 'pass1234!', '12345678', 'qwertyuiop', 'admin123!'].some(
          (cp) => password.toLowerCase() === cp || password.toLowerCase().includes(cp),
        ),
    },
    {
      id: 'easilyGuessed',
      label: 'Must not contain easily guessed info (birthyear, company/role names)',
      met: password.length > 0 &&
        !/(19\d\d|20\d\d)/.test(password) &&
        !['company', 'helpdesk', 'adrian', 'employee', 'admin', 'support', 'enterprise', 'corporate', department].some(
          (term) => term && password.toLowerCase().includes(term.toLowerCase()),
        ),
    },
  ];

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      if (mode === 'signup') {
        if (!firstName.trim() || !/^[a-zA-Z]+$/.test(firstName.trim())) {
          setError('First name must contain only English letters with no spaces or special characters.');
          return;
        }

        if (!lastName.trim() || !/^[a-zA-Z]+$/.test(lastName.trim())) {
          setError('Last name must contain only English letters with no spaces or special characters.');
          return;
        }

        if (password !== confirmPassword) {
          setError('Passwords do not match.');
          return;
        }

        const unmet = passwordRules.find((rule) => !rule.met);
        if (unmet) {
          setError(`Password rule failed: ${unmet.label}`);
          return;
        }

        const response = await signup(
          firstName,
          lastName,
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
            <div className="name-fields-row">
              <div className="neo-field">
                <label htmlFor="first-name">First name</label>
                <input
                  id="first-name"
                  type="text"
                  value={firstName}
                  onChange={(event) => setFirstName(event.target.value)}
                  placeholder="Jane"
                  required
                />
                {!isFirstNameValid && (
                  <span className="field-hint error-hint">
                    English letters only (no spaces).
                  </span>
                )}
              </div>

              <div className="neo-field">
                <label htmlFor="last-name">Last name</label>
                <input
                  id="last-name"
                  type="text"
                  value={lastName}
                  onChange={(event) => setLastName(event.target.value)}
                  placeholder="Doe"
                  required
                />
                {!isLastNameValid && (
                  <span className="field-hint error-hint">
                    English letters only (no spaces).
                  </span>
                )}
              </div>
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

          <div className="neo-field password-field-wrapper">
            <div className="password-label-row">
              <label htmlFor="password">Password</label>
              {mode === 'signup' && (
                <span
                  className="password-info-trigger"
                  onMouseEnter={() => setIsPasswordRulesVisible(true)}
                  onMouseLeave={() => setIsPasswordRulesVisible(false)}
                >
                  ⓘ Requirements
                </span>
              )}
            </div>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              onFocus={() => mode === 'signup' && setIsPasswordRulesVisible(true)}
              onBlur={() => mode === 'signup' && setIsPasswordRulesVisible(false)}
              onMouseEnter={() => mode === 'signup' && setIsPasswordRulesVisible(true)}
              onMouseLeave={() => mode === 'signup' && setIsPasswordRulesVisible(false)}
              placeholder={
                mode === 'signup' ? 'Create strong password' : 'Enter password'
              }
              minLength={mode === 'signup' ? 8 : undefined}
              required
            />
            {mode === 'signup' && isPasswordRulesVisible && (
              <div className="password-rules-popover" aria-live="polite">
                <div className="password-rules-header">Password Requirements</div>
                <ul className="password-rules-list">
                  {passwordRules.map((rule) => {
                    const isMet = password.length > 0 ? rule.met : false;
                    return (
                      <li
                        key={rule.id}
                        className={`rule-item ${isMet ? 'is-satisfied' : ''}`}
                      >
                        <span className="rule-icon">{isMet ? '✓' : '•'}</span>
                        <span className="rule-label">{rule.label}</span>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
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