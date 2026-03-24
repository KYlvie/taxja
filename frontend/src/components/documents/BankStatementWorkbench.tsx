import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import SubpageBackLink from '../common/SubpageBackLink';
import { Document } from '../../types/document';
import type {
  BankStatementImportSummary,
  BankStatementLine,
  BankStatementLineStatus,
} from '../../types/bankImport';
import { bankImportService } from '../../services/bankImportService';
import { documentService } from '../../services/documentService';
import { saveBlobWithNativeShare } from '../../mobile/files';
import { getLocaleForLanguage } from '../../utils/locale';
import { useRefreshStore } from '../../stores/refreshStore';
import { aiToast } from '../../stores/aiToastStore';
import './OCRReview.css';
import './BankStatementWorkbench.css';

interface BankStatementWorkbenchProps {
  document: Document;
  onDocumentUpdated?: (document: Document) => void;
  onCancel?: () => void;
  onPrevDocument?: () => void;
  onNextDocument?: () => void;
  hasPrevDocument?: boolean;
  hasNextDocument?: boolean;
}

const formatCurrency = (value: string | number | null | undefined, language: string) => {
  const numeric = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(numeric)) return '-';
  return numeric.toLocaleString(getLocaleForLanguage(language), {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};

const formatDate = (value: string | null | undefined, language: string) => {
  if (!value) return '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString(getLocaleForLanguage(language));
};

const lineMatchesStatus = (status: BankStatementLine['review_status'], target: BankStatementLineStatus | BankStatementLineStatus[]) => {
  if (!status) return false;
  if (Array.isArray(target)) return target.includes(status);
  return status === target;
};

const BankStatementWorkbench: React.FC<BankStatementWorkbenchProps> = ({
  document,
  onDocumentUpdated,
  onCancel,
  onPrevDocument,
  onNextDocument,
  hasPrevDocument = false,
  hasNextDocument = false,
}) => {
  const { t, i18n } = useTranslation();
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [statementImport, setStatementImport] = useState<BankStatementImportSummary | null>(null);
  const [lines, setLines] = useState<BankStatementLine[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMessage, setLoadingMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actingLineId, setActingLineId] = useState<number | null>(null);

  const refreshWorkbench = useCallback(async (importId: number, refreshDocument = false) => {
    const [nextImport, nextLines] = await Promise.all([
      bankImportService.getImport(importId),
      bankImportService.getLines(importId),
    ]);
    setStatementImport(nextImport);
    setLines(nextLines);

    if (refreshDocument) {
      try {
        const updatedDocument = await documentService.getDocument(document.id);
        onDocumentUpdated?.(updatedDocument);
      } catch (documentError) {
        console.warn('Failed to refresh bank statement document after workbench action', documentError);
      }
    }
  }, [document.id, onDocumentUpdated]);

  useEffect(() => {
    let disposed = false;
    let objectUrl: string | null = null;

    const load = async () => {
      setLoading(true);
      setError(null);
      setLoadingMessage(t('documents.bankWorkbench.initializing', 'Preparing the bank statement workbench...'));

      try {
        const [blob, initializedImport] = await Promise.all([
          documentService.downloadDocument(document.id),
          bankImportService.initializeFromDocument(document.id),
        ]);

        if (disposed) return;

        objectUrl = URL.createObjectURL(blob);
        setPreviewUrl(objectUrl);
        setStatementImport(initializedImport);

        setLoadingMessage(t('documents.bankWorkbench.loadingLines', 'Loading statement lines...'));
        const nextLines = await bankImportService.getLines(initializedImport.id);
        if (disposed) return;
        setLines(nextLines);
      } catch (loadError: any) {
        if (disposed) return;
        console.error('Failed to initialize bank statement workbench:', loadError);
        setError(
          loadError?.response?.data?.detail
          || loadError?.message
          || t('documents.bankWorkbench.loadFailed', 'Failed to load bank statement workbench.')
        );
      } finally {
        if (!disposed) {
          setLoading(false);
          setLoadingMessage(null);
        }
      }
    };

    void load();

    return () => {
      disposed = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [document.id, t]);

  const pendingLines = useMemo(
    () => lines.filter((line) => lineMatchesStatus(line.review_status, 'pending_review')),
    [lines]
  );
  const autoProcessedLines = useMemo(
    () => lines.filter((line) => lineMatchesStatus(line.review_status, ['auto_created', 'matched_existing'])),
    [lines]
  );
  const ignoredLines = useMemo(
    () => lines.filter((line) => lineMatchesStatus(line.review_status, 'ignored_duplicate')),
    [lines]
  );

  const handleDownload = useCallback(async () => {
    try {
      const blob = await documentService.downloadDocument(document.id);
      await saveBlobWithNativeShare(blob, document.file_name, t('documents.download'));
    } catch (downloadError) {
      console.error('Failed to download bank statement:', downloadError);
      aiToast(t('documents.downloadFailed', 'Download failed'), 'error');
    }
  }, [document.file_name, document.id, t]);

  const runLineAction = useCallback(async (
    lineId: number,
    action: 'create' | 'match' | 'ignore'
  ) => {
    if (!statementImport) return;

    setActingLineId(lineId);
    setError(null);
    try {
      if (action === 'create') {
        await bankImportService.confirmCreateLine(lineId);
      } else if (action === 'match') {
        await bankImportService.matchExistingLine(lineId);
      } else {
        await bankImportService.ignoreLine(lineId);
      }

      await refreshWorkbench(statementImport.id, true);
      useRefreshStore.getState().refreshTransactions();
      useRefreshStore.getState().refreshDashboard();
    } catch (actionError: any) {
      console.error(`Failed to ${action} bank statement line`, actionError);
      setError(
        actionError?.response?.data?.detail
        || actionError?.message
        || t('documents.bankWorkbench.actionFailed', 'The bank statement action could not be completed.')
      );
    } finally {
      setActingLineId(null);
    }
  }, [refreshWorkbench, statementImport, t]);

  const renderLineStatus = (status: BankStatementLine['review_status']) => {
    switch (status) {
      case 'auto_created':
        return t('documents.bankWorkbench.status.autoCreated', 'Auto-created');
      case 'matched_existing':
        return t('documents.bankWorkbench.status.matchedExisting', 'Matched existing');
      case 'ignored_duplicate':
        return t('documents.bankWorkbench.status.ignoredDuplicate', 'Ignored duplicate');
      case 'pending_review':
      default:
        return t('documents.bankWorkbench.status.pendingReview', 'Pending review');
    }
  };

  const renderLineGroup = (
    title: string,
    description: string,
    groupLines: BankStatementLine[],
    variant: 'pending' | 'resolved' | 'ignored'
  ) => (
    <section className={`bank-workbench-group bank-workbench-group--${variant}`}>
      <div className="bank-workbench-group__header">
        <div>
          <h4>{title}</h4>
          <p>{description}</p>
        </div>
        <span className="bank-workbench-group__count">{groupLines.length}</span>
      </div>
      {groupLines.length === 0 ? (
        <div className="bank-workbench-empty">
          {variant === 'pending'
            ? t('documents.bankWorkbench.emptyPending', 'No bank statement lines need confirmation right now.')
            : variant === 'resolved'
              ? t('documents.bankWorkbench.emptyResolved', 'No automatically processed statement lines yet.')
              : t('documents.bankWorkbench.emptyIgnored', 'No ignored duplicate lines yet.')}
        </div>
      ) : (
        <div className="bank-workbench-lines">
          {groupLines.map((line) => {
            const disabled = actingLineId === line.id;
            return (
              <article key={line.id} className="bank-workbench-line">
                <div className="bank-workbench-line__main">
                  <div className="bank-workbench-line__summary">
                    <div className="bank-workbench-line__amount">
                      {formatCurrency(line.amount, i18n.language)}
                    </div>
                    <div className="bank-workbench-line__meta">
                      <span>{formatDate(line.line_date, i18n.language)}</span>
                      <span>{line.counterparty || t('documents.bankWorkbench.noCounterparty', 'Unknown counterparty')}</span>
                    </div>
                  </div>
                  <div className="bank-workbench-line__purpose">
                    {line.purpose || line.raw_reference || t('documents.bankWorkbench.noPurpose', 'No payment purpose available.')}
                  </div>
                  <div className="bank-workbench-line__status-row">
                    <span className={`bank-workbench-line__status bank-workbench-line__status--${line.review_status || 'pending_review'}`}>
                      {renderLineStatus(line.review_status)}
                    </span>
                    {line.confidence_score && (
                      <span className="bank-workbench-line__confidence">
                        {t('documents.bankWorkbench.confidence', 'Confidence')}: {Math.round(Number(line.confidence_score) * 100)}%
                      </span>
                    )}
                    {line.linked_transaction && (
                      <span className="bank-workbench-line__linked">
                        {t('documents.bankWorkbench.linkedTransaction', 'Transaction')}: {line.linked_transaction.description || `#${line.linked_transaction.id}`}
                      </span>
                    )}
                  </div>
                </div>

                {variant === 'pending' && (
                  <div className="bank-workbench-line__actions">
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() => void runLineAction(line.id, 'create')}
                      disabled={disabled}
                    >
                      {t('documents.bankWorkbench.actions.create', 'Create transaction')}
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => void runLineAction(line.id, 'match')}
                      disabled={disabled}
                    >
                      {t('documents.bankWorkbench.actions.match', 'Match existing')}
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => void runLineAction(line.id, 'ignore')}
                      disabled={disabled}
                    >
                      {t('documents.bankWorkbench.actions.ignore', 'Ignore duplicate')}
                    </button>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );

  return (
    <div className="ocr-review bank-workbench">
      <div className="bank-workbench-topbar">
        <SubpageBackLink to="/documents" />
        {hasPrevDocument && onPrevDocument && (
          <button className="btn btn-secondary" onClick={onPrevDocument} title={String(t('documents.prevDocument'))}>
            {t('documents.prev', 'Previous')}
          </button>
        )}
        {hasNextDocument && onNextDocument && (
          <button className="btn btn-secondary" onClick={onNextDocument} title={String(t('documents.nextDocument'))}>
            {t('documents.next', 'Next')}
          </button>
        )}
        <h2 className="bank-workbench-topbar__title">{document.file_name}</h2>
        <button className="btn btn-primary" onClick={() => void handleDownload()}>
          {t('documents.download', 'Download')}
        </button>
        {onCancel && (
          <button className="btn btn-secondary" onClick={onCancel}>
            {t('common.close', 'Close')}
          </button>
        )}
      </div>

      <div className="review-header">
        <div className="review-header-main">
          <h2>{t('documents.bankWorkbench.title', 'Bank statement workbench')}</h2>
          <div className="confidence-badge">
            <span className="confidence-medium">
              {t('documents.review.confidence.high', 'High confidence')}
            </span>
            {document.confidence_score != null && (
              <span className="confidence-value">
                {(document.confidence_score * 100).toFixed(0)}%
              </span>
            )}
          </div>
        </div>
      </div>

      {error && <div className="review-warning">{error}</div>}
      {loading && (
        <div className="review-info-banner">
          {loadingMessage || t('common.loading', 'Loading...')}
        </div>
      )}

      <div className="review-content">
        <div className="document-preview">
          <h3>{t('documents.review.preview', 'Document preview')}</h3>
          <div className="preview-container">
            {!previewUrl ? (
              <div className="preview-loading">{t('common.loadingPreview', 'Loading preview...')}</div>
            ) : document.mime_type?.startsWith('image/') ? (
              <img src={previewUrl} alt={document.file_name} />
            ) : (
              <iframe src={previewUrl} title={document.file_name} />
            )}
          </div>
        </div>

        <div className="extracted-data bank-workbench-panel">
          <h3>{t('documents.bankWorkbench.summaryTitle', 'Import summary')}</h3>
          <div className="bank-workbench-summary">
            <div className="bank-workbench-summary__row">
              <span>{t('documents.suggestion.fields.bank_name', 'Bank')}</span>
              <strong>{statementImport?.bank_name || '-'}</strong>
            </div>
            <div className="bank-workbench-summary__row">
              <span>{t('documents.suggestion.fields.iban', 'IBAN')}</span>
              <strong>{statementImport?.iban || '-'}</strong>
            </div>
            <div className="bank-workbench-summary__row">
              <span>{t('documents.suggestion.fields.statement_period', 'Statement period')}</span>
              <strong>{statementImport?.statement_period || '-'}</strong>
            </div>
            <div className="bank-workbench-summary__row">
              <span>{t('documents.bankWorkbench.importedAt', 'Imported')}</span>
              <strong>{formatDate(statementImport?.created_at ?? undefined, i18n.language)}</strong>
            </div>
            <div className="bank-workbench-summary__stats">
              <div className="bank-workbench-stat">
                <span>{t('documents.bankWorkbench.totalCount', 'Total lines')}</span>
                <strong>{statementImport?.total_count ?? 0}</strong>
              </div>
              <div className="bank-workbench-stat">
                <span>{t('documents.bankWorkbench.autoProcessed', 'Auto processed')}</span>
                <strong>{(statementImport?.auto_created_count ?? 0) + (statementImport?.matched_existing_count ?? 0)}</strong>
              </div>
              <div className="bank-workbench-stat">
                <span>{t('documents.bankWorkbench.pendingReview', 'Pending review')}</span>
                <strong>{statementImport?.pending_review_count ?? 0}</strong>
              </div>
              <div className="bank-workbench-stat">
                <span>{t('documents.bankWorkbench.ignoredCount', 'Ignored')}</span>
                <strong>{statementImport?.ignored_count ?? 0}</strong>
              </div>
            </div>
          </div>

          {renderLineGroup(
            t('documents.bankWorkbench.groups.pending.title', 'Pending review'),
            t('documents.bankWorkbench.groups.pending.description', 'Low-confidence items stay here until you confirm how they should be handled.'),
            pendingLines,
            'pending'
          )}
          {renderLineGroup(
            t('documents.bankWorkbench.groups.resolved.title', 'Automatically processed'),
            t('documents.bankWorkbench.groups.resolved.description', 'These lines were auto-created or matched to an existing transaction.'),
            autoProcessedLines,
            'resolved'
          )}
          {renderLineGroup(
            t('documents.bankWorkbench.groups.ignored.title', 'Ignored duplicates'),
            t('documents.bankWorkbench.groups.ignored.description', 'These lines were ignored as duplicates and will not create transactions.'),
            ignoredLines,
            'ignored'
          )}
        </div>
      </div>
    </div>
  );
};

export default BankStatementWorkbench;
