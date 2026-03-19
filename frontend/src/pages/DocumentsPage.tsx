import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import DocumentUpload from '../components/documents/DocumentUpload';
import { translateDeductionReason } from '../utils/translateDeductionReason';
import DocumentList from '../components/documents/DocumentList';
import OCRReview from '../components/documents/OCRReview';
import EmployerReviewPanel from '../components/documents/EmployerReviewPanel';
import BescheidImport from '../components/documents/BescheidImport';
import E1FormImport from '../components/documents/E1FormImport';
import SuggestionCardFactory from '../components/documents/SuggestionCardFactory';
import { documentService, type AssetSuggestionConfirmationPayload } from '../services/documentService';
import { transactionService } from '../services/transactionService';
import { propertyService } from '../services/propertyService';
import { Document } from '../types/document';
import { Property } from '../types/property';
import { Transaction } from '../types/transaction';
import { saveBlobWithNativeShare } from '../mobile/files';
import { useRefreshStore } from '../stores/refreshStore';
import { aiToast } from '../stores/aiToastStore';
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

const RECEIPT_DOC_TYPES = new Set(['receipt', 'invoice']);
const INCOME_DOC_TYPES = new Set(['payslip', 'lohnzettel', 'einkommensteuerbescheid']);
const LEGACY_FINAL_ASSET_STATUSES = new Set(['confirmed', 'auto-created']);
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

