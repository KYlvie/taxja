import { useState, useEffect, useCallback } from 'react';
/* eslint-disable @typescript-eslint/no-explicit-any */
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import Select from '../components/common/Select';
import DocumentUpload from '../components/documents/DocumentUpload';
import { translateDeductionReason } from '../utils/translateDeductionReason';
import DocumentList from '../components/documents/DocumentList';
import OCRReview from '../components/documents/OCRReview';
import EmployerReviewPanel from '../components/documents/EmployerReviewPanel';
import BescheidImport from '../components/documents/BescheidImport';
import E1FormImport from '../components/documents/E1FormImport';
import DocumentActionGate from '../components/documents/DocumentActionGate';
import DocumentPresentationRouter from '../components/documents/DocumentPresentationRouter';
import SuggestionCardFactory from '../components/documents/SuggestionCardFactory';
import { documentService, type AssetSuggestionConfirmationPayload } from '../services/documentService';
import { transactionService } from '../services/transactionService';
import { propertyService } from '../services/propertyService';
import { Document } from '../types/document';
import { Property } from '../types/property';
import { ExpenseCategory, IncomeCategory, Transaction } from '../types/transaction';
import { saveBlobWithNativeShare } from '../mobile/files';
import { useRefreshStore } from '../stores/refreshStore';
import { aiToast } from '../stores/aiToastStore';
import { getLocaleForLanguage } from '../utils/locale';
import i18n from '../i18n';
import { formatTransactionCategoryLabel } from '../utils/formatTransactionCategoryLabel';
import { getApiErrorMessage, getLineItemReconciliationError } from '../utils/apiError';
import isDocumentPresentationResolverEnabled from '../documents/presentation/featureFlag';
import { resolveDocumentPresentation } from '../documents/presentation/resolveDocumentPresentation';
import { resolveControlPolicy } from '../documents/presentation/resolveControlPolicy';
import type {
  DocumentPresentationDraft,
} from '../documents/presentation/types';
import './DocumentsPage.css';

type ReceiptDraftItem = {
  description: string;
  amount: number;
  quantity: number | string;
  unitPrice?: number | null;
  vatRate?: number | null;
  vatIndicator?: string | null;
  category?: string;
  is_deductible?: boolean | null;
  deduction_reason?: string;
};

type AssetOutcomeRecord = {
  contract_version?: string;
  type?: string;
  status?: string;
  decision?: string;
  asset_id?: string | number | null;
  source?: string;
  quality_gate_decision?: string | null;
};

type PipelineCurrentState =
  | 'processing_phase_1'
  | 'first_result_available'
  | 'finalizing'
  | 'completed'
  | 'phase_2_failed';

const ACTIVE_REPROCESS_STATES = new Set<PipelineCurrentState>([
  'processing_phase_1',
  'first_result_available',
  'finalizing',
]);

const RECEIPT_DOC_TYPES = new Set(['receipt', 'invoice']);
const LEGACY_FINAL_ASSET_STATUSES = new Set(['confirmed', 'auto-created']);
const EXPENSE_CATEGORY_VALUES = new Set(Object.values(ExpenseCategory));
const INCOME_CATEGORY_VALUES = new Set(Object.values(IncomeCategory));
const OCR_META_SKIP_KEYS = [
  'field_confidence',
  'confidence',
  'import_suggestion',
  'asset_outcome',
  'line_items',
  'items',
  'vat_summary',
  'tax_analysis',
  '_additional_receipts',
  '_receipt_count',
  '_pipeline',
  '_validation',
  'correction_history',
  'multiple_receipts',
  'receipt_count',
  'receipts',
  'total_amount',
];

