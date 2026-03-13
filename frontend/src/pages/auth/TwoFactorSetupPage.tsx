import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '../../stores/authStore';
import { authService } from '../../services/authService';
import './AuthPages.css';

const TwoFactorSetupPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { updateUser } = useAuthStore();
  
  const [qrCode, setQrCode] = useState('');
  const [secret, setSecret] = useState('');
  const [verificationCode, setVerificationCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [setupLoading, setSetupLoading] = useState(true);

  useEffect(() => {
    const initSetup = async () => {
      try {
        const response = await authService.setup2FA();
        setQrCode(response.qr_code);
        setSecret(response.secret);
      } catch (err: any) {
        setError(err.response?.data?.detail || t('common.error'));
      } finally {
        setSetupLoading(false);
      }
    };

    initSetup();
  }, [t]);

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await authService.verify2FA(verificationCode);
      
      if (response.success) {
        updateUser({ two_factor_enabled: true });
        navigate('/profile');
      } else {
        setError(t('auth.invalid2FACode'));
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || t('common.error'));
    } finally {
      setLoading(false);
    }
  };

  if (setupLoading) {
    return (
      <div className="auth-page">
        <div className="auth-container">
          <p>{t('common.loading')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-container">
        <h1>{t('auth.setup2FA')}</h1>
        <p className="auth-description">{t('auth.setup2FADescription')}</p>
        
        <div className="two-factor-setup">
          <div className="qr-code-section">
            <h3>{t('auth.step1ScanQR')}</h3>
            {qrCode && (
              <div className="qr-code">
                <img src={qrCode} alt="2FA QR Code" />
              </div>
            )}
            <p className="secret-key">
              <strong>{t('auth.manualEntry')}:</strong>
              <br />
              <code>{secret}</code>
            </p>
          </div>

          <div className="verification-section">
            <h3>{t('auth.step2VerifyCode')}</h3>
            <form onSubmit={handleVerify} className="auth-form">
              <div className="form-group">
                <label>{t('auth.enter6DigitCode')}</label>
                <input
                  type="text"
                  value={verificationCode}
                  onChange={(e) => setVerificationCode(e.target.value)}
                  required
                  disabled={loading}
                  maxLength={6}
                  pattern="[0-9]{6}"
                  placeholder="000000"
                />
              </div>

              {error && <div className="error-message">{error}</div>}

              <button type="submit" className="btn-primary" disabled={loading}>
                {loading ? t('common.loading') : t('auth.verify')}
              </button>
            </form>
          </div>
        </div>

        <div className="auth-links">
          <button 
            onClick={() => navigate('/profile')} 
            className="btn-link"
          >
            {t('common.cancel')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default TwoFactorSetupPage;
