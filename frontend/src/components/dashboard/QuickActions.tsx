import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import './QuickActions.css';

export const QuickActions = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();

  const actions = [
    {
      icon: '📄',
      titleKey: 'quickActions.uploadDocument',
      descKey: 'quickActions.uploadDocumentDesc',
      color: '#3b82f6',
      path: '/documents'
    },
    {
      icon: '💰',
      titleKey: 'quickActions.addTransaction',
      descKey: 'quickActions.addTransactionDesc',
      color: '#10b981',
      path: '/transactions'
    },
    {
      icon: '💼',
      titleKey: 'quickActions.manageProperties',
      descKey: 'quickActions.managePropertiesDesc',
      color: '#f59e0b',
      path: '/properties'
    },
    {
      icon: '📊',
      titleKey: 'quickActions.generateReports',
      descKey: 'quickActions.generateReportsDesc',
      color: '#ec4899',
      path: '/reports'
    },
    {
      icon: '🤖',
      titleKey: 'quickActions.aiAssistant',
      descKey: 'quickActions.aiAssistantDesc',
      color: '#06b6d4',
      path: '/ai-assistant'
    }
  ];

  return (
    <div className="quick-actions-panel">
      <div className="quick-actions-header">
        <h2>⚡ {t('quickActions.title')}</h2>
        <p>{t('quickActions.subtitle')}</p>
      </div>
      <div className="quick-actions-grid">
        {actions.map((action, index) => (
          <button
            key={index}
            className="quick-action-card"
            onClick={() => navigate(action.path)}
            style={{ borderLeftColor: action.color }}
          >
            <div className="action-icon" style={{ backgroundColor: `${action.color}15` }}>
              {action.icon}
            </div>
            <div className="action-content">
              <h3>{t(action.titleKey)}</h3>
              <p>{t(action.descKey)}</p>
            </div>
            <div className="action-arrow">→</div>
          </button>
        ))}
      </div>
    </div>
  );
};