const toFiniteNumber = (value: unknown): number | null => {
  if (value === null || value === undefined || value === '') return null;
  const parsed = typeof value === 'string'
    ? Number(value.replace(',', '.'))
    : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const normalizeVatRate = (value: unknown): number | null => {
  const numeric = toFiniteNumber(value);
  if (numeric === null) return null;
  return numeric > 1 ? Number((numeric / 100).toFixed(4)) : Number(numeric.toFixed(4));
};

const EMPTY_DISPLAY_VALUE = '-';

const formatCurrencyDisplay = (value: unknown): string => {
  const numeric = toFiniteNumber(value);
  return numeric === null
    ? EMPTY_DISPLAY_VALUE
    : numeric.toLocaleString(getLocaleForLanguage(i18n.language), {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
};

const isValidReceiptCategoryForTransactionType = (
  category: string | undefined,
  transactionType: 'expense' | 'income' | 'unknown',
): boolean => {
  const token = String(category || '').trim();
  if (!token) return false;
  if (transactionType === 'income') {
    return INCOME_CATEGORY_VALUES.has(token as IncomeCategory);
  }
  if (transactionType === 'expense') {
    return EXPENSE_CATEGORY_VALUES.has(token as ExpenseCategory);
  }
  return INCOME_CATEGORY_VALUES.has(token as IncomeCategory)
    || EXPENSE_CATEGORY_VALUES.has(token as ExpenseCategory);
};

const normalizeReceiptItemsForTransactionType = (
  items: ReceiptDraftItem[],
  transactionType: 'expense' | 'income' | 'unknown',
): ReceiptDraftItem[] => items.map((item) => {
  const nextCategory = isValidReceiptCategoryForTransactionType(item.category, transactionType)
    ? item.category
    : undefined;

  if (transactionType === 'income') {
    return {
      ...item,
      category: nextCategory,
      is_deductible: false,
      deduction_reason: '',
    };
  }

  return {
    ...item,
    category: nextCategory,
  };
});

const buildReceiptSyncBlockedMessage = (
  error: any,
  t: any,
  options?: { ocrSaved?: boolean }
): string => {
  const reconciliation = getLineItemReconciliationError(error);
  if (reconciliation) {
    const expectedLabel = reconciliation.expected !== null
      ? formatCurrencyDisplay(reconciliation.expected)
      : EMPTY_DISPLAY_VALUE;
    const reconstructedLabel = reconciliation.reconstructed !== null
      ? formatCurrencyDisplay(reconciliation.reconstructed)
      : EMPTY_DISPLAY_VALUE;
    const prefix = options?.ocrSaved
      ? t(
          'documents.taxReview.syncBlockedAfterSave',
          'Document details were saved, but the linked transaction was not updated.'
        )
      : t(
          'documents.taxReview.syncBlocked',
          'The linked transaction was not updated.'
        );
    const template = t(
      'documents.taxReview.syncAmountMismatch',
      'The invoice total {{expected}} does not match the reconstructed line-item total {{reconstructed}}. Check the line-item amounts or VAT on this invoice, then save again.'
    );

    return `${prefix} ${template
      .replace('{{expected}}', expectedLabel)
      .replace('{{reconstructed}}', reconstructedLabel)}`;
  }

  const baseMessage = getApiErrorMessage(error, t('common.saveFailed', 'Save failed'));
  if (options?.ocrSaved) {
    return `${t(
      'documents.taxReview.syncBlockedAfterSave',
      'Document details were saved, but the linked transaction was not updated.'
    )} ${baseMessage}`;
  }
  return baseMessage;
};

const normalizeReceiptSection = (receipt: Record<string, any>): Record<string, any> => {
  const sanitized = { ...receipt };
  [
    '_additional_receipts',
    '_receipt_count',
    'tax_analysis',
    'import_suggestion',
    'asset_outcome',
    'multiple_receipts',
    'receipt_count',
    'receipts',
  ].forEach((key) => {
    delete sanitized[key];
  });
  return normalizeReceiptData(sanitized);
};

const buildTaxAnalysisItems = (items: ReceiptDraftItem[]) => {
  const mappedItems = items.map((item) => ({
    description: item.description,
    amount: item.amount,
    category: item.category,
    is_deductible: item.is_deductible === true,
    deduction_reason: item.deduction_reason || undefined,
  }));
  const deductible_amount = mappedItems
    .filter((item) => item.is_deductible)
    .reduce((sum, item) => sum + Number(item.amount || 0), 0);
  const non_deductible_amount = mappedItems
    .filter((item) => !item.is_deductible)
    .reduce((sum, item) => sum + Number(item.amount || 0), 0);

  return {
    items: mappedItems,
    deductible_amount,
    non_deductible_amount,
    is_split: deductible_amount > 0 && non_deductible_amount > 0,
  };
};

const parseOcrData = (ocrResult: unknown): Record<string, any> | null => {
  if (!ocrResult) return null;
  if (typeof ocrResult === 'string') {
    try {
      return JSON.parse(ocrResult);
    } catch {
      return null;
    }
  }
  if (typeof ocrResult === 'object') {
    return ocrResult as Record<string, any>;
  }
  return null;
};

const getAssetOutcome = (ocrResult: unknown): AssetOutcomeRecord | null => {
  const parsed = parseOcrData(ocrResult);
  const assetOutcome = parsed?.asset_outcome;
  if (assetOutcome && typeof assetOutcome === 'object' && assetOutcome.type === 'create_asset') {
    return assetOutcome as AssetOutcomeRecord;
  }

  const suggestion = parsed?.import_suggestion;
  if (
    suggestion
    && typeof suggestion === 'object'
    && suggestion.type === 'create_asset'
    && LEGACY_FINAL_ASSET_STATUSES.has(String(suggestion.status))
    && suggestion.asset_id
  ) {
    return {
      contract_version: 'v1',
      type: 'create_asset',
      status: suggestion.status === 'auto-created' ? 'auto_created' : 'confirmed',
      decision: suggestion.data?.decision || 'create_asset_suggestion',
      asset_id: suggestion.asset_id,
      source: 'legacy_compat',
      quality_gate_decision: suggestion.data?.quality_gate_decision ?? null,
    };
  }

  return null;
};

const getPipelineCurrentState = (
  ocrResult: unknown,
  processedAt?: string | null
): PipelineCurrentState | null => {
  const parsed = parseOcrData(ocrResult);
  const state = parsed?._pipeline?.current_state;
  if (typeof state === 'string' && state) {
    return state as PipelineCurrentState;
  }
  return processedAt ? 'completed' : null;
};

const getPipelineStatePresentation = (
  t: any,
  state: PipelineCurrentState | null
): { tone: 'info' | 'warning'; title: string; description: string } | null => {
  switch (state) {
    case 'processing_phase_1':
      return {
        tone: 'info',
        title: t('documents.pipeline.processingPhase1Title', 'Extracting document content'),
        description: t('documents.pipeline.processingPhase1Body', 'OCR and classification are still running. The first reviewable results will appear shortly.'),
      };
    case 'first_result_available':
      return {
        tone: 'info',
        title: t('documents.pipeline.firstResultTitle', 'First results are ready'),
        description: t('documents.pipeline.firstResultBody', 'OCR, classification, and extracted data have been saved. Follow-up suggestions are still being prepared.'),
      };
    case 'finalizing':
      return {
        tone: 'info',
        title: t('documents.pipeline.finalizingTitle', 'Finishing background processing'),
        description: t('documents.pipeline.finalizingBody', 'You can already review the first extracted results while automated suggestions and follow-up actions keep running.'),
      };
    case 'phase_2_failed':
      return {
        tone: 'warning',
        title: t('documents.pipeline.phase2FailedTitle', 'Follow-up automation did not finish'),
        description: t('documents.pipeline.phase2FailedBody', 'The initial OCR result is still available, and you can continue reviewing or editing the extracted data.'),
      };
    default:
      return null;
  }
};

const normalizeReceiptData = (receipt: any): Record<string, any> => {
  if (!receipt || typeof receipt !== 'object') return {};
  const normalized = { ...receipt };
  if (!Array.isArray(normalized.line_items) && Array.isArray(normalized.items)) {
    normalized.line_items = normalized.items;
  }
  return normalized;
};

const normalizeOcrDataForDisplay = (ocrResult: unknown): Record<string, any> | null => {
  const parsed = parseOcrData(ocrResult);
  if (!parsed || typeof parsed !== 'object') return parsed;

  const normalized = normalizeReceiptData(parsed);
  const multipleReceipts = (
    Array.isArray(normalized.multiple_receipts)
      ? normalized.multiple_receipts
      : Array.isArray(normalized.receipts)
        ? normalized.receipts
        : []
  )
    .filter((receipt: any) => receipt && typeof receipt === 'object')
    .map((receipt: any) => normalizeReceiptData(receipt));
  const additionalReceipts = (
    Array.isArray(normalized._additional_receipts) ? normalized._additional_receipts : []
  )
    .filter((receipt: any) => receipt && typeof receipt === 'object')
    .map((receipt: any) => normalizeReceiptData(receipt));

  if (multipleReceipts.length > 0) {
    const [primaryReceipt, ...restReceipts] = multipleReceipts;
    return {
      ...normalized,
      ...primaryReceipt,
      line_items: Array.isArray(primaryReceipt.line_items) ? primaryReceipt.line_items : normalized.line_items,
      vat_summary: Array.isArray(primaryReceipt.vat_summary) ? primaryReceipt.vat_summary : normalized.vat_summary,
      _additional_receipts: restReceipts.length > 0 ? restReceipts : additionalReceipts,
      _receipt_count: Number(normalized._receipt_count ?? normalized.receipt_count ?? multipleReceipts.length),
    };
  }

  return {
    ...normalized,
    _additional_receipts: additionalReceipts,
    _receipt_count: Number(
      normalized._receipt_count
      ?? normalized.receipt_count
      ?? (additionalReceipts.length > 0 ? additionalReceipts.length + 1 : 0)
    ),
  };
};

const getDisplayLineItems = (data: Record<string, any> | null | undefined): any[] => {
  if (!data || typeof data !== 'object') return [];
  if (Array.isArray(data.line_items) && data.line_items.length > 0) return data.line_items;
  if (Array.isArray(data.items) && data.items.length > 0) return data.items;

// Fallback: no line_items but an amount exists, so create a single whole-receipt item.
  // This ensures tax deductibility judgment is always available
  const amount = data.amount || data.total_amount || data.total;
  if (amount && Number(amount) > 0) {
    return [{
      name: data.description || data.merchant || 'Gesamtbetrag',
      description: data.description || data.merchant || 'Gesamtbetrag',
      quantity: 1,
      price: Number(amount),
      total: Number(amount),
      total_price: Number(amount),
    }];
  }
  return [];
};

const getAllReceiptsForDisplay = (data: Record<string, any> | null | undefined): Record<string, any>[] => {
  if (!data || typeof data !== 'object') return [];

  const primaryReceipt = normalizeReceiptSection(data);
  const additionalReceipts = Array.isArray(data._additional_receipts)
    ? data._additional_receipts
        .filter((receipt: any) => receipt && typeof receipt === 'object')
        .map((receipt: Record<string, any>) => normalizeReceiptSection(receipt))
    : [];

  return [primaryReceipt, ...additionalReceipts].filter((receipt) => {
    if (!receipt || typeof receipt !== 'object') return false;
    const hasScalarFields = Object.entries(receipt).some(
      ([key, value]) =>
        !key.startsWith('_')
        && !OCR_META_SKIP_KEYS.includes(key)
        && value !== null
        && value !== undefined
        && typeof value !== 'object'
    );
    return hasScalarFields || getDisplayLineItems(receipt).length > 0;
  });
};

const normalizeReceiptDraftItem = (item: any, fallback: any = {}): ReceiptDraftItem => {
  const quantity = item?.quantity ?? fallback?.quantity ?? 1;
  const amountCandidates = [
    item?.total,
    item?.total_price,
    item?.amount,
    fallback?.amount,
  ];
  const amount = amountCandidates
    .map(toFiniteNumber)
    .find((value) => value !== null)
    ?? 0;

  const unitPrice = [
    item?.unit_price,
    item?.price,
    fallback?.unit_price,
  ]
    .map(toFiniteNumber)
    .find((value) => value !== null)
    ?? (() => {
      const numericQuantity = toFiniteNumber(quantity);
      if (!numericQuantity || numericQuantity <= 0) return null;
      return Number((amount / numericQuantity).toFixed(2));
    })();

  return {
    description: String(item?.description || item?.name || fallback?.description || '').trim(),
    amount: Number(amount.toFixed(2)),
    quantity,
    unitPrice,
    vatRate: toFiniteNumber(item?.vat_rate ?? fallback?.vat_rate),
    vatIndicator: item?.vat_indicator ?? fallback?.vat_indicator ?? null,
    category: item?.category ?? fallback?.category,
    is_deductible:
      typeof item?.is_deductible === 'boolean'
        ? item.is_deductible
        : typeof fallback?.is_deductible === 'boolean'
          ? fallback.is_deductible
          : null,
    deduction_reason: item?.deduction_reason ?? fallback?.deduction_reason ?? '',
  };
};

const mapTransactionLineItemToDraftItem = (item: NonNullable<Transaction['line_items']>[number]): ReceiptDraftItem => {
  const quantity = toFiniteNumber(item.quantity) ?? 1;
  const unitPrice = toFiniteNumber(item.amount) ?? 0;
  const totalAmount = Number((unitPrice * quantity).toFixed(2));

  return {
    description: item.description,
    amount: totalAmount,
    quantity: item.quantity ?? 1,
    unitPrice,
    vatRate: toFiniteNumber(item.vat_rate),
    category: item.category,
    is_deductible: item.is_deductible ?? null,
    deduction_reason: item.deduction_reason ?? '',
  };
};

const buildReceiptDrafts = (
  data: Record<string, any> | null,
  linkedTransaction: Transaction | null
): Record<number, ReceiptDraftItem[]> => {
  const receipts = getAllReceiptsForDisplay(data);

  return receipts.reduce<Record<number, ReceiptDraftItem[]>>((result, receipt, receiptIndex) => {
    const rawItems = getDisplayLineItems(receipt);
    const taxItems = receiptIndex === 0 && Array.isArray(data?.tax_analysis?.items)
      ? data?.tax_analysis?.items
      : [];

    let draftItems = rawItems.map((item, itemIndex) => normalizeReceiptDraftItem(item, taxItems[itemIndex]));

    if (receiptIndex === 0 && linkedTransaction?.line_items?.length) {
      draftItems = linkedTransaction.line_items.map(mapTransactionLineItemToDraftItem);
    }

    result[receiptIndex] = draftItems.filter((item) => item.description || item.amount > 0);
    return result;
  }, {});
};

const buildReceiptPresentationDrafts = (
  documentType: string | undefined,
  data: Record<string, any> | null
): Record<number, DocumentPresentationDraft> => {
  const receipts = getAllReceiptsForDisplay(data);

  return receipts.reduce<Record<number, DocumentPresentationDraft>>((result, receipt, receiptIndex) => {
    const resolvedDocumentType = String(receipt.document_type || documentType || 'receipt').toLowerCase();
    const isInvoiceFamilyDocumentType = [
      'invoice',
      'credit_note',
      'gutschrift',
      'proforma_invoice',
      'delivery_note',
    ].includes(resolvedDocumentType);
    const transactionType = String(
      receipt._transaction_type
        ?? receipt.transaction_type
        ?? receipt.document_transaction_direction
        ?? receipt.transaction_direction
        ?? ''
    ).toLowerCase();
    const resolvedTransactionType = transactionType === 'income'
      ? 'income'
      : transactionType === 'expense'
        ? 'expense'
        : 'expense';

    result[receiptIndex] = {
      documentType: isInvoiceFamilyDocumentType ? 'invoice' : 'receipt',
      transactionType: resolvedTransactionType,
      documentTransactionDirection:
        receipt.document_transaction_direction
        ?? receipt.transaction_direction
        ?? null,
      commercialDocumentSemantics:
        receipt.commercial_document_semantics
        ?? (resolvedDocumentType === 'invoice' ? 'standard_invoice' : 'receipt'),
      isReversal:
        typeof receipt.is_reversal === 'boolean'
          ? receipt.is_reversal
          : null,
    };

    return result;
  }, {});
};

const RECEIPT_PRESENTATION_SCALAR_SKIP_KEYS = new Set([
  'document_type',
  'transaction_type',
  '_transaction_type',
  'document_transaction_direction',
  'document_transaction_direction_source',
  'document_transaction_direction_confidence',
  'commercial_document_semantics',
  'is_reversal',
]);

const buildReceiptScalarEntries = (receipt: Record<string, any>): [string, unknown][] =>
  Object.entries(receipt).filter(
    ([key, value]) =>
      !key.startsWith('_')
      && !OCR_META_SKIP_KEYS.includes(key)
      && !RECEIPT_PRESENTATION_SCALAR_SKIP_KEYS.has(key)
      && value !== null
      && value !== undefined
      && typeof value !== 'object'
  );

const buildUpdatedReceiptCorrections = (
  ocrResult: unknown,
  drafts: Record<number, ReceiptDraftItem[]>,
  presentationDrafts: Record<number, DocumentPresentationDraft>,
  documentType?: string
): Record<string, any> => {
  const displayData = normalizeOcrDataForDisplay(ocrResult);
  const receipts = getAllReceiptsForDisplay(displayData);
  const updatedReceipts = receipts.map((receipt, receiptIndex) => {
    const presentationDraft = presentationDrafts[receiptIndex] || {};
    const transactionType = presentationDraft.transactionType === 'income'
      ? 'income'
      : presentationDraft.transactionType === 'expense'
        ? 'expense'
        : 'unknown';
    const draftItems = normalizeReceiptItemsForTransactionType(
      drafts[receiptIndex] || [],
      transactionType,
    );
    const mappedItems = draftItems.map((item) => ({
      name: item.description,
      description: item.description,
      quantity: item.quantity,
      price: item.unitPrice ?? null,
      unit_price: item.unitPrice ?? null,
      total: item.amount,
      total_price: item.amount,
      amount: item.amount,
      vat_rate: item.vatRate ?? undefined,
      vat_indicator: item.vatIndicator ?? undefined,
      category: item.category ?? undefined,
      is_deductible: item.is_deductible === true,
      deduction_reason: item.deduction_reason || undefined,
    }));

    return {
      ...receipt,
      document_type: presentationDraft.documentType ?? receipt.document_type ?? documentType ?? 'receipt',
      _transaction_type: presentationDraft.transactionType ?? receipt._transaction_type ?? receipt.transaction_type,
      document_transaction_direction:
        presentationDraft.documentTransactionDirection
        ?? receipt.document_transaction_direction
        ?? receipt.transaction_direction,
      commercial_document_semantics:
        presentationDraft.commercialDocumentSemantics
        ?? receipt.commercial_document_semantics,
      is_reversal:
        typeof presentationDraft.isReversal === 'boolean'
          ? presentationDraft.isReversal
          : receipt.is_reversal,
      line_items: mappedItems,
      items: mappedItems,
    };
  });

  const corrections: Record<string, any> = {};
  const primaryItems = updatedReceipts[0]?.line_items || [];
  const primaryReceipt = updatedReceipts[0] || null;

  corrections._document_type = primaryReceipt?.document_type ?? documentType ?? 'receipt';
  corrections._transaction_type = primaryReceipt?._transaction_type ?? undefined;
  corrections.document_transaction_direction = primaryReceipt?.document_transaction_direction ?? undefined;
  corrections.commercial_document_semantics = primaryReceipt?.commercial_document_semantics ?? undefined;
  corrections.is_reversal = primaryReceipt?.is_reversal ?? undefined;
  corrections.line_items = primaryItems;
  corrections.items = primaryItems;

  if (updatedReceipts.length > 1) {
    corrections.multiple_receipts = updatedReceipts;
    corrections.receipt_count = updatedReceipts.length;
    corrections._additional_receipts = updatedReceipts.slice(1);
    corrections._receipt_count = updatedReceipts.length;
  }

  if (displayData?.tax_analysis && primaryItems.length > 0) {
    corrections.tax_analysis = {
      ...displayData.tax_analysis,
      ...buildTaxAnalysisItems(drafts[0] || []),
    };
  }

  return corrections;
};

const getReceiptTotalAmount = (receipt: Record<string, any> | null | undefined): number | null => {
  if (!receipt) return null;
  return [
    receipt.amount,
    receipt.total_amount,
    receipt.total,
  ]
    .map(toFiniteNumber)
    .find((value) => value !== null)
    ?? null;
};

const getReceiptVatAmount = (receipt: Record<string, any> | null | undefined): number | null => {
  if (!receipt) return null;

  const directVat = toFiniteNumber(receipt.vat_amount);
  if (directVat !== null) return Number(directVat.toFixed(2));

  if (receipt.vat_amounts && typeof receipt.vat_amounts === 'object') {
    const vatFromMap = Object.values(receipt.vat_amounts as Record<string, unknown>)
      .map(toFiniteNumber)
      .filter((value): value is number => value !== null)
      .reduce((sum, value) => sum + value, 0);
    if (vatFromMap > 0) return Number(vatFromMap.toFixed(2));
  }

  if (Array.isArray(receipt.vat_summary)) {
    const vatFromSummary = receipt.vat_summary
      .map((row: any) => toFiniteNumber(row?.vat_amount))
      .filter((value: number | null): value is number => value !== null)
      .reduce((sum: number, value: number) => sum + value, 0);
    if (vatFromSummary > 0) return Number(vatFromSummary.toFixed(2));
  }

  return null;
};

const buildTransactionLineItems = (
  items: ReceiptDraftItem[],
  receiptData?: Record<string, any> | null,
) => {
  const resolveCanonicalAmountAndQuantity = (
    item: ReceiptDraftItem,
    lineTotal: number,
  ): { quantity: number; amount: number } => {
    const rawQuantity = toFiniteNumber(item.quantity);
    const integerQuantity = rawQuantity && rawQuantity > 0 && Number.isInteger(rawQuantity)
      ? Number(rawQuantity)
      : 1;

    if (integerQuantity <= 1) {
      return {
        quantity: 1,
        amount: Number(lineTotal.toFixed(2)),
      };
    }

    const explicitUnitPrice = toFiniteNumber(item.unitPrice);
    if (explicitUnitPrice !== null) {
      const roundedUnitPrice = Number(explicitUnitPrice.toFixed(2));
      const reconstructed = Number((roundedUnitPrice * integerQuantity).toFixed(2));
      if (Math.abs(reconstructed - lineTotal) <= 0.01) {
        return {
          quantity: integerQuantity,
          amount: roundedUnitPrice,
        };
      }
    }

    const derivedUnitPrice = Number((lineTotal / integerQuantity).toFixed(2));
    const reconstructed = Number((derivedUnitPrice * integerQuantity).toFixed(2));
    if (Math.abs(reconstructed - lineTotal) <= 0.01) {
      return {
        quantity: integerQuantity,
        amount: derivedUnitPrice,
      };
    }

    return {
      quantity: 1,
      amount: Number(lineTotal.toFixed(2)),
    };
  };

  const baseItems = items
    .filter((item) => item.description.trim() && item.amount > 0)
    .map((item, index) => {
      const lineTotal = Number(item.amount.toFixed(2));
      const canonical = resolveCanonicalAmountAndQuantity(item, lineTotal);

      return {
      description: item.description.trim(),
      amount: canonical.amount,
      quantity: canonical.quantity,
      lineTotal,
      category: item.category,
      is_deductible: item.is_deductible === true,
      deduction_reason: item.deduction_reason?.trim() || undefined,
      vat_rate: normalizeVatRate(item.vatRate),
      sort_order: index,
    };
    });

  if (!receiptData || baseItems.length === 0) {
    return baseItems;
  }

  const receiptTotal = getReceiptTotalAmount(receiptData);
  if (receiptTotal === null) {
    return baseItems;
  }

  const baseTotal = Number(
    baseItems.reduce((sum, item) => sum + Number(item.lineTotal || item.amount || 0), 0).toFixed(2)
  );
  const grossGap = Number((receiptTotal - baseTotal).toFixed(2));

  if (Math.abs(grossGap) <= 0.01) {
    return baseItems;
  }

  const explicitVat = getReceiptVatAmount(receiptData);
  const inferredVat = baseItems.every((item) => item.vat_rate != null)
    ? Number(
      baseItems.reduce((sum, item) => {
        const rate = Number(item.vat_rate || 0);
        return sum + (Number(item.amount || 0) * rate);
      }, 0).toFixed(2)
    )
    : null;

  const vatToAllocate = explicitVat !== null && Math.abs(explicitVat - grossGap) <= 0.02
    ? explicitVat
    : inferredVat !== null && Math.abs(inferredVat - grossGap) <= 0.02
      ? inferredVat
      : null;

  if (vatToAllocate === null || vatToAllocate <= 0 || baseTotal <= 0) {
    return baseItems;
  }

  let remainingVat = Number(vatToAllocate.toFixed(2));

  return baseItems.map((item, index) => {
    const isLastItem = index === baseItems.length - 1;
    const rawShare = isLastItem
      ? remainingVat
      : Number((((item.lineTotal || item.amount) / baseTotal) * vatToAllocate).toFixed(2));
    const allocatedVat = Number(rawShare.toFixed(2));
    remainingVat = Number((remainingVat - allocatedVat).toFixed(2));

    if (item.is_deductible) {
      return {
        ...item,
        vat_amount: allocatedVat,
        vat_recoverable_amount: allocatedVat,
      };
    }

    const grossLineTotal = Number(((item.lineTotal || item.amount) + allocatedVat).toFixed(2));
    const grossCanonical = resolveCanonicalAmountAndQuantity(
      {
        ...item,
        amount: grossLineTotal,
      },
      grossLineTotal,
    );

    return {
      ...item,
      amount: grossCanonical.amount,
      quantity: grossCanonical.quantity,
      vat_amount: allocatedVat,
      vat_recoverable_amount: 0,
    };
  }).map(({ lineTotal, ...item }) => item);
};

const DocumentsPage = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { documentId } = useParams<{ documentId: string }>();
  const [searchParams] = useSearchParams();
  const uploadPropertyId = searchParams.get('property_id');
  const uploadType = searchParams.get('type');
  const resolverEnabled = isDocumentPresentationResolverEnabled();
  const [reviewingDocument, setReviewingDocument] = useState<Document | null>(null);
  const [bescheidOcrText, setBescheidOcrText] = useState<string | null>(null);
  const [bescheidDocId, setBescheidDocId] = useState<number | null>(null);
  const [bescheidParseResult, setBescheidParseResult] = useState<any>(null);
  const [e1OcrText, setE1OcrText] = useState<string | null>(null);
  const [e1DocId, setE1DocId] = useState<number | null>(null);
  const [e1ParseResult, setE1ParseResult] = useState<any>(null);
  const [viewingDocument, setViewingDocument] = useState<Document | null>(null);
  const [linkedTransaction, setLinkedTransaction] = useState<Transaction | null>(null);
  const [linkedAsset, setLinkedAsset] = useState<Property | null>(null);
  const [viewerBlobUrl, setViewerBlobUrl] = useState<string | null>(null);
  const [confirmingAction, setConfirmingAction] = useState<string | null>(null);
  const [confirmResult, setConfirmResult] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [taxOverrides, setTaxOverrides] = useState<Record<number, boolean>>({});
  const [docIdList, setDocIdList] = useState<number[]>([]);

  // Fetch document ID list for prev/next navigation
  useEffect(() => {
    documentService.getDocuments().then((docs: any) => {
      const list = (docs.documents || docs || []).map((d: any) => d.id).sort((a: number, b: number) => b - a);
      setDocIdList(list);
    }).catch(() => {});
  }, [refreshKey]);

  const navigateToDocument = (direction: 'prev' | 'next') => {
    if (!documentId || docIdList.length === 0) return;
    const currentId = parseInt(documentId);
    const idx = docIdList.indexOf(currentId);
    if (idx === -1) return;
    const targetIdx = direction === 'next' ? idx + 1 : idx - 1;
    if (targetIdx >= 0 && targetIdx < docIdList.length) {
      navigate(`/documents/${docIdList[targetIdx]}`, { replace: true });
    }
  };

  const hasPrevDoc = (() => {
    if (!documentId || docIdList.length === 0) return false;
    const idx = docIdList.indexOf(parseInt(documentId));
    return idx > 0;
  })();

  const hasNextDoc = (() => {
    if (!documentId || docIdList.length === 0) return false;
    const idx = docIdList.indexOf(parseInt(documentId));
    return idx >= 0 && idx < docIdList.length - 1;
  })();

  const [receiptItemDrafts, setReceiptItemDrafts] = useState<Record<number, ReceiptDraftItem[]>>({});
  const [receiptPresentationDrafts, setReceiptPresentationDrafts] = useState<Record<number, DocumentPresentationDraft>>({});
  const [editingReceiptIndex, setEditingReceiptIndex] = useState<number | null>(null);
  const [savingReceiptIndex, setSavingReceiptIndex] = useState<number | null>(null);
  const [receiptItemSaveResult, setReceiptItemSaveResult] = useState<{
    type: 'success' | 'error';
    message: string;
    receiptIndex: number;
  } | null>(null);

  // Inline OCR scalar field editing
  const [editingOcrField, setEditingOcrField] = useState<string | null>(null);
  const [editingOcrValue, setEditingOcrValue] = useState<string>('');
  const [savingOcrField, setSavingOcrField] = useState<string | null>(null);
  const [ocrFieldError, setOcrFieldError] = useState<string | null>(null);

  const clearDocumentPanels = useCallback(() => {
    setReviewingDocument(null);
    setViewingDocument(null);
    setBescheidOcrText(null);
    setBescheidDocId(null);
    setBescheidParseResult(null);
    setE1OcrText(null);
    setE1DocId(null);
    setE1ParseResult(null);
  }, []);

  const routeDocumentWithPresentation = useCallback((doc: Document) => {
    const decision = resolveDocumentPresentation(doc);
    const rawText = doc.raw_text || (typeof doc.ocr_result === 'string' ? doc.ocr_result : '');

    if (decision.template === 'tax_import') {
      clearDocumentPanels();
      if ((doc.document_type as string) === 'einkommensteuerbescheid' && rawText) {
        setBescheidOcrText(rawText);
        setBescheidDocId(doc.id);
        return;
      }
      if ((doc.document_type as string) === 'e1_form' && rawText) {
        setE1OcrText(rawText);
        setE1DocId(doc.id);
        return;
      }
      setReviewingDocument(doc);
      return;
    }

    clearDocumentPanels();
    if (decision.template === 'receipt_workbench') {
      setViewingDocument(doc);
      return;
    }

    setReviewingDocument(doc);
  }, [clearDocumentPanels]);

  const handleOcrFieldClick = (scopeKey: string, val: unknown) => {
    setOcrFieldError(null);
    setEditingOcrField(scopeKey);
    setEditingOcrValue(val != null ? String(val) : '');
  };

  const handleOcrFieldSave = async (scopeKey: string) => {
    if (!viewingDocument) return;
    // If value unchanged, just close editor
    const receiptMatch = scopeKey.match(/^receipt_(\d+)_(.+)$/);
    const origData = normalizeOcrDataForDisplay(viewingDocument.ocr_result);
    const origReceipts = getAllReceiptsForDisplay(origData);
    let origVal: unknown;
    if (receiptMatch) {
      const rIdx = parseInt(receiptMatch[1], 10);
      origVal = origReceipts[rIdx]?.[receiptMatch[2]];
    } else {
      origVal = origData?.[scopeKey];
    }
    if (String(origVal ?? '') === editingOcrValue) {
      setEditingOcrField(null);
      return;
    }
    setSavingOcrField(scopeKey);
    try {
      // Parse receipt-scoped key: "receipt_<idx>_<field>" or plain "<field>"
      if (receiptMatch) {
        const receiptIdx = parseInt(receiptMatch[1], 10);
        const fieldKey = receiptMatch[2];
        const displayData = normalizeOcrDataForDisplay(viewingDocument.ocr_result);
        const receipts = getAllReceiptsForDisplay(displayData);
        if (receipts[receiptIdx]) {
          receipts[receiptIdx][fieldKey] = editingOcrValue;
        }
        // For receipt 0, also update top-level field
        const corrections: Record<string, any> = { [fieldKey]: editingOcrValue };
        if (receipts.length > 1) {
          corrections.multiple_receipts = receipts;
          corrections._additional_receipts = receipts.slice(1);
        }
        await documentService.correctOCR(viewingDocument.id, corrections);
      } else {
        await documentService.correctOCR(viewingDocument.id, { [scopeKey]: editingOcrValue });
      }
      const updated = await documentService.getDocument(viewingDocument.id);
      setViewingDocument(updated);
    } catch (err) {
      console.error('OCR field save failed:', scopeKey, err);
      setOcrFieldError(t('documents.ocr.saveFailed', 'Save failed. Please try again.'));
    } finally {
      setSavingOcrField(null);
      setEditingOcrField(null);
    }
  };

  const formatOcrFieldValue = (key: string, val: unknown): string => {
    if (val === null || val === undefined) return EMPTY_DISPLAY_VALUE;
    if (typeof val === 'boolean') return val ? t('common.yes', 'Yes') : t('common.no', 'No');

    const s = String(val);

    // Translate enum values for known fields
    const enumTranslations: Record<string, Record<string, string>> = {
      document_transaction_direction: {
        income: t('documents.review.direction.income', 'Income'),
        expense: t('documents.review.direction.expense', 'Expense'),
        unknown: t('documents.review.direction.unknown', 'Unknown'),
      },
      document_transaction_direction_source: {
        manual: t('documents.review.directionSource.manual', 'Manual'),
        partyMatch: t('documents.review.directionSource.partyMatch', 'Party match'),
        merchant: t('documents.review.directionSource.merchant', 'Merchant'),
        statement: t('documents.review.directionSource.statement', 'Statement'),
        unknown: t('documents.review.direction.unknown', 'Unknown'),
      },
      commercial_document_semantics: {
        receipt: t('documents.review.semantics.receipt', 'Receipt'),
        standard_invoice: t('documents.review.semantics.standard_invoice', 'Standard invoice'),
        credit_note: t('documents.review.semantics.credit_note', 'Credit note'),
        proforma: t('documents.review.semantics.proforma', 'Proforma'),
        delivery_note: t('documents.review.semantics.delivery_note', 'Delivery note'),
        unknown: t('documents.review.direction.unknown', 'Unknown'),
      },
      user_contract_role: {
        landlord: t('documents.review.contractRole.landlord', 'Landlord'),
        tenant: t('documents.review.contractRole.tenant', 'Tenant'),
        buyer: t('documents.review.contractRole.buyer', 'Buyer'),
        seller: t('documents.review.contractRole.seller', 'Seller'),
        unknown: t('documents.review.direction.unknown', 'Unknown'),
      },
    };

    if (enumTranslations[key] && enumTranslations[key][s]) {
      return enumTranslations[key][s];
    }

    if (key.includes('date') && s.match(/^\d{4}-\d{2}-\d{2}/)) {
      try {
        return new Date(s).toLocaleDateString(getLocaleForLanguage(i18n.language));
      } catch {
        return s;
      }
    }

    if (
      [
        'amount',
        'vat_amount',
        'purchase_price',
        'building_value',
        'land_value',
        'grunderwerbsteuer',
        'notary_fees',
        'registry_fees',
        'monthly_rent',
        'betriebskosten',
        'heating_costs',
        'deposit_amount',
        'gross_income',
        'net_income',
        'withheld_tax',
        'social_insurance',
      ].includes(key) &&
      !isNaN(Number(val))
    ) {
      return formatCurrencyDisplay(val);
    }

    return s;
  };

  const formatReceiptItemName = (description: string | undefined, itemIndex: number): string => {
    const normalized = String(description || '').trim();
    return normalized || `Item ${itemIndex + 1}`;
  };

  const formatCategoryLabel = (category?: string | null): string => {
    return formatTransactionCategoryLabel(category, t);
  };

  const formatReceiptItemMeta = (item: ReceiptDraftItem): string => {
    const parts = [`${t('documents.ocr.quantity', 'Quantity')} ${item.quantity ?? 1}`];
    const categoryLabel = formatCategoryLabel(item.category);
    if (categoryLabel) {
      parts.push(categoryLabel);
    }
    return parts.join(' | ');
  };

  const getReceiptCategoryOptions = (transactionType: 'expense' | 'income' | 'unknown') => {
    if (transactionType === 'income') {
      return Object.values(IncomeCategory).map((category) => ({
        value: category,
        label: formatCategoryLabel(category),
      }));
    }

    return Object.values(ExpenseCategory).map((category) => ({
      value: category,
      label: formatCategoryLabel(category),
    }));
  };

  const getUniformReceiptCategory = (items: ReceiptDraftItem[]): string => {
    const uniqueCategories = Array.from(new Set(
      items
        .map((item) => String(item.category || '').trim())
        .filter(Boolean)
    ));
    return uniqueCategories.length === 1 ? uniqueCategories[0] : '';
  };

  const getPrimaryReceiptCategory = (
    items: ReceiptDraftItem[],
    transactionType: 'expense' | 'income' | 'unknown',
  ): string => {
    const uniformCategory = getUniformReceiptCategory(items);
    if (isValidReceiptCategoryForTransactionType(uniformCategory, transactionType)) {
      return uniformCategory;
    }

    const firstValid = items
      .map((item) => String(item.category || '').trim())
      .find((category) => isValidReceiptCategoryForTransactionType(category, transactionType));

    return firstValid || '';
  };

  const applyCategoryToReceiptItems = (
    items: ReceiptDraftItem[],
    category: string | undefined,
  ): ReceiptDraftItem[] => items.map((item) => ({
    ...item,
    category: category || undefined,
  }));

  const findMatchingTransaction = (
    item: ReceiptDraftItem,
    linkedTransactions: Array<{ transaction_id: number; description: string; amount: number; date: string | null; has_line_items?: boolean }> | undefined,
    itemIndex: number
  ): { transaction_id: number } | null => {
    if (!linkedTransactions || linkedTransactions.length === 0) return null;

    // Try exact match by description and amount
    const match = linkedTransactions.find(
      (txn) => txn.description === item.description && Math.abs(txn.amount - item.amount) < 0.01
    );
    if (match) return match;

    // If a transaction has line_items, all document items belong to it
    const withLineItems = linkedTransactions.find((txn) => txn.has_line_items);
    if (withLineItems) return withLineItems;

    // Fallback: match by index if within range
    if (itemIndex < linkedTransactions.length) return linkedTransactions[itemIndex];

    return null;
  };

  const findMatchingReceiptTransaction = (
    receiptIndex: number,
    receiptItems: ReceiptDraftItem[],
    linkedTransactions: Array<{ transaction_id: number; description: string; amount: number; date: string | null; has_line_items?: boolean }> | undefined,
  ): { transaction_id: number } | null => {
    if (!linkedTransactions || linkedTransactions.length === 0 || receiptItems.length === 0) {
      return null;
    }

    const receiptTotal = receiptItems.reduce((sum, item) => sum + Number(item.amount || 0), 0);
    const exactReceiptMatch = linkedTransactions.find((txn) => Math.abs(Number(txn.amount || 0) - receiptTotal) < 0.01);
    if (exactReceiptMatch) {
      return exactReceiptMatch;
    }

    for (let itemIndex = 0; itemIndex < receiptItems.length; itemIndex += 1) {
      const match = findMatchingTransaction(receiptItems[itemIndex], linkedTransactions, itemIndex);
      if (match) {
        return match;
      }
    }

    if (receiptIndex < linkedTransactions.length) {
      return linkedTransactions[receiptIndex];
    }

    return null;
  };

  const syncReceiptReviewToLinkedTransaction = async (
    receiptIndex: number,
    items: ReceiptDraftItem[],
    transactionType: 'expense' | 'income' | 'unknown',
  ) => {
    const displayData = normalizeReceiptData(parseOcrData(viewingDocument?.ocr_result));
    const receiptSections = getAllReceiptsForDisplay(displayData);
    const receiptData = receiptSections[receiptIndex] ?? null;
    const linkedTransactions = (viewingDocument as any)?.linked_transactions as
      Array<{ transaction_id: number; description: string; amount: number; date: string | null; has_line_items?: boolean }>
      | undefined;

    if (!linkedTransactions?.length || items.length === 0) return false;

    const matchedTransactionSummary = receiptIndex === 0 && linkedTransaction
      ? { transaction_id: linkedTransaction.id }
      : findMatchingReceiptTransaction(receiptIndex, items, linkedTransactions);

    if (!matchedTransactionSummary?.transaction_id) return false;

    const targetTransaction = receiptIndex === 0 && linkedTransaction?.id === matchedTransactionSummary.transaction_id
      ? linkedTransaction
      : await transactionService.getById(matchedTransactionSummary.transaction_id);

    const normalizedItems = normalizeReceiptItemsForTransactionType(items, transactionType);
    const syncedCategory = getPrimaryReceiptCategory(normalizedItems, transactionType);

    if (transactionType === 'income' && !syncedCategory) {
      throw new Error(
        t(
          'documents.receiptReview.selectIncomeCategory',
          'Choose an income category before saving this income document.'
        )
      );
    }

    const transactionUpdatePayload: Record<string, any> = {
      line_items: buildTransactionLineItems(normalizedItems, receiptData),
      reviewed: true,
      locked: true,
      suppress_rule_learning: true,
    };
    const receiptVatAmount = getReceiptVatAmount(receiptData);
    if (receiptVatAmount !== null) {
      transactionUpdatePayload.vat_amount = receiptVatAmount;
    }

    if (transactionType === 'expense') {
      transactionUpdatePayload.type = 'expense';
      if (syncedCategory) {
        transactionUpdatePayload.category = syncedCategory;
      }
      transactionUpdatePayload.is_deductible = normalizedItems.some((item) => item.is_deductible === true);
      transactionUpdatePayload.deduction_reason = normalizedItems.some((item) => item.is_deductible === true)
        && normalizedItems.some((item) => item.is_deductible === false)
        ? 'Mixed deductibility confirmed at line-item level'
        : undefined;
    } else if (transactionType === 'income') {
      transactionUpdatePayload.type = 'income';
      if (syncedCategory) {
        transactionUpdatePayload.category = syncedCategory;
      }
      transactionUpdatePayload.is_deductible = false;
      transactionUpdatePayload.deduction_reason = undefined;
    }

    await transactionService.update(targetTransaction.id, transactionUpdatePayload);
    return true;
  };

  const renderOcrFieldValue = (key: string, val: unknown, scopeKey?: string) => {
    const editKey = scopeKey || key;
    if (editingOcrField === editKey) {
      return (
        <input
          className="ocr-field-inline-input"
          autoFocus
          value={editingOcrValue}
          disabled={savingOcrField === editKey}
          onChange={(e) => setEditingOcrValue(e.target.value)}
          onBlur={() => handleOcrFieldSave(editKey)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleOcrFieldSave(editKey);
            if (e.key === 'Escape') setEditingOcrField(null);
          }}
        />
      );
    }
    return (
      <span
        className="ocr-field-value ocr-field-editable"
        onClick={() => handleOcrFieldClick(editKey, val)}
        title={t('documents.ocr.clickToEdit', 'Click to edit')}
      >
        {formatOcrFieldValue(key, val)}
        {savingOcrField === editKey && <span className="ocr-field-saving">...</span>}
        {ocrFieldError && !editingOcrField && <span className="ocr-field-error">{ocrFieldError}</span>}
        <span className="ocr-field-edit-icon">{t('common.edit', 'Edit')}</span>
      </span>
    );
  };

  // When navigated with a documentId param, load and show that document
  // When navigated back to /documents (no param), clear the detail view
  useEffect(() => {
    if (!documentId) {
      setViewingDocument(null);
      setReviewingDocument(null);
      setBescheidOcrText('');
      setE1OcrText('');
      return;
    }
    if (documentId) {
      const id = parseInt(documentId);
      if (!isNaN(id)) {
        documentService.getDocument(id).then((doc) => {
          if (resolverEnabled) {
            routeDocumentWithPresentation(doc);
            return;
          }

          const docType = doc.document_type as string;
          if (docType === 'einkommensteuerbescheid') {
            const rawText = doc.raw_text || (typeof doc.ocr_result === 'string' ? doc.ocr_result : '');
            if (rawText) {
              setBescheidOcrText(rawText);
              setBescheidDocId(id);
              return;
            }
          }
          if (docType === 'e1_form') {
            const rawText = doc.raw_text || (typeof doc.ocr_result === 'string' ? doc.ocr_result : '');
            if (rawText) {
              setE1OcrText(rawText);
              setE1DocId(id);
              return;
            }
          }
          if (doc.needs_review) {
            setReviewingDocument(doc);
          } else {
            setViewingDocument(doc);
          }
        }).catch((err) => {
          console.error('Failed to load document:', err);
        });
      }
    }
  }, [documentId, resolverEnabled, routeDocumentWithPresentation]);

  // Load document blob for preview
  useEffect(() => {
    if (!viewingDocument) {
      if (viewerBlobUrl) { URL.revokeObjectURL(viewerBlobUrl); setViewerBlobUrl(null); }
      return;
    }
    let url: string | null = null;
    documentService.downloadDocument(viewingDocument.id).then((blob) => {
      url = URL.createObjectURL(blob);
      setViewerBlobUrl(url);
    }).catch(() => {});
    return () => { if (url) URL.revokeObjectURL(url); };
    // viewerBlobUrl is intentionally excluded to avoid re-fetching the same blob
    // after storing the generated object URL in local state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewingDocument]);

  useEffect(() => {
    if (!viewingDocument?.transaction_id) {
      setLinkedTransaction(null);
      return;
    }

    let active = true;
    transactionService.getById(viewingDocument.transaction_id)
      .then((transaction) => {
        if (active) {
          setLinkedTransaction(transaction);
        }
      })
      .catch((error) => {
        console.error('Failed to load linked transaction:', error);
        if (active) {
          setLinkedTransaction(null);
        }
      });

    return () => {
      active = false;
    };
  }, [viewingDocument?.id, viewingDocument?.transaction_id]);

  useEffect(() => {
    const assetOutcome = getAssetOutcome(viewingDocument?.ocr_result);
    const linkedAssetId =
      assetOutcome && ['confirmed', 'auto_created'].includes(String(assetOutcome.status))
        ? assetOutcome.asset_id
        : null;

    if (!linkedAssetId) {
      setLinkedAsset(null);
      return;
    }

    let active = true;
    propertyService.getProperty(String(linkedAssetId))
      .then((asset) => {
        if (active) {
          setLinkedAsset(asset);
        }
      })
      .catch((error) => {
        console.error('Failed to load linked asset:', error);
        if (active) {
          setLinkedAsset(null);
        }
      });

    return () => {
      active = false;
    };
  }, [viewingDocument?.id, viewingDocument?.ocr_result]);

  useEffect(() => {
    if (!viewingDocument) {
      setReceiptItemDrafts({});
      setReceiptPresentationDrafts({});
      setEditingReceiptIndex(null);
      return;
    }

    const data = normalizeOcrDataForDisplay(viewingDocument.ocr_result);
    setReceiptItemDrafts(buildReceiptDrafts(data, linkedTransaction));
    setReceiptPresentationDrafts(
      buildReceiptPresentationDrafts(viewingDocument.document_type as string, data)
    );
    setEditingReceiptIndex(null);
    // Keep dependencies scoped to the receipt payload so unrelated object identity
    // changes do not reset local editing state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewingDocument?.id, viewingDocument?.ocr_result, linkedTransaction]);

  const handleDocumentSelect = async (document: Document) => {
    if (resolverEnabled) {
      try {
        const detail = await documentService.getDocument(document.id);
        routeDocumentWithPresentation(detail);
        navigate(`/documents/${document.id}`, { replace: true });
      } catch (err) {
        console.error('Failed to load document detail for presentation routing:', err);
      }
      return;
    }

    const docType = document.document_type as string;
    if (docType === 'einkommensteuerbescheid') {
      try {
        const detail = await documentService.getDocument(document.id);
        const rawText = detail.raw_text || (typeof detail.ocr_result === 'string' ? detail.ocr_result : '');
        if (rawText) {
          setBescheidOcrText(rawText);
          setBescheidDocId(document.id);
          return;
        }
      } catch (err) {
        console.error('Failed to load Bescheid document:', err);
      }
    }
    if (docType === 'e1_form') {
      try {
        const detail = await documentService.getDocument(document.id);
        const rawText = detail.raw_text || (typeof detail.ocr_result === 'string' ? detail.ocr_result : '');
        if (rawText) {
          setE1OcrText(rawText);
          setE1DocId(document.id);
          return;
        }
      } catch (err) {
        console.error('Failed to load E1 document:', err);
      }
    }
    if (document.needs_review) {
      setReviewingDocument(document);
    } else {
      setViewingDocument(document);
      navigate(`/documents/${document.id}`, { replace: true });
    }
  };

  const handleReviewComplete = () => {
    setReviewingDocument(null);
    navigate('/documents', { replace: true });
    setRefreshKey((k) => k + 1);
  };

  const handleReviewCancel = () => {
    setReviewingDocument(null);
    navigate('/documents', { replace: true });
  };

  const handleCloseViewer = () => {
    setViewingDocument(null);
    setLinkedTransaction(null);
    setLinkedAsset(null);
    setConfirmResult(null);
    setTaxOverrides({});
    setReceiptItemSaveResult(null);
    setReceiptItemDrafts({});
    setReceiptPresentationDrafts({});
    setEditingReceiptIndex(null);
    setSavingReceiptIndex(null);
    setEditingOcrField(null);
    navigate('/documents', { replace: true });
  };

  const handleConfirmProperty = useCallback(async () => {
    if (!viewingDocument) return;
    setConfirmingAction('property');
    setConfirmResult(null);
    try {
      await documentService.confirmProperty(viewingDocument.id);
      setConfirmResult({ type: 'success', message: t('documents.suggestion.propertyCreated') });
      aiToast(t('documents.suggestion.propertyCreated'), 'success');
      useRefreshStore.getState().refreshProperties();
      useRefreshStore.getState().refreshDashboard();
      const updated = await documentService.getDocument(viewingDocument.id);
      setViewingDocument(updated);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Error';
      setConfirmResult({ type: 'error', message: detail });
    } finally {
      setConfirmingAction(null);
    }
  }, [viewingDocument, t]);

  const handleConfirmRecurring = useCallback(async () => {
    if (!viewingDocument) return;
    setConfirmingAction('recurring');
    setConfirmResult(null);
    try {
      await documentService.confirmRecurring(viewingDocument.id);
      setConfirmResult({ type: 'success', message: t('documents.suggestion.recurringCreated') });
      aiToast(t('documents.suggestion.recurringCreated'), 'success');
      useRefreshStore.getState().refreshRecurring();
      useRefreshStore.getState().refreshDashboard();
      const updated = await documentService.getDocument(viewingDocument.id);
      setViewingDocument(updated);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Error';
      setConfirmResult({ type: 'error', message: detail });
    } finally {
      setConfirmingAction(null);
    }
  }, [viewingDocument, t]);

  const handleConfirmRecurringExpense = useCallback(async () => {
    if (!viewingDocument) return;
    setConfirmingAction('recurring_expense');
    setConfirmResult(null);
    try {
      await documentService.confirmRecurringExpense(viewingDocument.id);
      setConfirmResult({ type: 'success', message: t('documents.suggestion.recurringExpenseCreated') });
      aiToast(t('documents.suggestion.recurringExpenseCreated'), 'success');
      useRefreshStore.getState().refreshRecurring();
      useRefreshStore.getState().refreshTransactions();
      useRefreshStore.getState().refreshDashboard();
      const updated = await documentService.getDocument(viewingDocument.id);
      setViewingDocument(updated);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Error';
      setConfirmResult({ type: 'error', message: detail });
    } finally {
      setConfirmingAction(null);
    }
  }, [viewingDocument, t]);

  const handleConfirmAsset = useCallback(async (confirmation?: AssetSuggestionConfirmationPayload) => {
    if (!viewingDocument) return;
    setConfirmingAction('asset');
    setConfirmResult(null);
    try {
      const result = await documentService.confirmAsset(viewingDocument.id, confirmation);
      setConfirmResult({ type: 'success', message: t('documents.suggestion.assetCreated') });
      aiToast(t('documents.suggestion.assetCreated'), 'success');
      useRefreshStore.getState().refreshProperties();
      useRefreshStore.getState().refreshDashboard();
      const updated = await documentService.getDocument(viewingDocument.id);
      setViewingDocument(updated);

      const assetId = result?.asset_id || getAssetOutcome(updated.ocr_result)?.asset_id;
      if (assetId) {
        navigate(`/properties/${assetId}`);
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Error';
      setConfirmResult({ type: 'error', message: detail });
    } finally {
      setConfirmingAction(null);
    }
  }, [navigate, viewingDocument, t]);

  const handleConfirmLoan = useCallback(async () => {
    if (!viewingDocument) return;
    setConfirmingAction('loan');
    setConfirmResult(null);
    try {
      await documentService.confirmLoan(viewingDocument.id);
      setConfirmResult({ type: 'success', message: t('documents.suggestion.loanCreated') });
      aiToast(t('documents.suggestion.loanCreated'), 'success');
      useRefreshStore.getState().refreshRecurring();
      useRefreshStore.getState().refreshDashboard();
      const updated = await documentService.getDocument(viewingDocument.id);
      setViewingDocument(updated);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Error';
      setConfirmResult({ type: 'error', message: detail });
    } finally {
      setConfirmingAction(null);
    }
  }, [viewingDocument, t]);

  const handleConfirmLoanRepayment = useCallback(async () => {
    if (!viewingDocument) return;
    setConfirmingAction('loan_repayment');
    setConfirmResult(null);
    try {
      const result = await documentService.confirmLoanRepayment(viewingDocument.id);
      const promotedToPropertyLoan = Boolean(result?.recurring_id);
      const successMessage = promotedToPropertyLoan
        ? t(
            'documents.suggestion.loanRepaymentPromoted',
            'Loan linked to a property. We created the deductible interest schedule.'
          )
        : t(
            'documents.suggestion.loanContractAcknowledged',
            'Loan contract saved without creating expense entries because no property is linked yet.'
          );
      setConfirmResult({
        type: 'success',
        message: successMessage,
      });
      aiToast(successMessage, 'success');
      if (promotedToPropertyLoan) {
        useRefreshStore.getState().refreshRecurring();
        useRefreshStore.getState().refreshTransactions();
      }
      useRefreshStore.getState().refreshDashboard();
      const updated = await documentService.getDocument(viewingDocument.id);
      setViewingDocument(updated);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Error';
      setConfirmResult({ type: 'error', message: detail });
    } finally {
      setConfirmingAction(null);
    }
  }, [viewingDocument, t]);

  const handleDismissSuggestion = useCallback(async () => {
    if (!viewingDocument) return;
    setConfirmingAction('dismiss');
    try {
      await documentService.dismissSuggestion(viewingDocument.id);
      const updated = await documentService.getDocument(viewingDocument.id);
      setViewingDocument(updated);
      setConfirmResult(null);
    } catch (err: any) {
      console.error('Failed to dismiss suggestion:', err);
      aiToast(t('common.error', 'Operation failed'), 'error');
    } finally {
      setConfirmingAction(null);
    }
  }, [viewingDocument, t]);

  const handleConfirmTaxData = useCallback(async () => {
    if (!viewingDocument) return;
    setConfirmingAction('tax_data');
    setConfirmResult(null);
    try {
      await documentService.confirmTaxData(viewingDocument.id);
      setConfirmResult({ type: 'success', message: t('documents.suggestion.taxDataConfirmed') });
      aiToast(t('documents.suggestion.taxDataConfirmed'), 'success');
      useRefreshStore.getState().refreshDashboard();
      const updated = await documentService.getDocument(viewingDocument.id);
      setViewingDocument(updated);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Error';
      setConfirmResult({ type: 'error', message: detail });
    } finally {
      setConfirmingAction(null);
    }
  }, [viewingDocument, t]);

  const handleConfirmBankTransactions = useCallback(async (indices: number[]) => {
    if (!viewingDocument) return;
    setConfirmingAction('bank_import');
    setConfirmResult(null);
    try {
      await documentService.confirmBankTransactions(viewingDocument.id, indices);
      setConfirmResult({ type: 'success', message: t('documents.suggestion.taxDataConfirmed') });
      aiToast(t('documents.suggestion.taxDataConfirmed'), 'success');
      useRefreshStore.getState().refreshTransactions();
      useRefreshStore.getState().refreshDashboard();
      const updated = await documentService.getDocument(viewingDocument.id);
      setViewingDocument(updated);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Error';
      setConfirmResult({ type: 'error', message: detail });
    } finally {
      setConfirmingAction(null);
    }
  }, [viewingDocument, t]);

  const handleDownloadDocument = async () => {
    if (!viewingDocument) return;
    try {
      const blob = await documentService.downloadDocument(viewingDocument.id);
      await saveBlobWithNativeShare(blob, viewingDocument.file_name, t('documents.download'));
    } catch (error) {
      console.error('Failed to download:', error);
      aiToast(t('documents.downloadFailed', 'Download failed'), 'error');
    }
  };

  const [retryingOcr, setRetryingOcr] = useState(false);
  const waitForRetryCompletion = useCallback(async (documentId: number) => {
    let latest: Document | null = null;
    const MAX_ATTEMPTS = 40;

    for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt += 1) {
      const updated = await documentService.getDocument(documentId);
      latest = updated;
      setViewingDocument((current) => (current?.id === documentId ? updated : current));

      const currentState = getPipelineCurrentState(updated.ocr_result, updated.processed_at);
      if (!currentState || !ACTIVE_REPROCESS_STATES.has(currentState)) {
        return updated;
      }

      await new Promise((resolve) => window.setTimeout(resolve, 1500));
    }

    // Polling timed out — OCR likely failed silently on the backend
    aiToast(t('documents.reprocessTimeout', 'Reprocessing is taking too long. Please try again later.'), 'warning');
    return latest;
  }, [t]);

  const retryDocumentById = useCallback(async (documentId: number) => {
    setRetryingOcr(true);
    try {
      await documentService.retryOcr(documentId);
      aiToast(t('documents.reprocessStarted'), 'success');
      return await waitForRetryCompletion(documentId);
    } catch (error) {
      console.error('Failed to retry OCR:', error);
      aiToast(t('documents.reprocessFailed'), 'error');
      throw error;
    } finally {
      setRetryingOcr(false);
    }
  }, [t, waitForRetryCompletion]);

  const handleRetryTaxImportDocument = async (documentId: number, kind: 'bescheid' | 'e1') => {
    if (retryingOcr) return;
    const refreshed = await retryDocumentById(documentId);
    if (!refreshed) {
      return;
    }
    const currentState = getPipelineCurrentState(refreshed.ocr_result, refreshed.processed_at);
    if (currentState && ACTIVE_REPROCESS_STATES.has(currentState)) {
      aiToast('Claude is still reprocessing this document. Reopen it after completion to see the latest result.', 'info');
      return;
    }

    if (kind === 'bescheid') {
      setBescheidDocId(documentId);
      setBescheidOcrText(refreshed.raw_text || '');
      setBescheidParseResult(null);
      return;
    }

    setE1DocId(documentId);
    setE1OcrText(refreshed.raw_text || '');
    setE1ParseResult(null);
  };

  const handleOpenLinkedTransaction = () => {
    if (!viewingDocument?.transaction_id) return;
    navigate(`/transactions?transactionId=${viewingDocument.transaction_id}`);
  };

  const handleOpenLinkedAsset = () => {
    const assetId = linkedAsset?.id || getAssetOutcome(viewingDocument?.ocr_result)?.asset_id;
    if (!assetId) return;
    navigate(`/properties/${assetId}`);
  };

  const handleReceiptItemsChange = (receiptIndex: number, nextItems: ReceiptDraftItem[]) => {
    setReceiptItemDrafts((current) => ({
      ...current,
      [receiptIndex]: nextItems,
    }));
    setReceiptItemSaveResult(null);
  };

  const handleReceiptPresentationDraftChange = (
    receiptIndex: number,
    patch: Partial<DocumentPresentationDraft>
  ) => {
    const currentDraft = receiptPresentationDrafts[receiptIndex] || {};
    const nextTransactionType = patch.transactionType ?? currentDraft.transactionType;
    const previousDirection = currentDraft.documentTransactionDirection;
    const nextDirection = patch.documentTransactionDirection
      ?? (
        patch.transactionType
        && (!previousDirection || previousDirection === 'unknown' || previousDirection === currentDraft.transactionType)
          ? patch.transactionType
          : currentDraft.documentTransactionDirection
      );

    setReceiptPresentationDrafts((current) => ({
      ...current,
      [receiptIndex]: {
        ...(current[receiptIndex] || {}),
        ...patch,
        ...(nextDirection ? { documentTransactionDirection: nextDirection } : {}),
      },
    }));

    if (nextTransactionType === 'income' || nextTransactionType === 'expense') {
      setReceiptItemDrafts((current) => ({
        ...current,
        [receiptIndex]: normalizeReceiptItemsForTransactionType(
          current[receiptIndex] || [],
          nextTransactionType,
        ),
      }));
    }

    setReceiptItemSaveResult(null);
  };

  // Quick-decide: auto-save when user toggles a pending item in view mode
  const handleQuickDecide = async (receiptIndex: number, items: ReceiptDraftItem[]) => {
    if (!viewingDocument) return;
    setSavingReceiptIndex(receiptIndex);
    let ocrSaved = false;
    try {
      const drafts = { ...receiptItemDrafts, [receiptIndex]: items };
      const corrections = buildUpdatedReceiptCorrections(
        viewingDocument.ocr_result,
        drafts,
        receiptPresentationDrafts,
        viewingDocument.document_type as string
      );
      await documentService.correctOCR(viewingDocument.id, corrections);
      ocrSaved = true;
      const reviewTransactionType = resolveControlPolicy(
        viewingDocument,
        receiptPresentationDrafts[receiptIndex]
      ).transactionType;

      await syncReceiptReviewToLinkedTransaction(receiptIndex, items, reviewTransactionType);

      const updatedDocument = await documentService.getDocument(viewingDocument.id);
      setViewingDocument(updatedDocument);
      if (updatedDocument.transaction_id) {
        const updatedTransaction = await transactionService.getById(updatedDocument.transaction_id);
        setLinkedTransaction(updatedTransaction);
      }
      useRefreshStore.getState().refreshTransactions();
      useRefreshStore.getState().refreshDashboard();
      aiToast(t('documents.taxReview.quickDecideSaved', 'Saved'), 'success');
    } catch (error: any) {
      console.error('Failed to quick-decide:', error);
      const message = buildReceiptSyncBlockedMessage(error, t, { ocrSaved });
      setReceiptItemSaveResult({
        type: 'error',
        message,
        receiptIndex,
      });
      aiToast(message, 'error');
    } finally {
      setSavingReceiptIndex(null);
    }
  };

  const resetReceiptDraft = useCallback((receiptIndex: number) => {
    const data = normalizeOcrDataForDisplay(viewingDocument?.ocr_result);
    const freshDrafts = buildReceiptDrafts(data, linkedTransaction);
    const freshPresentationDrafts = buildReceiptPresentationDrafts(
      viewingDocument?.document_type as string,
      data
    );
    setReceiptItemDrafts((current) => ({
      ...current,
      [receiptIndex]: freshDrafts[receiptIndex] || [],
    }));
    setReceiptPresentationDrafts((current) => ({
      ...current,
      [receiptIndex]: freshPresentationDrafts[receiptIndex] || {},
    }));
    setReceiptItemSaveResult(null);
  }, [viewingDocument?.document_type, viewingDocument?.ocr_result, linkedTransaction]);

  const handleSaveReceiptReview = async (receiptIndex: number) => {
    if (!viewingDocument) return;

    setSavingReceiptIndex(receiptIndex);
    setReceiptItemSaveResult(null);
    let ocrSaved = false;

    try {
      const corrections = buildUpdatedReceiptCorrections(
        viewingDocument.ocr_result,
        receiptItemDrafts,
        receiptPresentationDrafts,
        viewingDocument.document_type as string
      );
      await documentService.correctOCR(viewingDocument.id, corrections);
      ocrSaved = true;
      const reviewTransactionType = resolveControlPolicy(
        viewingDocument,
        receiptPresentationDrafts[receiptIndex]
      ).transactionType;

      const syncedTransaction = await syncReceiptReviewToLinkedTransaction(
        receiptIndex,
        receiptItemDrafts[receiptIndex] || [],
        reviewTransactionType,
      );

      const updatedDocument = await documentService.getDocument(viewingDocument.id);
      setViewingDocument(updatedDocument);

      if (updatedDocument.transaction_id) {
        const updatedTransaction = await transactionService.getById(updatedDocument.transaction_id);
        setLinkedTransaction(updatedTransaction);
      }

      useRefreshStore.getState().refreshTransactions();
      useRefreshStore.getState().refreshDashboard();

      const message = syncedTransaction
        ? 'Receipt review saved and synced to the linked transaction.'
        : 'Receipt review saved.';
      setEditingReceiptIndex(null);
      setReceiptItemSaveResult({
        type: 'success',
        message,
        receiptIndex,
      });
      aiToast(message, 'success');
    } catch (error: any) {
      console.error('Failed to save receipt review:', error);
      const message = buildReceiptSyncBlockedMessage(error, t, { ocrSaved });
      setReceiptItemSaveResult({
        type: 'error',
        message,
        receiptIndex,
      });
      aiToast(message, 'error');
    } finally {
      setSavingReceiptIndex(null);
    }
  };

  const handleBescheidComplete = () => {
    setBescheidOcrText(null);
    setBescheidDocId(null);
    setBescheidParseResult(null);
    navigate('/documents', { replace: true });
    setRefreshKey((k) => k + 1);
  };

  const handleE1Complete = () => {
    setE1OcrText(null);
    setE1DocId(null);
    setE1ParseResult(null);
    navigate('/documents', { replace: true });
    setRefreshKey((k) => k + 1);
  };

  // Bescheid / E1 import views (triggered when OCR detects these document types)
  if (bescheidOcrText) {
    return (
      <div className="documents-page">
        <BescheidImport
          ocrText={bescheidOcrText}
          documentId={bescheidDocId ?? undefined}
          initialParseResult={bescheidParseResult}
          onRetry={bescheidDocId ? () => handleRetryTaxImportDocument(bescheidDocId, 'bescheid') : undefined}
          retrying={retryingOcr}
          onImportComplete={handleBescheidComplete}
          onCancel={handleBescheidComplete}
        />
      </div>
    );
  }

  if (e1OcrText) {
    return (
      <div className="documents-page">
        <E1FormImport
          ocrText={e1OcrText}
          documentId={e1DocId ?? undefined}
          initialParseResult={e1ParseResult}
          onRetry={e1DocId ? () => handleRetryTaxImportDocument(e1DocId, 'e1') : undefined}
          retrying={retryingOcr}
          onImportComplete={handleE1Complete}
          onCancel={handleE1Complete}
        />
      </div>
    );
  }

  if (reviewingDocument) {
    if (resolverEnabled) {
      return (
        <div className="documents-page">
          <DocumentPresentationRouter
            document={reviewingDocument}
            renderReceiptWorkbench={() => (
              <OCRReview
                documentId={Number(reviewingDocument.id)}

                presentationTemplate="generic_review"
                onConfirm={handleReviewComplete}
                onCancel={handleReviewCancel}
                onPrevDocument={hasPrevDoc ? () => navigateToDocument('prev') : undefined}
                onNextDocument={hasNextDoc ? () => navigateToDocument('next') : undefined}
                hasPrevDocument={hasPrevDoc}
                hasNextDocument={hasNextDoc}
              />
            )}
            renderContractReview={() => (
              <OCRReview
                documentId={Number(reviewingDocument.id)}

                presentationTemplate="contract_review"
                onConfirm={handleReviewComplete}
                onCancel={handleReviewCancel}
                onPrevDocument={hasPrevDoc ? () => navigateToDocument('prev') : undefined}
                onNextDocument={hasNextDoc ? () => navigateToDocument('next') : undefined}
                hasPrevDocument={hasPrevDoc}
                hasNextDocument={hasNextDoc}
              />
            )}
            renderGenericReview={() => (
              <OCRReview
                documentId={Number(reviewingDocument.id)}

                presentationTemplate="generic_review"
                onConfirm={handleReviewComplete}
                onCancel={handleReviewCancel}
                onPrevDocument={hasPrevDoc ? () => navigateToDocument('prev') : undefined}
                onNextDocument={hasNextDoc ? () => navigateToDocument('next') : undefined}
                hasPrevDocument={hasPrevDoc}
                hasNextDocument={hasNextDoc}
              />
            )}
            renderTaxImport={() => (
              <OCRReview
                documentId={Number(reviewingDocument.id)}

                presentationTemplate="tax_import"
                onConfirm={handleReviewComplete}
                onCancel={handleReviewCancel}
                onPrevDocument={hasPrevDoc ? () => navigateToDocument('prev') : undefined}
                onNextDocument={hasNextDoc ? () => navigateToDocument('next') : undefined}
                hasPrevDocument={hasPrevDoc}
                hasNextDocument={hasNextDoc}
              />
            )}
          />
        </div>
      );
    }

    return (
      <div className="documents-page">
        <OCRReview
          documentId={Number(reviewingDocument.id)}
          onConfirm={handleReviewComplete}
          onCancel={handleReviewCancel}
          onPrevDocument={hasPrevDoc ? () => navigateToDocument('prev') : undefined}
          onNextDocument={hasNextDoc ? () => navigateToDocument('next') : undefined}
          hasPrevDocument={hasPrevDoc}
          hasNextDocument={hasNextDoc}
        />
      </div>
    );
  }

  if (viewingDocument) {
    const liveViewerDecision = resolverEnabled
      ? resolveDocumentPresentation(viewingDocument, receiptPresentationDrafts[0])
      : null;

    if (resolverEnabled && liveViewerDecision?.template !== 'receipt_workbench') {
      return (
        <div className="documents-page">
          <DocumentPresentationRouter
            document={viewingDocument}
            decision={liveViewerDecision ?? undefined}
            renderReceiptWorkbench={() => null}
            renderContractReview={() => (
              <OCRReview
                documentId={Number(viewingDocument.id)}

                presentationTemplate="contract_review"
                onConfirm={handleReviewComplete}
                onCancel={handleReviewCancel}
                onPrevDocument={hasPrevDoc ? () => navigateToDocument('prev') : undefined}
                onNextDocument={hasNextDoc ? () => navigateToDocument('next') : undefined}
                hasPrevDocument={hasPrevDoc}
                hasNextDocument={hasNextDoc}
              />
            )}
            renderGenericReview={() => (
              <OCRReview
                documentId={Number(viewingDocument.id)}

                presentationTemplate="generic_review"
                onConfirm={handleReviewComplete}
                onCancel={handleReviewCancel}
                onPrevDocument={hasPrevDoc ? () => navigateToDocument('prev') : undefined}
                onNextDocument={hasNextDoc ? () => navigateToDocument('next') : undefined}
                hasPrevDocument={hasPrevDoc}
                hasNextDocument={hasNextDoc}
              />
            )}
            renderTaxImport={() => (
              <OCRReview
                documentId={Number(viewingDocument.id)}

                presentationTemplate="tax_import"
                onConfirm={handleReviewComplete}
                onCancel={handleReviewCancel}
                onPrevDocument={hasPrevDoc ? () => navigateToDocument('prev') : undefined}
                onNextDocument={hasNextDoc ? () => navigateToDocument('next') : undefined}
                hasPrevDocument={hasPrevDoc}
                hasNextDocument={hasNextDoc}
              />
            )}
          />
        </div>
      );
    }

    const isImage = viewingDocument.mime_type?.startsWith('image/');
    const isPdf = viewingDocument.mime_type === 'application/pdf';
    const viewerOcrData = normalizeOcrDataForDisplay(viewingDocument.ocr_result);
    const assetOutcome = getAssetOutcome(viewingDocument.ocr_result);
    const pipelineCurrentState = getPipelineCurrentState(
      viewingDocument.ocr_result,
      viewingDocument.processed_at
    );
    const pipelineStatePresentation = getPipelineStatePresentation(t, pipelineCurrentState);
    const linkedTransactionSummary = linkedTransaction
      ? [linkedTransaction.description || null, linkedTransaction.date || null].filter(Boolean).join(' | ')
      : t('documents.linkedTransaction.hint', 'This document already created a linked transaction. You can open it directly.');
    const linkedAssetTitle = linkedAsset?.name
      || (linkedAsset?.asset_type
        ? t(`properties.assetTypes.${linkedAsset.asset_type}`, linkedAsset.asset_type)
        : t('documents.linkedAsset.title', 'Linked asset'));
    const linkedAssetSummary = linkedAsset
      ? [
          linkedAsset.supplier || null,
          linkedAsset.put_into_use_date || linkedAsset.purchase_date || null,
        ].filter(Boolean).join(' | ')
      : t('documents.linkedAsset.hint', 'This document already created an asset record. You can open it directly.');
    const linkedAssetTaxFlags = linkedAsset
      ? [
          linkedAsset.gwg_elected
            ? t('documents.linkedAsset.gwg', 'GWG one-off expense')
            : linkedAsset.depreciation_method === 'degressive'
              ? t('documents.linkedAsset.degressive', 'Declining-balance depreciation')
              : linkedAsset.depreciation_method === 'linear'
                ? t('documents.linkedAsset.linear', 'Straight-line depreciation')
                : null,
          linkedAsset.business_use_percentage != null
            ? `${t('documents.linkedAsset.businessUse', 'Business use')} ${linkedAsset.business_use_percentage}%`
            : null,
          linkedAsset.ifb_candidate
            ? t('documents.linkedAsset.ifbCandidate', 'IFB candidate')
            : null,
        ].filter(Boolean)
      : [];
    const linkedAssetValueSummary = linkedAsset
      ? [
          linkedAsset.annual_depreciation != null
            ? `${t('documents.linkedAsset.annualDepreciation', 'Annual depreciation')} ${linkedAsset.annual_depreciation.toLocaleString(getLocaleForLanguage(i18n.language), { style: 'currency', currency: 'EUR' })}`
            : null,
          linkedAsset.remaining_value != null
            ? `${t('documents.linkedAsset.remainingValue', 'Remaining value')} ${linkedAsset.remaining_value.toLocaleString(getLocaleForLanguage(i18n.language), { style: 'currency', currency: 'EUR' })}`
            : null,
        ].filter(Boolean)
      : [];

    return (
      <div className="documents-page">
        <div className="document-viewer">
          <div className="viewer-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button className="btn btn-secondary" onClick={handleCloseViewer}>
                {t('common.back')}
              </button>
              {hasPrevDoc && (
                <button className="btn btn-secondary" onClick={() => navigateToDocument('prev')} title={t('documents.prevDocument', 'Previous document')}>
                  ← {t('documents.prev', 'Prev')}
                </button>
              )}
              {hasNextDoc && (
                <button className="btn btn-secondary" onClick={() => navigateToDocument('next')} title={t('documents.nextDocument', 'Next document')}>
                  {t('documents.next', 'Next')} →
                </button>
              )}
            </div>
            <h2>{viewingDocument.file_name}</h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button className="btn btn-primary" onClick={handleDownloadDocument}>
                {t('documents.download')}
              </button>
            </div>
          </div>
          <div className="viewer-meta">
            <span>{t(`documents.types.${viewingDocument.document_type}`)}</span>
            <span>{new Date(viewingDocument.created_at).toLocaleDateString(getLocaleForLanguage(i18n.language))}</span>
            {viewingDocument.confidence_score != null && (
              <span>{t('documents.confidence')}: {(viewingDocument.confidence_score * 100).toFixed(0)}%</span>
            )}
            {(() => {
              const count = viewerOcrData?._receipt_count;
              if (count && count > 1) {
                return <span className="multi-receipt-badge">{t('documents.multiReceipt.badge', { count })}</span>;
              }
              return null;
            })()}
          </div>
          {pipelineStatePresentation && (
            <div className={`viewer-pipeline-state viewer-pipeline-state--${pipelineStatePresentation.tone}`}>
              <strong>{pipelineStatePresentation.title}</strong>
              <span>{pipelineStatePresentation.description}</span>
            </div>
          )}
          {viewingDocument.transaction_id && (
            <div className="viewer-linked-transaction">
              <div className="viewer-linked-transaction-copy">
                <strong>{t('documents.linkedTransaction.title', 'Linked transaction')}</strong>
                <span>{linkedTransactionSummary}</span>
              </div>
              <button type="button" className="btn btn-primary" onClick={handleOpenLinkedTransaction}>
                {t('documents.linkedTransaction.open', 'Open transaction')}
              </button>
            </div>
          )}
          {assetOutcome && linkedAsset && (
            <div className="viewer-linked-asset">
              <div className="viewer-linked-asset-copy">
                <strong>{t('documents.linkedAsset.title', 'Linked asset')}</strong>
                <span>{linkedAssetTitle}</span>
                <span>{linkedAssetSummary}</span>
                {linkedAssetTaxFlags.length > 0 && (
                  <div className="viewer-linked-asset-badges">
                    {linkedAssetTaxFlags.map((flag) => (
                      <span key={flag} className="viewer-linked-asset-badge">{flag}</span>
                    ))}
                  </div>
                )}
                {linkedAssetValueSummary.length > 0 && (
                  <span>{linkedAssetValueSummary.join(' | ')}</span>
                )}
              </div>
              <button type="button" className="btn btn-primary" onClick={handleOpenLinkedAsset}>
                {t('documents.linkedAsset.open', 'Open asset')}
              </button>
            </div>
          )}
          <div className="viewer-content">
            {!viewerBlobUrl ? (
              <div className="viewer-fallback"><p>{t('common.loadingPreview')}</p></div>
            ) : isImage ? (
              <img src={viewerBlobUrl} alt={viewingDocument.file_name} className="viewer-image" />
            ) : isPdf ? (
              <iframe src={viewerBlobUrl} title={viewingDocument.file_name} className="viewer-pdf" />
            ) : (
              <div className="viewer-fallback">
                <p>{t('documents.previewNotAvailable')}</p>
                <button className="btn btn-primary" onClick={handleDownloadDocument}>
                  {t('documents.download')}
                </button>
              </div>
            )}
          </div>
          <EmployerReviewPanel document={viewingDocument} />
          {viewingDocument.ocr_result && (
            <div className="viewer-ocr-result">
              <div className="ocr-result-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', gap: '12px' }}>
                <h3 style={{ margin: 0, flexShrink: 0 }}>{t('documents.ocrResult')}</h3>
              </div>
              <div className="ocr-fields-grid">
                {(() => {
                  const data = normalizeOcrDataForDisplay(viewingDocument.ocr_result);
                  if (!data || typeof data !== 'object') {
                    return <pre>{String(viewingDocument.ocr_result)}</pre>;
                  }

                  const labels: Record<string, string> = {
                    property_address: t('documents.ocr.propertyAddress'),
                    street: t('documents.ocr.street'),
                    unit_number: t('documents.ocr.unitNumber'),
                    city: t('documents.ocr.city'),
                    postal_code: t('documents.ocr.postalCode'),
                    purchase_price: t('documents.ocr.purchasePrice'),
                    purchase_date: t('documents.ocr.purchaseDate'),
                    building_value: t('documents.ocr.buildingValue'),
                    land_value: t('documents.ocr.landValue'),
                    grunderwerbsteuer: t('documents.ocr.transferTax'),
                    notary_fees: t('documents.ocr.notaryFees'),
                    registry_fees: t('documents.ocr.registryFees'),
                    buyer_name: t('documents.ocr.buyerName'),
                    seller_name: t('documents.ocr.sellerName'),
                    notary_name: t('documents.ocr.notaryName'),
                    notary_location: t('documents.ocr.notaryLocation'),
                    construction_year: t('documents.ocr.constructionYear'),
                    property_type: t('documents.ocr.propertyType'),
                    asset_name: t('documents.ocr.assetName', 'Asset name'),
                    asset_type: t('documents.ocr.assetType', 'Asset type'),
                    first_registration_date: t('documents.ocr.firstRegistrationDate', 'First registration date'),
                    vehicle_identification_number: t('documents.ocr.vehicleIdentificationNumber', 'VIN'),
                    license_plate: t('documents.ocr.licensePlate', 'License plate'),
                    mileage_km: t('documents.ocr.mileageKm', 'Mileage'),
                    is_used_asset: t('documents.ocr.isUsedAsset', 'Used asset'),
                    monthly_rent: t('documents.ocr.monthlyRent'),
                    start_date: t('documents.ocr.startDate'),
                    end_date: t('documents.ocr.endDate'),
                    betriebskosten: t('documents.ocr.operatingCosts'),
                    heating_costs: t('documents.ocr.heatingCosts'),
                    deposit_amount: t('documents.ocr.deposit'),
                    utilities_included: t('documents.ocr.utilitiesIncluded'),
                    tenant_name: t('documents.ocr.tenantName'),
                    landlord_name: t('documents.ocr.landlordName'),
                    contract_type: t('documents.ocr.contractType'),
                    gross_income: t('documents.ocr.grossIncome'),
                    net_income: t('documents.ocr.netIncome'),
                    withheld_tax: t('documents.ocr.withheldTax'),
                    social_insurance: t('documents.ocr.socialInsurance'),
                    employer: t('documents.ocr.employer'),
                    date: t('documents.ocr.date'),
                    employee_name: t('documents.ocr.employeeName'),
                    personnel_number: t('documents.ocr.personnelNumber'),
                    amount: t('documents.ocr.amount', 'Amount'),
                    merchant: t('documents.ocr.merchant', 'Merchant'),
                    supplier: t('documents.ocr.supplier', 'Supplier'),
                    description: t('documents.ocr.description', 'Description'),
                    product_summary: t('documents.ocr.productSummary', 'Product summary'),
                    vat_amount: t('documents.ocr.vatAmount'),
                    vat_rate: t('documents.ocr.vatRate'),
                    payment_method: t('documents.ocr.paymentMethod', 'Payment method'),
                    currency: t('documents.ocr.currency', 'Currency'),
                    invoice_number: t('documents.ocr.invoiceNumber', 'Invoice number'),
                    tax_id: t('documents.ocr.taxId', 'Tax ID'),
                    is_reversal: t('documents.ocr.isReversal', 'Reversal'),
                    document_transaction_direction: t('documents.review.directionLabel', 'Direction'),
                    document_transaction_direction_source: t('documents.review.directionSourceLabel', 'Direction source'),
                    document_transaction_direction_confidence: t('documents.review.directionConfidence', 'Direction confidence'),
                    commercial_document_semantics: t('documents.review.semanticsLabel', 'Semantics'),
                    user_contract_role: t('documents.review.contractRoleLabel', 'Contract role'),
                    user_contract_role_source: t('documents.review.contractRoleSourceLabel', 'Role source'),
                    _extraction_method: t('documents.ocr.extractionMethod', 'Extraction method'),
                    _llm_supplement: t('documents.ocr.llmSupplement', 'LLM supplement'),
                    loan_amount: t('documents.ocr.loanAmount', 'Loan amount'),
                    interest_rate: t('documents.ocr.interestRate', 'Interest rate'),
                    monthly_payment: t('documents.ocr.monthlyPayment', 'Monthly payment'),
                    lender_name: t('documents.ocr.lenderName', 'Lender'),
                    borrower_name: t('documents.ocr.borrowerName', 'Borrower'),
                    contract_number: t('documents.ocr.contractNumber', 'Contract number'),
                    first_rate_date: t('documents.ocr.firstRateDate', 'First payment date'),
                    term_years: t('documents.ocr.termYears', 'Term (years)'),
                    term_months: t('documents.ocr.termMonths', 'Term (months)'),
                    purpose: t('documents.ocr.loanPurpose', 'Loan purpose'),
                    annual_interest_amount: t('documents.ocr.annualInterestAmount', 'Annual interest'),
                    certificate_year: t('documents.ocr.certificateYear', 'Certificate year'),
                    insurer_name: t('documents.ocr.insurerName', 'Insurer'),
                    versicherer: t('documents.ocr.insurerName', 'Insurer'),
                    policy_holder_name: t('documents.ocr.policyHolderName', 'Policy holder'),
                    versicherungsnehmer: t('documents.ocr.policyHolderName', 'Policy holder'),
                    insurance_type: t('documents.ocr.insuranceType', 'Insurance type'),
                    versicherungsart: t('documents.ocr.insuranceType', 'Insurance type'),
                    praemie: t('documents.ocr.premium', 'Premium'),
                    premium: t('documents.ocr.premium', 'Premium'),
                    polizze: t('documents.ocr.policyNumber', 'Policy number'),
                    payment_frequency: t('documents.ocr.paymentFrequency', 'Payment frequency'),
                    zahlungsfrequenz: t('documents.ocr.paymentFrequency', 'Payment frequency'),
                  };

                  const skipKeys = ['field_confidence', 'confidence', 'import_suggestion', 'asset_outcome', 'line_items', 'items', 'vat_summary', 'tax_analysis', '_additional_receipts', '_receipt_count', '_pipeline', '_validation', 'correction_history', 'multiple_receipts', 'receipt_count', 'receipts', 'total_amount', 'purchase_contract_kind'];

                  // Define expected fields per document type so users can see & edit missing ones
                  const purchaseContractKind =
                    data.purchase_contract_kind === 'asset' ||
                    data.asset_type ||
                    data.asset_name ||
                    data.vehicle_identification_number ||
                    (getAssetOutcome(data)?.type === 'create_asset')
                      ? 'asset'
                      : 'property';
                  const purchaseContractFields =
                    purchaseContractKind === 'asset'
                      ? ['asset_name', 'asset_type', 'purchase_price', 'purchase_date', 'seller_name', 'buyer_name', 'first_registration_date', 'vehicle_identification_number', 'license_plate', 'mileage_km', 'is_used_asset']
                      : ['property_address', 'street', 'unit_number', 'city', 'postal_code', 'purchase_price', 'purchase_date', 'building_value', 'land_value', 'grunderwerbsteuer', 'notary_fees', 'registry_fees', 'buyer_name', 'seller_name', 'construction_year', 'property_type'];
                  const expectedFieldsByType: Record<string, string[]> = {
                    purchase_contract: purchaseContractFields,
                    rental_contract: ['property_address', 'street', 'unit_number', 'city', 'postal_code', 'monthly_rent', 'start_date', 'end_date', 'betriebskosten', 'heating_costs', 'deposit_amount', 'utilities_included', 'tenant_name', 'landlord_name', 'contract_type'],
                    payslip: ['gross_income', 'net_income', 'withheld_tax', 'social_insurance', 'employer', 'employee_name', 'personnel_number', 'date'],
                    lohnzettel: ['gross_income', 'net_income', 'withheld_tax', 'social_insurance', 'employer', 'employee_name', 'personnel_number', 'date'],
                    loan_contract: ['loan_amount', 'interest_rate', 'monthly_payment', 'lender_name', 'borrower_name', 'contract_number', 'start_date', 'end_date', 'term_years', 'purpose', 'property_address', 'annual_interest_amount', 'certificate_year'],
                    versicherungsbestaetigung: ['insurer_name', 'policy_holder_name', 'insurance_type', 'praemie', 'polizze', 'payment_frequency', 'start_date', 'end_date'],
                  };
                  const docType = viewingDocument.document_type as string;
                  const expectedFields = expectedFieldsByType[docType] || [];

                  // Build entries: existing data fields + missing expected fields (as null)
                  const existingEntries = Object.entries(data).filter(
                    ([k, v]) => !skipKeys.includes(k) && !k.startsWith('_') && v !== null && v !== undefined
                      && typeof v !== 'object'
                  );
                  const existingKeys = new Set(existingEntries.map(([k]) => k));
                  const missingEntries: [string, unknown][] = expectedFields
                    .filter(k => !existingKeys.has(k))
                    .map(k => [k, null]);
                  const entries = [...existingEntries, ...missingEntries];

                  const lineItems = getDisplayLineItems(data);
                  const vatSummary = Array.isArray(data.vat_summary) ? data.vat_summary : [];
                  const isReceiptDocument = RECEIPT_DOC_TYPES.has((viewingDocument.document_type as string).toLowerCase());
                  const receiptSections = isReceiptDocument ? getAllReceiptsForDisplay(data) : [];

                  const fmtEur = (v: unknown) => formatCurrencyDisplay(v);
                  const fmtPct = (v: unknown) => {
                    if (v == null || isNaN(Number(v))) return EMPTY_DISPLAY_VALUE;
                    const n = Number(v);
                    // VLM may return 10/20 (whole %) or 0.10/0.20 (decimal)
                    const pct = n >= 1 ? n : n * 100;
                    return `${pct.toFixed(0)}%`;
                  };

                  // Austrian VAT indicator to rate mapping
                  const vatIndicatorMap: Record<string, number> = { A: 10, B: 20, C: 13, D: 0 };
                  const resolveVatRate = (item: any): string => {
                    if (item.vat_rate != null && !isNaN(Number(item.vat_rate))) {
                      return fmtPct(item.vat_rate);
                    }
                    const ind = (item.vat_indicator || '').toUpperCase().trim();
                    if (ind && vatIndicatorMap[ind] !== undefined) {
                      return `${vatIndicatorMap[ind]}%`;
                    }
                    return EMPTY_DISPLAY_VALUE;
                  };

                  return (
                    <>
                      {isReceiptDocument && receiptSections.length > 0 && (
                        <div className="receipt-breakdown-list">
                          {receiptSections.map((receipt, receiptIndex) => {
                            const receiptEntries = buildReceiptScalarEntries(receipt);
                            const receiptItems = receiptItemDrafts[receiptIndex] || [];
                            const receiptPresentationDraft = receiptPresentationDrafts[receiptIndex] || {};
                            const isReceiptEditing = editingReceiptIndex === receiptIndex;
                            const receiptVatSummary = Array.isArray(receipt.vat_summary) ? receipt.vat_summary : [];
                            const receiptPresentationDocument = {
                              ...viewingDocument,
                              document_type:
                                receiptPresentationDraft.documentType
                                ?? receipt.document_type
                                ?? viewingDocument.document_type,
                              ocr_result: receipt,
                            };
                              const liveReceiptDecision = resolveDocumentPresentation(
                                receiptPresentationDocument,
                                receiptPresentationDraft
                              );
                              const receiptShouldShowExpenseControls = !liveReceiptDecision.controlPolicy.hideDeductibility;
                              const receiptCategoryOptions = getReceiptCategoryOptions(
                                liveReceiptDecision.controlPolicy.transactionType
                              );
                              const receiptCategoryValue = getUniformReceiptCategory(receiptItems);
                              const receiptCategoryLabel = receiptCategoryValue
                                ? formatCategoryLabel(receiptCategoryValue)
                                : receiptItems.some((item) => String(item.category || '').trim())
                                  ? t('documents.receiptReview.mixedCategories', 'Mixed categories')
                                  : t('documents.receiptReview.noCategory', 'No category assigned');
                              const deductibleTotal = receiptItems
                                .filter((item) => item.is_deductible === true)
                                .reduce((sum, item) => sum + item.amount, 0);
                            const nonDeductibleTotal = receiptItems
                              .filter((item) => item.is_deductible === false)
                              .reduce((sum, item) => sum + item.amount, 0);

                            return (
                              <section key={`receipt-${receiptIndex}`} className="receipt-breakdown-card">
                                <div className="receipt-breakdown-header">
                                  <div>
                                    <h4>{t('documents.receiptReview.receiptNumber', { number: receiptIndex + 1 })}</h4>
                                    <p>
                                      {[receipt.merchant, receipt.date ? formatOcrFieldValue('date', receipt.date) : null]
                                        .filter(Boolean)
                                        .join(' | ') || 'OCR-detected receipt'}
                                    </p>
                                  </div>
                                  <div className="receipt-breakdown-header-actions">
                                    <div className="receipt-breakdown-amount">{fmtEur(receipt.amount)}</div>
                                    {!isReceiptEditing && (
                                      <button
                                        type="button"
                                        className="receipt-review-edit-btn receipt-review-edit-btn--header"
                                        onClick={() => {
                                          setEditingReceiptIndex(receiptIndex);
                                          setReceiptItemSaveResult(null);
                                        }}
                                      >
                                        {t('common.edit', 'Edit')}
                                      </button>
                                    )}
                                  </div>
                                </div>

                                <div className="receipt-presentation-strip">
                                  <div className="receipt-presentation-fields">
                                    <label className="receipt-presentation-field">
                                      <span>{t('documents.ocr.documentType', 'Document type')}</span>
                                      <select
                                        value={String(
                                          receiptPresentationDraft.documentType
                                          ?? receipt.document_type
                                          ?? viewingDocument.document_type
                                          ?? 'receipt'
                                        )}
                                        disabled={!isReceiptEditing}
                                        onChange={(event) => {
                                          handleReceiptPresentationDraftChange(receiptIndex, {
                                            documentType: event.target.value,
                                          });
                                        }}
                                      >
                                        <option value="receipt">{t('documents.types.receipt', 'Receipt')}</option>
                                        <option value="invoice">{t('documents.types.invoice', 'Invoice')}</option>
                                      </select>
                                    </label>

                                    <div className="receipt-presentation-field">
                                      <span>{t('documents.review.transactionType', 'Transaction type')}</span>
                                      <div className="receipt-presentation-toggle-group">
                                        <button
                                          type="button"
                                          className={`toggle-btn ${liveReceiptDecision.controlPolicy.transactionType === 'income' ? 'active income' : ''}`}
                                          disabled={!isReceiptEditing}
                                          onClick={() => handleReceiptPresentationDraftChange(receiptIndex, {
                                            transactionType: 'income',
                                            documentTransactionDirection: 'income',
                                          })}
                                        >
                                          {t('documents.review.direction.income', 'Income')}
                                        </button>
                                        <button
                                          type="button"
                                          className={`toggle-btn ${liveReceiptDecision.controlPolicy.transactionType === 'expense' ? 'active expense' : ''}`}
                                          disabled={!isReceiptEditing}
                                          onClick={() => handleReceiptPresentationDraftChange(receiptIndex, {
                                            transactionType: 'expense',
                                            documentTransactionDirection: 'expense',
                                          })}
                                        >
                                          {t('documents.review.direction.expense', 'Expense')}
                                        </button>
                                      </div>
                                    </div>

                                    <label className="receipt-presentation-field">
                                      <span>{t('documents.review.semanticLabel', 'Semantics')}</span>
                                      <select
                                        value={String(
                                          receiptPresentationDraft.commercialDocumentSemantics
                                          ?? receipt.commercial_document_semantics
                                          ?? (String(receiptPresentationDraft.documentType ?? receipt.document_type ?? viewingDocument.document_type) === 'invoice'
                                            ? 'standard_invoice'
                                            : 'receipt')
                                        )}
                                        disabled={!isReceiptEditing}
                                        onChange={(event) => {
                                          handleReceiptPresentationDraftChange(receiptIndex, {
                                            commercialDocumentSemantics: event.target.value,
                                          });
                                        }}
                                      >
                                        <option value="receipt">{t('documents.review.semantic.receipt', 'Receipt')}</option>
                                        <option value="standard_invoice">{t('documents.review.semantic.invoice', 'Standard invoice')}</option>
                                        <option value="credit_note">{t('documents.review.semantic.creditNote', 'Credit note')}</option>
                                        <option value="proforma">{t('documents.review.semantic.proforma', 'Proforma')}</option>
                                        <option value="delivery_note">{t('documents.review.semantic.deliveryNote', 'Delivery note')}</option>
                                      </select>
                                    </label>

                                    <label className="receipt-presentation-field receipt-presentation-field--checkbox">
                                      <span>{t('documents.review.reversal', 'Reversal')}</span>
                                      <input
                                        type="checkbox"
                                        checked={Boolean(
                                          receiptPresentationDraft.isReversal
                                          ?? receipt.is_reversal
                                        )}
                                        disabled={!isReceiptEditing}
                                        onChange={(event) => {
                                          handleReceiptPresentationDraftChange(receiptIndex, {
                                            isReversal: event.target.checked,
                                          });
                                        }}
                                      />
                                    </label>
                                  </div>

                                  {(liveReceiptDecision.badges.length > 0 || liveReceiptDecision.helpers.length > 0) && (
                                    <div className="receipt-presentation-meta">
                                      {liveReceiptDecision.badges.length > 0 && (
                                        <div className="receipt-presentation-badges">
                                          {liveReceiptDecision.badges.map((badge) => (
                                            <span key={`${receiptIndex}-${badge}`} className="receipt-presentation-badge">
                                              {badge}
                                            </span>
                                          ))}
                                        </div>
                                      )}
                                      {liveReceiptDecision.helpers.length > 0 && (
                                        <div className="receipt-presentation-helpers">
                                          {liveReceiptDecision.helpers.map((helper) => (
                                            <p key={`${receiptIndex}-${helper}`} className="receipt-presentation-helper">
                                              {helper}
                                            </p>
                                          ))}
                                        </div>
                                      )}
                                    </div>
                                  )}
                                </div>

                                {receiptEntries.length > 0 && (
                                  <div className="ocr-fields-table">
                                    {receiptEntries.map(([key, val]) => (
                                      <div key={`${receiptIndex}-${key}`} className="ocr-field-row">
                                        <span className="ocr-field-label">{labels[key] || key}</span>
                                        {renderOcrFieldValue(key, val, `receipt_${receiptIndex}_${key}`)}
                                      </div>
                                    ))}
                                  </div>
                                )}

                                {receiptItems.length > 0 && (
                                  <div className="ocr-line-items">
                                    {(() => {
                                      const hasVatData = receiptItems.some((item) => item.vatRate != null || (item.vatIndicator && item.vatIndicator.trim()));
                                      return (
                                        <div className="line-items-table">
                                          <div className="line-items-header">
                                            <span className="li-col-name">{t('documents.ocr.itemName')}</span>
                                            <span className="li-col-qty">{t('documents.ocr.quantity')}</span>
                                            <span className="li-col-price">{t('documents.ocr.unitPrice')}</span>
                                            <span className="li-col-total">{t('documents.ocr.totalPrice')}</span>
                                            {hasVatData && <span className="li-col-vat">{t('documents.ocr.vatRate')}</span>}
                                            {hasVatData && <span className="li-col-ind">{t('documents.ocr.vatIndicator')}</span>}
                                          </div>
                                          {receiptItems.map((item, itemIndex) => (
                                            <div key={`receipt-item-${receiptIndex}-${itemIndex}`} className="line-items-row">
                                              <span className="li-col-name">
                                                {isReceiptEditing ? (
                                                  <input
                                                    type="text"
                                                    className="line-item-edit-input"
                                                    value={item.description || ''}
                                                    onChange={(event) => {
                                                      const nextItems = [...receiptItems];
                                                      nextItems[itemIndex] = {
                                                        ...nextItems[itemIndex],
                                                        description: event.target.value,
                                                      };
                                                      handleReceiptItemsChange(receiptIndex, nextItems);
                                                    }}
                                                  />
                                                ) : (
                                                  formatReceiptItemName(item.description, itemIndex)
                                                )}
                                              </span>
                                              <span className="li-col-qty">
                                                {isReceiptEditing ? (
                                                  <input
                                                    type="number"
                                                    min="0"
                                                    step="0.01"
                                                    className="line-item-edit-input line-item-edit-input--numeric"
                                                    value={item.quantity ?? ''}
                                                    onChange={(event) => {
                                                      const nextItems = [...receiptItems];
                                                      nextItems[itemIndex] = {
                                                        ...nextItems[itemIndex],
                                                        quantity: event.target.value,
                                                      };
                                                      handleReceiptItemsChange(receiptIndex, nextItems);
                                                    }}
                                                  />
                                                ) : (
                                                  item.quantity ?? 1
                                                )}
                                              </span>
                                              <span className="li-col-price">
                                                {isReceiptEditing ? (
                                                  <input
                                                    type="number"
                                                    min="0"
                                                    step="0.01"
                                                    className="line-item-edit-input line-item-edit-input--numeric"
                                                    value={item.unitPrice ?? ''}
                                                    onChange={(event) => {
                                                      const nextItems = [...receiptItems];
                                                      nextItems[itemIndex] = {
                                                        ...nextItems[itemIndex],
                                                        unitPrice: toFiniteNumber(event.target.value),
                                                      };
                                                      handleReceiptItemsChange(receiptIndex, nextItems);
                                                    }}
                                                  />
                                                ) : (
                                                  fmtEur(item.unitPrice)
                                                )}
                                              </span>
                                              <span className="li-col-total">
                                                {isReceiptEditing ? (
                                                  <input
                                                    type="number"
                                                    min="0"
                                                    step="0.01"
                                                    className="line-item-edit-input line-item-edit-input--numeric"
                                                    value={item.amount ?? ''}
                                                    onChange={(event) => {
                                                      const nextItems = [...receiptItems];
                                                      nextItems[itemIndex] = {
                                                        ...nextItems[itemIndex],
                                                        amount: toFiniteNumber(event.target.value) ?? 0,
                                                      };
                                                      handleReceiptItemsChange(receiptIndex, nextItems);
                                                    }}
                                                  />
                                                ) : (
                                                  fmtEur(item.amount)
                                                )}
                                              </span>
                                              {hasVatData && (
                                                <span className="li-col-vat">
                                                  {isReceiptEditing ? (
                                                    <input
                                                      type="number"
                                                      min="0"
                                                      step="0.01"
                                                      className="line-item-edit-input line-item-edit-input--numeric"
                                                      value={item.vatRate ?? ''}
                                                      onChange={(event) => {
                                                        const nextItems = [...receiptItems];
                                                        nextItems[itemIndex] = {
                                                          ...nextItems[itemIndex],
                                                          vatRate: toFiniteNumber(event.target.value),
                                                        };
                                                        handleReceiptItemsChange(receiptIndex, nextItems);
                                                      }}
                                                    />
                                                  ) : (
                                                    resolveVatRate({ vat_rate: item.vatRate, vat_indicator: item.vatIndicator })
                                                  )}
                                                </span>
                                              )}
                                              {hasVatData && (
                                                <span className="li-col-ind">
                                                  {isReceiptEditing ? (
                                                    <input
                                                      type="text"
                                                      className="line-item-edit-input line-item-edit-input--short"
                                                      value={item.vatIndicator || ''}
                                                      onChange={(event) => {
                                                        const nextItems = [...receiptItems];
                                                        nextItems[itemIndex] = {
                                                          ...nextItems[itemIndex],
                                                          vatIndicator: event.target.value,
                                                        };
                                                        handleReceiptItemsChange(receiptIndex, nextItems);
                                                      }}
                                                    />
                                                  ) : (
                                                    item.vatIndicator || EMPTY_DISPLAY_VALUE
                                                  )}
                                                </span>
                                              )}
                                            </div>
                                          ))}
                                        </div>
                                      );
                                    })()}
                                  </div>
                                )}

                                {receiptItems.length > 0 && (
                                  <div className="receipt-review-card">
                                    <div className="receipt-review-header">
                                      <div>
                                        <h5>
                                          {receiptShouldShowExpenseControls
                                            ? t('documents.taxReview.title', 'Tax review')
                                            : t('documents.receiptReview.incomeTitle', 'Income details')}
                                        </h5>
                                        <p>
                                          {receiptShouldShowExpenseControls
                                            ? (
                                                isReceiptEditing
                                                  ? t('documents.taxReview.editHint', 'The system already prepared a first pass. You can now correct line items and deductibility.')
                                                  : t('documents.taxReview.viewHint', 'The system shows its first assessment here. Edit only when the classification looks wrong.')
                                              )
                                            : (
                                                isReceiptEditing
                                                  ? t('documents.receiptReview.incomeEditingHint', 'You can correct item names, quantities, amounts, and VAT details, then save directly.')
                                                  : t('documents.receiptReview.incomeStatusHint', 'The extracted item, quantity, amount, and VAT details stay visible here without expense-only deductibility controls.')
                                              )}
                                        </p>
                                        <div className="receipt-review-category-row">
                                          <span className="receipt-review-category-label">
                                            {t('documents.ocr.category', 'Category')}
                                          </span>
                                          <Select
                                            value={receiptCategoryValue}
                                            onChange={(value) => {
                                              handleReceiptItemsChange(
                                                receiptIndex,
                                                applyCategoryToReceiptItems(receiptItems, value || undefined),
                                              );
                                            }}
                                            options={receiptCategoryOptions}
                                            placeholder={
                                              receiptItems.some((item) => String(item.category || '').trim())
                                                ? t('documents.receiptReview.mixedCategories', 'Mixed categories')
                                                : t('documents.receiptReview.noCategory', 'No category assigned')
                                            }
                                            size="sm"
                                            disabled={!isReceiptEditing}
                                            aria-label={`receipt-category-${receiptIndex}`}
                                          />
                                          {!isReceiptEditing && (
                                            <span className="receipt-review-category-value">
                                              {receiptCategoryLabel}
                                            </span>
                                          )}
                                        </div>
                                        <p className="receipt-review-category-hint">
                                          {isReceiptEditing
                                            ? t(
                                              'documents.receiptReview.categoryEditHint',
                                              'Use the selector above to apply one category to the whole receipt, or adjust each line item below.'
                                            )
                                            : t(
                                              'documents.receiptReview.categoryReadonlyHint',
                                              'Click Edit to unlock category and deductibility changes for this receipt.'
                                            )}
                                        </p>
                                      </div>
                                      <div className="receipt-review-header-side">
                                        <DocumentActionGate
                                          action="deductibility_controls"
                                          policy={liveReceiptDecision.controlPolicy}
                                          helpers={liveReceiptDecision.helpers}
                                        >
                                          {({ hidden }) => !hidden ? (
                                            <div className="receipt-review-summary">
                                              <span className="deductible">{`${t('documents.ocr.deductible', 'Deductible')} ${fmtEur(deductibleTotal)}`}</span>
                                              <span className="non-deductible">{`${t('documents.ocr.notDeductible', 'Non-deductible')} ${fmtEur(nonDeductibleTotal)}`}</span>
                                            </div>
                                          ) : null}
                                        </DocumentActionGate>
                                        <DocumentActionGate
                                          action="bulk_expense_quick_actions"
                                          policy={liveReceiptDecision.controlPolicy}
                                          helpers={liveReceiptDecision.helpers}
                                        >
                                          {({ hidden }) => !hidden ? (
                                            <div className="receipt-review-batch-actions">
                                              <button
                                              type="button"
                                              className="receipt-review-batch-btn deductible"
                                              disabled={savingReceiptIndex !== null}
                                                onClick={() => {
                                                  const nextItems = receiptItems.map((item) => ({ ...item, is_deductible: true }));
                                                  handleReceiptItemsChange(receiptIndex, nextItems);
                                                handleQuickDecide(receiptIndex, nextItems);
                                              }}
                                            >
                                                {t('documents.taxReview.markAllDeductible', 'Mark all deductible')}
                                              </button>
                                              <button
                                                type="button"
                                                className="receipt-review-batch-btn non-deductible"
                                                disabled={savingReceiptIndex !== null}
                                                onClick={() => {
                                                  const nextItems = receiptItems.map((item) => ({ ...item, is_deductible: false }));
                                                  handleReceiptItemsChange(receiptIndex, nextItems);
                                                handleQuickDecide(receiptIndex, nextItems);
                                              }}
                                            >
                                                {t('documents.taxReview.markAllNotDeductible', 'Mark all non-deductible')}
                                              </button>
                                            </div>
                                          ) : null}
                                        </DocumentActionGate>
                                      </div>
                                    </div>

                                    <div className="receipt-review-items">
                                      {receiptItems.map((item, itemIndex) => {
                                        const decisionClass = receiptShouldShowExpenseControls
                                          ? item.is_deductible === true
                                            ? 'deductible'
                                            : item.is_deductible === false
                                              ? 'non-deductible'
                                              : 'needs-review'
                                          : 'needs-review';

                                        return (
                                          <div key={`review-${receiptIndex}-${itemIndex}`} className={`receipt-review-item ${decisionClass}`}>
                                            <div className="receipt-review-item-top">
                                              <div className="receipt-review-main">
                                                <span className="receipt-review-name">
                                                  {formatReceiptItemName(item.description, itemIndex)}
                                                </span>
                                                <span className="receipt-review-meta">
                                                  {formatReceiptItemMeta(item)}
                                                </span>
                                              </div>
                                              <span className="receipt-review-item-amount">{fmtEur(item.amount)}</span>
                                              {(() => {
                                                const linkedTxns = (viewingDocument as any)?.linked_transactions;
                                                if (!linkedTxns || linkedTxns.length === 0) return null;
                                                const matchedTxn = findMatchingTransaction(item, linkedTxns, itemIndex);
                                                return matchedTxn ? (
                                                  <span
                                                    className="line-item-txn-status created"
                                                    title={t('documents.lineItems.viewTransaction', 'View transaction')}
                                                    onClick={() => navigate(`/transactions?transactionId=${matchedTxn.transaction_id}`)}
                                                    role="button"
                                                    tabIndex={0}
                                                    onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/transactions?transactionId=${matchedTxn.transaction_id}`); }}
                                                  >
                                                    Linked
                                                  </span>
                                                ) : (
                                                  <span
                                                    className="line-item-txn-status not-created"
                                                    title={t('documents.lineItems.noTransaction', 'No transaction created')}
                                                  >
                                                    Pending
                                                  </span>
                                                );
                                              })()}
                                            </div>

                                            <div className="receipt-review-item-category-edit">
                                              <span className="receipt-review-item-category-label">
                                                {t('documents.ocr.category', 'Category')}
                                              </span>
                                              <Select
                                                value={item.category || ''}
                                                onChange={(value) => {
                                                  const nextItems = [...receiptItems];
                                                  nextItems[itemIndex] = {
                                                    ...nextItems[itemIndex],
                                                    category: value || undefined,
                                                  };
                                                  handleReceiptItemsChange(receiptIndex, nextItems);
                                                }}
                                                options={receiptCategoryOptions}
                                                placeholder={t('documents.receiptReview.selectCategory', 'Select category')}
                                                size="sm"
                                                disabled={!isReceiptEditing}
                                                aria-label={`receipt-item-category-${receiptIndex}-${itemIndex}`}
                                              />
                                              {!isReceiptEditing && (
                                                <span className="receipt-review-item-category-value">
                                                  {formatCategoryLabel(item.category)
                                                    || t('documents.receiptReview.noCategory', 'No category assigned')}
                                                </span>
                                              )}
                                            </div>

                                            {!receiptShouldShowExpenseControls ? (
                                              <div className="receipt-review-readonly">
                                                <span className="receipt-review-status needs-review">
                                                  {!liveReceiptDecision.controlPolicy.isPostable
                                                    ? t('documents.review.nonPostable', 'Non-postable')
                                                    : isReceiptEditing
                                                      ? t('documents.receiptReview.incomeEditing', 'Editing income details')
                                                      : t('documents.receiptReview.incomeStatus', 'Income details')}
                                                </span>
                                                <p className="receipt-review-reason-text">
                                                  {liveReceiptDecision.helpers[0]
                                                    || (isReceiptEditing
                                                      ? t('documents.receiptReview.incomeEditingHint', 'You can correct item names, quantities, amounts, and VAT details, then save directly.')
                                                      : t('documents.receiptReview.incomeStatusHint', 'The extracted item, quantity, amount, and VAT details stay visible here without expense-only deductibility controls.'))}
                                                </p>
                                              </div>
                                            ) : !isReceiptEditing && item.is_deductible !== null ? (
                                              <div className="receipt-review-readonly">
                                                <span className={`receipt-review-status ${decisionClass}`}>
                                                  {item.is_deductible === true
                                                    ? t('documents.ocr.deductible', 'Deductible')
                                                    : t('documents.ocr.notDeductible', 'Non-deductible')}
                                                </span>
                                                <p className="receipt-review-reason-text">
                                                  {translateDeductionReason(
                                                    item.deduction_reason || '',
                                                    i18n?.language || 'de',
                                                  ) || t('documents.taxReview.pendingReason', 'The system did not provide a reason yet. Click edit if you want to adjust this decision.')}
                                                </p>
                                              </div>
                                            ) : !isReceiptEditing && item.is_deductible === null ? (
                                              <div className="receipt-review-inline-decide">
                                                <span className="receipt-review-status needs-review">
                                                  {t('documents.taxReview.needsReview', 'Needs review')}
                                                </span>
                                                <div className="receipt-review-toggle-group">
                                                  <button
                                                    type="button"
                                                    className="receipt-review-toggle"
                                                    disabled={savingReceiptIndex !== null}
                                                    onClick={() => {
                                                      const nextItems = [...receiptItems];
                                                      nextItems[itemIndex] = { ...nextItems[itemIndex], is_deductible: true };
                                                      handleReceiptItemsChange(receiptIndex, nextItems);
                                                      handleQuickDecide(receiptIndex, nextItems);
                                                    }}
                                                  >
                                                    {t('documents.ocr.deductible', 'Deductible')}
                                                  </button>
                                                  <button
                                                    type="button"
                                                    className="receipt-review-toggle"
                                                    disabled={savingReceiptIndex !== null}
                                                    onClick={() => {
                                                      const nextItems = [...receiptItems];
                                                      nextItems[itemIndex] = { ...nextItems[itemIndex], is_deductible: false };
                                                      handleReceiptItemsChange(receiptIndex, nextItems);
                                                      handleQuickDecide(receiptIndex, nextItems);
                                                    }}
                                                  >
                                                    {t('documents.ocr.notDeductible', 'Non-deductible')}
                                                  </button>
                                                </div>
                                              </div>
                                            ) : (
                                              <>
                                                <div className="receipt-review-toggle-group">
                                                  <button
                                                    type="button"
                                                    className={`receipt-review-toggle ${item.is_deductible === true ? 'active deductible' : ''}`}
                                                    onClick={() => {
                                                      const nextItems = [...receiptItems];
                                                      nextItems[itemIndex] = { ...nextItems[itemIndex], is_deductible: true };
                                                      handleReceiptItemsChange(receiptIndex, nextItems);
                                                    }}
                                                  >
                                                    {t('documents.ocr.deductible', 'Deductible')}
                                                  </button>
                                                  <button
                                                    type="button"
                                                    className={`receipt-review-toggle ${item.is_deductible === false ? 'active non-deductible' : ''}`}
                                                    onClick={() => {
                                                      const nextItems = [...receiptItems];
                                                      nextItems[itemIndex] = { ...nextItems[itemIndex], is_deductible: false };
                                                      handleReceiptItemsChange(receiptIndex, nextItems);
                                                    }}
                                                  >
                                                    {t('documents.ocr.notDeductible', 'Non-deductible')}
                                                  </button>
                                                </div>

                                                <input
                                                  type="text"
                                                  className="receipt-review-reason-input"
                                                  placeholder={t('documents.taxReview.reasonPlaceholder', 'Add a reason or note')}
                                                  value={item.deduction_reason || ''}
                                                  onChange={(event) => {
                                                    const nextItems = [...receiptItems];
                                                    nextItems[itemIndex] = {
                                                      ...nextItems[itemIndex],
                                                      deduction_reason: event.target.value,
                                                    };
                                                    handleReceiptItemsChange(receiptIndex, nextItems);
                                                  }}
                                                />
                                              </>
                                            )}
                                          </div>
                                        );
                                      })}
                                    </div>

                                    {receiptItemSaveResult?.receiptIndex === receiptIndex && (
                                      <div className={`receipt-review-result ${receiptItemSaveResult.type}`}>
                                        {receiptItemSaveResult.message}
                                      </div>
                                    )}

                                    <div className="receipt-review-footer">
                                      <p>
                                        {receiptShouldShowExpenseControls
                                          ? (
                                            isReceiptEditing
                                              ? (
                                                receiptIndex === 0 && linkedTransaction
                                                  ? t('documents.taxReview.editingLinkedTransaction', 'Saving will update both recognition data and the linked transaction.')
                                                  : t('documents.taxReview.editingDocumentOnly', 'Saving will update the recognition details and record this manual correction.')
                                              )
                                              : t('documents.taxReview.readonlyHint', 'Showing the system\'s initial assessment. Edit only if the assessment is incorrect.')
                                          )
                                          : (
                                            !liveReceiptDecision.controlPolicy.isPostable
                                              ? (liveReceiptDecision.helpers[0]
                                                || t('documents.review.nonPostableHint', 'This document stays as a reference document and will not create a transaction.'))
                                              : isReceiptEditing
                                                ? t('documents.receiptReview.incomeFooterEditing', 'Saving updates the OCR details for this income document and syncs any linked transaction when present.')
                                                : t('documents.receiptReview.incomeFooterReadonly', 'This area shows the extracted income document details. Enter edit mode if item names, quantities, amounts, or VAT need correction.')
                                          )}
                                      </p>
                                      {isReceiptEditing && (
                                        <div className="receipt-review-actions">
                                          <button
                                            type="button"
                                            className="btn btn-secondary"
                                            onClick={() => {
                                              resetReceiptDraft(receiptIndex);
                                              setEditingReceiptIndex(null);
                                            }}
                                            disabled={savingReceiptIndex !== null}
                                          >
                                            {t('common.cancel', 'Cancel')}
                                          </button>
                                          <button
                                            type="button"
                                            className="btn btn-primary"
                                            onClick={() => handleSaveReceiptReview(receiptIndex)}
                                            disabled={savingReceiptIndex !== null}
                                          >
                                            {savingReceiptIndex === receiptIndex
                                              ? t('common.saving', 'Saving...')
                                              : !receiptShouldShowExpenseControls
                                                ? !liveReceiptDecision.controlPolicy.isPostable
                                                  ? t('documents.review.saveReferenceDocument', 'Save document details')
                                                  : receiptIndex === 0 && linkedTransaction
                                                    ? t('documents.taxReview.saveAndSync', 'Save and sync transaction')
                                                    : t('documents.receiptReview.saveIncomeDocument', 'Save document')
                                                : receiptIndex === 0 && linkedTransaction
                                                ? t('documents.taxReview.saveAndSync', 'Save and sync transaction')
                                                : t('documents.taxReview.saveReceipt', 'Save receipt')}
                                          </button>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                )}

                                {receiptVatSummary.length > 0 && (
                                  <div className="ocr-vat-summary">
                                    <h4>{t('documents.ocr.vatSummary')}</h4>
                                    <div className="vat-summary-table">
                                      <div className="vat-summary-header">
                                        <span>{t('documents.ocr.vatRate')}</span>
                                        <span>{t('documents.ocr.netAmount')}</span>
                                        <span>{t('documents.ocr.vatAmount')}</span>
                                      </div>
                                      {receiptVatSummary.map((row: any, idx: number) => (
                                        <div key={`receipt-vat-${receiptIndex}-${idx}`} className="vat-summary-row">
                                          <span>{fmtPct(row.rate)}</span>
                                          <span>{fmtEur(row.net_amount)}</span>
                                          <span>{fmtEur(row.vat_amount)}</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </section>
                            );
                          })}
                        </div>
                      )}

                      {!isReceiptDocument && entries.length > 0 && (
                        <div className="ocr-fields-table">
                          {entries.map(([key, val]) => (
                            <div key={key} className="ocr-field-row">
                              <span className="ocr-field-label">{labels[key] || key}</span>
                              {renderOcrFieldValue(key, val)}
                            </div>
                          ))}
                        </div>
                      )}

                      {!isReceiptDocument && lineItems.length > 0 && (
                        <div className="ocr-line-items">
                          {(() => {
                            const hasVatData = lineItems.some((item: any) => item.vat_rate != null || (item.vat_indicator && item.vat_indicator.trim()));
                            return (
                              <div className="line-items-table">
                                <div className="line-items-header">
                                  <span className="li-col-name">{t('documents.ocr.itemName')}</span>
                                  <span className="li-col-qty">{t('documents.ocr.quantity')}</span>
                                  <span className="li-col-price">{t('documents.ocr.unitPrice')}</span>
                                  <span className="li-col-total">{t('documents.ocr.totalPrice')}</span>
                                  {hasVatData && <span className="li-col-vat">{t('documents.ocr.vatRate')}</span>}
                                  {hasVatData && <span className="li-col-ind">{t('documents.ocr.vatIndicator')}</span>}
                                </div>
                                {lineItems.map((item: any, idx: number) => (
                                  <div key={idx} className="line-items-row">
                                    <span className="li-col-name">{item.name || EMPTY_DISPLAY_VALUE}</span>
                                    <span className="li-col-qty">{item.quantity ?? 1}</span>
                                    <span className="li-col-price">{fmtEur(item.unit_price ?? item.price)}</span>
                                    <span className="li-col-total">{fmtEur(item.total_price ?? item.total)}</span>
                                    {hasVatData && <span className="li-col-vat">{resolveVatRate(item)}</span>}
                                    {hasVatData && <span className="li-col-ind">{item.vat_indicator || EMPTY_DISPLAY_VALUE}</span>}
                                  </div>
                                ))}
                              </div>
                            );
                          })()}
                        </div>
                      )}

                      {!isReceiptDocument && vatSummary.length > 0 && (
                        <div className="ocr-vat-summary">
                          <h4>{t('documents.ocr.vatSummary')}</h4>
                          <div className="vat-summary-table">
                            <div className="vat-summary-header">
                              <span>{t('documents.ocr.vatRate')}</span>
                              <span>{t('documents.ocr.netAmount')}</span>
                              <span>{t('documents.ocr.vatAmount')}</span>
                            </div>
                            {vatSummary.map((row: any, idx: number) => (
                              <div key={idx} className="vat-summary-row">
                                <span>{fmtPct(row.rate)}</span>
                                <span>{fmtEur(row.net_amount)}</span>
                                <span>{fmtEur(row.vat_amount)}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {!isReceiptDocument && entries.length === 0 && lineItems.length === 0 && (
                        <p style={{ color: '#999' }}>{t('documents.ocr.noData')}</p>
                      )}

                      {/* Additional receipts from multi-receipt document */}
                      {!isReceiptDocument && (() => {
                        const additionalReceipts = Array.isArray(data._additional_receipts) ? data._additional_receipts : [];
                        if (additionalReceipts.length === 0) return null;
                        return (
                          <div className="multi-receipt-section">
                            <h4>{t('documents.multiReceipt.additionalReceipts', { count: additionalReceipts.length })}</h4>
                            {additionalReceipts.map((receipt: any, rIdx: number) => {
                              const normalizedReceipt = normalizeReceiptData(receipt);
                              const rEntries = Object.entries(normalizedReceipt).filter(
                                ([k, v]) => !k.startsWith('_') && v !== null && v !== undefined && typeof v !== 'object'
                                  && !['field_confidence', 'confidence', 'line_items', 'items', 'vat_summary', 'total_amount', 'receipt_count'].includes(k)
                              );
                              const rLineItems = getDisplayLineItems(normalizedReceipt);
                              return (
                                <div key={rIdx} className="additional-receipt-card">
                                  <div className="additional-receipt-header">
                                    <span>{t('documents.multiReceipt.receiptNumber', { number: rIdx + 2 })}</span>
                                    {receipt.amount && <span className="receipt-amount">{formatCurrencyDisplay(receipt.amount)}</span>}
                                  </div>
                                  {rEntries.length > 0 && (
                                    <div className="ocr-fields-table">
                                      {rEntries.map(([key, val]) => (
                                        <div key={key} className="ocr-field-row">
                                          <span className="ocr-field-label">{labels[key] || key}</span>
                                          {renderOcrFieldValue(key, val)}
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                  {rLineItems.length > 0 && (
                                    <div className="ocr-line-items">
                                      <div className="line-items-table">
                                        <div className="line-items-header">
                                          <span className="li-col-name">{t('documents.ocr.itemName')}</span>
                                          <span className="li-col-qty">{t('documents.ocr.quantity')}</span>
                                          <span className="li-col-price">{t('documents.ocr.unitPrice')}</span>
                                          <span className="li-col-total">{t('documents.ocr.totalPrice')}</span>
                                        </div>
                                        {rLineItems.map((item: any, liIdx: number) => (
                                          <div key={liIdx} className="line-items-row">
                                            <span className="li-col-name">{item.name || EMPTY_DISPLAY_VALUE}</span>
                                            <span className="li-col-qty">{item.quantity ?? 1}</span>
                                            <span className="li-col-price">{fmtEur(item.unit_price ?? item.price)}</span>
                                            <span className="li-col-total">{fmtEur(item.total_price ?? item.total)}</span>
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        );
                      })()}
                    </>
                  );
                })()}
              </div>
            </div>
          )}

            {/* Tax analysis is skipped for income documents where deductibility does not apply. */}
          {(() => {
            const incomeDocTypes = ['payslip', 'lohnzettel', 'einkommensteuerbescheid'];
            if (
              incomeDocTypes.includes(viewingDocument.document_type as string)
              || RECEIPT_DOC_TYPES.has(viewingDocument.document_type as string)
            ) return null;

            const data = normalizeOcrDataForDisplay(viewingDocument.ocr_result);
            const taxAnalysis = data?.tax_analysis;
            if (!taxAnalysis || !taxAnalysis.items || taxAnalysis.items.length === 0) return null;

            const fmtEur2 = (v: number | string | null | undefined) =>
              v != null ? formatCurrencyDisplay(v) : EMPTY_DISPLAY_VALUE;

            // Apply user overrides to items
            const effectiveItems = taxAnalysis.items.map((item: any, idx: number) => {
              const overridden = taxOverrides[idx] !== undefined;
              const isDeductible = overridden ? taxOverrides[idx] : item.is_deductible;
              return { ...item, is_deductible: isDeductible, overridden };
            });

            const totalDeductible = effectiveItems
              .filter((it: any) => it.is_deductible)
              .reduce((sum: number, it: any) => sum + Number(it.amount || 0), 0);
            const totalNonDeductible = effectiveItems
              .filter((it: any) => !it.is_deductible)
              .reduce((sum: number, it: any) => sum + Number(it.amount || 0), 0);

            return (
              <div className="tax-analysis-card">
                <div className="tax-analysis-header">
                  <h3>{t('documents.ocr.taxAnalysis')}</h3>
                  {taxAnalysis.is_split && (
                    <span className="split-badge">{t('documents.ocr.splitReceipt')}</span>
                  )}
                </div>

                <div className="tax-analysis-summary">
                  <div className="tax-summary-item deductible">
                    <span className="tax-summary-label">{t('documents.ocr.deductibleAmount')}</span>
                    <span className="tax-summary-value">{fmtEur2(totalDeductible)}</span>
                  </div>
                  <div className="tax-summary-item non-deductible">
                    <span className="tax-summary-label">{t('documents.ocr.nonDeductibleAmount')}</span>
                    <span className="tax-summary-value">{fmtEur2(totalNonDeductible)}</span>
                  </div>
                </div>

                <div className="tax-analysis-items">
                  {effectiveItems.map((item: any, idx: number) => (
                    <div key={idx} className={`tax-item ${item.is_deductible ? 'deductible' : 'non-deductible'}`}>
                      <div className="tax-item-header">
                        <span className="tax-item-badge">
                          {item.is_deductible ? t('documents.ocr.deductible') : t('documents.ocr.notDeductible')}
                          {item.overridden && <span className="tax-override-badge">{t('documents.ocr.userOverride', 'Manual')}</span>}
                        </span>
                        <span className="tax-item-amount">{fmtEur2(item.amount)}</span>
                      </div>
                      <div className="tax-item-desc">{item.description}</div>
                      {item.category && (
                        <div className="tax-item-category">
                          {t('documents.ocr.category')}: {formatCategoryLabel(item.category)}
                        </div>
                      )}
                      {item.deduction_reason && (
                        <div className="tax-item-reason">
                          {t('documents.ocr.reason')}: {item.deduction_reason}
                        </div>
                      )}
                      <button
                        className={`tax-override-btn ${item.is_deductible ? 'mark-non-deductible' : 'mark-deductible'}`}
                        onClick={() => setTaxOverrides(prev => ({ ...prev, [idx]: !item.is_deductible }))}
                      >
                        {item.is_deductible
                          ? t('documents.ocr.markNonDeductible', 'Mark as non-deductible')
                          : t('documents.ocr.markDeductible', 'Mark as deductible')}
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}

          {/* Import Suggestion Confirmation Card */}
          {(() => {
            const data = normalizeOcrDataForDisplay(viewingDocument.ocr_result);
            const suggestion = data?.import_suggestion;
            const isLegacyLoanNeedsInput =
              suggestion?.status === 'needs_input'
              && (suggestion?.type === 'create_loan' || suggestion?.type === 'create_loan_repayment');
            const isVisibleSuggestion =
              suggestion
              && (suggestion.status === 'pending'
                || suggestion.status === 'ready_to_confirm'
                || isLegacyLoanNeedsInput);
            if (!isVisibleSuggestion) return null;

            return (
              <DocumentActionGate
                action="suggestion_create"
                policy={(liveViewerDecision ?? resolveDocumentPresentation(viewingDocument)).controlPolicy}
                helpers={(liveViewerDecision ?? resolveDocumentPresentation(viewingDocument)).helpers}
              >
                {({ hidden, disabled, reason }) => !hidden ? (
                  <SuggestionCardFactory
                    suggestion={suggestion}
                    confirmResult={confirmResult}
                    confirmingAction={confirmingAction}
                    onConfirm={() => {}}
                    onDismiss={handleDismissSuggestion}
                    onConfirmProperty={handleConfirmProperty}
                    onConfirmRecurring={handleConfirmRecurring}
                    onConfirmRecurringExpense={handleConfirmRecurringExpense}
                    onConfirmAsset={handleConfirmAsset}
                    onConfirmLoan={handleConfirmLoan}
                    onConfirmLoanRepayment={handleConfirmLoanRepayment}
                    onConfirmTaxData={handleConfirmTaxData}
                    onConfirmBankTransactions={handleConfirmBankTransactions}
                    confirmDisabled={disabled}
                    confirmDisabledReason={reason}
                    documentId={viewingDocument.id}
                  />
                ) : null}
              </DocumentActionGate>
            );
          })()}
        </div>
      </div>
    );
  }

  // Main view: upload zone at top + document list below (no tabs)
  return (
    <div className="documents-page">
      <div className="page-header">
        <h1>{t('documents.title')}</h1>
      </div>

      <div className="upload-section">
        {uploadPropertyId && (
          <div className="upload-context-hint" style={{
            padding: '12px 16px',
            marginBottom: '12px',
            background: '#eff6ff',
            border: '1px solid #bfdbfe',
            borderRadius: '8px',
            color: '#1e40af',
            fontSize: '0.9rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}>
            <span>
              {uploadType === 'purchase_contract'
                ? t('documents.upload.contextHintPurchase', { propertyId: uploadPropertyId })
                : uploadType === 'loan_contract'
                  ? t('documents.upload.contextHintLoan', { propertyId: uploadPropertyId })
                  : t('documents.upload.contextHintRental', { propertyId: uploadPropertyId })}
            </span>
          </div>
        )}
        <DocumentUpload propertyId={uploadPropertyId} />
      </div>

      <div className="documents-list-section">
        <DocumentList key={refreshKey} onDocumentSelect={handleDocumentSelect} />
      </div>
    </div>
  );
};

export default DocumentsPage;
