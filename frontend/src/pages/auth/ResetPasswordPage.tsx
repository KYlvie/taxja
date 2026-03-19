import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { authService } from '../../services/authService';
import LanguageSwitcher from '../../components/common/LanguageSwitcher';
import './AuthPages.css';

const ResetPasswordPage = () => {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password.length < 8) {
      setError(t('auth.passwordTooShort', 'Password must be at least 8 characters.'));
      return;
    }
    if (password !== confirmPassword) {
      setError(t('auth.passwordMismatch', 'Passwords do not match.'));
      return;
    }

    setLoading(true);
    try {
      await authService.resetPassword(token, password);
      setSuccess(true);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (detail === 'invalid_or_expired_token' || detail === 'token_expired') {
        setError(t('auth.resetTokenExpired', 'This reset link is invalid or has expired. Please request a new one.'));
      } else {
        setError(t('common.error'));
      }
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="auth-page">
        <div className="auth-container">
          <h1>{t('common.appName')}</h1>
          <div className="error-message">
            {t('auth.resetTokenMissing', 'Invalid reset link. Please request a new password reset.')}
          </div>
          <div className="auth-links">
            <Link to="/forgot-password">{t('auth.forgotPassword', 'Forgot password')}</Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="language-switcher-top-right">
        <LanguageSwitcher />
      </div>
      <div className="auth-container">
        <h1>{t('common.appName')}</h1>
        <p className="auth-slogan">{t('auth.resetPassword', 'Reset password')}</p>

        {success ? (
          <div className="success-message">
            <p>{t('auth.passwordResetSuccess', 'Your password has been reset successfully.')}</p>
            <div className="auth-links" style={{ marginTop: 16 }}>
              <Link to="/login">{t('auth.login')}</Link>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="auth-form">
            <div className="form-group">
              <label>{t('auth.newPassword', 'New password')}</label>
              <div className="password-input-wrapper">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  disabled={loading}
                  minLength={8}
                  autoFocus
                />
                <button
                  type="button"
                  className="password-toggle-btn"
                  onClick={() => setShowPassword(!showPassword)}
                  tabIndex={-1}
                >
                  {showPassword ? '🙈' : '👁'}
                </button>
              </div>
            </div>
            <div className="form-group">
              <label>{t('auth.confirmPassword', 'Confirm password')}</label>
              <input
                type={showPassword ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                disabled={loading}
              />
            </div>
            {error && <div className="error-message">{error}</div>}
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? t('common.loading') : t('auth.resetPassword', 'Reset password')}
            </button>
          </form>
        )}

        <div className="auth-links">
          <Link to="/login">{t('auth.backToLogin', 'Back to login')}</Link>
        </div>
      </div>
    </div>
  );
};

export default ResetPasswordPage;
