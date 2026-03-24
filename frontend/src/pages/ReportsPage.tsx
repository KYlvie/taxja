import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { BarChart3, ClipboardList, FileStack, Landmark, Scale, TriangleAlert, type LucideIcon } from 'lucide-react';
import { transactionService } from '../services/transactionService';
import { useAuthStore } from '../stores/authStore';
import FuturisticIcon, { type FuturisticIconTone } from '../components/common/FuturisticIcon';
import EAReport from '../components/reports/EAReport';
import BilanzReport from '../components/reports/BilanzReport';
import SaldenlisteReport from '../components/reports/SaldenlisteReport';
import PeriodensaldenlisteReport from '../components/reports/PeriodensaldenlisteReport';
import TaxFormPreview from '../components/reports/TaxFormPreview';
import './ReportsPage.css';

type TabType = 'ea' | 'bilanz' | 'taxform' | 'saldenliste' | 'periodensaldenliste';

const tabMeta: Record<TabType, { icon: LucideIcon; tone: FuturisticIconTone }> = {
  ea: { icon: BarChart3, tone: 'violet' },
  bilanz: { icon: Scale, tone: 'amber' },
  taxform: { icon: Landmark, tone: 'slate' },
  saldenliste: { icon: ClipboardList, tone: 'amber' },
  periodensaldenliste: { icon: FileStack, tone: 'cyan' },
};

const ReportsPage = () => {
  const { t } = useTranslation();
  const { user } = useAuthStore();
  const userType = user?.user_type || '';
  const isGmbH = userType === 'gmbh';
  const showBilanz = isGmbH || userType === 'selfEmployed' || userType === 'self_employed'
    || userType === 'mixed';

  const [activeTab, setActiveTab] = useState<TabType>(isGmbH ? 'bilanz' : 'ea');
  const [unreviewedCount, setUnreviewedCount] = useState(0);

  useEffect(() => {
    transactionService
      .getAll({ needs_review: true }, { page: 1, page_size: 1 })
      .then((res) => setUnreviewedCount(res.total))
      .catch(() => setUnreviewedCount(0));
  }, []);

  return (
    <div className="reports-page">
      <div className="page-header">
        <h1>{t('nav.reports')}</h1>
      </div>

      <div className="tabs">
        {!isGmbH && (
          <button
            className={`tab ${activeTab === 'ea' ? 'active' : ''}`}
            onClick={() => setActiveTab('ea')}
          >
            <FuturisticIcon icon={tabMeta.ea.icon} tone={tabMeta.ea.tone} size="xs" />
            <span>{t('reports.tabs.ea')}</span>
          </button>
        )}
        {showBilanz && (
          <button
            className={`tab ${activeTab === 'bilanz' ? 'active' : ''}`}
            onClick={() => setActiveTab('bilanz')}
          >
            <FuturisticIcon icon={tabMeta.bilanz.icon} tone={tabMeta.bilanz.tone} size="xs" />
            <span>{t('reports.tabs.bilanz')}</span>
          </button>
        )}
        <button
          className={`tab ${activeTab === 'saldenliste' ? 'active' : ''}`}
          onClick={() => setActiveTab('saldenliste')}
        >
          <FuturisticIcon icon={tabMeta.saldenliste.icon} tone={tabMeta.saldenliste.tone} size="xs" />
          <span>{t('reports.tabs.saldenliste')}</span>
        </button>
        <button
          className={`tab ${activeTab === 'periodensaldenliste' ? 'active' : ''}`}
          onClick={() => setActiveTab('periodensaldenliste')}
          >
          <FuturisticIcon icon={tabMeta.periodensaldenliste.icon} tone={tabMeta.periodensaldenliste.tone} size="xs" />
          <span>{t('reports.tabs.periodensaldenliste')}</span>
        </button>
        <button
          className={`tab tab-taxform ${activeTab === 'taxform' ? 'active' : ''}`}
          onClick={() => setActiveTab('taxform')}
        >
          <FuturisticIcon icon={tabMeta.taxform.icon} tone={tabMeta.taxform.tone} size="xs" />
          <span>{isGmbH ? 'K1' : t('reports.tabs.taxForm')}</span>
        </button>
      </div>

      {unreviewedCount > 0 && (
        <div className="report-warning-banner">
          <TriangleAlert size={16} />
          <span>
            {t('reports.unreviewedWarning', {
              count: unreviewedCount,
              defaultValue: '{{count}} unreviewed transaction(s) are included in this report. Please review them for accuracy.'
            })}
          </span>
          <Link to="/transactions?needs_review=true">
            {t('reports.reviewTransactions', 'Review transactions')}
          </Link>
        </div>
      )}

      <div className="tab-content">
        {activeTab === 'ea' && (
          <div className="ea-tab">
            <EAReport />
          </div>
        )}

        {activeTab === 'bilanz' && (
          <div className="bilanz-tab">
            <BilanzReport />
          </div>
        )}

        {activeTab === 'taxform' && (
          <div className="taxform-tab">
            <TaxFormPreview />
          </div>
        )}

        {activeTab === 'saldenliste' && (
          <div className="saldenliste-tab">
            <SaldenlisteReport />
          </div>
        )}

        {activeTab === 'periodensaldenliste' && (
          <div className="periodensaldenliste-tab">
            <PeriodensaldenlisteReport />
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportsPage;
