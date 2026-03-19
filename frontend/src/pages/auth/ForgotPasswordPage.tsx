import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { authService } from '../../services/authService';
import LanguageSwitcher from '../../components/common/LanguageSwitcher';
import './AuthPages.css';

const ForgotPasswordPage = () => {
  const { t, i18n } = useTranslation();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await authService.forgotPassword(email, i18n.resolvedLanguage || 'de');
      setSent(true);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (detail === 'please_wait_before_resending') {
        setError(t('auth.resendWait', 'Please wait 60 seconds before resending.'));
      } else {
        setError(t('common.error'));
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
        <p className="auth-slogan">{t('auth.forgotPassword', 'Forgot password')}</p>

        {sent ? (
          <div className="success-message">
            <p>{t('auth.resetEmailSent', 'If this email is registered, you will receive a password reset link shortly.')}</p>
            <p style={{ marginTop: 12, fontSize: '0.85rem', color: 'var(--color-text-secondary)' }}>
              {t('auth.checkSpam', 'Please also check your spam folder.')}
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="auth-form">
            <p style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)', marginBottom: 16 }}>
              {t('auth.forgotPasswordHint', 'Enter your email address and we will send you a link to reset your password.')}
            </p>
            <div className="form-group">
              <label>{t('auth.email')}</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={loading}
                autoFocus
              />
            </div>
            {error && <div className="error-message">{error}</div>}
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? t('common.loading') : t('auth.sendResetLink', 'Send reset link')}
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

export default ForgotPasswordPage;