const normalizeReceiptSection = (receipt: Record<string, any>): Record<string, any> => {
  const { _additional_receipts, _receipt_count, tax_analysis, import_suggestion, asset_outcome, multiple_receipts, receipt_count, receipts, ...rest } = receipt;
  return normalizeReceiptData(rest);
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
        title: t('documents.pipeline.processingPhase1Title', '正在提取文档内容'),
        description: t('documents.pipeline.processingPhase1Body', 'OCR 和分类仍在进行中，稍后会显示首批可查看结果。'),
      };
    case 'first_result_available':
      return {
        tone: 'info',
        title: t('documents.pipeline.firstResultTitle', '首批结果已可见'),
        description: t('documents.pipeline.firstResultBody', '已保存 OCR、分类和提取结果，后续自动建议仍在处理中。'),
      };
    case 'finalizing':
      return {
        tone: 'info',
        title: t('documents.pipeline.finalizingTitle', '正在完成后续处理'),
        description: t('documents.pipeline.finalizingBody', '你现在可以查看首批结果；自动建议和落库动作仍在继续。'),
      };
    case 'phase_2_failed':
      return {
        tone: 'warning',
        title: t('documents.pipeline.phase2FailedTitle', '后续自动处理未完成'),
        description: t('documents.pipeline.phase2FailedBody', '首批 OCR 结果已保留，你仍然可以查看和编辑当前提取结果。'),
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
  if (Array.isArray(data.line_items)) return data.line_items;
  if (Array.isArray(data.items)) return data.items;
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

const mapTransactionLineItemToDraftItem = (item: NonNullable<Transaction['line_items']>[number]): ReceiptDraftItem => ({
  description: item.description,
  amount: Number(item.amount || 0),
  quantity: item.quantity ?? 1,
  unitPrice: Number(item.amount || 0),
  vatRate: toFiniteNumber(item.vat_rate),
  category: item.category,
  is_deductible: item.is_deductible ?? null,
  deduction_reason: item.deduction_reason ?? '',
});

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

const buildReceiptScalarEntries = (receipt: Record<string, any>): [string, unknown][] =>
  Object.entries(receipt).filter(
    ([key, value]) =>
      !key.startsWith('_')
      && !OCR_META_SKIP_KEYS.includes(key)
      && value !== null
      && value !== undefined
      && typeof value !== 'object'
  );

const buildUpdatedReceiptCorrections = (
  ocrResult: unknown,
  drafts: Record<number, ReceiptDraftItem[]>
): Record<string, any> => {
  const displayData = normalizeOcrDataForDisplay(ocrResult);
  const receipts = getAllReceiptsForDisplay(displayData);
  const updatedReceipts = receipts.map((receipt, receiptIndex) => {
    const draftItems = drafts[receiptIndex] || [];
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
      line_items: mappedItems,
      items: mappedItems,
    };
  });

  const corrections: Record<string, any> = {};
  const primaryItems = updatedReceipts[0]?.line_items || [];

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

const buildTransactionLineItems = (items: ReceiptDraftItem[]) =>
  items
    .filter((item) => item.description.trim() && item.amount > 0)
    .map((item, index) => ({
      description: item.description.trim(),
      amount: Number(item.amount.toFixed(2)),
      quantity: Number.isInteger(toFiniteNumber(item.quantity))
        ? Number(item.quantity)
        : 1,
      category: item.category,
      is_deductible: item.is_deductible === true,
      deduction_reason: item.deduction_reason?.trim() || undefined,
      vat_rate: normalizeVatRate(item.vatRate),
      sort_order: index,
    }));

const DocumentsPage = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { documentId } = useParams<{ documentId: string }>();
  const [searchParams] = useSearchParams();
  const uploadPropertyId = searchParams.get('property_id');
  const uploadType = searchParams.get('type');
  const [reviewingDocument, setReviewingDocument] = useState<number | null>(null);
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

  const [receiptItemDrafts, setReceiptItemDrafts] = useState<Record<number, ReceiptDraftItem[]>>({});
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
      setOcrFieldError(t('documents.ocr.saveFailed', '保存失败，请重试'));
    } finally {
      setSavingOcrField(null);
      setEditingOcrField(null);
    }
  };

  const formatOcrFieldValue = (key: string, val: unknown): string => {
    if (val === null || val === undefined) return '—';
    if (typeof val === 'boolean') return val ? '✓' : '✗';

    const s = String(val);
    if (key.includes('date') && s.match(/^\d{4}-\d{2}-\d{2}/)) {
      try {
        return new Date(s).toLocaleDateString('de-AT');
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
      return `€ ${Number(val).toLocaleString('de-AT', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`;
    }

    return s;
  };

  const formatReceiptItemName = (description: string | undefined, itemIndex: number): string => {
    const normalized = String(description || '').trim();
    return normalized || `项目 ${itemIndex + 1}`;
  };

  const formatCategoryLabel = (category?: string | null): string => {
    const normalized = String(category || '').trim();
    if (!normalized) return '';

    const translationKey = normalized.toLowerCase().replace(/[\\/\s-]+/g, '_');
    const translated = t(`transactions.categories.${translationKey}`, { defaultValue: normalized });

    if (translated && translated !== `transactions.categories.${translationKey}`) {
      return translated;
    }

    return normalized.replace(/_/g, ' ');
  };

  const formatReceiptItemMeta = (item: ReceiptDraftItem): string => {
    const parts = [`${t('documents.ocr.quantity', '数量')} ${item.quantity ?? 1}`];
    const categoryLabel = formatCategoryLabel(item.category);
    if (categoryLabel) {
      parts.push(categoryLabel);
    }
    return parts.join(' | ');
  };

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
        title={t('documents.ocr.clickToEdit', '点击编辑')}
      >
        {formatOcrFieldValue(key, val)}
        {savingOcrField === editKey && <span className="ocr-field-saving">…</span>}
        {ocrFieldError && !editingOcrField && <span className="ocr-field-error">{ocrFieldError}</span>}
        <span className="ocr-field-edit-icon">✏️</span>
      </span>
    );
  };

  // When navigated with a documentId param, load and show that document
  useEffect(() => {
    if (documentId) {
      const id = parseInt(documentId);
      if (!isNaN(id)) {
        documentService.getDocument(id).then((doc) => {
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
            setReviewingDocument(id);
          } else {
            setViewingDocument(doc);
          }
        }).catch((err) => {
          console.error('Failed to load document:', err);
        });
      }
    }
  }, [documentId]);

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
      setEditingReceiptIndex(null);
      return;
    }

    const data = normalizeOcrDataForDisplay(viewingDocument.ocr_result);
    setReceiptItemDrafts(buildReceiptDrafts(data, linkedTransaction));
    setEditingReceiptIndex(null);
  }, [viewingDocument?.id, viewingDocument?.ocr_result, linkedTransaction]);

  const handleDocumentSelect = async (document: Document) => {
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
      setReviewingDocument(document.id);
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
  }, [viewingDocument]);

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
  const handleRetryOcr = async () => {
    if (!viewingDocument || retryingOcr) return;
    setRetryingOcr(true);
    try {
      await documentService.retryOcr(viewingDocument.id);
      aiToast(t('documents.reprocessStarted'), 'success');
      // Reload document after a short delay to let OCR finish
      setTimeout(async () => {
        try {
          const updated = await documentService.getDocument(viewingDocument.id);
          setViewingDocument(updated);
        } catch { /* ignore */ }
        setRetryingOcr(false);
      }, 3000);
    } catch (error) {
      console.error('Failed to retry OCR:', error);
      aiToast(t('documents.reprocessFailed'), 'error');
      setRetryingOcr(false);
    }
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

  // Quick-decide: auto-save when user toggles a pending item in view mode
  const handleQuickDecide = async (receiptIndex: number, items: ReceiptDraftItem[]) => {
    if (!viewingDocument) return;
    setSavingReceiptIndex(receiptIndex);
    try {
      const drafts = { ...receiptItemDrafts, [receiptIndex]: items };
      const corrections = buildUpdatedReceiptCorrections(viewingDocument.ocr_result, drafts);
      await documentService.correctOCR(viewingDocument.id, corrections);

      if (receiptIndex === 0 && linkedTransaction) {
        await transactionService.update(linkedTransaction.id, {
          line_items: buildTransactionLineItems(items),
          is_deductible: items.some((item) => item.is_deductible === true),
          reviewed: true,
          locked: true,
        });
      }

      const updatedDocument = await documentService.getDocument(viewingDocument.id);
      setViewingDocument(updatedDocument);
      if (updatedDocument.transaction_id) {
        const updatedTransaction = await transactionService.getById(updatedDocument.transaction_id);
        setLinkedTransaction(updatedTransaction);
      }
      useRefreshStore.getState().refreshTransactions();
      useRefreshStore.getState().refreshDashboard();
      aiToast(t('documents.taxReview.quickDecideSaved', '已保存'), 'success');
    } catch (error: any) {
      console.error('Failed to quick-decide:', error);
      aiToast(error?.response?.data?.detail || error?.message || 'Save failed', 'error');
    } finally {
      setSavingReceiptIndex(null);
    }
  };

  const resetReceiptDraft = useCallback((receiptIndex: number) => {
    const data = normalizeOcrDataForDisplay(viewingDocument?.ocr_result);
    const freshDrafts = buildReceiptDrafts(data, linkedTransaction);
    setReceiptItemDrafts((current) => ({
      ...current,
      [receiptIndex]: freshDrafts[receiptIndex] || [],
    }));
    setReceiptItemSaveResult(null);
  }, [viewingDocument?.ocr_result, linkedTransaction]);

  const handleSaveReceiptReview = async (receiptIndex: number) => {
    if (!viewingDocument) return;

    setSavingReceiptIndex(receiptIndex);
    setReceiptItemSaveResult(null);

    try {
      const corrections = buildUpdatedReceiptCorrections(viewingDocument.ocr_result, receiptItemDrafts);
      await documentService.correctOCR(viewingDocument.id, corrections);

      if (receiptIndex === 0 && linkedTransaction) {
        await transactionService.update(linkedTransaction.id, {
          line_items: buildTransactionLineItems(receiptItemDrafts[receiptIndex] || []),
          is_deductible: (receiptItemDrafts[receiptIndex] || []).some((item) => item.is_deductible === true),
          deduction_reason: (receiptItemDrafts[receiptIndex] || []).some((item) => item.is_deductible === true)
            && (receiptItemDrafts[receiptIndex] || []).some((item) => item.is_deductible === false)
            ? 'Mixed deductibility confirmed at line-item level'
            : undefined,
          reviewed: true,
          locked: true,
        });
      }

      const updatedDocument = await documentService.getDocument(viewingDocument.id);
      setViewingDocument(updatedDocument);

      if (updatedDocument.transaction_id) {
        const updatedTransaction = await transactionService.getById(updatedDocument.transaction_id);
        setLinkedTransaction(updatedTransaction);
      }

      useRefreshStore.getState().refreshTransactions();
      useRefreshStore.getState().refreshDashboard();

      const message = receiptIndex === 0 && linkedTransaction
        ? '小票判断已保存，并同步到交易记录'
        : '小票判断已保存';
      setEditingReceiptIndex(null);
      setReceiptItemSaveResult({
        type: 'success',
        message,
        receiptIndex,
      });
      aiToast(message, 'success');
    } catch (error: any) {
      console.error('Failed to save receipt review:', error);
      const message = error?.response?.data?.detail || error?.message || 'Save failed';
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
          onImportComplete={handleE1Complete}
          onCancel={handleE1Complete}
        />
      </div>
    );
  }

  if (reviewingDocument) {
    return (
      <div className="documents-page">
        <OCRReview
          documentId={reviewingDocument}
          onConfirm={handleReviewComplete}
          onCancel={handleReviewCancel}
        />
      </div>
    );
  }

  if (viewingDocument) {
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
      ? [linkedTransaction.description || null, linkedTransaction.date || null].filter(Boolean).join(' · ')
      : t('documents.linkedTransaction.hint', '这份文档已经生成交易记录，可直接前往查看。');
    const linkedAssetTitle = linkedAsset?.name
      || (linkedAsset?.asset_type
        ? t(`properties.assetTypes.${linkedAsset.asset_type}`, linkedAsset.asset_type)
        : t('documents.linkedAsset.title', '已创建资产'));
    const linkedAssetSummary = linkedAsset
      ? [
          linkedAsset.supplier || null,
          linkedAsset.put_into_use_date || linkedAsset.purchase_date || null,
        ].filter(Boolean).join(' · ')
      : t('documents.linkedAsset.hint', '这份文档已经创建资产台账，可直接前往查看。');
    const linkedAssetTaxFlags = linkedAsset
      ? [
          linkedAsset.gwg_elected
            ? t('documents.linkedAsset.gwg', 'GWG 一次性费用化')
            : linkedAsset.depreciation_method === 'degressive'
              ? t('documents.linkedAsset.degressive', '递减折旧')
              : linkedAsset.depreciation_method === 'linear'
                ? t('documents.linkedAsset.linear', '线性折旧')
                : null,
          linkedAsset.business_use_percentage != null
            ? `${t('documents.linkedAsset.businessUse', '业务使用')} ${linkedAsset.business_use_percentage}%`
            : null,
          linkedAsset.ifb_candidate
            ? t('documents.linkedAsset.ifbCandidate', 'IFB 候选')
            : null,
        ].filter(Boolean)
      : [];
    const linkedAssetValueSummary = linkedAsset
      ? [
          linkedAsset.annual_depreciation != null
            ? `${t('documents.linkedAsset.annualDepreciation', '年折旧')} ${linkedAsset.annual_depreciation.toLocaleString('de-AT', { style: 'currency', currency: 'EUR' })}`
            : null,
          linkedAsset.remaining_value != null
            ? `${t('documents.linkedAsset.remainingValue', '剩余价值')} ${linkedAsset.remaining_value.toLocaleString('de-AT', { style: 'currency', currency: 'EUR' })}`
            : null,
        ].filter(Boolean)
      : [];

    return (
      <div className="documents-page">
        <div className="document-viewer">
          <div className="viewer-header">
            <button className="btn btn-secondary" onClick={handleCloseViewer}>
              ← {t('common.back')}
            </button>
            <h2>{viewingDocument.file_name}</h2>
            <button className="btn btn-primary" onClick={handleDownloadDocument}>
              ⬇️ {t('documents.download')}
            </button>
            <button className="btn btn-secondary" onClick={handleRetryOcr} disabled={retryingOcr}>
              🔄 {retryingOcr ? t('documents.reprocessing') : t('documents.reprocess')}
            </button>
          </div>
          <div className="viewer-meta">
            <span>{t(`documents.types.${viewingDocument.document_type}`)}</span>
            <span>{new Date(viewingDocument.created_at).toLocaleDateString('de-AT')}</span>
            {viewingDocument.confidence_score != null && (
              <span>{t('documents.confidence')}: {(viewingDocument.confidence_score * 100).toFixed(0)}%</span>
            )}
            {(() => {
              const count = viewerOcrData?._receipt_count;
              if (count && count > 1) {
                return <span className="multi-receipt-badge">📑 {t('documents.multiReceipt.badge', { count })}</span>;
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
                <strong>{t('documents.linkedTransaction.title', '已生成交易')}</strong>
                <span>{linkedTransactionSummary}</span>
              </div>
              <button type="button" className="btn btn-primary" onClick={handleOpenLinkedTransaction}>
                {t('documents.linkedTransaction.open', '已生成交易，前往查看')}
              </button>
            </div>
          )}
          {assetOutcome && linkedAsset && (
            <div className="viewer-linked-asset">
              <div className="viewer-linked-asset-copy">
                <strong>{t('documents.linkedAsset.title', '已创建资产')}</strong>
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
                  <span>{linkedAssetValueSummary.join(' · ')}</span>
                )}
              </div>
              <button type="button" className="btn btn-primary" onClick={handleOpenLinkedAsset}>
                {t('documents.linkedAsset.open', '前往查看资产')}
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
                  ⬇️ {t('documents.download')}
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
                    asset_name: t('documents.ocr.assetName', '资产名称'),
                    asset_type: t('documents.ocr.assetType', '资产类型'),
                    first_registration_date: t('documents.ocr.firstRegistrationDate', '首次登记日期'),
                    vehicle_identification_number: t('documents.ocr.vehicleIdentificationNumber', '车架号'),
                    license_plate: t('documents.ocr.licensePlate', '车牌号'),
                    mileage_km: t('documents.ocr.mileageKm', '里程'),
                    is_used_asset: t('documents.ocr.isUsedAsset', '是否二手'),
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
                    amount: t('documents.ocr.amount', '金额'),
                    merchant: t('documents.ocr.merchant', '商家'),
                    supplier: t('documents.ocr.supplier', '供应商'),
                    description: t('documents.ocr.description', '描述'),
                    product_summary: t('documents.ocr.productSummary', '商品摘要'),
                    vat_amount: t('documents.ocr.vatAmount'),
                    vat_rate: t('documents.ocr.vatRate'),
                    payment_method: t('documents.ocr.paymentMethod', '支付方式'),
                    currency: t('documents.ocr.currency', '货币'),
                    invoice_number: t('documents.ocr.invoiceNumber', '发票号'),
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

                  const fmtEur = (v: unknown) =>
                    v != null && !isNaN(Number(v))
                      ? `€ ${Number(v).toLocaleString('de-AT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                      : '—';
                  const fmtPct = (v: unknown) => {
                    if (v == null || isNaN(Number(v))) return '—';
                    const n = Number(v);
                    // VLM may return 10/20 (whole %) or 0.10/0.20 (decimal)
                    const pct = n >= 1 ? n : n * 100;
                    return `${pct.toFixed(0)}%`;
                  };

                  // Austrian VAT indicator → rate mapping
                  const vatIndicatorMap: Record<string, number> = { A: 10, B: 20, C: 13, D: 0 };
                  const resolveVatRate = (item: any): string => {
                    if (item.vat_rate != null && !isNaN(Number(item.vat_rate))) {
                      return fmtPct(item.vat_rate);
                    }
                    const ind = (item.vat_indicator || '').toUpperCase().trim();
                    if (ind && vatIndicatorMap[ind] !== undefined) {
                      return `${vatIndicatorMap[ind]}%`;
                    }
                    return '—';
                  };

                  return (
                    <>
                      {isReceiptDocument && receiptSections.length > 0 && (
                        <div className="receipt-breakdown-list">
                          {receiptSections.map((receipt, receiptIndex) => {
                            const receiptEntries = buildReceiptScalarEntries(receipt);
                            const receiptItems = receiptItemDrafts[receiptIndex] || [];
                            const isReceiptEditing = editingReceiptIndex === receiptIndex;
                            const receiptVatSummary = Array.isArray(receipt.vat_summary) ? receipt.vat_summary : [];
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
                                    <h4>{`小票 ${receiptIndex + 1}`}</h4>
                                    <p>
                                      {[receipt.merchant, receipt.date ? formatOcrFieldValue('date', receipt.date) : null]
                                        .filter(Boolean)
                                        .join(' | ') || 'OCR 识别的小票'}
                                    </p>
                                  </div>
                                  <div className="receipt-breakdown-amount">{fmtEur(receipt.amount)}</div>
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
                                                    item.vatIndicator || '—'
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

                                {!INCOME_DOC_TYPES.has(viewingDocument.document_type as string) && receiptItems.length > 0 && (
                                  <div className="receipt-review-card">
                                    <div className="receipt-review-header">
                                      <div>
                                        <h5>{t('documents.taxReview.title', '税务判断')}</h5>
                                        <p>
                                          {isReceiptEditing
                                            ? t('documents.taxReview.editHint', '系统已先做预判，您现在可以修正商品明细和抵税判断。')
                                            : t('documents.taxReview.viewHint', '系统会先给出预判，只有您觉得不对时再点编辑修改。')}
                                        </p>
                                      </div>
                                      <div className="receipt-review-header-side">
                                        <div className="receipt-review-summary">
                                          <span className="deductible">{`${t('documents.ocr.deductible', '可抵税')} ${fmtEur(deductibleTotal)}`}</span>
                                          <span className="non-deductible">{`${t('documents.ocr.notDeductible', '不可抵税')} ${fmtEur(nonDeductibleTotal)}`}</span>
                                        </div>
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
                                            ✅ {t('documents.taxReview.markAllDeductible', '全部可抵税')}
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
                                            ❌ {t('documents.taxReview.markAllNotDeductible', '全部不可抵税')}
                                          </button>
                                        </div>
                                        {!isReceiptEditing && (
                                          <button
                                            type="button"
                                            className="receipt-review-edit-btn"
                                            onClick={() => {
                                              setEditingReceiptIndex(receiptIndex);
                                              setReceiptItemSaveResult(null);
                                            }}
                                          >
                                            {t('common.edit', '编辑')}
                                          </button>
                                        )}
                                      </div>
                                    </div>

                                    <div className="receipt-review-items">
                                      {receiptItems.map((item, itemIndex) => {
                                        const decisionClass = item.is_deductible === true
                                          ? 'deductible'
                                          : item.is_deductible === false
                                            ? 'non-deductible'
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
                                                    🔗✅
                                                  </span>
                                                ) : (
                                                  <span
                                                    className="line-item-txn-status not-created"
                                                    title={t('documents.lineItems.noTransaction', 'No transaction created')}
                                                  >
                                                    🔗⏳
                                                  </span>
                                                );
                                              })()}
                                            </div>

                                            {!isReceiptEditing && item.is_deductible !== null ? (
                                              <div className="receipt-review-readonly">
                                                <span className={`receipt-review-status ${decisionClass}`}>
                                                  {item.is_deductible === true
                                                    ? t('documents.ocr.deductible', '可抵税')
                                                    : t('documents.ocr.notDeductible', '不可抵税')}
                                                </span>
                                                <p className="receipt-review-reason-text">
                                                  {translateDeductionReason(
                                                    item.deduction_reason || '',
                                                    i18n?.language || 'de',
                                                  ) || t('documents.taxReview.pendingReason', '系统暂时没有给出原因，请点击编辑后修正。')}
                                                </p>
                                              </div>
                                            ) : !isReceiptEditing && item.is_deductible === null ? (
                                              <div className="receipt-review-inline-decide">
                                                <span className="receipt-review-status needs-review">
                                                  {t('documents.taxReview.needsReview', '待确认')}
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
                                                    ✅ {t('documents.ocr.deductible', '可抵税')}
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
                                                    ❌ {t('documents.ocr.notDeductible', '不可抵税')}
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
                                                    {t('documents.ocr.deductible', '可抵税')}
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
                                                    {t('documents.ocr.notDeductible', '不可抵税')}
                                                  </button>
                                                </div>

                                                <input
                                                  type="text"
                                                  className="receipt-review-reason-input"
                                                  placeholder={t('documents.taxReview.reasonPlaceholder', '填写判断原因或备注')}
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
                                        {isReceiptEditing
                                          ? (
                                            receiptIndex === 0 && linkedTransaction
                                              ? t('documents.taxReview.editingLinkedTransaction', '保存后会同时更新 OCR 内容和已关联的交易记录。')
                                              : t('documents.taxReview.editingDocumentOnly', '保存后会更新这份文档的 OCR 明细，并记录这次人工修正。')
                                          )
                                          : t('documents.taxReview.readonlyHint', '这里先展示系统预判。只有系统判断不准确时，才需要进入编辑。')}
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
                                            {t('common.cancel', '取消')}
                                          </button>
                                          <button
                                            type="button"
                                            className="btn btn-primary"
                                            onClick={() => handleSaveReceiptReview(receiptIndex)}
                                            disabled={savingReceiptIndex !== null}
                                          >
                                            {savingReceiptIndex === receiptIndex
                                              ? t('common.saving', '保存中...')
                                              : receiptIndex === 0 && linkedTransaction
                                                ? t('documents.taxReview.saveAndSync', '保存并同步交易')
                                                : t('documents.taxReview.saveReceipt', '保存这张小票')}
                                          </button>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                )}

                                {receiptVatSummary.length > 0 && (
                                  <div className="ocr-vat-summary">
                                    <h4>📊 {t('documents.ocr.vatSummary')}</h4>
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
                                    <span className="li-col-name">{item.name || '—'}</span>
                                    <span className="li-col-qty">{item.quantity ?? 1}</span>
                                    <span className="li-col-price">{fmtEur(item.unit_price ?? item.price)}</span>
                                    <span className="li-col-total">{fmtEur(item.total_price ?? item.total)}</span>
                                    {hasVatData && <span className="li-col-vat">{resolveVatRate(item)}</span>}
                                    {hasVatData && <span className="li-col-ind">{item.vat_indicator || '—'}</span>}
                                  </div>
                                ))}
                              </div>
                            );
                          })()}
                        </div>
                      )}

                      {!isReceiptDocument && vatSummary.length > 0 && (
                        <div className="ocr-vat-summary">
                          <h4>📊 {t('documents.ocr.vatSummary')}</h4>
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
                            <h4>📑 {t('documents.multiReceipt.additionalReceipts', { count: additionalReceipts.length })}</h4>
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
                                    <span>🧾 {t('documents.multiReceipt.receiptNumber', { number: rIdx + 2 })}</span>
                                    {receipt.amount && <span className="receipt-amount">€ {Number(receipt.amount).toLocaleString('de-AT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>}
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
                                            <span className="li-col-name">{item.name || '—'}</span>
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

          {/* Tax Analysis Card — skip for income documents (payslip/lohnzettel) where deductibility is not applicable */}
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
              v != null ? `€ ${Number(v).toLocaleString('de-AT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—';

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
                  <span className="tax-analysis-icon">📋</span>
                  <h3>{t('documents.ocr.taxAnalysis')}</h3>
                  {taxAnalysis.is_split && (
                    <span className="split-badge">{t('documents.ocr.splitReceipt')}</span>
                  )}
                </div>

                <div className="tax-analysis-summary">
                  <div className="tax-summary-item deductible">
                    <span className="tax-summary-label">✅ {t('documents.ocr.deductibleAmount')}</span>
                    <span className="tax-summary-value">{fmtEur2(totalDeductible)}</span>
                  </div>
                  <div className="tax-summary-item non-deductible">
                    <span className="tax-summary-label">❌ {t('documents.ocr.nonDeductibleAmount')}</span>
                    <span className="tax-summary-value">{fmtEur2(totalNonDeductible)}</span>
                  </div>
                </div>

                <div className="tax-analysis-items">
                  {effectiveItems.map((item: any, idx: number) => (
                    <div key={idx} className={`tax-item ${item.is_deductible ? 'deductible' : 'non-deductible'}`}>
                      <div className="tax-item-header">
                        <span className="tax-item-badge">
                          {item.is_deductible ? '✅' : '❌'}
                          {item.is_deductible ? t('documents.ocr.deductible') : t('documents.ocr.notDeductible')}
                          {item.overridden && <span className="tax-override-badge">{t('documents.ocr.userOverride', '手动')}</span>}
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
                          ? t('documents.ocr.markNonDeductible', '标记为不可报税')
                          : t('documents.ocr.markDeductible', '标记为可报税')}
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
            if (!suggestion || suggestion.status !== 'pending') return null;

            return (
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
                onConfirmTaxData={handleConfirmTaxData}
                onConfirmBankTransactions={handleConfirmBankTransactions}
              />
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
            <span>📋</span>
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
