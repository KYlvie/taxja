import { useTranslation } from 'react-i18next';
import ClassificationRules from '../components/transactions/ClassificationRules';
import SubpageBackLink from '../components/common/SubpageBackLink';

const ClassificationRulesPage = () => {
  const { t } = useTranslation();

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '1rem 0' }}>
      <div style={{ marginBottom: '1rem' }}>
        <SubpageBackLink to="/transactions" />
        <h2 style={{ margin: 0 }}>
          {t('classificationRules.pageTitle', 'Rules and Memory')}
        </h2>
        <p style={{ margin: '0.5rem 0 0', color: 'var(--color-text-secondary)' }}>
          {t(
            'classificationRules.pageSubtitle',
            'These memories are created automatically when you confirm categories, deductibility decisions, or bank statement actions, helping similar transactions land in the right place next time.'
          )}
        </p>
      </div>
      <ClassificationRules />
    </div>
  );
};

export default ClassificationRulesPage;
