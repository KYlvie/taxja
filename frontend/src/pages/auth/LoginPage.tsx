import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '../../stores/authStore';
import { authService } from '../../services/authService';
import { accountService } from '../../services/accountService';
import { userService } from '../../services/userService';
import GoogleSignInButton from '../../components/auth/GoogleSignInButton';
import LanguageSwitcher from '../../components/common/LanguageSwitcher';
import DeactivatedAccountBanner from '../../components/account/DeactivatedAccountBanner';
import { isNativeApp } from '../../mobile/runtime';
import './AuthPages.css';

const LoginPage = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const login = useAuthStore((state) => state.login);
  const updateUser = useAuthStore((state) => state.updateUser);
  const showGoogleSection = !isNativeApp();
  const googleLoginEnabled = Boolean(import.meta.env.VITE_GOOGLE_CLIENT_ID?.trim()) && showGoogleSection;

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

  const completeLogin = async (response: {
    access_token: string;
    token_type: string;
    user: Record<string, any>;
  }) => {
    login(response.user as any, response.access_token);
    if (response.user.language) {
      i18n.changeLanguage(response.user.language);
    }
    navigate('/dashboard');

    try {
      const fullProfile = await userService.getProfile();
      updateUser(fullProfile);
    } catch (profileError) {
      console.warn('Failed to sync full user profile after login', profileError);
    }
  };

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

      await completeLogin(response);
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

  const handleGoogleError = (code: 'google_login_unavailable' | 'google_token_invalid') => {
    if (code === 'google_login_unavailable') {
      setError(
        t(
          'auth.googleLoginUnavailable',
          'Google sign-in is not available right now. Please use your email and password.',
        ),
      );
      return;
    }

    setError(
      t(
        'auth.googleLoginFailed',
        'Google sign-in failed. Please try again or use your email and password.',
      ),
    );
  };

  const handleGoogleCredential = async (credential: string) => {
    setError('');
    setDeactivatedInfo(null);
    setUnverifiedEmail('');
    setLoading(true);

    try {
      const response = await authService.loginWithGoogle(credential);
      await completeLogin(response);
    } catch (err: any) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail;

      if (!err.response) {
        setError(
          t(
            'auth.networkError',
            'Unable to connect to the server. Please check your internet connection.',
          ),
        );
      } else if (status === 404 && detail === 'google_account_not_registered') {
        setError(
          t(
            'auth.googleAccountNotRegistered',
            'No Taxja account was found for this Google email yet. Please register first, then use Google sign-in with the same email.',
          ),
        );
      } else if (status === 409 && detail === 'google_login_requires_password') {
        setError(
          t(
            'auth.googleLoginRequiresPassword',
            'This account has two-factor authentication enabled. Please sign in with your email and password.',
          ),
        );
      } else if (status === 409 && detail === 'google_account_conflict') {
        setError(
          t(
            'auth.googleAccountConflict',
            'This Taxja account is already linked to a different Google account. Please use your email and password.',
          ),
        );
      } else if (status === 503 && detail === 'google_login_unavailable') {
        handleGoogleError('google_login_unavailable');
      } else {
        handleGoogleError('google_token_invalid');
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
            {showGoogleSection ? (
              <>
                <div className="auth-social-section">
                  {googleLoginEnabled ? (
                    <>
                      <GoogleSignInButton
                        disabled={loading}
                        label={t('auth.continueWithGoogle', 'Continue with Google')}
                        locale={i18n?.resolvedLanguage || i18n?.language || 'en'}
                        onCredential={handleGoogleCredential}
                        onError={handleGoogleError}
                      />
                      <p className="auth-social-note">
                        {t(
                          'auth.googleExistingAccountHint',
                          'Use the same Google email address as your existing Taxja account.',
                        )}
                      </p>
                    </>
                  ) : (
                    <>
                      <button
                        type="button"
                        className="btn-secondary google-signin-placeholder google-signin-placeholder--visible"
                        disabled
                      >
                        {t('auth.continueWithGoogle', 'Continue with Google')}
                      </button>
                      <p className="auth-social-note auth-social-note--warning">
                        {t(
                          'auth.googleClientIdMissing',
                          'Google sign-in code is ready, but this environment still needs a Google Client ID before the button can work.',
                        )}
                      </p>
                    </>
                  )}
                </div>

                <div className="auth-divider">
                  <span>{t('auth.orContinueWithEmail', 'Or continue with email')}</span>
                </div>
              </>
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
