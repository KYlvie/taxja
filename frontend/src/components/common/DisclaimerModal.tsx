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

  if (!isOpen) return null;

  const handleAccept = async () => {
    setLoading(true);
    setError('');
    try {
      await userService.acceptDisclaimer();
      onAccept();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (detail) setError(detail);
      else if (!err.response) setError(t('disclaimer.errorNetwork'));
      else setError(t('disclaimer.errorGeneric'));
    } finally {
      setLoading(false);
    }
  };

  const items = [
    {
      num: 1,
      label: t('disclaimer.section1Title'),
      text: t('disclaimer.section1Content'),
    },
    {
      num: 2,
      label: t('disclaimer.section2Title'),
      text: t('disclaimer.section2Content'),
    },
    {
      num: 3,
      label: t('disclaimer.section3Title'),
      text: null,
      list: [
        t('disclaimer.limitation1'),
        t('disclaimer.limitation2'),
        t('disclaimer.limitation3'),
        t('disclaimer.limitation4'),
      ],
    },
    {
      num: 4,
      label: t('disclaimer.section4Title'),
      text: t('disclaimer.section4Content'),
    },
    {
      num: 5,
      label: t('disclaimer.section5Title'),
      text: t('disclaimer.section5Content'),
    },
    {
      num: 6,
      label: t('disclaimer.section6Title'),
      text: t('disclaimer.section6Content'),
    },
    {
      num: 7,
      label: t('disclaimer.section7Title'),
      text: t('disclaimer.section7Content'),
    },
  ];

  return (
    <div className="dcl-overlay" role="dialog" aria-modal="true">
      {/* Animated background orbs */}
      <div className="dcl-orb dcl-orb-1" />
      <div className="dcl-orb dcl-orb-2" />
      <div className="dcl-orb dcl-orb-3" />
      <div className="dcl-mesh" />

      <div className="dcl-dialog">
        <div className="dcl-glow" />

        <div className="dcl-inner">
          <div className="dcl-header">
            <div className="dcl-badge">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 9v4m0 4h.01" />
                <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              </svg>
              <span>{t('disclaimer.importantNotice', 'Important')}</span>
            </div>
            <h2>{t('disclaimer.title')}</h2>
          </div>

          <div className="dcl-body">
            {items.map((item, i) => (
              <div key={i} className="dcl-item" style={{ animationDelay: `${i * 0.08}s` }}>
                <div className="dcl-item-num">{item.num}</div>
                <div className="dcl-item-content">
                  <div className="dcl-item-label">{item.label}</div>
                  {item.text && <p>{item.text}</p>}
                  {item.list && (
                    <ul>
                      {item.list.map((li, j) => (
                        <li key={j}>{li}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            ))}
          </div>

          {error && <div className="dcl-error">{error}</div>}

          <div className="dcl-footer">
            <p>{t('disclaimer.acceptanceNotice')}</p>
            <button onClick={handleAccept} className="dcl-btn" disabled={loading}>
              {loading ? <span className="dcl-spinner" /> : t('disclaimer.acceptAndContinue')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DisclaimerModal;
