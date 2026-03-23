import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Lightbulb, X } from 'lucide-react';
import { dashboardService } from '../../services/dashboardService';
import FuturisticIcon from '../common/FuturisticIcon';
import { normalizeLanguage } from '../../utils/locale';
import './IncomeTypeHint.css';

interface Suggestion {
  category: string;
  message: string;
  suggested_types: string[];
}

interface IncomeProfile {
  user_type: string;
  tax_year: number;
  detected: { category: string; amount: number }[];
  suggestions: Suggestion[];
}

const IncomeTypeHint = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [profile, setProfile] = useState<IncomeProfile | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const currentLanguage = normalizeLanguage(i18n.resolvedLanguage || i18n.language);

  useEffect(() => {
    const fetch = async () => {
      try {
        const data = await dashboardService.getIncomeProfile();
        setProfile(data);
      } catch {
        // silently ignore
      }
    };
    fetch();
  }, [currentLanguage]);

  if (!profile || profile.suggestions.length === 0 || dismissed) {
    return null;
  }

  return (
    <div className="income-type-hint" role="alert">
      <div className="income-type-hint-header">
        <span className="income-type-hint-icon">
          <FuturisticIcon icon={Lightbulb} tone="amber" size="sm" />
        </span>
        <span className="income-type-hint-title">{t('dashboard.incomeHint.title')}</span>
        <button
          className="income-type-hint-dismiss"
          onClick={() => setDismissed(true)}
          aria-label={t('common.close')}
        >
          <X size={14} />
        </button>
      </div>
      <ul className="income-type-hint-list">
        {profile.suggestions.map((s) => (
          <li key={s.category}>{s.message}</li>
        ))}
      </ul>
      <button
        className="income-type-hint-action"
        onClick={() => navigate('/profile')}
      >
        {t('dashboard.incomeHint.goToProfile')}
      </button>
    </div>
  );
};

export default IncomeTypeHint;
