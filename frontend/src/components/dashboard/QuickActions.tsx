import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { BarChart3, ChevronRight, FileText, Search, Zap, type LucideIcon } from 'lucide-react';
import FuturisticIcon, { type FuturisticIconTone } from '../common/FuturisticIcon';
import './QuickActions.css';

export const QuickActions = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();

  const actions = [
    {
      icon: FileText,
      tone: 'cyan' as FuturisticIconTone,
      titleKey: 'quickActions.uploadDocument',
      descKey: 'quickActions.uploadDocumentDesc',
      color: '#3b82f6',
      path: '/documents',
    },
    {
      icon: BarChart3,
      tone: 'rose' as FuturisticIconTone,
      titleKey: 'quickActions.generateReports',
      descKey: 'quickActions.generateReportsDesc',
      color: '#ec4899',
      path: '/reports',
    },
    {
      icon: Search,
      tone: 'emerald' as FuturisticIconTone,
      titleKey: 'quickActions.viewTransactions',
      descKey: 'quickActions.viewTransactionsDesc',
      color: '#10b981',
      path: '/transactions',
    },
  ] as Array<{
    icon: LucideIcon;
    tone: FuturisticIconTone;
    titleKey: string;
    descKey: string;
    color: string;
    path: string;
  }>;

  return (
    <div className="quick-actions-panel">
      <div className="quick-actions-header">
        <h2>
          <FuturisticIcon icon={Zap} tone="violet" size="sm" className="quick-actions-title-icon" />
          {t('quickActions.title')}
        </h2>
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
            <div className="action-icon">
              <FuturisticIcon icon={action.icon} tone={action.tone} size="md" />
            </div>
            <div className="action-content">
              <h3>{t(action.titleKey)}</h3>
              <p>{t(action.descKey)}</p>
            </div>
            <div className="action-arrow">
              <ChevronRight size={16} />
            </div>
          </button>
        ))}
      </div>
    </div>
  );
};
