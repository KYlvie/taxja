import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import SubpageBackLink from '../components/common/SubpageBackLink';
import AssetLiabilityOverview from '../components/liabilities/AssetLiabilityOverview';
import { liabilityService } from '../services/liabilityService';
import { LiabilitySummary } from '../types/liability';
import './TaxToolsPage.css';

const LiabilityOverviewPage = () => {
  const { t } = useTranslation();
  const [summary, setSummary] = useState<LiabilitySummary | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await liabilityService.getSummary();
        setSummary(data);
      } catch {
        setSummary(null);
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  return (
    <div className="tax-tools-page">
      <div className="tax-tools-header">
        <SubpageBackLink to="/liabilities" label={t('common.back', 'Back')} />
        <h1>{t('liabilities.overview.pageTitle', 'Liability Overview')}</h1>
      </div>

      <div className="tax-tools-content">
        <AssetLiabilityOverview summary={summary} loading={loading} />
      </div>
    </div>
  );
};

export default LiabilityOverviewPage;
