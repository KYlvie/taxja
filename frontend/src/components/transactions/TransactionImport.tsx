import { useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { ImportResult, Transaction } from '../../types/transaction';
import './TransactionImport.css';

interface TransactionImportProps {
  onImport: (file: File) => Promise<ImportResult>;
  onConfirm: (transactions: Transaction[]) => void;
  onCancel: () => void;
}

const TransactionImport = ({
  onImport,
  onConfirm,
  onCancel,
}: TransactionImportProps) => {
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      if (!selectedFile.name.endsWith('.csv')) {
        setError(t('transactions.import.invalidFileType'));
        return;
      }
      setFile(selectedFile);
      setError(null);
      setImportResult(null);
    }
  };

  const handleImport = async () => {
    if (!file) return;

    setIsImporting(true);
    setError(null);

    try {
      const result = await onImport(file);
      setImportResult(result);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('transactions.import.error'));
    } finally {
      setIsImporting(false);
    }
  };

  const handleConfirm = () => {
    if (importResult?.transactions) {
      onConfirm(importResult.transactions);
    }
  };

  const handleReset = () => {
    setFile(null);
    setImportResult(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="transaction-import-overlay" onClick={onCancel}>
      <div className="transaction-import" onClick={(e) => e.stopPropagation()}>
        <div className="import-header">
          <h2>{t('transactions.import.title')}</h2>
          <button className="btn-close" onClick={onCancel}>
            ✕
          </button>
        </div>

        <div className="import-body">
          {!importResult ? (
            <>
              <div className="import-instructions">
                <h3>{t('transactions.import.instructions')}</h3>
                <ul>
                  <li>{t('transactions.import.instruction1')}</li>
                  <li>{t('transactions.import.instruction2')}</li>
                  <li>{t('transactions.import.instruction3')}</li>
                </ul>
              </div>

              <div className="file-upload">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv"
                  onChange={handleFileSelect}
                  id="csv-file"
                  className="file-input"
                />
                <label htmlFor="csv-file" className="file-label">
                  <span className="file-icon">📁</span>
                  <span>
                    {file ? file.name : t('transactions.import.selectFile')}
                  </span>
                </label>
              </div>

              {error && (
                <div className="import-error">
                  <span className="error-icon">⚠️</span>
                  <span>{error}</span>
                </div>
              )}

              <div className="import-actions">
                <button className="btn btn-secondary" onClick={onCancel}>
                  {t('common.cancel')}
                </button>
                <button
                  className="btn btn-primary"
                  onClick={handleImport}
                  disabled={!file || isImporting}
                >
                  {isImporting ? t('transactions.import.importing') : t('common.import')}
                </button>
              </div>
            </>
          ) : (
            <>
              <div className="import-summary">
                <h3>{t('transactions.import.summary')}</h3>
                <div className="summary-stats">
                  <div className="stat-card success">
                    <div className="stat-value">{importResult.success}</div>
                    <div className="stat-label">
                      {t('transactions.import.successful')}
                    </div>
                  </div>
                  {importResult.duplicates > 0 && (
                    <div className="stat-card warning">
                      <div className="stat-value">{importResult.duplicates}</div>
                      <div className="stat-label">
                        {t('transactions.import.duplicates')}
                      </div>
                    </div>
                  )}
                  {importResult.failed > 0 && (
                    <div className="stat-card error">
                      <div className="stat-value">{importResult.failed}</div>
                      <div className="stat-label">
                        {t('transactions.import.failed')}
                      </div>
                    </div>
                  )}
                </div>

                {importResult.errors && importResult.errors.length > 0 && (
                  <div className="import-errors">
                    <h4>{t('transactions.import.errors')}</h4>
                    <ul>
                      {importResult.errors.map((err, idx) => (
                        <li key={idx}>
                          {t('transactions.import.rowError', {
                            row: err.row,
                            error: err.error,
                          })}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              <div className="import-preview">
                <h3>{t('transactions.import.preview')}</h3>
                <div className="preview-list">
                  {importResult.transactions.slice(0, 5).map((txn, idx) => (
                    <div key={idx} className="preview-item">
                      <span className="preview-date">
                        {new Date(txn.date).toLocaleDateString('de-AT')}
                      </span>
                      <span className="preview-description">{txn.description}</span>
                      <span className={`preview-amount ${txn.type}`}>
                        {new Intl.NumberFormat('de-AT', {
                          style: 'currency',
                          currency: 'EUR',
                        }).format(txn.amount)}
                      </span>
                    </div>
                  ))}
                  {importResult.transactions.length > 5 && (
                    <div className="preview-more">
                      {t('transactions.import.andMore', {
                        count: importResult.transactions.length - 5,
                      })}
                    </div>
                  )}
                </div>
              </div>

              <div className="import-actions">
                <button className="btn btn-secondary" onClick={handleReset}>
                  {t('transactions.import.importAnother')}
                </button>
                <button className="btn btn-primary" onClick={handleConfirm}>
                  {t('transactions.import.confirm')}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default TransactionImport;
