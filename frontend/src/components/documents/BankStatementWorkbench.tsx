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
import {
  buildFallbackBankStatementLines,
  type FallbackBankStatementLine,
  type FallbackTransactionDirection,
} from '../../utils/bankStatementFallback';
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

type BankStatementWorkbenchMode = 'remote' | 'fallback';
type AmountTone = 'credit' | 'debit' | 'neutral';

interface FallbackBankStatementSummary {
  bank_name?: string | null;
  iban?: string | null;
  statement_period?: string | null;
  imported_at?: string | null;
  taxpayer_name?: string | null;
  tax_year?: string | number | null;
  opening_balance?: string | number | null;
  closing_balance?: string | number | null;
  total_count: number;
  credit_count: number;
  debit_count: number;
}

const parseLooseDate = (value: string): Date | null => {
  const parsed = new Date(value);
  if (!Number.isNaN(parsed.getTime())) {
    return parsed;
  }

  const normalized = value.trim().match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
  if (!normalized) {
    return null;
  }

  const [, day, month, year] = normalized;
  const fallback = new Date(`${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}T00:00:00`);
  return Number.isNaN(fallback.getTime()) ? null : fallback;
};

const toAmountNumber = (value: string | number | null | undefined): number | null => {
  if (value === null || value === undefined || value === '') return null;
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null;
  }

  const normalized = String(value).trim();
  if (!normalized) return null;

  const compact = normalized.replace(/\s/g, '').replace(/[\u20AC$\u00A3]/g, '');
  const european = /^-?\d{1,3}(\.\d{3})*,\d+$/.test(compact);
  const standard = /^-?\d+(,\d+)?$/.test(compact);
  const sanitized = european
    ? compact.replace(/\./g, '').replace(',', '.')
    : standard
      ? compact.replace(',', '.')
      : compact.replace(/,/g, '');

  const parsed = Number(sanitized);
  return Number.isFinite(parsed) ? parsed : null;
};

