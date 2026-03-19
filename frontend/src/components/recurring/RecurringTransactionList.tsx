import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useConfirm } from '../../hooks/useConfirm';
import { RecurringTransaction } from '../../types/recurring';
import { recurringService } from '../../services/recurringService';
import { RecurringTransactionCard } from './RecurringTransactionCard';
import { CreateRecurringModal } from './CreateRecurringModal';
import { EditRecurringModal } from './EditRecurringModal';
import { useRefreshStore } from '../../stores/refreshStore';
import './RecurringTransactionList.css';

export const RecurringTransactionList: React.FC = () => {
  const { t } = useTranslation();
  const { confirm: showConfirm } = useConfirm();
  const recurringVersion = useRefreshStore((s) => s.recurringVersion);
  const [transactions, setTransactions] = useState<RecurringTransaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'active' | 'paused'>('all');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingTransaction, setEditingTransaction] = useState<RecurringTransaction | null>(null);

  const loadTransactions = async () => {
    try {
      setLoading(true);
      const data = await recurringService.list(false);
      setTransactions(data.items || []);
    } catch (error) {
      console.error('Failed to load recurring transactions:', error);
      setTransactions([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTransactions();
  }, [recurringVersion]);

  const handlePause = async (id: number) => {
    const ok = await showConfirm(t('recurring.confirmPause'), { variant: 'warning' });
    if (ok) {
      try {
        await recurringService.pause(id);
        await loadTransactions();
      } catch (error) {
        console.error('Failed to pause transaction:', error);
      }
    }
  };

  const handleResume = async (id: number) => {
    try {
      await recurringService.resume(id);
      await loadTransactions();
    } catch (error) {
      console.error('Failed to resume transaction:', error);
    }
  };

  const handleDelete = async (id: number) => {
    const ok2 = await showConfirm(t('recurring.confirmDelete'), { variant: 'danger', confirmText: t('common.delete') });
    if (ok2) {
      try {
        await recurringService.delete(id);
        await loadTransactions();
      } catch (error) {
        console.error('Failed to delete transaction:', error);
      }
    }
  };

  const filteredTransactions = transactions.filter(t => {
    if (filter === 'active') return t.is_active;
    if (filter === 'paused') return !t.is_active;
    return true;
  });

  if (loading) {
    return (
      <div className="recurring-page">
        <div className="loading-state">
          <div className="loading-spinner"></div>
          <div>{t('common.loading')}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="recurring-page">
      <div className="recurring-header">
        <h1>{t('recurring.title')}</h1>
        <div className="recurring-actions">
          <button
            onClick={() => setShowCreateModal(true)}
            className="btn-create-rental"
          >
            ➕ {t('recurring.create.title')}
          </button>
        </div>
      </div>

      <div className="recurring-filters">
        <button
          onClick={() => setFilter('all')}
          className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
        >
          {t('recurring.filter.all')} ({transactions.length})
        </button>
        <button
          onClick={() => setFilter('active')}
          className={`filter-btn ${filter === 'active' ? 'active' : ''}`}
        >
          {t('recurring.filter.active')} ({transactions.filter(t => t.is_active).length})
        </button>
        <button
          onClick={() => setFilter('paused')}
          className={`filter-btn ${filter === 'paused' ? 'active' : ''}`}
        >
          {t('recurring.filter.paused')} ({transactions.filter(t => !t.is_active).length})
        </button>
      </div>

      {filteredTransactions.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📋</div>
          <div className="empty-state-text">{t('recurring.noTransactions')}</div>
          <div className="empty-state-hint">
            {filter === 'all' 
              ? '点击上方按钮创建您的第一个定期交易'
              : `当前没有${filter === 'active' ? '活跃' : '已暂停'}的定期交易`
            }
          </div>
        </div>
      ) : (
        <div className="recurring-list">
          {filteredTransactions.map(transaction => (
            <RecurringTransactionCard
              key={transaction.id}
              transaction={transaction}
              onPause={handlePause}
              onResume={handleResume}
              onEdit={setEditingTransaction}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      {showCreateModal && (
        <CreateRecurringModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => {
            setShowCreateModal(false);
            loadTransactions();
          }}
        />
      )}

      {editingTransaction && (
        <EditRecurringModal
          transaction={editingTransaction}
          onClose={() => setEditingTransaction(null)}
          onSuccess={() => {
            setEditingTransaction(null);
            loadTransactions();
          }}
        />
      )}
    </div>
  );
};
