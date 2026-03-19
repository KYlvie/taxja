import { useEffect, useState } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '../../stores/authStore';
import { authService } from '../../services/authService';
import LanguageSwitcher from '../../components/common/LanguageSwitcher';
import './AuthPages.css';

const VerifyEmailPage = () => {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const loginStore = useAuthStore((s) => s.login);
  const token = searchParams.get('token');

  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setErrorMsg(t('auth.verifyMissingToken', 'No verification token found.'));
      return;
    }

    const verify = async () => {
      try {
        const res = await authService.verifyEmail(token);
        loginStore(res.user, res.access_token);
        setStatus('success');
        // Redirect to dashboard after 2 seconds
        setTimeout(() => navigate('/dashboard'), 2000);
      } catch (err: any) {
        setStatus('error');
        const detail = err.response?.data?.detail;
        if (detail === 'invalid_or_expired_token') {
          setErrorMsg(t('auth.verifyInvalidToken', 'This link is invalid or has expired.'));
        } else {
          setErrorMsg(t('common.error'));
        }
      }
    };

    verify();
  }, [token, loginStore, navigate, t]);

  return (
    <div className="auth-page">
      <div className="language-switcher-top-right">
        <LanguageSwitcher />
      </div>
      <div className="auth-container" style={{ textAlign: 'center' }}>
        {status === 'loading' && (
          <>
            <div style={{ fontSize: '2.5rem', marginBottom: '16px' }}>⏳</div>
            <h1>{t('auth.verifyingEmail', 'Verifying your email...')}</h1>
            <p style={{ color: 'var(--color-text-secondary)' }}>{t('common.loading')}</p>
          </>
        )}

        {status === 'success' && (
          <>
            <div style={{ fontSize: '3rem', marginBottom: '16px' }}>✅</div>
            <h1>{t('auth.emailVerified', 'Email verified!')}</h1>
            <p style={{ color: 'var(--color-text-secondary)', margin: '16px 0' }}>
              {t('auth.emailVerifiedDesc', 'Your account is now active. Redirecting to dashboard...')}
            </p>
            <Link to="/dashboard" className="btn-primary" style={{ textDecoration: 'none', padding: '10px 24px' }}>
              {t('auth.goToDashboard', 'Go to Dashboard')}
            </Link>
          </>
        )}

        {status === 'error' && (
          <>
            <div style={{ fontSize: '3rem', marginBottom: '16px' }}>❌</div>
            <h1>{t('auth.verifyFailed', 'Verification failed')}</h1>
            <p style={{ color: 'var(--color-text-secondary)', margin: '16px 0' }}>{errorMsg}</p>
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', marginTop: '24px' }}>
              <Link to="/register" className="btn-secondary" style={{ textDecoration: 'none', padding: '10px 24px' }}>
                {t('auth.register')}
              </Link>
              <Link to="/login" className="btn-primary" style={{ textDecoration: 'none', padding: '10px 24px' }}>
                {t('auth.login')}
              </Link>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default VerifyEmailPage;
