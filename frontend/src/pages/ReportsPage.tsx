import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '../stores/authStore';
import AuditChecklist from '../components/reports/AuditChecklist';
import EAReport from '../components/reports/EAReport';
import BilanzReport from '../components/reports/BilanzReport';
import SaldenlisteReport from '../components/reports/SaldenlisteReport';
import PeriodensaldenlisteReport from '../components/reports/PeriodensaldenlisteReport';
import TaxFormPreview from '../components/reports/TaxFormPreview';
import YearWarning from '../components/reports/YearWarning';
import './ReportsPage.css';

type TabType = 'ea' | 'bilanz' | 'taxform' | 'saldenliste' | 'periodensaldenliste' | 'audit';

const ReportsPage = () => {
  const { t } = useTranslation();
  const currentYear = new Date().getFullYear();
  const { user } = useAuthStore();
  const userType = user?.user_type || '';
  const isGmbH = userType === 'gmbh';
  // Bilanz tab visible for: GmbH (mandatory), self-employed, mixed (may need it if >€700k)
  // Hidden for: pure employee, pure landlord
  const showBilanz = isGmbH || userType === 'selfEmployed' || userType === 'self_employed'
    || userType === 'mixed';

  // GmbH users default to Bilanz tab (they must use Bilanzierung)
  const [activeTab, setActiveTab] = useState<TabType>(isGmbH ? 'bilanz' : 'ea');
  const [auditYear, setAuditYear] = useState(currentYear);

  return (
    <div className="reports-page">
      <div className="page-header">
        <h1>{t('nav.reports')}</h1>
        <p className="page-subtitle">{t('reports.pageSubtitle')}</p>
      </div>

      <div className="tabs">
        {!isGmbH && (
          <button
            className={`tab ${activeTab === 'ea' ? 'active' : ''}`}
            onClick={() => setActiveTab('ea')}
          >
            📊 {t('reports.tabs.ea')}
          </button>
        )}
        {showBilanz && (
          <button
            className={`tab ${activeTab === 'bilanz' ? 'active' : ''}`}
            onClick={() => setActiveTab('bilanz')}
          >
            📒 {t('reports.tabs.bilanz')}
          </button>
        )}
        <button
          className={`tab ${activeTab === 'taxform' ? 'active' : ''}`}
          onClick={() => setActiveTab('taxform')}
        >
          🏛️ {isGmbH ? 'K1' : t('reports.tabs.taxForm')}
        </button>
        <button
          className={`tab ${activeTab === 'saldenliste' ? 'active' : ''}`}
          onClick={() => setActiveTab('saldenliste')}
        >
          📋 {t('reports.tabs.saldenliste')}
        </button>
        <button
          className={`tab ${activeTab === 'periodensaldenliste' ? 'active' : ''}`}
          onClick={() => setActiveTab('periodensaldenliste')}
        >
          📅 {t('reports.tabs.periodensaldenliste')}
        </button>
        <button
          className={`tab ${activeTab === 'audit' ? 'active' : ''}`}
          onClick={() => setActiveTab('audit')}
        >
          {t('reports.tabs.audit')}
        </button>
      </div>

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

        {activeTab === 'audit' && (
          <div className="audit-tab">
            <div className="year-selector">
              <label htmlFor="audit-year">{t('reports.selectYear')}</label>
              <select
                id="audit-year"
                value={auditYear}
                onChange={(e) => setAuditYear(parseInt(e.target.value))}
              >
                {Array.from({ length: 5 }, (_, i) => currentYear - i).map((year) => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                ))}
              </select>
            </div>
            <YearWarning taxYear={auditYear} />
            <AuditChecklist taxYear={auditYear} />
          </div>
        )}

      </div>
    </div>
  );
};


export default ReportsPage;
