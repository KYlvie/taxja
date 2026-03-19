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

      try {
        const fullProfile = await userService.getProfile();
        updateUser(fullProfile);
      } catch (profileError) {
        console.warn('Failed to sync full user profile after login', profileError);
      }

      navigate('/dashboard');
    } catch (err: any) {
      if (err.response?.status === 403 && err.response?.data?.requires_2fa) {
        setShowTwoFactor(true);
        setError(t('auth.enter2FACode'));
      } else if (
        err.response?.status === 403 &&
        err.response?.data?.account_status === 'deactivated'
      ) {
        setDeactivatedInfo({
          coolingOffDaysRemaining: err.response.data.cooling_off_days_remaining ?? 0,
        });
      } else if (
        err.response?.status === 403 &&
        (err.response?.data?.detail === 'email_not_verified' ||
          err.response?.data?.detail?.detail === 'email_not_verified')
      ) {
        const emailAddress = err.response?.data?.email || err.response?.data?.detail?.email || email;
        setUnverifiedEmail(emailAddress);
      } else {
        const detail = err.response?.data?.detail;
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

          {showTwoFactor ? (
            <div className="form-group">
              <label>{t('auth.twoFactorCode')}</label>
              <input
                type="text"
                value={twoFactorCode}
                onChange={(event) => setTwoFactorCode(event.target.value)}
                required
                disabled={loading}
                maxLength={6}
              />
            </div>
          ) : null}

          {error ? <div className="error-message">{error}</div> : null}

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? t('common.loading') : t('auth.login')}
          </button>
        </form>

        <div className="auth-links">
          <Link to="/forgot-password">{t('auth.forgotPassword')}</Link>
          <Link to="/register">{t('auth.register')}</Link>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
