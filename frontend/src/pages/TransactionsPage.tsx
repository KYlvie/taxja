import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import Select from '../components/common/Select';
import { Download, Plus, RefreshCw, Sparkles, Trash2 } from 'lucide-react';
import { useTransactionStore } from '../stores/transactionStore';
import { transactionService } from '../services/transactionService';
import { saveBlobWithNativeShare } from '../mobile/files';
import TransactionList from '../components/transactions/TransactionList';
import TransactionFilters from '../components/transactions/TransactionFilters';
import TransactionForm from '../components/transactions/TransactionForm';
import TransactionDetail from '../components/transactions/TransactionDetail';
import { Transaction, TransactionFormData } from '../types/transaction';
import { useRefreshStore } from '../stores/refreshStore';
import { aiToast } from '../stores/aiToastStore';
import { useAIConfirmation } from '../hooks/useAIConfirmation';
import './TransactionsPage.css';

type ViewMode = 'list' | 'create' | 'edit' | 'detail';

const TransactionsPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const transactionIdParam = searchParams.get('transactionId');
  const {
    transactions,
    filters,
    selectedTransaction,
    isLoading,
    error,
    pagination,
    setTransactions,
    addTransaction,
    updateTransaction,
    deleteTransaction,
    setFilters,
    setSelectedTransaction,
    setLoading,
    setError,
    setPagination,
    clearFilters,
  } = useTransactionStore();

  const transactionsVersion = useRefreshStore((s) => s.transactionsVersion);
  const { confirm: aiConfirm, alert: aiAlert } = useAIConfirmation();
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [sortBy] = useState<'date' | 'amount'>('date');
  const [sortOrder] = useState<'asc' | 'desc'>('desc');
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [batchDeleting, setBatchDeleting] = useState(false);

  const setTransactionQueryParam = (transactionId: number | null) => {
    const next = new URLSearchParams(searchParams);
    if (transactionId == null) {
      next.delete('transactionId');
    } else {
      next.set('transactionId', String(transactionId));
    }
    setSearchParams(next, { replace: true });
  };

  const openTransactionDetail = (transaction: Transaction) => {
    setSelectedTransaction(transaction);
    setViewMode('detail');
    setTransactionQueryParam(transaction.id);
  };

  const closeTransactionDetail = () => {
    setViewMode('list');
    setSelectedTransaction(null);
    setTransactionQueryParam(null);
  };

  useEffect(() => {
    void fetchTransactions();
  }, [filters, pagination.page, pagination.pageSize, sortBy, sortOrder, transactionsVersion]);

  useEffect(() => {
    if (!transactionIdParam) {
      return;
    }

    const transactionId = Number(transactionIdParam);
    if (!Number.isInteger(transactionId) || transactionId <= 0) {
      setTransactionQueryParam(null);
      return;
    }

    let active = true;
    transactionService.getById(transactionId)
      .then((transaction) => {
        if (!active) return;
        setSelectedTransaction(transaction);
        setViewMode('detail');
      })
      .catch((err: any) => {
        if (!active) return;
        const msg = err.response?.data?.detail || t('transactions.fetchError');
        setError(msg);
        aiToast(msg, 'error');
        setTransactionQueryParam(null);
      });

    return () => {
      active = false;
    };
  }, [transactionIdParam]);

  // Clear selection when filters change (but NOT on page change — keep cross-page selection)
  useEffect(() => {
    setSelectedIds(new Set());
  }, [filters]);

  const fetchTransactions = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await transactionService.getAll(filters, {
        page: pagination.page,
        page_size: pagination.pageSize,
      });

      setTransactions(response.items);
      setPagination({
        total: response.total,
        page: response.page,
        pageSize: response.page_size,
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || t('transactions.fetchError'));
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTransaction = async (data: TransactionFormData) => {
    try {
      const newTransaction = await transactionService.create(data);
      addTransaction(newTransaction);
      setViewMode('list');
      aiToast(t('transactions.createSuccess', 'Transaction created'), 'success');
    } catch (err: any) {
      const msg = err.response?.data?.detail || t('transactions.createError');
      setError(msg);
      aiToast(msg, 'error');
      throw err;
    }
  };

  const handleUpdateTransaction = async (data: TransactionFormData) => {
    if (!selectedTransaction) return;

    try {
      const updated = await transactionService.update(selectedTransaction.id, data);
      updateTransaction(selectedTransaction.id, updated);
      setViewMode('list');
      setSelectedTransaction(null);
      setTransactionQueryParam(null);
      aiToast(t('transactions.updateSuccess', 'Transaction updated'), 'success');
    } catch (err: any) {
      const msg = err.response?.data?.detail || t('transactions.updateError');
      setError(msg);
      aiToast(msg, 'error');
      throw err;
    }
  };

  const handleDeleteTransaction = async (id: number) => {
    try {
      const check = await transactionService.deleteCheck(id);

      if (check.warning_type === 'document_only') {
        const goToDoc = await aiConfirm(
          t('transactions.deleteCheck.documentOnly', { name: check.document_name }),
          { variant: 'info', confirmText: t('transactions.deleteCheck.goToDocument', 'View Document'), cancelText: t('common.close', 'Close') }
        );
        if (goToDoc && check.document_id) {
          navigate(`/documents/${check.document_id}`);
        }
        return;
      }

      if (check.warning_type === 'document_multi') {
        const confirmed = await aiConfirm(
          t('transactions.deleteCheck.documentMulti', {
            name: check.document_name || '-',
            count: check.linked_transaction_count ?? 0,
          })
        );
        if (!confirmed) return;
        await transactionService.delete(id, true);
      } else if (check.warning_type === 'recurring') {
        const confirmed = await aiConfirm(t('transactions.deleteCheck.recurring'));
        if (!confirmed) return;
        await transactionService.delete(id, true);
      } else {
        const confirmed = await aiConfirm(t('transactions.deleteCheck.confirmDelete'));
        if (!confirmed) return;
        await transactionService.delete(id);
      }

      deleteTransaction(id);
      setViewMode('list');
      setSelectedTransaction(null);
      setTransactionQueryParam(null);
      aiToast(t('transactions.deleteSuccess', 'Transaction deleted'), 'success');
    } catch (err: any) {
      const msg = err.response?.data?.detail || t('transactions.deleteError');
      setError(msg);
      aiToast(msg, 'error');
    }
  };

  const handleBatchDelete = async () => {
    if (selectedIds.size === 0) return;
    setBatchDeleting(true);
    try {
      // Pre-check first
      const preCheck = await transactionService.batchDelete(Array.from(selectedIds), false);

      const safeCount = preCheck.safe?.length || 0;
      const confirmCount = preCheck.needs_confirmation?.length || 0;
      const blockedCount = preCheck.blocked?.length || 0;

      if (blockedCount > 0 && safeCount === 0 && confirmCount === 0) {
        await aiAlert(t('transactions.batchDeleteCheck.blocked', { count: blockedCount }));
        return;
      }

      // Show summary and ask for confirmation
      const summary = t('transactions.batchDeleteCheck.summary', {
        safe: safeCount,
        confirm: confirmCount,
        blocked: blockedCount,
      });

      if (blockedCount > 0) {
        const blockedMsg = t('transactions.batchDeleteCheck.blocked', { count: blockedCount });
        if (!await aiConfirm(`${summary}\n\n${blockedMsg}\n\n${t('transactions.deleteCheck.confirmDelete')}`)) return;
      } else {
        if (!await aiConfirm(`${summary}\n\n${t('transactions.deleteCheck.confirmDelete')}`)) return;
      }

      // Execute with force
      const result = await transactionService.batchDelete(Array.from(selectedIds), true);
      for (const id of result.deleted) {
        deleteTransaction(id);
      }
      setSelectedIds(new Set());
      aiToast(t('transactions.batchDeleteSuccess', { count: result.count }), 'success');
    } catch (err: any) {
      const msg = err.response?.data?.detail || t('transactions.deleteError');
      setError(msg);
      aiToast(msg, 'error');
    } finally {
      setBatchDeleting(false);
    }
  };

  const handleToggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleToggleSelectAll = () => {
    const currentPageIds = sortedTransactions.map((t) => t.id);
    const allCurrentSelected = currentPageIds.every((id) => selectedIds.has(id));
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (allCurrentSelected) {
        // Deselect current page items only
        for (const id of currentPageIds) next.delete(id);
      } else {
        // Select all current page items (keep other pages)
        for (const id of currentPageIds) next.add(id);
      }
      return next;
    });
  };

  const handlePauseRecurring = async (id: number) => {
    try {
      const updated = await transactionService.pause(id);
      updateTransaction(id, updated);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('transactions.updateError'));
    }
  };

  const handleResumeRecurring = async (id: number) => {
    try {
      const updated = await transactionService.resume(id);
      updateTransaction(id, updated);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('transactions.updateError'));
    }
  };

  const handleMarkReviewed = async (id: number) => {
    try {
      const updated = await transactionService.markReviewed(id);
      updateTransaction(id, updated);
      setSelectedTransaction(updated);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('transactions.updateError'));
    }
  };

  const handleExportCSV = async () => {
    try {
      const blob = await transactionService.exportCSV(filters);
      await saveBlobWithNativeShare(
        blob,
        `transactions_${new Date().toISOString().split('T')[0]}.csv`,
        t('common.export')
      );
    } catch (err: any) {
      setError(err.response?.data?.detail || t('transactions.exportError'));
    }
  };

  const sortedTransactions = [...transactions].sort((left, right) => {
    const multiplier = sortOrder === 'asc' ? 1 : -1;

    if (sortBy === 'date') {
      return multiplier * (new Date(left.date).getTime() - new Date(right.date).getTime());
    }

    return multiplier * (left.amount - right.amount);
  });

  if (viewMode === 'create') {
    return (
      <div className="transactions-page">
        <TransactionForm
          onSubmit={handleCreateTransaction}
          onCancel={() => setViewMode('list')}
        />
      </div>
    );
  }

  if (viewMode === 'edit' && selectedTransaction) {
    return (
      <div className="transactions-page">
        <TransactionForm
          transaction={selectedTransaction}
          onSubmit={handleUpdateTransaction}
          onCancel={() => {
            closeTransactionDetail();
          }}
        />
      </div>
    );
  }

  return (
    <div className="transactions-page">
      <div className="page-header">
        <div className="transactions-header-copy">
          <h1>{t('transactions.title')}</h1>
          <p className="transactions-header-subtitle">
            {t(
              'classificationRules.transactionsSubtitle',
              'View transactions, recurring bookings, and the classification memory your corrections teach the system.'
            )}
          </p>
        </div>
        <div className="header-actions">
          <Link to="/recurring" className="btn btn-secondary">
            <RefreshCw size={16} />
            <span>{t('recurring.title', 'Recurring Transactions')}</span>
          </Link>
          <Link to="/classification-rules" className="btn btn-secondary">
            <Sparkles size={16} />
            <span>{t('classificationRules.navLabel', 'Classification Memory')}</span>
          </Link>
          <button type="button" className="btn btn-secondary" onClick={handleExportCSV}>
            <Download size={16} />
            <span>{t('common.export')}</span>
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setViewMode('create')}
          >
            <Plus size={16} />
            <span>{t('transactions.addTransaction')}</span>
          </button>
        </div>
      </div>

      {error ? (
        <div className="error-banner">
          <span>{error}</span>
          <button type="button" onClick={() => setError(null)} aria-label={t('common.close')}>
            ×
          </button>
        </div>
      ) : null}

      <TransactionFilters
        filters={filters}
        onFilterChange={setFilters}
        onClear={clearFilters}
      />

      {isLoading ? (
        <div className="loading-container">
          <div className="spinner"></div>
          <p>{t('common.loading')}</p>
        </div>
      ) : (
        <>
          <TransactionList
            transactions={sortedTransactions}
            onEdit={(transaction) => {
              setSelectedTransaction(transaction);
              setViewMode('edit');
              setTransactionQueryParam(null);
            }}
            onDelete={handleDeleteTransaction}
            onView={openTransactionDetail}
            onPause={handlePauseRecurring}
            onResume={handleResumeRecurring}
            onEditRecurring={() => navigate('/recurring')}
            selectedIds={selectedIds}
            onToggleSelect={handleToggleSelect}
            onToggleSelectAll={handleToggleSelectAll}
          />

          {selectedIds.size > 0 && (
            <div className="batch-action-bar">
              <span>
                {t('transactions.selectedCount', { count: selectedIds.size })}
                {selectedIds.size > sortedTransactions.filter((t) => selectedIds.has(t.id)).length && (
                  <> ({t('transactions.acrossPages', 'across pages')})</>
                )}
              </span>
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleBatchDelete}
                disabled={batchDeleting}
              >
                <Trash2 size={16} />
                {batchDeleting
                  ? t('common.loading')
                  : t('transactions.batchDelete', { count: selectedIds.size })}
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setSelectedIds(new Set())}
              >
                {t('common.cancel')}
              </button>
            </div>
          )}

          {pagination.total > 0 && (
            <div className="pagination">
              <div className="pagination-page-size">
                <label htmlFor="page-size-select">{t('transactions.perPage', 'Per page')}</label>
                <Select id="page-size-select" value={String(pagination.pageSize)}
                  onChange={v => setPagination({ pageSize: Number(v), page: 1 })} size="sm"
                  options={[
                    { value: '10', label: '10' },
                    { value: '20', label: '20' },
                    { value: '50', label: '50' },
                    { value: '100', label: '100' },
                  ]} />
              </div>
              {pagination.total > pagination.pageSize && (
                <>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setPagination({ page: pagination.page - 1 })}
                    disabled={pagination.page === 1}
                  >
                    {t('common.previous')}
                  </button>
                  <span className="pagination-info">
                    {t('transactions.pagination', {
                      page: pagination.page,
                      total: Math.ceil(pagination.total / pagination.pageSize),
                    })}
                  </span>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setPagination({ page: pagination.page + 1 })}
                    disabled={pagination.page >= Math.ceil(pagination.total / pagination.pageSize)}
                  >
                    {t('common.next')}
                  </button>
                </>
              )}
              <span className="pagination-total">
                {t('transactions.totalCount', { count: pagination.total })}
              </span>
            </div>
          )}
        </>
      )}

      {viewMode === 'detail' && selectedTransaction ? (
        <TransactionDetail
          transaction={selectedTransaction}
          onEdit={() => {
            setTransactionQueryParam(null);
            setViewMode('edit');
          }}
          onDelete={() => {
            setTransactionQueryParam(null);
            void handleDeleteTransaction(selectedTransaction.id);
          }}
          onClose={closeTransactionDetail}
          onMarkReviewed={handleMarkReviewed}
        />
      ) : null}

    </div>
  );
};

export default TransactionsPage;
