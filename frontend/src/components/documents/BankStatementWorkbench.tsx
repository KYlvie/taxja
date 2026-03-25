import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import SubpageBackLink from '../common/SubpageBackLink';
import { Document } from '../../types/document';
import type {
  BankStatementImportSummary,
  BankStatementLine,
  BankStatementLineResolutionReason,
  BankStatementLineStatus,
  BankStatementPeriod,
  BankStatementTransactionSummary,
} from '../../types/bankImport';
import { bankImportService } from '../../services/bankImportService';
import {
  documentService,
  type ConfirmBankTransactionPayload,
} from '../../services/documentService';
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
type BankWorkbenchFilter = 'all' | BankStatementLineStatus;
type AmountTone = 'credit' | 'debit' | 'neutral';
type BankStatementDisplayStatusTone = BankStatementLineStatus | 'revoked';

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
  imported_count: number;
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

const ViewIcon = () => (
  <svg className="icon-svg" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path
      d="M2.8 12C4.9 8.2 8.1 6.3 12 6.3C15.9 6.3 19.1 8.2 21.2 12C19.1 15.8 15.9 17.7 12 17.7C8.1 17.7 4.9 15.8 2.8 12Z"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinejoin="round"
    />
    <circle cx="12" cy="12" r="2.6" stroke="currentColor" strokeWidth="1.8" />
  </svg>
);

const UndoIcon = () => (
  <svg className="icon-svg" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path
      d="M8 8H4.5V4.5"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M5 8C6.8 5.8 9.4 4.5 12.3 4.5C17.4 4.5 21.5 8.6 21.5 13.7C21.5 18.8 17.4 22.9 12.3 22.9C8.4 22.9 5 20.5 3.7 16.9"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
    />
  </svg>
);

const UnmatchIcon = () => (
  <svg className="icon-svg" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path
      d="M10.2 13.8L13.8 10.2"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
    />
    <path
      d="M8.4 15.6L6.6 17.4C5.1 18.9 2.7 18.9 1.2 17.4C-0.3 15.9 -0.3 13.5 1.2 12L4.6 8.6C6.1 7.1 8.5 7.1 10 8.6"
      transform="translate(6.5 0)"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
    />
    <path
      d="M15.6 8.4L17.4 6.6C18.9 5.1 18.9 2.7 17.4 1.2C15.9 -0.3 13.5 -0.3 12 1.2L8.6 4.6C7.1 6.1 7.1 8.5 8.6 10"
      transform="translate(0 6.5)"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
    />
    <path
      d="M5 5L19 19"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
    />
  </svg>
);

const CreateTransactionIcon = () => (
  <svg className="icon-svg" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M12 5V19" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    <path d="M5 12H19" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
  </svg>
);

const MatchTransactionIcon = () => (
  <svg className="icon-svg" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path
      d="M10 14L8 16C6.34 17.66 3.66 17.66 2 16C0.34 14.34 0.34 11.66 2 10L5.5 6.5C7.16 4.84 9.84 4.84 11.5 6.5"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M14 10L16 8C17.66 6.34 20.34 6.34 22 8C23.66 9.66 23.66 12.34 22 14L18.5 17.5C16.84 19.16 14.16 19.16 12.5 17.5"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path d="M9 15L15 9" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
  </svg>
);

