import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '../../stores/authStore';
import { authService } from '../../services/authService';
import { accountService } from '../../services/accountService';
import { userService } from '../../services/userService';
import LanguageSwitcher from '../../components/common/LanguageSwitcher';
import DeactivatedAccountBanner from '../../components/account/DeactivatedAccountBanner';
import './AuthPages.css';

const LoginPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const login = useAuthStore((state) => state.login);
  const updateUser = useAuthStore((state) => state.updateUser);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [twoFactorCode, setTwoFactorCode] = useState('');
  const [showTwoFactor, setShowTwoFactor] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [deactivatedInfo, setDeactivatedInfo] = useState<{
    coolingOffDaysRemaining: number;
  } | null>(null);
  const [unverifiedEmail, setUnverifiedEmail] = useState('');
  const [resending, setResending] = useState(false);
  const [resendMsg, setResendMsg] = useState('');

  const showDeactivatedSuccess =
    new URLSearchParams(location.search).get('account_deactivated') === '1';

  const handleReactivate = async () => {
    await accountService.reactivateAccount('');
    setDeactivatedInfo(null);
    setError('');
  };

  const handleResendVerification = async () => {
    setResending(true);
    setResendMsg('');

    try {
      await authService.resendVerification(unverifiedEmail);
      setResendMsg(t('auth.verificationResent', 'Verification email resent.'));
    } catch (err: any) {
      const detail = err.response?.data?.detail;

      if (detail === 'please_wait_before_resending') {
        setResendMsg(t('auth.resendWait', 'Please wait 60 seconds before resending.'));
      } else {
        setResendMsg(t('common.error'));
      }
    } finally {
      setResending(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    setDeactivatedInfo(null);
    setLoading(true);

    try {
      const response = await authService.login({
        email,
        password,
        two_factor_code: twoFactorCode || undefined,
      });

      login(response.user, response.access_token);
      navigate('/dashboard');

      try {
        const fullProfile = await userService.getProfile();
        updateUser(fullProfile);
      } catch (profileError) {
        console.warn('Failed to sync full user profile after login', profileError);
      }
    } catch (err: any) {
      const status = err.response?.status;
      const data = err.response?.data;

      if (!err.response) {
        // Network error — no response from server
        setError(t('auth.networkError', 'Unable to connect to the server. Please check your internet connection.'));
      } else if (status === 403 && data?.requires_2fa) {
        setShowTwoFactor(true);
        setError('');
      } else if (status === 403 && data?.account_status === 'deactivated') {
        setDeactivatedInfo({
          coolingOffDaysRemaining: data.cooling_off_days_remaining ?? 0,
        });
      } else if (status === 403 && data?.account_status === 'deletion_pending') {
        setError(t('auth.accountDeletionPending', 'This account has been scheduled for permanent deletion and can no longer be accessed.'));
      } else if (
        status === 403 &&
        (data?.detail === 'email_not_verified' || data?.detail?.detail === 'email_not_verified')
      ) {
        const emailAddress = data?.email || data?.detail?.email || email;
        setUnverifiedEmail(emailAddress);
      } else if (status === 429) {
        setError(t('auth.tooManyAttempts', 'Too many login attempts. Please wait a moment and try again.'));
      } else if (status === 422) {
        // Validation error — show specific field errors if available
        const errors = data?.error?.details?.errors || data?._detail_obj?.details?.errors;
        if (errors && Array.isArray(errors) && errors.length > 0) {
          const fieldMessages = errors.map((e: any) => e.message).filter(Boolean);
          setError(fieldMessages.join('\n') || t('auth.invalidInput', 'Please check your email and password format.'));
        } else {
          setError(t('auth.invalidInput', 'Please check your email and password format.'));
        }
      } else if (status === 500 || status === 502 || status === 503) {
        setError(t('auth.serverError', 'The server is temporarily unavailable. Please try again later.'));
      } else {
        // 401 or other errors — show the backend message
        const detail = data?.detail;
        if (typeof detail === 'string') {
          setError(detail);
        } else if (detail?.message) {
          setError(detail.message);
        } else {
          setError(t('auth.loginFailed', 'Login failed. Please check your email and password.'));
        }
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="language-switcher-top-right">
        <LanguageSwitcher />
      </div>

      <div className="auth-container">
        <h1>{t('common.appName')}</h1>
        <p className="auth-slogan">{t('common.slogan')}</p>

        {showDeactivatedSuccess ? (
          <div className="success-message">
            <strong>
              {t('account.deleteWizard.deactivatedSuccessTitle', 'Account deactivated')}
            </strong>
            <div>
              {t(
                'account.deleteWizard.deactivatedSuccessBody',
                'Your account has been deactivated. You can sign in again during the cooling-off period to reactivate it.'
              )}
            </div>
          </div>
        ) : null}

        {deactivatedInfo ? (
          <DeactivatedAccountBanner
            coolingOffDaysRemaining={deactivatedInfo.coolingOffDaysRemaining}
            onReactivate={handleReactivate}
          />
        ) : null}

        {unverifiedEmail ? (
          <div className="error-message auth-verification-panel">
            <div className="auth-verification-icon" aria-hidden="true">
              Mail
            </div>
            <p>
              {t('auth.emailNotVerified', 'Your email has not been verified yet.')}
            </p>
            <p className="auth-verification-hint">
              {t(
                'auth.checkInboxOrResend',
                'Check your inbox or resend the verification email.'
              )}
            </p>
            <button
              type="button"
              className="btn-secondary"
              onClick={handleResendVerification}
              disabled={resending}
            >
              {resending ? t('common.loading') : t('auth.resendEmail', 'Resend verification email')}
            </button>
            {resendMsg ? <p className="auth-verification-message">{resendMsg}</p> : null}
          </div>
        ) : null}



        {showTwoFactor ? (
          <>
            <div className="success-message" style={{ marginBottom: '16px' }}>
              <strong>{t('auth.twoFactorRequired', 'Two-factor authentication required')}</strong>
              <div>
                {t('auth.enter2FACodeForAccount', 'Enter the 6-digit code from your authenticator app for {{email}}.', { email })}
              </div>
            </div>

            <form onSubmit={handleSubmit} className="auth-form">
              <div className="form-group">
                <label>{t('auth.twoFactorCode', '2FA Code')}</label>
                <input
                  type="text"
                  value={twoFactorCode}
                  onChange={(event) => setTwoFactorCode(event.target.value)}
                  disabled={loading}
                  maxLength={6}
                  placeholder="000000"
                  autoComplete="one-time-code"
                  autoFocus
                />
              </div>

              {error ? <div className="error-message">{error}</div> : null}

              <button type="submit" className="btn-primary" disabled={loading}>
                {loading ? t('common.loading') : t('auth.verify', 'Verify')}
              </button>
            </form>

            <div className="auth-links">
              <button
                type="button"
                className="btn-link"
                onClick={() => {
                  setShowTwoFactor(false);
                  setTwoFactorCode('');
                  setError('');
                }}
              >
                {t('common.back', 'Back')}
              </button>
            </div>
          </>
        ) : (
          <>
            <form onSubmit={handleSubmit} className="auth-form">
              <div className="form-group">
                <label>{t('auth.email')}</label>
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                  disabled={loading}
                />
              </div>

              <div className="form-group">
                <label>{t('auth.password')}</label>
                <div className="password-input-wrapper">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                    disabled={loading}
                  />
                  <button
                    type="button"
                    className="password-toggle-btn"
                    onClick={() => setShowPassword(!showPassword)}
                    tabIndex={-1}
                    aria-label={showPassword ? t('auth.hidePassword', 'Hide password') : t('auth.showPassword', 'Show password')}
                  >
                    {showPassword ? '🙈' : '👁'}
                  </button>
                </div>
              </div>

              {error ? <div className="error-message">{error}</div> : null}

              <button type="submit" className="btn-primary" disabled={loading}>
                {loading ? t('common.loading') : t('auth.login')}
              </button>
            </form>

            <div className="auth-links">
              <Link to="/forgot-password">{t('auth.forgotPassword')}</Link>
              <Link to="/register">{t('auth.register')}</Link>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default LoginPage;
