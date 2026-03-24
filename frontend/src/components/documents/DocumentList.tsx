import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import Select from '../common/Select';
import { documentService } from '../../services/documentService';
import { useDocumentStore } from '../../stores/documentStore';
import { useAIAdvisorStore } from '../../stores/aiAdvisorStore';
import { aiToast } from '../../stores/aiToastStore';
import { Document, DocumentType } from '../../types/document';
import { canReprocessDocument } from '../../utils/documentReprocessing';
import { saveBlobWithNativeShare } from '../../mobile/files';
import { getLocaleForLanguage } from '../../utils/locale';
import DateInput from '../common/DateInput';
import DeleteDocumentDialog from './DeleteDocumentDialog';
import './DocumentList.css';

export interface DocumentListSummary {
  totalCount: number;
  reviewCount: number;
  confirmableIds: number[];
}

interface DocumentListProps {
  onDocumentSelect?: (document: Document) => void;
  onSummaryChange?: (summary: DocumentListSummary) => void;
}

type ViewMode = 'grid' | 'list';
type DocumentGroupId =
  | 'all'
  | 'employment'
  | 'self_employed'
  | 'property'
  | 'social_insurance'
  | 'tax_filing'
  | 'deductions'
  | 'expense'
  | 'banking'
  | 'other';

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];
const DEFAULT_PAGE_SIZE = 20;

const SearchIcon = () => (
  <svg className="icon-svg" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <circle cx="11" cy="11" r="6.5" stroke="currentColor" strokeWidth="1.8" />
    <path
      d="M16 16L21 21"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
    />
  </svg>
);

const GridIcon = () => (
  <svg className="icon-svg" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <rect
      x="4"
      y="4"
      width="6.5"
      height="6.5"
      rx="1.2"
      stroke="currentColor"
      strokeWidth="1.6"
    />
    <rect
      x="13.5"
      y="4"
      width="6.5"
      height="6.5"
      rx="1.2"
      stroke="currentColor"
      strokeWidth="1.6"
    />
    <rect
      x="4"
      y="13.5"
      width="6.5"
      height="6.5"
      rx="1.2"
      stroke="currentColor"
      strokeWidth="1.6"
    />
    <rect
      x="13.5"
      y="13.5"
      width="6.5"
      height="6.5"
      rx="1.2"
      stroke="currentColor"
      strokeWidth="1.6"
    />
  </svg>
);

const ListIcon = () => (
  <svg className="icon-svg" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M8 6H20" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    <path d="M8 12H20" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    <path d="M8 18H20" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    <circle cx="4.5" cy="6" r="1.3" fill="currentColor" />
    <circle cx="4.5" cy="12" r="1.3" fill="currentColor" />
    <circle cx="4.5" cy="18" r="1.3" fill="currentColor" />
  </svg>
);

const DownloadIcon = () => (
  <svg className="icon-svg" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M12 4V14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    <path
      d="M8.5 10.5L12 14L15.5 10.5"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path d="M5 18.5H19" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
  </svg>
);

const DeleteIcon = () => (
  <svg className="icon-svg" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M5.5 7H18.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    <path
      d="M9 7V5.5C9 4.67 9.67 4 10.5 4H13.5C14.33 4 15 4.67 15 5.5V7"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
    />
    <path d="M8.5 10V17" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    <path d="M12 10V17" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    <path d="M15.5 10V17" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    <path
      d="M7.5 7L8.2 18.2C8.27 19.27 9.15 20.1 10.22 20.1H13.78C14.85 20.1 15.73 19.27 15.8 18.2L16.5 7"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);