const IgnoreDuplicateIcon = () => (
  <svg className="icon-svg" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path
      d="M6.5 6.5H17.5V17.5H6.5V6.5Z"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinejoin="round"
    />
    <path
      d="M3 12L7 16L21 2"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const formatDate = (value: string | null | undefined, language: string) => {
  if (!value) return '-';
  const parsed = parseLooseDate(value);
  if (!parsed) return value;
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString(getLocaleForLanguage(language));
};

const getDateDistanceDays = (
  left: string | null | undefined,
  right: string | null | undefined,
): number | null => {
  if (!left || !right) return null;
  const leftDate = parseLooseDate(left);
  const rightDate = parseLooseDate(right);
  if (!leftDate || !rightDate) return null;
  const diffMs = Math.abs(leftDate.getTime() - rightDate.getTime());
  return Math.round(diffMs / (1000 * 60 * 60 * 24));
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

const isStatementPeriodObject = (value: unknown): value is BankStatementPeriod => (
  Boolean(value)
  && typeof value === 'object'
  && !Array.isArray(value)
  && ('start' in (value as Record<string, unknown>) || 'end' in (value as Record<string, unknown>))
);

const formatStatementPeriod = (value: unknown, language: string): string => {
  if (isStatementPeriodObject(value)) {
    const start = toNullableString(value.start);
    const end = toNullableString(value.end);

    if (start && end) {
      return `${formatDate(start, language)} - ${formatDate(end, language)}`;
    }

    return start ? formatDate(start, language) : end ? formatDate(end, language) : '-';
  }

  const explicit = toNullableString(value);
  return explicit || '-';
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
  if (isStatementPeriodObject(ocrData.statement_period)) {
    const start = toNullableString(ocrData.statement_period.start);
    const end = toNullableString(ocrData.statement_period.end);

    if (start && end) {
      return `${start} - ${end}`;
    }

    return start || end || null;
  }

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
  const importedFallbackFingerprints = Array.isArray(suggestion?.fallback_imported_fingerprints)
    ? suggestion.fallback_imported_fingerprints
      .map((value) => toNullableString(value))
      .filter((value): value is string => Boolean(value))
    : [];
  const sourceData = Object.keys(suggestionData).length > 0 ? suggestionData : ocrData;
  const rawTransactions = Array.isArray(sourceData.transactions)
    ? sourceData.transactions
    : Array.isArray(ocrData.transactions)
      ? ocrData.transactions
      : [];
  const lines = buildFallbackBankStatementLines(
    rawTransactions,
    document.raw_text,
    importedFallbackFingerprints,
  );

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
      imported_count: lines.filter((line) => line.is_imported).length,
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
  const navigate = useNavigate();
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
  const [fallbackActingId, setFallbackActingId] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<BankWorkbenchFilter>('all');
  const [bulkActing, setBulkActing] = useState(false);

  const refreshDocumentSnapshot = useCallback(async () => {
    try {
      const updatedDocument = await documentService.getDocument(document.id);
      onDocumentUpdated?.(updatedDocument);
      return updatedDocument;
    } catch (documentError) {
      console.warn('Failed to refresh bank statement document after workbench action', documentError);
      return null;
    }
  }, [document.id, onDocumentUpdated]);

  const syncFallbackStateFromDocument = useCallback((sourceDocument: Document) => {
    const fallbackState = buildFallbackState(sourceDocument);
    setFallbackSummary(fallbackState.summary);
    setFallbackLines(fallbackState.lines);
  }, []);

  const refreshWorkbench = useCallback(async (importId: number, refreshDocument = false) => {
    const [nextImport, nextLines] = await Promise.all([
      bankImportService.getImport(importId),
      bankImportService.getLines(importId),
    ]);
    setStatementImport(nextImport);
    setLines(nextLines);

    if (refreshDocument) {
      await refreshDocumentSnapshot();
    }
  }, [refreshDocumentSnapshot]);

  useEffect(() => {
    let disposed = false;
    let objectUrl: string | null = null;

    const load = async () => {
      setLoading(true);
      setError(null);
      setMode('remote');
      setStatementImport(null);
      setLines([]);
      setPreviewUrl(null);
      setFallbackSummary(null);
      setFallbackLines([]);
      setLoadingMessage(t('documents.bankWorkbench.initializing', 'Preparing the bank statement workbench...'));

      const previewPromise = (async () => {
        try {
          const blob = await documentService.downloadDocument(document.id);

          if (disposed) return;

          objectUrl = URL.createObjectURL(blob);
          setPreviewUrl(objectUrl);
        } catch (previewError) {
          if (disposed) return;
          console.warn('Failed to load bank statement preview:', previewError);
        }
      })();

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
          setMode('fallback');
          syncFallbackStateFromDocument(document);
          return;
        }

        console.error('Failed to initialize bank statement workbench:', loadError);
        setError(
          loadError?.response?.data?.detail
          || loadError?.message
          || t('documents.bankWorkbench.loadFailed', 'Failed to load bank statement workbench.')
        );
      } finally {
        void previewPromise;
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
  }, [document, syncFallbackStateFromDocument, t]);

  const normalizedRemoteLines = useMemo(
    () => lines.map((line) => {
      const hasCreatedTransaction = Boolean(line.created_transaction?.id ?? line.created_transaction_id);
      const hasLinkedTransaction = Boolean(line.linked_transaction?.id ?? line.linked_transaction_id);

      let reviewStatus: BankStatementLineStatus =
        (line.review_status as BankStatementLineStatus | null) ?? 'pending_review';
      let suggestedAction = line.suggested_action ?? 'create_new';
      let resolutionReason: BankStatementLineResolutionReason | null =
        (line.resolution_reason as BankStatementLineResolutionReason | null) ?? null;

      if (reviewStatus === 'auto_created' && !hasCreatedTransaction) {
        reviewStatus = 'pending_review';
        suggestedAction = 'create_new';
        resolutionReason = resolutionReason ?? 'orphan_repaired';
      } else if (reviewStatus === 'matched_existing' && !hasLinkedTransaction) {
        reviewStatus = 'pending_review';
        suggestedAction = 'create_new';
        resolutionReason = resolutionReason ?? 'orphan_repaired';
      } else if (
        reviewStatus === 'pending_review'
        && suggestedAction === 'match_existing'
        && !hasLinkedTransaction
      ) {
        suggestedAction = 'create_new';
        resolutionReason = resolutionReason ?? 'orphan_repaired';
      }

      return {
        ...line,
        review_status: reviewStatus,
        suggested_action: suggestedAction,
        resolution_reason: resolutionReason,
      };
    }),
    [lines],
  );

  const pendingLines = useMemo(
    () => normalizedRemoteLines.filter((line) => lineMatchesStatus(line.review_status, 'pending_review')),
    [normalizedRemoteLines]
  );
  const matchedLines = useMemo(
    () => normalizedRemoteLines.filter((line) => lineMatchesStatus(line.review_status, 'matched_existing')),
    [normalizedRemoteLines]
  );
  const createdLines = useMemo(
    () => normalizedRemoteLines.filter((line) => lineMatchesStatus(line.review_status, 'auto_created')),
    [normalizedRemoteLines]
  );
  const ignoredLines = useMemo(
    () => normalizedRemoteLines.filter((line) => lineMatchesStatus(line.review_status, 'ignored_duplicate')),
    [normalizedRemoteLines]
  );
  const filteredRemoteLines = useMemo(
    () => activeFilter === 'all'
      ? normalizedRemoteLines
      : normalizedRemoteLines.filter((line) => lineMatchesStatus(line.review_status, activeFilter)),
    [activeFilter, normalizedRemoteLines]
  );
  const actionablePendingLines = useMemo(
    () => pendingLines.filter((line) => (
      line.suggested_action === 'create_new'
      || (line.suggested_action === 'match_existing' && Boolean(line.linked_transaction_id))
      || line.suggested_action === 'ignore'
    )),
    [pendingLines]
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
      action: 'create' | 'match' | 'ignore' | 'undo-create' | 'unmatch'
    ) => {
      if (!statementImport) return;

      setActingLineId(lineId);
      setError(null);
      try {
        if (action === 'create') {
          await bankImportService.confirmCreateLine(lineId);
        } else if (action === 'match') {
          await bankImportService.matchExistingLine(lineId);
        } else if (action === 'undo-create') {
          await bankImportService.undoCreateLine(lineId);
        } else if (action === 'unmatch') {
          await bankImportService.unmatchLine(lineId);
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

  const runSuggestedAction = useCallback(async (line: BankStatementLine) => {
    if (line.suggested_action === 'match_existing' && line.linked_transaction_id) {
      await runLineAction(line.id, 'match');
      return;
    }
    if (line.suggested_action === 'ignore') {
      await runLineAction(line.id, 'ignore');
      return;
    }
    await runLineAction(line.id, 'create');
  }, [runLineAction]);

  const handleBulkConfirm = useCallback(async () => {
    if (!statementImport || actionablePendingLines.length === 0) {
      return;
    }

    setBulkActing(true);
    setError(null);
    try {
      for (const line of actionablePendingLines) {
        if (line.suggested_action === 'match_existing' && line.linked_transaction_id) {
          await bankImportService.matchExistingLine(line.id, line.linked_transaction_id);
        } else if (line.suggested_action === 'ignore') {
          await bankImportService.ignoreLine(line.id);
        } else {
          await bankImportService.confirmCreateLine(line.id);
        }
      }

      await refreshWorkbench(statementImport.id, true);
      useRefreshStore.getState().refreshTransactions();
      useRefreshStore.getState().refreshDashboard();
    } catch (bulkError: any) {
      console.error('Failed to bulk confirm bank statement lines', bulkError);
      setError(
        bulkError?.response?.data?.detail
        || bulkError?.message
        || t('documents.bankWorkbench.actionFailed', 'The bank statement action could not be completed.')
      );
    } finally {
      setBulkActing(false);
    }
  }, [actionablePendingLines, refreshWorkbench, statementImport, t]);

  const confirmFallbackLines = useCallback(async (targetLines: FallbackBankStatementLine[]) => {
    if (targetLines.length === 0) {
      return;
    }

    setFallbackActingId(targetLines.length === 1 ? targetLines[0].id : '__all__');
    setError(null);
    try {
      const selectedLineIds = new Set(targetLines.map((line) => line.id));
      const allFallbackPayload: ConfirmBankTransactionPayload[] = fallbackLines.map((line) => ({
        date: line.line_date ?? null,
        amount: line.amount ?? null,
        counterparty: line.counterparty ?? null,
        purpose: line.purpose ?? null,
        raw_reference: line.raw_reference ?? null,
        fingerprint: line.fingerprint ?? null,
      }));
      const selectedIndices = fallbackLines.reduce<number[]>((indices, line, index) => {
        if (selectedLineIds.has(line.id)) {
          indices.push(index);
        }
        return indices;
      }, []);
      const result = await documentService.confirmBankTransactions(
        document.id,
        selectedIndices,
        allFallbackPayload,
      );
      const updatedDocument = await refreshDocumentSnapshot();
      if (updatedDocument) {
        syncFallbackStateFromDocument(updatedDocument);
      }
      useRefreshStore.getState().refreshTransactions();
      useRefreshStore.getState().refreshDashboard();
      if (result.imported > 0) {
        aiToast(
          result.imported === 1
            ? t('documents.bankWorkbench.fallback.createdOne', 'Created 1 transaction.')
            : t('documents.bankWorkbench.fallback.createdMany', 'Created {{count}} transactions.', { count: result.imported }),
          'success',
        );
      } else if (result.skipped_duplicates > 0) {
        aiToast(
          targetLines.length === 1
            ? t('documents.bankWorkbench.fallback.alreadyImportedOne', 'This statement line was already imported.')
            : t('documents.bankWorkbench.fallback.alreadyImportedMany', 'These statement lines were already imported.'),
          'info',
        );
      } else {
        aiToast(
          t('documents.bankWorkbench.fallback.noTransactionsCreated', 'No new transactions were created.'),
          'warning',
        );
      }
    } catch (fallbackError: any) {
      console.error('Failed to confirm fallback bank statement lines', fallbackError);
      setError(
        fallbackError?.response?.data?.detail
        || fallbackError?.message
        || t('documents.bankWorkbench.actionFailed', 'The bank statement action could not be completed.')
      );
    } finally {
      setFallbackActingId(null);
    }
  }, [document.id, fallbackLines, refreshDocumentSnapshot, syncFallbackStateFromDocument, t]);

  const handleFallbackConfirmAll = useCallback(async () => {
    const pendingFallbackLines = fallbackLines.filter((line) => !line.is_imported);
    await confirmFallbackLines(pendingFallbackLines);
  }, [confirmFallbackLines, fallbackLines]);

  const getDisplayStatus = useCallback((line: BankStatementLine): {
    label: string;
    tone: BankStatementDisplayStatusTone;
  } => {
    if (line.review_status === 'pending_review') {
      if (line.resolution_reason === 'revoked_create') {
        return {
          label: t('documents.bankWorkbench.status.revokedCreate', 'Create undone'),
          tone: 'revoked',
        };
      }

      if (line.resolution_reason === 'revoked_match') {
        return {
          label: t('documents.bankWorkbench.status.revokedMatch', 'Match removed'),
          tone: 'revoked',
        };
      }

      return {
        label: t('documents.bankWorkbench.status.pendingReview', 'Pending review'),
        tone: 'pending_review',
      };
    }

    if (line.review_status === 'auto_created') {
      return {
        label: t('documents.bankWorkbench.status.autoCreated', 'Auto-created'),
        tone: 'auto_created',
      };
    }

    if (line.review_status === 'matched_existing') {
      return {
        label: t('documents.bankWorkbench.status.matchedExisting', 'Matched existing'),
        tone: 'matched_existing',
      };
    }

    return {
      label: t('documents.bankWorkbench.status.ignoredDuplicate', 'Ignored'),
      tone: 'ignored_duplicate',
    };
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

  const getSuggestedActionLabel = useCallback((line: BankStatementLine) => {
    if (line.suggested_action === 'match_existing') {
      return t('documents.bankWorkbench.actions.match', 'Match existing');
    }
    if (line.suggested_action === 'ignore') {
      return t('documents.bankWorkbench.actions.ignore', 'Ignore');
    }
    return t('documents.bankWorkbench.actions.create', 'Create transaction');
  }, [t]);

  const getSuggestedActionBadgeLabel = useCallback((line: BankStatementLine): string | null => {
    if (line.review_status !== 'pending_review') {
      return null;
    }

    if (
      line.resolution_reason === 'revoked_create'
      || line.resolution_reason === 'revoked_match'
      || line.resolution_reason === 'orphan_repaired'
    ) {
      return null;
    }

    if (line.suggested_action === 'match_existing' && line.linked_transaction_id) {
      return t('documents.bankWorkbench.suggested.match', 'Suggested match');
    }
    if (line.suggested_action === 'ignore') {
      return t('documents.bankWorkbench.suggested.ignore', 'Suggested ignore');
    }
    return t('documents.bankWorkbench.suggested.create', 'Suggested create');
  }, [t]);

  const getSuggestedActionHint = useCallback((line: BankStatementLine): string | null => {
    if (line.review_status !== 'pending_review') {
      return null;
    }

    if (line.resolution_reason === 'orphan_repaired') {
      return t(
        'documents.bankWorkbench.reason.orphanRepaired',
        'The linked transaction is no longer available. Review this line again.'
      );
    }

    if (
      line.resolution_reason === 'revoked_create'
      || line.resolution_reason === 'revoked_match'
    ) {
      return null;
    }

    if (line.suggested_action === 'match_existing' && line.linked_transaction_id) {
      return line.linked_transaction?.description
        || `${t('documents.bankWorkbench.linkedTransaction', 'Transaction')} #${line.linked_transaction_id}`;
    }

    return null;
  }, [t]);

  const getActualLinkedTransaction = useCallback((line: BankStatementLine): BankStatementTransactionSummary | null => {
    if (line.review_status === 'auto_created') {
      return line.created_transaction ?? line.linked_transaction ?? null;
    }
    if (line.review_status === 'matched_existing') {
      return line.linked_transaction ?? line.created_transaction ?? null;
    }
    return null;
  }, []);

  const getActualLinkedTransactionId = useCallback((line: BankStatementLine): number | null => {
    if (line.review_status === 'auto_created') {
      return (
        line.created_transaction?.id
        ?? line.created_transaction_id
        ?? line.linked_transaction?.id
        ?? line.linked_transaction_id
        ?? null
      );
    }
    if (line.review_status === 'matched_existing') {
      return (
        line.linked_transaction?.id
        ?? line.linked_transaction_id
        ?? line.created_transaction?.id
        ?? line.created_transaction_id
        ?? null
      );
    }
    return null;
  }, []);

  const handleOpenTransaction = useCallback((transactionId: number | null) => {
    if (!transactionId) {
      return;
    }
    navigate(`/transactions?transactionId=${transactionId}`);
  }, [navigate]);

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

  const renderRemoteTable = () => {
    const filterOptions: Array<{
      key: BankWorkbenchFilter;
      label: string;
      count: number;
    }> = [
      { key: 'all', label: t('documents.bankWorkbench.totalCount', 'Total lines'), count: lines.length },
      { key: 'pending_review', label: t('documents.bankWorkbench.pendingReview', 'Pending review'), count: pendingLines.length },
      { key: 'matched_existing', label: t('documents.bankWorkbench.status.matchedExisting', 'Matched existing'), count: matchedLines.length },
      { key: 'auto_created', label: t('documents.bankWorkbench.status.autoCreated', 'Auto-created'), count: createdLines.length },
      { key: 'ignored_duplicate', label: t('documents.bankWorkbench.status.ignoredDuplicate', 'Ignored duplicate'), count: ignoredLines.length },
    ];

    return (
      <section className="bank-workbench-group bank-workbench-group--pending">
        <div className="bank-workbench-group__header">
          <div>
            <h4>{t('documents.bankWorkbench.title', 'Bank statement workbench')}</h4>
            <p>
              {t(
                'documents.suggestion.bankWorkbenchHint',
                'Open the bank statement workbench to review low-confidence items, match existing transactions, and confirm new transactions.'
              )}
            </p>
          </div>
          <div className="bank-workbench-toolbar__actions">
            <button
              type="button"
              className="btn btn-primary bank-workbench-toolbar__button"
              onClick={() => void handleBulkConfirm()}
              disabled={bulkActing || actionablePendingLines.length === 0}
            >
              {t('common.oneClickConfirm', 'One-click confirm')}
            </button>
          </div>
        </div>

        <div className="bank-workbench-toolbar">
          <div className="bank-workbench-filter-grid">
            {filterOptions.map((option) => (
              <button
                key={option.key}
                type="button"
                className={`bank-workbench-filter-card ${activeFilter === option.key ? 'bank-workbench-filter-card--active' : ''}`}
                onClick={() => setActiveFilter(option.key)}
              >
                <span>{option.label}</span>
                <strong>{option.count}</strong>
              </button>
            ))}
          </div>
        </div>

        {filteredRemoteLines.length === 0 ? (
          <div className="bank-workbench-empty">
            {t('documents.bankWorkbench.emptyPending', 'No bank statement lines need confirmation right now.')}
          </div>
        ) : (
          <>
            <div className="bank-workbench-table-shell">
              <table className="bank-workbench-table bank-workbench-table--reconciliation">
                <thead>
                  <tr>
                    <th>{t('transactions.date', 'Date')}</th>
                    <th>{t('documents.suggestion.fields.counterparty', 'Counterparty')}</th>
                    <th>{t('documents.suggestion.fields.purpose', 'Purpose')}</th>
                    <th>{t('transactions.amount', 'Amount')}</th>
                    <th>{t('documents.bankWorkbench.linkedTransaction', 'Transaction')}</th>
                    <th>{t('common.status', 'Status')}</th>
                    <th>{t('common.actions', 'Actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRemoteLines.map((line) => {
                    const disabled = actingLineId === line.id || bulkActing;
                    const confidenceLabel = formatConfidence(line.confidence_score);
                    const displayStatus = getDisplayStatus(line);
                    const actualLinkedTransaction = getActualLinkedTransaction(line);
                    const actualLinkedTransactionId = getActualLinkedTransactionId(line);
                    const linkedReference = actualLinkedTransactionId
                      ? `${t('documents.bankWorkbench.linkedTransaction', 'Transaction')} #${actualLinkedTransactionId}`
                      : null;
                    const actualTransactionLabel = actualLinkedTransaction?.description || linkedReference;
                    const suggestedActionBadgeLabel = getSuggestedActionBadgeLabel(line);
                    const suggestedActionHint = getSuggestedActionHint(line);
                    const dateDelta = getDateDistanceDays(line.line_date, actualLinkedTransaction?.transaction_date);
                    const isPending = line.review_status === 'pending_review';

                    return (
                      <tr key={line.id}>
                        <td>
                          <div className="bank-workbench-cell">
                            <div className="bank-workbench-cell__primary">
                              {formatDate(line.line_date, i18n.language)}
                            </div>
                            {actualLinkedTransaction?.transaction_date && (
                              <div className="bank-workbench-cell__secondary">
                                {formatDate(actualLinkedTransaction.transaction_date, i18n.language)}
                              </div>
                            )}
                          </div>
                        </td>
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
                          {actualTransactionLabel && (
                            <div className="bank-workbench-cell">
                              <div className="bank-workbench-cell__primary">
                                {actualTransactionLabel}
                              </div>
                              {actualLinkedTransaction?.transaction_date && (
                                <div className="bank-workbench-cell__secondary">
                                  {t('transactions.date', 'Date')}: {formatDate(actualLinkedTransaction.transaction_date, i18n.language)}
                                </div>
                              )}
                              {dateDelta !== null && dateDelta > 0 && (
                                <div className="bank-workbench-cell__secondary">
                                  {dateDelta}d
                                </div>
                              )}
                            </div>
                          )}
                        </td>
                        <td>
                          <div className="bank-workbench-cell">
                            <span className={`bank-workbench-line__status bank-workbench-line__status--${displayStatus.tone}`}>
                              {displayStatus.label}
                            </span>
                            {confidenceLabel && (
                              <div className="bank-workbench-cell__secondary">
                                {t('documents.bankWorkbench.confidence', 'Confidence')}: {confidenceLabel}
                              </div>
                            )}
                            {suggestedActionBadgeLabel && (
                              <div className="bank-workbench-cell__secondary bank-workbench-cell__secondary--inline">
                                <span className={`bank-workbench-line__suggestion bank-workbench-line__suggestion--${line.suggested_action || 'create_new'}`}>
                                  {suggestedActionBadgeLabel}
                                </span>
                              </div>
                            )}
                            {suggestedActionHint && (
                              <div className="bank-workbench-cell__secondary">
                                {suggestedActionHint}
                              </div>
                            )}
                          </div>
                        </td>
                        <td className="bank-workbench-table__actions">
                          {isPending ? (
                            <div className="bank-workbench-utility-actions">
                              <button
                                type="button"
                                className="bank-workbench-utility-btn bank-workbench-utility-btn--primary"
                                onClick={() => void runSuggestedAction(line)}
                                disabled={disabled}
                                aria-label={getSuggestedActionLabel(line)}
                                title={getSuggestedActionLabel(line)}
                              >
                                {line.suggested_action === 'match_existing' ? <MatchTransactionIcon /> : <CreateTransactionIcon />}
                              </button>
                              {line.suggested_action !== 'match_existing' && line.linked_transaction_id && (
                                <button
                                  type="button"
                                  className="bank-workbench-utility-btn"
                                  onClick={() => void runLineAction(line.id, 'match')}
                                  disabled={disabled}
                                  aria-label={t('documents.bankWorkbench.actions.match', 'Match existing')}
                                  title={t('documents.bankWorkbench.actions.match', 'Match existing')}
                                >
                                  <MatchTransactionIcon />
                                </button>
                              )}
                              {line.suggested_action !== 'create_new' && (
                                <button
                                  type="button"
                                  className="bank-workbench-utility-btn"
                                  onClick={() => void runLineAction(line.id, 'create')}
                                  disabled={disabled}
                                  aria-label={t('documents.bankWorkbench.actions.create', 'Create transaction')}
                                  title={t('documents.bankWorkbench.actions.create', 'Create transaction')}
                                >
                                  <CreateTransactionIcon />
                                </button>
                              )}
                              <button
                                type="button"
                                className="bank-workbench-utility-btn bank-workbench-utility-btn--warning"
                                onClick={() => void runLineAction(line.id, 'ignore')}
                                disabled={disabled}
                                aria-label={t('documents.bankWorkbench.actions.ignore', 'Ignore')}
                                title={t('documents.bankWorkbench.actions.ignore', 'Ignore')}
                              >
                                <IgnoreDuplicateIcon />
                              </button>
                            </div>
                          ) : (
                            actualLinkedTransactionId ? (
                              <div className="bank-workbench-utility-actions">
                                <button
                                  type="button"
                                  className="bank-workbench-utility-btn"
                                  onClick={() => handleOpenTransaction(actualLinkedTransactionId)}
                                  aria-label={t('documents.lineItems.viewTransaction', 'View transaction')}
                                  title={t('documents.lineItems.viewTransaction', 'View transaction')}
                                >
                                  <ViewIcon />
                                </button>
                                {line.review_status === 'auto_created' && line.created_transaction_id && (
                                  <button
                                    type="button"
                                    className="bank-workbench-utility-btn bank-workbench-utility-btn--warning"
                                    onClick={() => void runLineAction(line.id, 'undo-create')}
                                    disabled={disabled}
                                    aria-label={t('documents.bankWorkbench.actions.undoCreate', 'Undo create')}
                                    title={t('documents.bankWorkbench.actions.undoCreate', 'Undo create')}
                                  >
                                    <UndoIcon />
                                  </button>
                                )}
                                {line.review_status === 'matched_existing' && (
                                  <button
                                    type="button"
                                    className="bank-workbench-utility-btn bank-workbench-utility-btn--warning"
                                    onClick={() => void runLineAction(line.id, 'unmatch')}
                                    disabled={disabled}
                                    aria-label={t('documents.bankWorkbench.actions.unmatch', 'Unmatch')}
                                    title={t('documents.bankWorkbench.actions.unmatch', 'Unmatch')}
                                  >
                                    <UnmatchIcon />
                                  </button>
                                )}
                              </div>
                            ) : (
                              <span className="bank-workbench-table__static-action">
                                {displayStatus.label}
                              </span>
                            )
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="bank-workbench-mobile-list">
              {filteredRemoteLines.map((line) => {
                const disabled = actingLineId === line.id || bulkActing;
                const confidenceLabel = formatConfidence(line.confidence_score);
                const displayStatus = getDisplayStatus(line);
                const actualLinkedTransaction = getActualLinkedTransaction(line);
                const actualLinkedTransactionId = getActualLinkedTransactionId(line);
                const actualTransactionLabel = actualLinkedTransaction?.description
                  || (actualLinkedTransactionId
                    ? `${t('documents.bankWorkbench.linkedTransaction', 'Transaction')} #${actualLinkedTransactionId}`
                    : null);
                const suggestedActionBadgeLabel = getSuggestedActionBadgeLabel(line);
                const suggestedActionHint = getSuggestedActionHint(line);
                const dateDelta = getDateDistanceDays(line.line_date, actualLinkedTransaction?.transaction_date);
                const isPending = line.review_status === 'pending_review';

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
                      <span className={`bank-workbench-line__status bank-workbench-line__status--${displayStatus.tone}`}>
                        {displayStatus.label}
                      </span>
                      {actualTransactionLabel && (
                        <span className="bank-workbench-mobile-card__meta-item">
                          {actualTransactionLabel}
                        </span>
                      )}
                      {dateDelta !== null && dateDelta > 0 && (
                        <span className="bank-workbench-mobile-card__meta-item">
                          {dateDelta}d
                        </span>
                      )}
                      {confidenceLabel && (
                        <span className="bank-workbench-mobile-card__meta-item">
                          {t('documents.bankWorkbench.confidence', 'Confidence')}: {confidenceLabel}
                        </span>
                      )}
                      {suggestedActionBadgeLabel && (
                        <span className="bank-workbench-mobile-card__meta-item">
                          <span className={`bank-workbench-line__suggestion bank-workbench-line__suggestion--${line.suggested_action || 'create_new'}`}>
                            {suggestedActionBadgeLabel}
                          </span>
                        </span>
                      )}
                      {suggestedActionHint && (
                        <span className="bank-workbench-mobile-card__meta-item">
                          {suggestedActionHint}
                        </span>
                      )}
                    </div>

                    {isPending ? (
                      <div className="bank-workbench-line__actions bank-workbench-line__actions--mobile">
                        <button
                          type="button"
                          className="btn btn-primary bank-workbench-action-btn bank-workbench-action-btn--primary"
                          onClick={() => void runSuggestedAction(line)}
                          disabled={disabled}
                        >
                          {getSuggestedActionLabel(line)}
                        </button>
                        {line.suggested_action !== 'create_new' && (
                          <button
                            type="button"
                            className="btn btn-secondary bank-workbench-action-btn"
                            onClick={() => void runLineAction(line.id, 'create')}
                            disabled={disabled}
                          >
                            {t('documents.bankWorkbench.actions.create', 'Create transaction')}
                          </button>
                        )}
                        {line.suggested_action !== 'match_existing' && line.linked_transaction_id && (
                          <button
                            type="button"
                            className="btn btn-secondary bank-workbench-action-btn"
                            onClick={() => void runLineAction(line.id, 'match')}
                            disabled={disabled}
                          >
                            {t('documents.bankWorkbench.actions.match', 'Match existing')}
                          </button>
                        )}
                        <button
                          type="button"
                          className="btn btn-secondary bank-workbench-action-btn"
                          onClick={() => void runLineAction(line.id, 'ignore')}
                          disabled={disabled}
                        >
                          {t('documents.bankWorkbench.actions.ignore', 'Ignore')}
                        </button>
                      </div>
                    ) : actualLinkedTransactionId ? (
                      <div className="bank-workbench-line__actions bank-workbench-line__actions--mobile">
                        <button
                          type="button"
                          className="btn btn-secondary bank-workbench-action-btn"
                          onClick={() => handleOpenTransaction(actualLinkedTransactionId)}
                        >
                          {t('documents.lineItems.viewTransaction', 'View transaction')}
                        </button>
                        {line.review_status === 'auto_created' && line.created_transaction_id && (
                          <button
                            type="button"
                            className="btn btn-secondary bank-workbench-action-btn bank-workbench-action--warning"
                            onClick={() => void runLineAction(line.id, 'undo-create')}
                            disabled={disabled}
                          >
                            {t('documents.bankWorkbench.actions.undoCreate', 'Undo create')}
                          </button>
                        )}
                        {line.review_status === 'matched_existing' && (
                          <button
                            type="button"
                            className="btn btn-secondary bank-workbench-action-btn bank-workbench-action--warning"
                            onClick={() => void runLineAction(line.id, 'unmatch')}
                            disabled={disabled}
                          >
                            {t('documents.bankWorkbench.actions.unmatch', 'Unmatch')}
                          </button>
                        )}
                      </div>
                    ) : null}
                  </article>
                );
              })}
            </div>
          </>
        )}
      </section>
    );
  };

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
        <div className="bank-workbench-toolbar__actions">
          <span className="bank-workbench-group__count">{fallbackLines.length}</span>
          <button
            type="button"
            className="btn btn-primary bank-workbench-toolbar__button"
            onClick={() => void handleFallbackConfirmAll()}
            disabled={fallbackActingId !== null || fallbackLines.every((line) => line.is_imported)}
          >
            {t('common.confirm', 'Confirm')}
          </button>
        </div>
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
                  <th>{t('documents.suggestion.fields.counterparty', 'Counterparty')}</th>
                  <th>{t('documents.suggestion.fields.purpose', 'Purpose')}</th>
                  <th>{t('transactions.amount', 'Amount')}</th>
                  <th>{t('documents.bankWorkbench.direction.label', 'Direction')}</th>
                  <th>{t('common.status', 'Status')}</th>
                  <th>{t('common.actions', 'Actions')}</th>
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
                    <td>
                      <span className={`bank-workbench-line__status bank-workbench-line__status--${line.is_imported ? 'auto_created' : 'pending_review'}`}>
                        {line.is_imported
                          ? t('documents.bankWorkbench.status.autoCreated', 'Auto-created')
                          : t('documents.bankWorkbench.status.pendingReview', 'Pending review')}
                      </span>
                    </td>
                    <td className="bank-workbench-table__actions">
                      <div className="bank-workbench-line__actions">
                        <button
                          type="button"
                          className="btn btn-primary"
                          onClick={() => void confirmFallbackLines([line])}
                          disabled={Boolean(line.is_imported) || fallbackActingId !== null}
                        >
                          {line.is_imported
                            ? t('documents.bankWorkbench.status.autoCreated', 'Auto-created')
                            : t('documents.bankWorkbench.actions.create', 'Create transaction')}
                        </button>
                      </div>
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
                  <span className={`bank-workbench-line__status bank-workbench-line__status--${line.is_imported ? 'auto_created' : 'pending_review'}`}>
                    {line.is_imported
                      ? t('documents.bankWorkbench.status.autoCreated', 'Auto-created')
                      : t('documents.bankWorkbench.status.pendingReview', 'Pending review')}
                  </span>
                </div>

                <div className="bank-workbench-line__actions bank-workbench-line__actions--mobile">
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => void confirmFallbackLines([line])}
                    disabled={Boolean(line.is_imported) || fallbackActingId !== null}
                  >
                    {line.is_imported
                      ? t('documents.bankWorkbench.status.autoCreated', 'Auto-created')
                      : t('documents.bankWorkbench.actions.create', 'Create transaction')}
                  </button>
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
                  <strong>{formatStatementPeriod(statementImport?.statement_period, i18n.language)}</strong>
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
                    : t('common.confirm', 'Confirm')}
                </span>
                <strong>
                  {mode === 'remote'
                    ? statementImport?.ignored_count ?? 0
                    : fallbackSummary?.imported_count ?? 0}
                </strong>
              </div>
            </div>
          </div>

          {mode === 'remote' ? (
            renderRemoteTable()
          ) : (
            renderFallbackTable()
          )}
        </div>
      </div>
    </div>
  );
};

export default BankStatementWorkbench;
