import { useState, useRef, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { isAxiosError } from 'axios';
import { FileSpreadsheet, Upload, X } from 'lucide-react';
import { ImportResult, Transaction } from '../../types/transaction';
import { pickNativeSingleFile, supportsNativeFileActions } from '../../mobile/files';
import { getLocaleForLanguage } from '../../utils/locale';
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
  const { t, i18n } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nativeActionsEnabled = useMemo(() => supportsNativeFileActions(), []);
  const locale = getLocaleForLanguage(i18n.resolvedLanguage || i18n.language);

  const applyFile = (selectedFile: File | null) => {
    if (!selectedFile) {
      return;
    }

    if (!selectedFile.name.toLowerCase().endsWith('.csv')) {
      setError(t('transactions.import.invalidFileType'));
      return;
    }

    setFile(selectedFile);
    setError(null);
    setImportResult(null);
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    applyFile(event.target.files?.[0] || null);
  };

  const handleNativeFilePick = async () => {
    try {
      const selectedFile = await pickNativeSingleFile(['text/csv', '.csv']);
      applyFile(selectedFile);
    } catch (err: unknown) {
      const message = String(err instanceof Error ? err.message : '').toLowerCase();
      if (message.includes('cancel')) {
        return;
      }
      setError(t('transactions.import.error'));
    }
  };

  const handleImport = async () => {
    if (!file) return;

    setIsImporting(true);
    setError(null);

    try {
      const result = await onImport(file);
      setImportResult(result);
    } catch (err: unknown) {
      const detail = isAxiosError(err)
        ? (err.response?.data as { detail?: string } | undefined)?.detail
        : undefined;
      setError(detail || t('transactions.import.error'));
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
      <div className="transaction-import" onClick={(event) => event.stopPropagation()}>
        <div className="import-header">
          <h2>{t('transactions.import.title')}</h2>
          <button type="button" className="btn-close" onClick={onCancel} aria-label={t('common.close')}>
            <X size={18} />
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
                  accept=".csv,text/csv"
                  onChange={handleFileSelect}
                  id="csv-file"
                  className="file-input"
                />
                <label
                  htmlFor={nativeActionsEnabled ? undefined : 'csv-file'}
                  className={`file-label${nativeActionsEnabled ? ' mobile-enabled' : ''}`}
                  onClick={(event) => {
                    if (nativeActionsEnabled) {
                      event.preventDefault();
                      void handleNativeFilePick();
                    }
                  }}
                >
                  <span className="file-icon">
                    <FileSpreadsheet size={24} />
                  </span>
                  <span>{file ? file.name : t('transactions.import.selectFile')}</span>
                </label>
              </div>

              {nativeActionsEnabled ? (
                <button type="button" className="btn btn-secondary import-mobile-trigger" onClick={handleNativeFilePick}>
                  <Upload size={16} />
                  <span>{t('transactions.import.selectFile')}</span>
                </button>
              ) : null}

              {error ? (
                <div className="import-error">
                  <span>{error}</span>
                </div>
              ) : null}

              <div className="import-actions">
                <button type="button" className="btn btn-secondary" onClick={onCancel}>
                  {t('common.cancel')}
                </button>
                <button
                  type="button"
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
                    <div className="stat-label">{t('transactions.import.successful')}</div>
                  </div>
                  {importResult.duplicates > 0 ? (
                    <div className="stat-card warning">
                      <div className="stat-value">{importResult.duplicates}</div>
                      <div className="stat-label">{t('transactions.import.duplicates')}</div>
                    </div>
                  ) : null}
                  {importResult.failed > 0 ? (
                    <div className="stat-card error">
                      <div className="stat-value">{importResult.failed}</div>
                      <div className="stat-label">{t('transactions.import.failed')}</div>
                    </div>
                  ) : null}
                </div>

                {importResult.errors && importResult.errors.length > 0 ? (
                  <div className="import-errors">
                    <h4>{t('transactions.import.errors')}</h4>
                    <ul>
                      {importResult.errors.map((importError, index) => (
                        <li key={`${importError.row}-${index}`}>
                          {t('transactions.import.rowError', {
                            row: importError.row,
                            error: importError.error,
                          })}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>

              <div className="import-preview">
                <h3>{t('transactions.import.preview')}</h3>
                <div className="preview-list">
                  {importResult.transactions.slice(0, 5).map((transaction, index) => (
                    <div key={`${transaction.date}-${index}`} className="preview-item">
                      <span className="preview-date">
                        {new Date(transaction.date).toLocaleDateString(locale)}
                      </span>
                      <span className="preview-description">{transaction.description}</span>
                      <span className={`preview-amount ${transaction.type}`}>
                        {new Intl.NumberFormat(locale, {
                          style: 'currency',
                          currency: 'EUR',
                        }).format(transaction.amount)}
                      </span>
                    </div>
                  ))}
                  {importResult.transactions.length > 5 ? (
                    <div className="preview-more">
                      {t('transactions.import.andMore', {
                        count: importResult.transactions.length - 5,
                      })}
                    </div>
                  ) : null}
                </div>
              </div>

              <div className="import-actions">
                <button type="button" className="btn btn-secondary" onClick={handleReset}>
                  {t('transactions.import.importAnother')}
                </button>
                <button type="button" className="btn btn-primary" onClick={handleConfirm}>
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
