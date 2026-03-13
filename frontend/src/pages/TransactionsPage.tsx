import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useTransactionStore } from '../stores/transactionStore';
import { transactionService } from '../services/transactionService';
import TransactionList from '../components/transactions/TransactionList';
import TransactionFilters from '../components/transactions/TransactionFilters';
import TransactionForm from '../components/transactions/TransactionForm';
import TransactionDetail from '../components/transactions/TransactionDetail';
import TransactionImport from '../components/transactions/TransactionImport';
import { Transaction, TransactionFormData } from '../types/transaction';
import './TransactionsPage.css';

type ViewMode = 'list' | 'create' | 'edit' | 'detail' | 'import';

const TransactionsPage = () => {
  const { t } = useTranslation();
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

  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [sortBy, _setSortBy] = useState<'date' | 'amount'>('date');
  const [sortOrder, _setSortOrder] = useState<'asc' | 'desc'>('desc');

  useEffect(() => {
    fetchTransactions();
  }, [filters, pagination.page, pagination.pageSize, sortBy, sortOrder]);

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
    } catch (err: any) {
      setError(err.response?.data?.detail || t('transactions.createError'));
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
    } catch (err: any) {
      setError(err.response?.data?.detail || t('transactions.updateError'));
      throw err;
    }
  };

  const handleDeleteTransaction = async (id: number) => {
    try {
      await transactionService.delete(id);
      deleteTransaction(id);
      setViewMode('list');
      setSelectedTransaction(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('transactions.deleteError'));
    }
  };

  const handlePauseRecurring = async (id: number) => {
    try {
      const updated = await transactionService.pause(id);
      updateTransaction(id, updated);
    } catch (err: any) {
      setError(err.response?.data?.detail || '暂停失败');
    }
  };

  const handleResumeRecurring = async (id: number) => {
    try {
      const updated = await transactionService.resume(id);
      updateTransaction(id, updated);
    } catch (err: any) {
      setError(err.response?.data?.detail || '恢复失败');
    }
  };

  const handleImportCSV = async (file: File) => {
    return await transactionService.importCSV(file);
  };

  const handleConfirmImport = (importedTransactions: Transaction[]) => {
    importedTransactions.forEach((txn) => addTransaction(txn));
    setViewMode('list');
  };

  const handleExportCSV = async () => {
    try {
      const blob = await transactionService.exportCSV(filters);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `transactions_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('transactions.exportError'));
    }
  };


  const sortedTransactions = [...transactions].sort((a, b) => {
    const multiplier = sortOrder === 'asc' ? 1 : -1;
    if (sortBy === 'date') {
      return multiplier * (new Date(a.date).getTime() - new Date(b.date).getTime());
    } else {
      return multiplier * (a.amount - b.amount);
    }
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
            setViewMode('list');
            setSelectedTransaction(null);
          }}
        />
      </div>
    );
  }

  return (
    <div className="transactions-page">
      <div className="page-header">
        <h1>{t('transactions.title')}</h1>
        <div className="header-actions">
          <button className="btn btn-secondary" onClick={handleExportCSV}>
            📥 {t('common.export')}
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => setViewMode('import')}
          >
            📤 {t('common.import')}
          </button>
          <button
            className="btn btn-primary"
            onClick={() => setViewMode('create')}
          >
            + {t('transactions.addTransaction')}
          </button>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <span>⚠️ {error}</span>
          <button onClick={() => setError(null)}>✕</button>
        </div>
      )}

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
            onEdit={(txn) => {
              setSelectedTransaction(txn);
              setViewMode('edit');
            }}
            onDelete={handleDeleteTransaction}
            onView={(txn) => {
              setSelectedTransaction(txn);
              setViewMode('detail');
            }}
            onPause={handlePauseRecurring}
            onResume={handleResumeRecurring}
          />

          {pagination.total > pagination.pageSize && (
            <div className="pagination">
              <button
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
                className="btn btn-secondary"
                onClick={() => setPagination({ page: pagination.page + 1 })}
                disabled={
                  pagination.page >= Math.ceil(pagination.total / pagination.pageSize)
                }
              >
                {t('common.next')}
              </button>
            </div>
          )}
        </>
      )}

      {viewMode === 'detail' && selectedTransaction && (
        <TransactionDetail
          transaction={selectedTransaction}
          onEdit={() => setViewMode('edit')}
          onDelete={() => handleDeleteTransaction(selectedTransaction.id)}
          onClose={() => {
            setViewMode('list');
            setSelectedTransaction(null);
          }}
        />
      )}

      {viewMode === 'import' && (
        <TransactionImport
          onImport={handleImportCSV}
          onConfirm={handleConfirmImport}
          onCancel={() => setViewMode('list')}
        />
      )}
    </div>
  );
};

export default TransactionsPage;