const RetryIcon = () => (
  <svg className="icon-svg" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M4 12a8 8 0 0 1 14.93-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    <path d="M20 12a8 8 0 0 1-14.93 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    <path d="M18.5 4.5V8H15" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M5.5 19.5V16H9" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const ReviewIcon = () => (
  <svg className="icon-svg" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path
      d="M12 3.5L21 19H3L12 3.5Z"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinejoin="round"
    />
    <path d="M12 9V13" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    <circle cx="12" cy="16.5" r="1" fill="currentColor" />
  </svg>
);

const ConfirmReviewIcon = () => (
  <svg className="icon-svg" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path
      d="M7 12.5L10.2 15.7L17.5 8.5"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8" />
  </svg>
);

const documentGroups: Array<{
  id: Exclude<DocumentGroupId, 'all'>;
  types: DocumentType[];
}> = [
  {
    id: 'employment',
    types: [
      DocumentType.PAYSLIP,
      DocumentType.LOHNZETTEL,
      DocumentType.L1_FORM,
      DocumentType.L1K_BEILAGE,
      DocumentType.L1AB_BEILAGE,
    ],
  },
  {
    id: 'self_employed',
    types: [
      DocumentType.E1A_BEILAGE,
      DocumentType.JAHRESABSCHLUSS,
      DocumentType.U1_FORM,
      DocumentType.U30_FORM,
      DocumentType.GEWERBESCHEIN,
    ],
  },
  {
    id: 'property',
    types: [
      DocumentType.PURCHASE_CONTRACT,
      DocumentType.RENTAL_CONTRACT,
      DocumentType.E1B_BEILAGE,
      DocumentType.PROPERTY_TAX,
      DocumentType.GRUNDBUCHAUSZUG,
      DocumentType.BETRIEBSKOSTENABRECHNUNG,
    ],
  },
  {
    id: 'social_insurance',
    types: [
      DocumentType.SVS_NOTICE,
      DocumentType.VERSICHERUNGSBESTAETIGUNG,
      DocumentType.LOAN_CONTRACT,
    ],
  },
  {
    id: 'tax_filing',
    types: [
      DocumentType.E1_FORM,
      DocumentType.E1KV_BEILAGE,
      DocumentType.EINKOMMENSTEUERBESCHEID,
    ],
  },
  {
    id: 'deductions',
    types: [
      DocumentType.SPENDENBESTAETIGUNG,
      DocumentType.KINDERBETREUUNGSKOSTEN,
      DocumentType.FORTBILDUNGSKOSTEN,
      DocumentType.PENDLERPAUSCHALE,
      DocumentType.KIRCHENBEITRAG,
    ],
  },
  {
    id: 'expense',
    types: [DocumentType.RECEIPT, DocumentType.INVOICE],
  },
  {
    id: 'banking',
    types: [DocumentType.BANK_STATEMENT, DocumentType.KONTOAUSZUG],
  },
  {
    id: 'other',
    types: [DocumentType.OTHER, DocumentType.UNKNOWN],
  },
];

const getDocumentGroupId = (type: DocumentType): Exclude<DocumentGroupId, 'all'> => {
  const matchedGroup = documentGroups.find((group) => group.types.includes(type));
  return matchedGroup?.id || 'other';
};

const sortDocumentsByDate = (items: Document[]) =>
  [...items].sort(
    (left, right) =>
      new Date(right.created_at).getTime() - new Date(left.created_at).getTime()
  );

/**
 * Extract the document's own date(s) from OCR data for year grouping.
 * - Receipts/invoices: use ocr_result.date
 * - Contracts: use start_date only (NOT the full range — a 25-year loan
 *   would otherwise appear duplicated in every year group)
 * - Fallback: created_at (upload date)
 * Returns an array of years this document belongs to.
 */
const getDocumentYears = (doc: Document): number[] => {
  const ocr = doc.ocr_result as Record<string, any> | undefined;
  const years = new Set<number>();

  if (ocr) {
    // Try document_date or date field
    const dateStr = ocr.document_date || ocr.date;
    if (dateStr && typeof dateStr === 'string') {
      const parsed = new Date(dateStr);
      if (!isNaN(parsed.getTime())) years.add(parsed.getFullYear());
    }

    // For contracts: only use start_date year (not the full span)
    const startStr = ocr.start_date || ocr.lease_start;
    if (startStr && typeof startStr === 'string') {
      const s = new Date(startStr);
      if (!isNaN(s.getTime())) years.add(s.getFullYear());
    }

    // For purchase contracts
    const purchaseDate = ocr.purchase_date;
    if (purchaseDate && typeof purchaseDate === 'string') {
      const p = new Date(purchaseDate);
      if (!isNaN(p.getTime())) years.add(p.getFullYear());
    }
  }

  // Fallback to upload date
  if (years.size === 0) {
    years.add(new Date(doc.created_at).getFullYear());
  }

  return Array.from(years);
};

const groupDocumentsByYear = (items: Document[]): Array<{ year: number; documents: Document[] }> => {
  const yearMap = new Map<number, Document[]>();
  for (const doc of items) {
    const docYears = getDocumentYears(doc);
    for (const year of docYears) {
      if (!yearMap.has(year)) yearMap.set(year, []);
      yearMap.get(year)!.push(doc);
    }
  }
  return Array.from(yearMap.entries())
    .sort(([a], [b]) => b - a)
    .map(([year, documents]) => ({ year, documents }));
};

const DocumentList: React.FC<DocumentListProps> = ({ onDocumentSelect, onSummaryChange }) => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { documents, total, loading, filters, setDocuments, setLoading, setFilters } =
    useDocumentStore();
  const pushMessage = useAIAdvisorStore((s) => s.pushMessage);

  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [activeGroup, setActiveGroup] = useState<DocumentGroupId>('all');
  const [activeYear, setActiveYear] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Document | null>(null);
  const [retryingId, setRetryingId] = useState<number | null>(null);
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const [confirmStage, setConfirmStage] = useState<'idle' | 'confirming'>('idle');
  const [expandedYears, setExpandedYears] = useState<Set<number>>(new Set());
  const locale = getLocaleForLanguage(i18n.resolvedLanguage || i18n.language);

  const loadDocuments = useCallback(async () => {
    try {
      setLoading(true);
      const result = await documentService.getDocuments(filters, page, pageSize);
      setDocuments(result.documents, result.total);
    } catch (error) {
      console.error('Failed to load documents:', error);
    } finally {
      setLoading(false);
    }
  }, [filters, page, pageSize, setDocuments, setLoading]);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  const hasProcessingDocuments = documents.some(
    (doc) => doc.ocr_status === 'processing' || (!doc.processed_at && doc.ocr_status !== 'failed')
  );

  useEffect(() => {
    if (!hasProcessingDocuments) return undefined;

    const intervalId = window.setInterval(() => {
      void loadDocuments();
    }, 5000);

    return () => window.clearInterval(intervalId);
  }, [hasProcessingDocuments, loadDocuments]);

  const handleFilterChange = (key: string, value: string | boolean | undefined) => {
    setFilters({ ...filters, [key]: value });
    setPage(1);
  };

  const handleSearch = (search: string) => {
    setFilters({ ...filters, search });
    setPage(1);
  };

  const handleDocumentClick = (document: Document) => {
    if (onDocumentSelect) {
      onDocumentSelect(document);
      return;
    }

    navigate(`/documents/${document.id}`);
  };

  const handleDownload = async (document: Document, event: React.MouseEvent) => {
    event.stopPropagation();
    try {
      const blob = await documentService.downloadDocument(document.id);
      await saveBlobWithNativeShare(blob, document.file_name, t('documents.download'));
    } catch (error) {
      console.error('Failed to download document:', error);
    }
  };

  const handleDelete = async (document: Document, event: React.MouseEvent) => {
    event.stopPropagation();
    setDeleteTarget(document);
  };

  const handleDeleteConfirm = async (deleteMode: 'document_only' | 'with_data') => {
    if (!deleteTarget) return;
    const deletedName = deleteTarget.file_name;
    setDeleteTarget(null);
    setDeletingId(deleteTarget.id);
    try {
      await documentService.deleteDocument(deleteTarget.id, deleteMode);
      loadDocuments();

      // Push AI feedback after successful deletion
      const tipMsg = t('ai.proactive.deleteSuccess', { name: deletedName });
      const followUp = deleteMode === 'with_data'
        ? t('ai.proactive.deleteWithDataHint')
        : t('ai.proactive.deleteDocOnlyHint');
      pushMessage({ type: 'tip', content: `${tipMsg}\n${followUp}` });
    } catch (error: any) {
      console.error('Failed to delete document:', error);
    } finally {
      setDeletingId(null);
    }
  };

  const handleRetry = async (document: Document, event: React.MouseEvent) => {
    event.stopPropagation();
    if (retryingId) return;
    setRetryingId(document.id);
    try {
      await documentService.retryOcr(document.id);
      aiToast(t('documents.reprocessStarted'), 'success');
      // Poll for completion, then refresh the list
      for (let attempt = 0; attempt < 40; attempt++) {
        await new Promise((r) => setTimeout(r, 1500));
        const updated = await documentService.getDocument(document.id);
        const pipeline = (updated.ocr_result as any)?._pipeline;
        const state = pipeline?.current_state;
        if (!state || state === 'completed' || state === 'phase_2_failed') {
          break;
        }
      }
      await loadDocuments();
    } catch (error) {
      console.error('Failed to retry OCR:', error);
      aiToast(t('documents.reprocessFailed'), 'error');
    } finally {
      setRetryingId(null);
    }
  };

  const isPendingReview = (doc: Document): boolean => {
    const ocr = (doc.ocr_result || {}) as Record<string, any>;
    if (doc.ocr_status === 'failed' || doc.ocr_status === 'processing' || !doc.processed_at) {
      return false;
    }

    return Boolean(doc.needs_review || (doc.ocr_result && !ocr.confirmed));
  };

  const needsConfirmation = (doc: Document): boolean => {
    const ocr = (doc.ocr_result || {}) as Record<string, any>;
    return Boolean(isPendingReview(doc) && doc.ocr_result && !ocr.confirmed);
  };

  const handleReviewClick = async (doc: Document, event: React.MouseEvent) => {
    event.stopPropagation();
    if (confirmStage === 'idle' || confirmingId !== doc.id) {
      // First click: show "confirm?" state
      setConfirmingId(doc.id);
      setConfirmStage('confirming');
      // Auto-reset after 3 seconds if user doesn't click again
      setTimeout(() => {
        setConfirmStage((prev) => {
          if (prev === 'confirming') { setConfirmingId(null); return 'idle'; }
          return prev;
        });
      }, 3000);
    } else {
      // Second click: actually confirm
      setConfirmStage('idle');
      try {
        await documentService.confirmOCR(doc.id);
        aiToast(t('documents.reviewActionSuccess', 'Document reviewed'), 'success');
        loadDocuments();
      } catch {
        aiToast(t('documents.reviewActionFailed', 'Review failed'), 'error');
      } finally {
        setConfirmingId(null);
      }
    }
  };

  const formatDate = (dateString: string) => {
    if (!dateString) return '—';
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return '—';
    return new Intl.DateTimeFormat(locale, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(d);
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatConfidence = (score?: number | null) =>
    score == null ? '-' : `${(score * 100).toFixed(0)}%`;

  const getDocumentTypeLabel = (type: DocumentType) => t(`documents.types.${type}`);

  const getDocumentIconLabel = (document: Document) => {
    const mimeType = document.mime_type || '';
    if (mimeType.startsWith('image/')) return 'IMG';
    if (mimeType === 'application/pdf') return 'PDF';
    return 'DOC';
  };

  const getDocumentStatusInfo = (doc: Document): { label: string; tone: string } => {
    const ocr = (doc.ocr_result || {}) as Record<string, any>;
    const isConfirmed = ocr.confirmed === true;
    const hasTransaction = !!doc.transaction_id;

    // Failed / processing take priority
    if (doc.ocr_status === 'failed') {
      return { label: t('documents.failed'), tone: 'failed' };
    }
    if (doc.ocr_status === 'processing' || !doc.processed_at) {
      return { label: t('documents.status.processing', 'Processing'), tone: 'processing' };
    }

    if (isPendingReview(doc)) {
      return { label: t('documents.status.pendingReview', 'Pending review'), tone: 'pending' };
    }

    // Confirmed states — vary by document type
    const docType = doc.document_type;
    const receiptTypes = ['receipt', 'invoice', 'credit_note', 'gutschrift', 'proforma_invoice', 'delivery_note'];
    const contractTypes = [
      'rental_contract', 'mietvertrag', 'purchase_contract', 'loan_contract',
      'kreditvertrag', 'versicherungsbestaetigung', 'insurance_confirmation',
    ];

    if (receiptTypes.includes(docType)) {
      return { label: t('documents.status.transactionCreated', 'Transaction created'), tone: 'linked' };
    }
    if (contractTypes.includes(docType)) {
      return { label: t('documents.status.contractProcessed', 'Contract processed'), tone: 'linked' };
    }
    if (isConfirmed) {
      return { label: t('documents.status.reviewed', 'Reviewed'), tone: 'ready' };
    }

    // Fallback — has transaction but not explicitly confirmed
    if (hasTransaction) {
      return { label: t('documents.status.transactionCreated', 'Transaction created'), tone: 'linked' };
    }

    return { label: t('documents.status.recognized', 'Recognized'), tone: 'ready' };
  };

  const getStatusLabel = (document: Document) => getDocumentStatusInfo(document).label;
  const getStatusTone = (document: Document) => getDocumentStatusInfo(document).tone;

  const sortedDocuments = sortDocumentsByDate(documents);
  const groupedDocuments = documentGroups.map((group) => ({
    ...group,
    documents: sortedDocuments.filter(
      (document) => getDocumentGroupId(document.document_type) === group.id
    ),
  }));

  const visibleDocuments =
    activeGroup === 'all'
      ? sortedDocuments
      : sortedDocuments.filter(
          (document) => getDocumentGroupId(document.document_type) === activeGroup
        );

  // Compute available years from document dates (OCR) for year filter buttons
  const availableYears = React.useMemo(() => {
    const yearSet = new Set<number>();
    for (const doc of visibleDocuments) {
      for (const y of getDocumentYears(doc)) yearSet.add(y);
    }
    return Array.from(yearSet).sort((a, b) => b - a);
  }, [visibleDocuments]);

  // Apply year filter
  const yearFilteredDocuments = activeYear
    ? visibleDocuments.filter((doc) => getDocumentYears(doc).includes(activeYear))
    : visibleDocuments;

  const activeGroupLabel =
    activeGroup === 'all'
      ? t('documents.groups.all')
      : t(`documents.groups.${activeGroup}`);

  const reviewCount = yearFilteredDocuments.filter((document) => isPendingReview(document)).length;
  const confirmableIds = React.useMemo(
    () => yearFilteredDocuments
      .filter((document) => needsConfirmation(document))
      .map((document) => document.id),
    [yearFilteredDocuments]
  );
  const confirmableIdSignature = confirmableIds.join(',');
  const totalPages = Math.ceil(total / pageSize);

  useEffect(() => {
    onSummaryChange?.({
      totalCount: yearFilteredDocuments.length,
      reviewCount,
      confirmableIds,
    });
  }, [confirmableIdSignature, onSummaryChange, reviewCount, yearFilteredDocuments.length]);

  const renderGridItem = (document: Document) => (
    <div
      key={document.id}
      className={`document-card ${isPendingReview(document) ? 'pending-review-row' : ''}`}
      onClick={() => handleDocumentClick(document)}
    >
      <div className="document-card-top">
        <div className="document-card-icon">{getDocumentIconLabel(document)}</div>
        <span className={`document-status-badge ${getStatusTone(document)}`}>
          {getStatusLabel(document)}
        </span>
      </div>

      <div className="document-card-body">
        <div className="document-name">{document.file_name}</div>
        <div className="document-card-type">
          {getDocumentTypeLabel(document.document_type)}
        </div>
      </div>

      <div className="document-card-meta">
        <span>{formatDate(document.created_at)}</span>
        <span>{formatFileSize(document.file_size)}</span>
        <span>
          {t('documents.confidence')}: {formatConfidence(document.confidence_score)}
        </span>
      </div>

      <div className="document-row-actions document-row-actions-card">
        <div className="document-utility-actions">
          <button
            type="button"
            className="download-btn"
            onClick={(event) => handleDownload(document, event)}
            title={t('documents.download')}
            aria-label={t('documents.download')}
          >
            <DownloadIcon />
          </button>
          <button
            type="button"
            className="delete-btn"
            onClick={(event) => handleDelete(document, event)}
            disabled={deletingId === document.id}
            title={t('common.delete')}
            aria-label={t('common.delete')}
          >
            <DeleteIcon />
          </button>
          {canReprocessDocument(document) && (
            <button
              type="button"
              className="retry-btn"
              onClick={(event) => handleRetry(document, event)}
              disabled={retryingId === document.id}
              title={t('documents.reprocess')}
              aria-label={t('documents.reprocess')}
            >
              <RetryIcon />
            </button>
          )}
          {needsConfirmation(document) && (
            <button
              type="button"
              className={`review-btn ${confirmingId === document.id && confirmStage === 'confirming' ? 'confirm-pulse' : ''}`}
              onClick={(event) => handleReviewClick(document, event)}
              title={confirmingId === document.id && confirmStage === 'confirming'
                ? t('documents.confirmReview', 'Confirm review?')
                : t('documents.reviewAction', 'Review')}
              aria-label={confirmingId === document.id && confirmStage === 'confirming'
                ? t('documents.confirmReview', 'Confirm review?')
                : t('documents.reviewAction', 'Review')}
            >
              {confirmingId === document.id && confirmStage === 'confirming'
                ? <ConfirmReviewIcon />
                : <ReviewIcon />}
            </button>
          )}
        </div>
      </div>
    </div>
  );

  const renderListItem = (document: Document) => (
    <div
      key={document.id}
      className={`document-row ${isPendingReview(document) ? 'pending-review-row' : ''}`}
      onClick={() => handleDocumentClick(document)}
    >
      <div className="document-main-cell">
        <div className="document-icon-small">{getDocumentIconLabel(document)}</div>
        <div className="document-name-stack">
          <div className="document-name">{document.file_name}</div>
          <div className="document-mobile-meta">
            <span>{getDocumentTypeLabel(document.document_type)}</span>
            <span>{formatDate(document.created_at)}</span>
            <span>{formatFileSize(document.file_size)}</span>
            <span>{formatConfidence(document.confidence_score)}</span>
          </div>
        </div>
      </div>

      <div className="document-col document-col-type">
        <span className="document-type-pill">
          {getDocumentTypeLabel(document.document_type)}
        </span>
      </div>

      <div className="document-col document-col-date">{formatDate(document.created_at)}</div>
      <div className="document-col document-col-size">{formatFileSize(document.file_size)}</div>
      <div className="document-col document-col-confidence">
        {formatConfidence(document.confidence_score)}
      </div>

      <div className="document-col document-col-status">
        <span className={`document-status-badge ${getStatusTone(document)}`}>
          {getStatusLabel(document)}
        </span>
      </div>

      <div className="document-row-actions">
        <div className="document-utility-actions">
          <button
            type="button"
            className="download-btn"
            onClick={(event) => handleDownload(document, event)}
            title={t('documents.download')}
            aria-label={t('documents.download')}
          >
            <DownloadIcon />
          </button>
          <button
            type="button"
            className="delete-btn"
            onClick={(event) => handleDelete(document, event)}
            disabled={deletingId === document.id}
            title={t('common.delete')}
            aria-label={t('common.delete')}
          >
            <DeleteIcon />
          </button>
          {canReprocessDocument(document) && (
            <button
              type="button"
              className="retry-btn"
              onClick={(event) => handleRetry(document, event)}
              disabled={retryingId === document.id}
              title={t('documents.reprocess')}
              aria-label={t('documents.reprocess')}
            >
              <RetryIcon />
            </button>
          )}
          {needsConfirmation(document) && (
            <button
              type="button"
              className={`review-btn ${confirmingId === document.id && confirmStage === 'confirming' ? 'confirm-pulse' : ''}`}
              onClick={(event) => handleReviewClick(document, event)}
              title={confirmingId === document.id && confirmStage === 'confirming'
                ? t('documents.confirmReview', 'Confirm review?')
                : t('documents.reviewAction', 'Review')}
              aria-label={confirmingId === document.id && confirmStage === 'confirming'
                ? t('documents.confirmReview', 'Confirm review?')
                : t('documents.reviewAction', 'Review')}
            >
              {confirmingId === document.id && confirmStage === 'confirming'
                ? <ConfirmReviewIcon />
                : <ReviewIcon />}
            </button>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <>
    <div className="document-list">
      <div className="document-toolbar card">
        <div className="list-header">
          <div className="view-toggle">
            <button
              type="button"
              className={viewMode === 'grid' ? 'active' : ''}
              onClick={() => setViewMode('grid')}
              title={t('documents.viewGrid')}
              aria-label={t('documents.viewGrid')}
            >
              <GridIcon />
            </button>
            <button
              type="button"
              className={viewMode === 'list' ? 'active' : ''}
              onClick={() => setViewMode('list')}
              title={t('documents.viewList')}
              aria-label={t('documents.viewList')}
            >
              <ListIcon />
            </button>
          </div>
        </div>

        <div className="document-group-tabs">
          <button
            type="button"
            className={`document-group-tab ${activeGroup === 'all' ? 'active' : ''}`}
            onClick={() => {
              setActiveGroup('all');
              setPage(1);
            }}
          >
            <span>{t('documents.groups.all')}</span>
            <strong>{documents.length}</strong>
          </button>

          {groupedDocuments.map((group) => (
            <button
              key={group.id}
              type="button"
              className={`document-group-tab ${activeGroup === group.id ? 'active' : ''}`}
              onClick={() => {
                setActiveGroup(group.id);
                setPage(1);
              }}
            >
              <span>{t(`documents.groups.${group.id}`)}</span>
              <strong>{group.documents.length}</strong>
            </button>
          ))}
        </div>

        <div className="list-filters">
          <div className="year-filter-tabs">
            <button
              type="button"
              className={`year-filter-tab ${activeYear === null ? 'active' : ''}`}
              onClick={() => { setActiveYear(null); setPage(1); }}
            >
              {t('documents.filters.allYears')}
            </button>
            {availableYears.map((year) => (
              <button
                key={year}
                type="button"
                className={`year-filter-tab ${activeYear === year ? 'active' : ''}`}
                onClick={() => { setActiveYear(year); setPage(1); }}
              >
                {year}
              </button>
            ))}
          </div>

          <div className="document-filters-grid">
            <div className="filter-group">
              <label>{t('documents.filters.startDate')}</label>
              <DateInput
                value={filters.start_date || ''}
                onChange={(val) => handleFilterChange('start_date', val)}
                locale={getLocaleForLanguage(i18n.language)}
                todayLabel={String(t('common.today', 'Today'))}
              />
            </div>

            <div className="filter-group">
              <label>{t('documents.filters.endDate')}</label>
              <DateInput
                value={filters.end_date || ''}
                onChange={(val) => handleFilterChange('end_date', val)}
                locale={getLocaleForLanguage(i18n.language)}
                todayLabel={String(t('common.today', 'Today'))}
              />
            </div>

            <div className="filter-group">
              <label>{t('transactions.type')}</label>
              <Select
                value={filters.document_type || ''}
                onChange={(v) => handleFilterChange('document_type', v || undefined)}
                placeholder={t('documents.filters.allTypes')}
                size="sm"
                options={Object.values(DocumentType)
                  .filter((v) => v !== DocumentType.UNKNOWN)
                  .map((v) => ({ value: v, label: t(`documents.types.${v}`) }))}
              />
            </div>

            <div className="filter-group">
              <label>{t('transactions.deductible', '可抵扣')}</label>
              <Select
                value={filters.is_deductible === undefined ? '' : String(filters.is_deductible)}
                onChange={(v) => handleFilterChange('is_deductible', v === '' ? undefined : v === 'true')}
                placeholder={t('transactions.filters.all')}
                size="sm"
                options={[
                  { value: 'true', label: t('transactions.filters.deductibleOnly') },
                  { value: 'false', label: t('transactions.filters.nonDeductible') },
                ]}
              />
            </div>

            <div className="filter-group">
              <label>{t('transactions.filters.recurring', '定期交易')}</label>
              <Select
                value={filters.is_recurring === undefined ? '' : String(filters.is_recurring)}
                onChange={(v) => handleFilterChange('is_recurring', v === '' ? undefined : v === 'true')}
                placeholder={t('transactions.filters.all')}
                size="sm"
                options={[
                  { value: 'true', label: t('transactions.filters.recurringOnly') },
                  { value: 'false', label: t('transactions.filters.oneTimeOnly') },
                ]}
              />
            </div>

            <div className="filter-group">
              <label>{t('documents.needsReview', '待审核')}</label>
              <Select
                value={filters.needs_review === undefined ? '' : String(filters.needs_review)}
                onChange={(v) => handleFilterChange('needs_review', v === '' ? undefined : v === 'true')}
                placeholder={t('transactions.filters.all')}
                size="sm"
                options={[
                  { value: 'true', label: t('transactions.filters.needsReviewOnly') },
                ]}
              />
            </div>
          </div>

          <div className="document-search-row">
            <div className="filter-group filter-group--full">
              <label>{t('common.search', '搜索')}</label>
              <div className="search-bar">
                <input
                  type="text"
                  placeholder={t('documents.search.placeholder')}
                  value={filters.search || ''}
                  onChange={(event) => handleSearch(event.target.value)}
                />
                <span className="search-icon" aria-hidden="true">
                  <SearchIcon />
                </span>
              </div>
            </div>
          </div>

          <div className="document-filter-actions">
            <button className="btn btn-secondary" onClick={() => { setFilters({}); setPage(1); }}>
              {t('documents.filters.clear', '清除')}
            </button>
            <button className="btn btn-primary" onClick={() => loadDocuments()}>
              {t('documents.filters.apply', '应用')}
            </button>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="loading-state">
          <div className="spinner"></div>
          <p>{t('common.loading')}</p>
        </div>
      ) : documents.length === 0 ? (
        <div className="empty-state">
          <p>{t('documents.empty')}</p>
        </div>
      ) : yearFilteredDocuments.length === 0 ? (
        <div className="empty-state">
          <p>{t('documents.emptyGroup')}</p>
        </div>
      ) : (
        <>
          <section className="document-table-shell">
            <div className="document-table-header">
              <div className="document-table-heading">
                <span className="document-table-eyebrow">{t('documents.title')}</span>
                <h3>{activeGroupLabel}</h3>
              </div>
              <div className="document-table-meta">
                <Select value={String(pageSize)} onChange={v => { setPageSize(Number(v)); setPage(1); }}
                  aria-label={t('documents.pageSize')} size="sm"
                  options={PAGE_SIZE_OPTIONS.map(s => ({ value: String(s), label: `${s} ${t('documents.perPage')}` }))} />
              </div>
            </div>

            {groupDocumentsByYear(yearFilteredDocuments).map((yearGroup) => {
              const isCollapsed = !expandedYears.has(yearGroup.year);
              return (
              <div key={yearGroup.year} className="document-year-group">
                <button
                  type="button"
                  className="document-year-header document-year-header--toggle"
                  onClick={() => setExpandedYears(prev => {
                    const next = new Set(prev);
                    if (next.has(yearGroup.year)) next.delete(yearGroup.year);
                    else next.add(yearGroup.year);
                    return next;
                  })}
                  aria-expanded={!isCollapsed}
                >
                  <span className={`document-year-chevron ${isCollapsed ? "" : "document-year-chevron--open"}`}>&#9654;</span>
                  <h4>{yearGroup.year}</h4>
                  <span className="document-year-count">{yearGroup.documents.length}</span>
                </button>

                {!isCollapsed && (viewMode === 'list' ? (
                  <>
                    <div className="document-table-head">
                      <span>{t('documents.list.name')}</span>
                      <span>{t('documents.list.type')}</span>
                      <span>{t('documents.list.uploadDate')}</span>
                      <span>{t('documents.list.size')}</span>
                      <span>{t('documents.list.confidence')}</span>
                      <span>{t('documents.list.status')}</span>
                      <span>{t('documents.actions')}</span>
                    </div>
                    <div className="documents-list">{yearGroup.documents.map(renderListItem)}</div>
                  </>
                ) : (
                  <div className="documents-grid">{yearGroup.documents.map(renderGridItem)}</div>
                ))}
              </div>
              );
            })}
          </section>

          {totalPages > 1 && (
            <div className="pagination">
              <button type="button" onClick={() => setPage(page - 1)} disabled={page === 1}>
                {t('common.previous')}
              </button>
              <span>
                {t('common.page')} {page} {t('common.of')} {totalPages}
              </span>
              <button
                type="button"
                onClick={() => setPage(page + 1)}
                disabled={page === totalPages}
              >
                {t('common.next')}
              </button>
            </div>
          )}
        </>
      )}
    </div>

    {deleteTarget && (
      <DeleteDocumentDialog
        documentId={deleteTarget.id}
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
      />
    )}
    </>
  );
};

export default DocumentList;
