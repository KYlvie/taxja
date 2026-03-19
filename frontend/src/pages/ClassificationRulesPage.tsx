import { useTranslation } from 'react-i18next';
import ClassificationRules from '../components/transactions/ClassificationRules';
import SubpageBackLink from '../components/common/SubpageBackLink';

const ClassificationRulesPage = () => {
  const { t } = useTranslation();

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '1rem 0' }}>
      <div style={{ marginBottom: '1rem' }}>
        <SubpageBackLink to="/advanced" />
        <h2 style={{ margin: 0 }}>{t('classificationRules.pageTitle', 'Classification Rules')}</h2>
        <p style={{ margin: '4px 0 0', color: 'var(--color-text-secondary)', fontSize: '0.9rem' }}>
          {t('classificationRules.pageSubtitle', 'Rules are auto-created when you correct a transaction category. They ensure future similar transactions are classified the same way.')}
        </p>
      </div>
      <ClassificationRules />
    </div>
  );
};

export default ClassificationRulesPage;
