import { useTranslation } from 'react-i18next';
import SubpageBackLink from '../components/common/SubpageBackLink';
import { RecurringTransactionList } from '../components/recurring/RecurringTransactionList';
import './RecurringTransactionsPage.css';

const RecurringTransactionsPage = () => {
  const { t } = useTranslation();

  return (
    <div className="recurring-transactions-page">
      <SubpageBackLink to="/advanced" label={t('common.back', 'Back')} />
      <RecurringTransactionList />
    </div>
  );
};

export default RecurringTransactionsPage;
