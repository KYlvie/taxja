import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { getLocaleForLanguage } from '../../utils/locale';
import ConfirmDialog from '../common/ConfirmDialog';
import './UserSubscriptionList.css';

interface UserSubscription {
  user_id: number;
  email: string;
  plan_type: string;
  status: string;
  current_period_start: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
}

interface UserSubscriptionListProps {
  onGrantTrial?: (userId: number) => void;
  onChangePlan?: (userId: number, newPlanId: number) => void;
  onExtend?: (userId: number, days: number) => void;
}

const UserSubscriptionList: React.FC<UserSubscriptionListProps> = ({
  onGrantTrial,
  onChangePlan,
  onExtend,
}) => {
  const { t, i18n } = useTranslation();
  const [subscriptions, setSubscriptions] = useState<UserSubscription[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const itemsPerPage = 20;
  const locale = getLocaleForLanguage(i18n.resolvedLanguage || i18n.language);
  const [showGrantTrialConfirm, setShowGrantTrialConfirm] = useState<number | null>(null);

  useEffect(() => {
    fetchSubscriptions();
  }, [currentPage, searchTerm]);

  const fetchSubscriptions = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        page: currentPage.toString(),
        limit: itemsPerPage.toString(),
        ...(searchTerm && { search: searchTerm }),
      });

      const response = await fetch(`/api/v1/admin/subscriptions?${params}`);
      const data = await response.json();

      setSubscriptions(data.items || []);
      setTotalPages(Math.ceil((data.total || 0) / itemsPerPage));
    } catch (error) {
      console.error('Failed to fetch subscriptions:', error);
    } finally {
      setLoading(false);
    }
  };

  const getPlanLabel = (plan: string) => {
    const key = `pricing.plans.${plan}.name`;
    const label = t(key);
    return label === key ? plan.toUpperCase() : label;
  };

  const getStatusLabel = (status: string) => {
    const key = `admin.status.${status}`;
    const label = t(key);
    return label === key ? status : label;
  };

  const handleSearch = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchTerm(event.target.value);
    setCurrentPage(1);
  };

  const handleGrantTrialRequest = (userId: number) => {
    setShowGrantTrialConfirm(userId);
  };

  const handleGrantTrialConfirm = async () => {
    const userId = showGrantTrialConfirm;
    setShowGrantTrialConfirm(null);
    if (!userId) return;

    try {
      await fetch(`/api/v1/admin/subscriptions/${userId}/grant-trial`, {
        method: 'POST',
      });
      fetchSubscriptions();
      onGrantTrial?.(userId);
    } catch (error) {
      console.error('Failed to grant trial:', error);
    }
  };

  const handleChangePlan = async (userId: number) => {
    const newPlanId = prompt(t('admin.prompt.new_plan_id'));
    if (!newPlanId) return;

    try {
      await fetch(`/api/v1/admin/subscriptions/${userId}/change-plan`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan_id: parseInt(newPlanId, 10) }),
      });
      fetchSubscriptions();
      onChangePlan?.(userId, parseInt(newPlanId, 10));
    } catch (error) {
      console.error('Failed to change plan:', error);
    }
  };

  const handleExtend = async (userId: number) => {
    const days = prompt(t('admin.prompt.extend_days'));
    if (!days) return;

    try {
      await fetch(`/api/v1/admin/subscriptions/${userId}/extend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ days: parseInt(days, 10) }),
      });
      fetchSubscriptions();
      onExtend?.(userId, parseInt(days, 10));
    } catch (error) {
      console.error('Failed to extend subscription:', error);
    }
  };

  const getStatusBadge = (status: string) => {
    const statusClass = status.toLowerCase().replace('_', '-');
    return <span className={`status-badge ${statusClass}`}>{getStatusLabel(status)}</span>;
  };

  if (loading && subscriptions.length === 0) {
    return <div className="loading">{t('common.loading')}</div>;
  }

  return (
    <div className="user-subscription-list">
      <div className="list-header">
        <h2>{t('admin.subscriptions.title')}</h2>
        <input
          type="text"
          placeholder={t('admin.subscriptions.search')}
          value={searchTerm}
          onChange={handleSearch}
          className="search-input"
        />
      </div>

      <div className="table-container">
        <table className="subscriptions-table">
          <thead>
            <tr>
              <th>{t('admin.subscriptions.user_id')}</th>
              <th>{t('admin.subscriptions.email')}</th>
              <th>{t('admin.subscriptions.plan')}</th>
              <th>{t('admin.subscriptions.status')}</th>
              <th>{t('admin.subscriptions.period_end')}</th>
              <th>{t('admin.subscriptions.actions')}</th>
            </tr>
          </thead>
          <tbody>
            {subscriptions.map((sub) => (
              <tr key={sub.user_id}>
                <td>{sub.user_id}</td>
                <td>{sub.email}</td>
                <td>
                  <span className={`plan-badge ${sub.plan_type}`}>
                    {getPlanLabel(sub.plan_type)}
                  </span>
                </td>
                <td>{getStatusBadge(sub.status)}</td>
                <td>
                  {new Date(sub.current_period_end).toLocaleDateString(locale)}
                  {sub.cancel_at_period_end && (
                    <span className="cancel-notice">
                      {' '}
                      ({t('admin.subscriptions.canceling')})
                    </span>
                  )}
                </td>
                <td>
                  <div className="action-buttons">
                    <button
                      type="button"
                      onClick={() => handleGrantTrialRequest(sub.user_id)}
                      className="btn-small"
                      title={t('admin.actions.grant_trial')}
                    >
                      {t('admin.actions.grant_trial_short')}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleChangePlan(sub.user_id)}
                      className="btn-small"
                      title={t('admin.actions.change_plan')}
                    >
                      {t('admin.actions.change_plan_short')}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleExtend(sub.user_id)}
                      className="btn-small"
                      title={t('admin.actions.extend')}
                    >
                      {t('admin.actions.extend_short')}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="pagination">
          <button
            type="button"
            onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
            disabled={currentPage === 1}
          >
            {t('common.previous')}
          </button>
          <span>
            {t('common.page')} {currentPage} / {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
            disabled={currentPage === totalPages}
          >
            {t('common.next')}
          </button>
        </div>
      )}
      <ConfirmDialog
        isOpen={showGrantTrialConfirm !== null}
        message={t('admin.confirm.grant_trial', 'Grant trial to this user?')}
        variant="warning"
        confirmText={t('common.confirm', 'Confirm')}
        cancelText={t('common.cancel', 'Cancel')}
        onConfirm={handleGrantTrialConfirm}
        onCancel={() => setShowGrantTrialConfirm(null)}
      />
    </div>
  );
};

export default UserSubscriptionList;
