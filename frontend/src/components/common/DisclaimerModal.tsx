import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { userService } from '../../services/userService';
import './DisclaimerModal.css';

interface DisclaimerModalProps {
  isOpen: boolean;
  onAccept: () => void;
}

const DisclaimerModal = ({ isOpen, onAccept }: DisclaimerModalProps) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [hasScrolled, setHasScrolled] = useState(false);

  if (!isOpen) return null;

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const element = e.currentTarget;
    const isAtBottom = element.scrollHeight - element.scrollTop <= element.clientHeight + 50;
    if (isAtBottom && !hasScrolled) {
      setHasScrolled(true);
    }
  };

  const handleAccept = async () => {
    setLoading(true);
    setError('');

    try {
      await userService.acceptDisclaimer();
      onAccept();
    } catch (err: any) {
      setError(err.response?.data?.detail || t('common.error'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-container disclaimer-modal">
        <div className="modal-header">
          <h2>{t('disclaimer.title')}</h2>
        </div>

        <div className="modal-body" onScroll={handleScroll}>
          <div className="disclaimer-content">
            <div className="disclaimer-warning">
              <strong>⚠️ {t('disclaimer.importantNotice')}</strong>
            </div>

            <h3>{t('disclaimer.section1Title')}</h3>
            <p>{t('disclaimer.section1Content')}</p>

            <h3>{t('disclaimer.section2Title')}</h3>
            <p>{t('disclaimer.section2Content')}</p>

            <h3>{t('disclaimer.section3Title')}</h3>
            <ul>
              <li>{t('disclaimer.limitation1')}</li>
              <li>{t('disclaimer.limitation2')}</li>
              <li>{t('disclaimer.limitation3')}</li>
              <li>{t('disclaimer.limitation4')}</li>
            </ul>

            <h3>{t('disclaimer.section4Title')}</h3>
            <p>{t('disclaimer.section4Content')}</p>

            <h3>{t('disclaimer.section5Title')}</h3>
            <p>{t('disclaimer.section5Content')}</p>

            <h3>{t('disclaimer.section6Title')}</h3>
            <p>{t('disclaimer.section6Content')}</p>

            <div className="disclaimer-footer-notice">
              <p><strong>{t('disclaimer.footerNotice')}</strong></p>
              <p>{t('disclaimer.steuerberaterNotice')}</p>
            </div>

            {!hasScrolled && (
              <div className="scroll-indicator">
                ↓ {t('disclaimer.scrollToBottom')}
              </div>
            )}
          </div>
        </div>

        {error && <div className="error-message">{error}</div>}

        <div className="modal-footer">
          <p className="acceptance-notice">
            {t('disclaimer.acceptanceNotice')}
          </p>
          <button
            onClick={handleAccept}
            className="btn-primary"
            disabled={loading || !hasScrolled}
          >
            {loading ? t('common.loading') : t('disclaimer.acceptAndContinue')}
          </button>
          {!hasScrolled && (
            <p className="scroll-hint">{t('disclaimer.scrollHint')}</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default DisclaimerModal;