const formatCurrency = (value: string | number | null | undefined, language: string) => {
  const numeric = toAmountNumber(value);
  if (numeric === null) return '-';
  return numeric.toLocaleString(getLocaleForLanguage(language), {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};

const formatDate = (value: string | null | undefined, language: string) => {
  if (!value) return '-';
  const parsed = parseLooseDate(value);
  if (!parsed) return value;
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString(getLocaleForLanguage(language));
};

const parseOcrResult = (ocrResult: unknown): Record<string, unknown> => {
  if (!ocrResult) return {};
  if (typeof ocrResult === 'string') {
    try {
      const parsed = JSON.parse(ocrResult);
      return parsed && typeof parsed === 'object' ? parsed as Record<string, unknown> : {};
    } catch {
      return {};
    }
  }

  return typeof ocrResult === 'object' ? ocrResult as Record<string, unknown> : {};
};

const toNullableString = (value: unknown): string | null => {
  if (value === null || value === undefined) return null;
  const normalized = String(value).trim();
  return normalized ? normalized : null;
};

const getAmountTone = (
  amount: string | number | null | undefined,
  fallbackDirection?: FallbackTransactionDirection
): AmountTone => {
  if (fallbackDirection === 'credit') return 'credit';
  if (fallbackDirection === 'debit') return 'debit';

  const numeric = toAmountNumber(amount);
  if (numeric === null) return 'neutral';
  if (numeric > 0) return 'credit';
  if (numeric < 0) return 'debit';
  return 'neutral';
};

const formatConfidence = (value: string | number | null | undefined) => {
  const numeric = toAmountNumber(value);
  if (numeric === null) return null;
  const normalized = numeric <= 1 ? numeric * 100 : numeric;
  return `${Math.round(normalized)}%`;
};

const buildStatementPeriod = (ocrData: Record<string, unknown>): string | null => {
  const explicit = toNullableString(ocrData.statement_period);
  if (explicit) {
    return explicit;
  }

  const periodStart = toNullableString(ocrData.period_start);
  const periodEnd = toNullableString(ocrData.period_end);

  if (periodStart && periodEnd) {
    return `${periodStart} - ${periodEnd}`;
  }

  return periodStart || periodEnd || null;
};

const buildFallbackState = (document: Document): {
  summary: FallbackBankStatementSummary;
  lines: FallbackBankStatementLine[];
} => {
  const ocrData = parseOcrResult(document.ocr_result);
  const suggestion = ocrData.import_suggestion && typeof ocrData.import_suggestion === 'object'
    ? ocrData.import_suggestion as Record<string, unknown>
    : null;
  const suggestionData = suggestion?.data && typeof suggestion.data === 'object'
    ? suggestion.data as Record<string, unknown>
    : {};
  const sourceData = Object.keys(suggestionData).length > 0 ? suggestionData : ocrData;
  const rawTransactions = Array.isArray(sourceData.transactions)
    ? sourceData.transactions
    : Array.isArray(ocrData.transactions)
      ? ocrData.transactions
      : [];
  const lines = buildFallbackBankStatementLines(rawTransactions, document.raw_text);

  return {
    summary: {
      bank_name: toNullableString(sourceData.bank_name) || toNullableString(ocrData.bank_name),
      iban: toNullableString(sourceData.iban) || toNullableString(ocrData.iban),
      statement_period: buildStatementPeriod(sourceData) || buildStatementPeriod(ocrData),
      imported_at: document.processed_at || document.uploaded_at || document.created_at,
      taxpayer_name: toNullableString(sourceData.taxpayer_name)
        || toNullableString(ocrData.taxpayer_name)
        || toNullableString(ocrData.account_holder),
      tax_year: (sourceData.tax_year as string | number | null | undefined)
        ?? (ocrData.tax_year as string | number | null | undefined)
        ?? null,
      opening_balance: (sourceData.opening_balance as string | number | null | undefined)
        ?? (ocrData.opening_balance as string | number | null | undefined)
        ?? null,
      closing_balance: (sourceData.closing_balance as string | number | null | undefined)
        ?? (ocrData.closing_balance as string | number | null | undefined)
        ?? null,
      total_count: lines.length,
      credit_count: lines.filter((line) => line.direction === 'credit').length,
      debit_count: lines.filter((line) => line.direction === 'debit').length,
    },
    lines,
  };
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
  const [mode, setMode] = useState<BankStatementWorkbenchMode>('remote');
  const [statementImport, setStatementImport] = useState<BankStatementImportSummary | null>(null);
  const [lines, setLines] = useState<BankStatementLine[]>([]);
  const [fallbackSummary, setFallbackSummary] = useState<FallbackBankStatementSummary | null>(null);
  const [fallbackLines, setFallbackLines] = useState<FallbackBankStatementLine[]>([]);
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
      setMode('remote');
      setStatementImport(null);
      setLines([]);
      setFallbackSummary(null);
      setFallbackLines([]);
      setLoadingMessage(t('documents.bankWorkbench.initializing', 'Preparing the bank statement workbench...'));

      try {
        const blob = await documentService.downloadDocument(document.id);

        if (disposed) return;

        objectUrl = URL.createObjectURL(blob);
        setPreviewUrl(objectUrl);

        try {
          const initializedImport = await bankImportService.initializeFromDocument(document.id);

          if (disposed) return;

          setStatementImport(initializedImport);
          setMode('remote');

          setLoadingMessage(t('documents.bankWorkbench.loadingLines', 'Loading statement lines...'));
          const nextLines = await bankImportService.getLines(initializedImport.id);
          if (disposed) return;
          setLines(nextLines);
        } catch (loadError: any) {
          if (disposed) return;
          if (
            loadError?.response?.status === 404
            && loadError?.response?.data?.detail === 'Not Found'
          ) {
            const fallbackState = buildFallbackState(document);
            setMode('fallback');
            setFallbackSummary(fallbackState.summary);
            setFallbackLines(fallbackState.lines);
            return;
          }

          throw loadError;
        }
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
  }, [document, t]);

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

  const renderLineStatus = useCallback((status: BankStatementLine['review_status']) => {
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
  }, [t]);

  const renderFallbackDirection = useCallback((direction: FallbackTransactionDirection) => {
    switch (direction) {
      case 'credit':
        return t('documents.bankWorkbench.direction.credit', 'Credit');
      case 'debit':
        return t('documents.bankWorkbench.direction.debit', 'Debit');
      default:
        return t('documents.bankWorkbench.direction.unknown', 'Detected');
    }
  }, [t]);

  const fallbackSummaryRows = useMemo(() => {
    if (!fallbackSummary) {
      return [];
    }

    return [
      { label: t('documents.suggestion.fields.bank_name', 'Bank'), value: fallbackSummary.bank_name },
      { label: t('documents.suggestion.fields.iban', 'IBAN'), value: fallbackSummary.iban },
      { label: t('documents.suggestion.fields.statement_period', 'Statement period'), value: fallbackSummary.statement_period },
      { label: t('documents.bankWorkbench.accountHolder', 'Account holder'), value: fallbackSummary.taxpayer_name },
      { label: t('documents.bankWorkbench.taxYear', 'Tax year'), value: fallbackSummary.tax_year },
      {
        label: t('documents.bankWorkbench.openingBalance', 'Opening balance'),
        value: fallbackSummary.opening_balance == null
          ? null
          : formatCurrency(fallbackSummary.opening_balance, i18n.language),
      },
      {
        label: t('documents.bankWorkbench.closingBalance', 'Closing balance'),
        value: fallbackSummary.closing_balance == null
          ? null
          : formatCurrency(fallbackSummary.closing_balance, i18n.language),
      },
      {
        label: t('documents.bankWorkbench.importedAt', 'Imported'),
        value: fallbackSummary.imported_at ? formatDate(fallbackSummary.imported_at, i18n.language) : null,
      },
    ].filter((row): row is { label: string; value: string | number } => row.value !== null && row.value !== undefined && row.value !== '');
  }, [fallbackSummary, i18n.language, t]);

  const renderPurposeCell = (
    primaryValue: string | null | undefined,
    secondaryValue?: string | null
  ) => {
    const primary = primaryValue || t('documents.bankWorkbench.noPurpose', 'No payment purpose available.');
    const secondary = secondaryValue && secondaryValue !== primary ? secondaryValue : null;

    return (
      <div className="bank-workbench-cell">
        <div className="bank-workbench-cell__primary">{primary}</div>
        {secondary && <div className="bank-workbench-cell__secondary">{secondary}</div>}
      </div>
    );
  };

  const renderRemoteTable = (
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
        <>
          <div className="bank-workbench-table-shell">
            <table className="bank-workbench-table">
              <thead>
                <tr>
                  <th>{t('transactions.date', 'Date')}</th>
                  <th>{t('documents.fields.counterparty', 'Counterparty')}</th>
                  <th>{t('documents.fields.purpose', 'Purpose')}</th>
                  <th>{t('transactions.amount', 'Amount')}</th>
                  <th>{t('common.status', 'Status')}</th>
                  <th>{t('common.actions', 'Actions')}</th>
                </tr>
              </thead>
              <tbody>
                {groupLines.map((line) => {
                  const disabled = actingLineId === line.id;
                  const confidenceLabel = formatConfidence(line.confidence_score);
                  const linkedTransaction = line.linked_transaction || line.created_transaction;
                  const linkedDescription = linkedTransaction?.description || null;
                  const linkedReference = linkedTransaction?.id
                    ? `${t('documents.bankWorkbench.linkedTransaction', 'Transaction')} #${linkedTransaction.id}`
                    : null;

                  return (
                    <tr key={line.id}>
                      <td>{formatDate(line.line_date, i18n.language)}</td>
                      <td>
                        <div className="bank-workbench-cell">
                          <div className="bank-workbench-cell__primary">
                            {line.counterparty || t('documents.bankWorkbench.noCounterparty', 'Unknown counterparty')}
                          </div>
                          {linkedReference && (
                            <div className="bank-workbench-cell__secondary">{linkedReference}</div>
                          )}
                        </div>
                      </td>
                      <td>{renderPurposeCell(line.purpose || line.raw_reference, line.raw_reference)}</td>
                      <td>
                        <span className={`bank-workbench-amount bank-workbench-amount--${getAmountTone(line.amount)}`}>
                          {formatCurrency(line.amount, i18n.language)}
                        </span>
                      </td>
                      <td>
                        <div className="bank-workbench-cell">
                          <span className={`bank-workbench-line__status bank-workbench-line__status--${line.review_status || 'pending_review'}`}>
                            {renderLineStatus(line.review_status)}
                          </span>
                          {confidenceLabel && (
                            <div className="bank-workbench-cell__secondary">
                              {t('documents.bankWorkbench.confidence', 'Confidence')}: {confidenceLabel}
                            </div>
                          )}
                          {linkedDescription && (
                            <div className="bank-workbench-cell__secondary">{linkedDescription}</div>
                          )}
                        </div>
                      </td>
                      <td className="bank-workbench-table__actions">
                        {variant === 'pending' ? (
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
                        ) : (
                          <span className="bank-workbench-table__static-action">-</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="bank-workbench-mobile-list">
            {groupLines.map((line) => {
              const disabled = actingLineId === line.id;
              const confidenceLabel = formatConfidence(line.confidence_score);
              const linkedTransaction = line.linked_transaction || line.created_transaction;

              return (
                <article key={`mobile-${line.id}`} className="bank-workbench-mobile-card">
                  <div className="bank-workbench-mobile-card__top">
                    <div className="bank-workbench-cell">
                      <div className="bank-workbench-cell__primary">
                        {line.counterparty || t('documents.bankWorkbench.noCounterparty', 'Unknown counterparty')}
                      </div>
                      <div className="bank-workbench-cell__secondary">
                        {formatDate(line.line_date, i18n.language)}
                      </div>
                    </div>
                    <span className={`bank-workbench-amount bank-workbench-amount--${getAmountTone(line.amount)}`}>
                      {formatCurrency(line.amount, i18n.language)}
                    </span>
                  </div>

                  {renderPurposeCell(line.purpose || line.raw_reference, line.raw_reference)}

                  <div className="bank-workbench-mobile-card__meta">
                    <span className={`bank-workbench-line__status bank-workbench-line__status--${line.review_status || 'pending_review'}`}>
                      {renderLineStatus(line.review_status)}
                    </span>
                    {confidenceLabel && (
                      <span className="bank-workbench-mobile-card__meta-item">
                        {t('documents.bankWorkbench.confidence', 'Confidence')}: {confidenceLabel}
                      </span>
                    )}
                    {linkedTransaction?.description && (
                      <span className="bank-workbench-mobile-card__meta-item">
                        {linkedTransaction.description}
                      </span>
                    )}
                  </div>

                  {variant === 'pending' && (
                    <div className="bank-workbench-line__actions bank-workbench-line__actions--mobile">
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
        </>
      )}
    </section>
  );

  const renderFallbackTable = () => (
    <section className="bank-workbench-group bank-workbench-group--pending">
      <div className="bank-workbench-group__header">
        <div>
          <h4>{t('documents.bankWorkbench.fallbackTransactionsTitle', 'Extracted transaction lines')}</h4>
          <p>
            {t(
              'documents.bankWorkbench.fallbackTransactionsDescription',
              'Each detected statement entry is shown as a table row, even when the full bank import workbench is unavailable.'
            )}
          </p>
        </div>
        <span className="bank-workbench-group__count">{fallbackLines.length}</span>
      </div>
      {fallbackLines.length === 0 ? (
        <div className="bank-workbench-empty">
          {t('documents.bankWorkbench.noExtractedTransactions', 'No transaction lines were extracted from this bank statement yet.')}
        </div>
      ) : (
        <>
          <div className="bank-workbench-table-shell">
            <table className="bank-workbench-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>{t('transactions.date', 'Date')}</th>
                  <th>{t('documents.fields.counterparty', 'Counterparty')}</th>
                  <th>{t('documents.fields.purpose', 'Purpose')}</th>
                  <th>{t('transactions.amount', 'Amount')}</th>
                  <th>{t('documents.bankWorkbench.direction.label', 'Direction')}</th>
                </tr>
              </thead>
              <tbody>
                {fallbackLines.map((line, index) => (
                  <tr key={line.id}>
                    <td>{index + 1}</td>
                    <td>{formatDate(line.line_date ?? undefined, i18n.language)}</td>
                    <td>
                      <div className="bank-workbench-cell">
                        <div className="bank-workbench-cell__primary">
                          {line.counterparty || t('documents.bankWorkbench.noCounterparty', 'Unknown counterparty')}
                        </div>
                      </div>
                    </td>
                    <td>{renderPurposeCell(line.purpose, line.raw_reference)}</td>
                    <td>
                      <span className={`bank-workbench-amount bank-workbench-amount--${getAmountTone(line.amount, line.direction)}`}>
                        {formatCurrency(line.amount, i18n.language)}
                      </span>
                    </td>
                    <td>
                      <span className={`bank-workbench-line__status bank-workbench-line__status--fallback-${line.direction}`}>
                        {renderFallbackDirection(line.direction)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="bank-workbench-mobile-list">
            {fallbackLines.map((line, index) => (
              <article key={`fallback-mobile-${line.id}`} className="bank-workbench-mobile-card">
                <div className="bank-workbench-mobile-card__top">
                  <div className="bank-workbench-cell">
                    <div className="bank-workbench-cell__primary">
                      #{index + 1} {line.counterparty || t('documents.bankWorkbench.noCounterparty', 'Unknown counterparty')}
                    </div>
                    <div className="bank-workbench-cell__secondary">
                      {formatDate(line.line_date ?? undefined, i18n.language)}
                    </div>
                  </div>
                  <span className={`bank-workbench-amount bank-workbench-amount--${getAmountTone(line.amount, line.direction)}`}>
                    {formatCurrency(line.amount, i18n.language)}
                  </span>
                </div>

                {renderPurposeCell(line.purpose, line.raw_reference)}

                <div className="bank-workbench-mobile-card__meta">
                  <span className={`bank-workbench-line__status bank-workbench-line__status--fallback-${line.direction}`}>
                    {renderFallbackDirection(line.direction)}
                  </span>
                </div>
              </article>
            ))}
          </div>
        </>
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
              {mode === 'remote'
                ? t('documents.bankWorkbench.mode.import', 'Import workbench')
                : t('documents.bankWorkbench.mode.extracted', 'Extracted rows')}
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
      {!loading && mode === 'fallback' && (
        <div className="review-info-banner">
          {t(
            'documents.bankWorkbench.localFallbackNotice',
            'This bank statement is shown as extracted transaction lines because the bank import workbench is unavailable in this environment.'
          )}
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
          <h3>
            {mode === 'remote'
              ? t('documents.bankWorkbench.summaryTitle', 'Import summary')
              : t('documents.bankWorkbench.fallbackSummaryTitle', 'Extracted statement details')}
          </h3>
          <div className="bank-workbench-summary">
            {mode === 'remote' ? (
              <>
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
              </>
            ) : (
              fallbackSummaryRows.map((row) => (
                <div key={row.label} className="bank-workbench-summary__row">
                  <span>{row.label}</span>
                  <strong>{row.value}</strong>
                </div>
              ))
            )}
            <div className="bank-workbench-summary__stats">
              <div className="bank-workbench-stat">
                <span>{t('documents.bankWorkbench.totalCount', 'Total lines')}</span>
                <strong>{mode === 'remote' ? statementImport?.total_count ?? 0 : fallbackSummary?.total_count ?? 0}</strong>
              </div>
              <div className="bank-workbench-stat">
                <span>
                  {mode === 'remote'
                    ? t('documents.bankWorkbench.autoProcessed', 'Auto processed')
                    : t('documents.bankWorkbench.creditCount', 'Credits')}
                </span>
                <strong>
                  {mode === 'remote'
                    ? (statementImport?.auto_created_count ?? 0) + (statementImport?.matched_existing_count ?? 0)
                    : fallbackSummary?.credit_count ?? 0}
                </strong>
              </div>
              <div className="bank-workbench-stat">
                <span>
                  {mode === 'remote'
                    ? t('documents.bankWorkbench.pendingReview', 'Pending review')
                    : t('documents.bankWorkbench.debitCount', 'Debits')}
                </span>
                <strong>
                  {mode === 'remote'
                    ? statementImport?.pending_review_count ?? 0
                    : fallbackSummary?.debit_count ?? 0}
                </strong>
              </div>
              <div className="bank-workbench-stat">
                <span>
                  {mode === 'remote'
                    ? t('documents.bankWorkbench.ignoredCount', 'Ignored')
                    : t('documents.bankWorkbench.readOnlyMode', 'Read-only mode')}
                </span>
                <strong>
                  {mode === 'remote'
                    ? statementImport?.ignored_count ?? 0
                    : t('documents.bankWorkbench.readOnlyShort', 'OCR')}
                </strong>
              </div>
            </div>
          </div>

          {mode === 'remote' ? (
            <>
              {renderRemoteTable(
                t('documents.bankWorkbench.groups.pending.title', 'Pending review'),
                t('documents.bankWorkbench.groups.pending.description', 'Low-confidence items stay here until you confirm how they should be handled.'),
                pendingLines,
                'pending'
              )}
              {renderRemoteTable(
                t('documents.bankWorkbench.groups.resolved.title', 'Automatically processed'),
                t('documents.bankWorkbench.groups.resolved.description', 'These lines were auto-created or matched to an existing transaction.'),
                autoProcessedLines,
                'resolved'
              )}
              {renderRemoteTable(
                t('documents.bankWorkbench.groups.ignored.title', 'Ignored duplicates'),
                t('documents.bankWorkbench.groups.ignored.description', 'These lines were ignored as duplicates and will not create transactions.'),
                ignoredLines,
                'ignored'
              )}
            </>
          ) : (
            renderFallbackTable()
          )}
        </div>
      </div>
    </div>
  );
};

export default BankStatementWorkbench;
