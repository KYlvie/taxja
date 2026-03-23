import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Select from '../components/common/Select';
import { useSubscriptionStore } from '../stores/subscriptionStore';
import SubpageBackLink from '../components/common/SubpageBackLink';
import './CreditHistoryPage.css';

const CreditHistoryPage: React.FC = () => {
  const { t } = useTranslation();
  const { creditHistory, creditLoading, fetchCreditHistory } = useSubscriptionStore();
  const [filter, setFilter] = useState<string>('all');
  const [offset, setOffset] = useState(0);
  const PAGE_SIZE = 20;

  useEffect(() => {
    fetchCreditHistory(PAGE_SIZE, 0);
  }, [fetchCreditHistory]);

  const loadMore = () => {
    const newOffset = offset + PAGE_SIZE;
    setOffset(newOffset);
    fetchCreditHistory(PAGE_SIZE, newOffset);
  };

  const filteredHistory = filter === 'all'
    ? creditHistory
    : creditHistory.filter(e => e.operation === filter);

  const getOperationIcon = (op: string) => {
    switch (op) {
      case 'deduction': return '📤';
      case 'refund': return '📥';
      case 'monthly_reset': return '🔄';
      case 'topup': return '💰';
      case 'topup_expiry': return '⏰';
      case 'overage_settlement': return '📊';
      case 'migration': return '🔀';
      default: return '📋';
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  return (
    <div className="credit-history-page">
      <div className="credit-history-header">
        <SubpageBackLink to="/dashboard" />
        <h1>{t('credits.history_title', 'Credit History')}</h1>
      </div>

      <div className="credit-history-filter">
        <label htmlFor="operation-filter">{t('credits.filter_by', 'Filter by')}:</label>
        <Select id="operation-filter" value={filter} onChange={setFilter} size="sm"
          options={[
            { value: 'all', label: t('credits.filter_all', 'All') },
            { value: 'deduction', label: t('credits.filter_deduction', 'Deductions') },
            { value: 'refund', label: t('credits.filter_refund', 'Refunds') },
            { value: 'monthly_reset', label: t('credits.filter_reset', 'Monthly Resets') },
            { value: 'topup', label: t('credits.filter_topup', 'Top-ups') },
            { value: 'topup_expiry', label: t('credits.filter_expiry', 'Expired Top-ups') },
            { value: 'overage_settlement', label: t('credits.filter_overage', 'Overage Settlements') },
          ]} />
      </div>

      <div className="credit-history-list">
        {filteredHistory.length === 0 && !creditLoading && (
          <div className="empty-state">{t('credits.no_history', 'No credit history yet.')}</div>
        )}
        {filteredHistory.map((entry) => (
          <div key={entry.id} className="history-entry">
            <div className="entry-icon">{getOperationIcon(entry.operation)}</div>
            <div className="entry-details">
              <div className="entry-operation">
                {entry.operation_detail || entry.operation}
              </div>
              {entry.reason && <div className="entry-reason">{entry.reason}</div>}
              <div className="entry-time">{formatDate(entry.created_at)}</div>
            </div>
            <div className={`entry-amount ${entry.credit_amount > 0 ? 'positive' : 'negative'}`}>
              {entry.credit_amount > 0 ? '+' : ''}{entry.credit_amount}
            </div>
          </div>
        ))}
      </div>

      {creditHistory.length >= PAGE_SIZE && (
        <button
          className="load-more-btn"
          onClick={loadMore}
          disabled={creditLoading}
        >
          {creditLoading ? t('common.loading', 'Loading...') : t('credits.load_more', 'Load More')}
        </button>
      )}
    </div>
  );
};

export default CreditHistoryPage;
