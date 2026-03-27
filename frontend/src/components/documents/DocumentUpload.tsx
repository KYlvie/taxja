import React, { useCallback, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Camera, FolderUp, ScanSearch, GripVertical, Trash2, Layers, Upload, X } from 'lucide-react';
import { documentService } from '../../services/documentService';
import { employerService } from '../../services/employerService';
import { getLocaleForLanguage } from '../../utils/locale';
import { useDocumentStore } from '../../stores/documentStore';
import { useAIAdvisorStore } from '../../stores/aiAdvisorStore';
import { useAuthStore } from '../../stores/authStore';
import { useRefreshStore } from '../../stores/refreshStore';
import { Document, UploadProgress } from '../../types/document';
import {
  capturePhotoAsFile,
  pickNativeFiles,
  supportsNativeFileActions,
} from '../../mobile/files';
import {
  buildUploadEntries,
  buildMergedEntry,
  shouldStageFiles,
  sortFilesByName,
} from '../../utils/documentUploadGrouping';
import './DocumentUpload.css';

const createUploadLocalId = () =>
  `upload-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

const DOCUMENT_PICKER_TYPES = ['image/*', 'application/pdf'];
const EMPLOYER_ELIGIBLE_USER_TYPES = new Set(['self_employed', 'mixed']);

const shouldEnableEmployerDetection = (
  user?: { user_type?: string; employer_mode?: string | null } | null
) =>
  Boolean(
    user &&
      user.employer_mode &&
      user.employer_mode !== 'none' &&
      user.user_type &&
      EMPLOYER_ELIGIBLE_USER_TYPES.has(user.user_type)
  );

const parseDocumentOcrResult = (document: Partial<Document> | null | undefined) => {
  if (!document?.ocr_result) return null;
  if (typeof document.ocr_result === 'string') {
    try {
      return JSON.parse(document.ocr_result) as Record<string, any>;
    } catch {
      return null;
    }
  }
  return document.ocr_result as Record<string, any>;
};

const getDocumentPollingState = (document: Partial<Document> | null | undefined) => {
  const ocrData = parseDocumentOcrResult(document);
  const pipelineState = ocrData?._pipeline?.current_state;
  const ocrStatus = document?.ocr_status;
  const isTerminal = Boolean(
    document?.processed_at
      || ocrStatus === 'completed'
      || ocrStatus === 'failed'
      || pipelineState === 'completed'
      || pipelineState === 'phase_2_failed'
  );
  const hasSnapshot = Boolean(
    ocrData
      || (document?.confidence_score ?? 0) > 0
      || ocrStatus
      || pipelineState
      || document?.processed_at
  );

  return { ocrData, isTerminal, hasSnapshot };
};

interface StagedFile {
  id: string;
  file: File;
  previewUrl: string;
}

interface DocumentUploadProps {
  propertyId?: string | null;
  onDocumentsSubmitted?: (documents: Document[]) => void;
}

const DocumentUpload: React.FC<DocumentUploadProps> = ({ propertyId, onDocumentsSubmitted }) => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploads, setUploads] = useState<UploadProgress[]>([]);
  const [pickerError, setPickerError] = useState<string | null>(null);
  const [capturedPages, setCapturedPages] = useState<File[]>([]);
  const [stagedFiles, setStagedFiles] = useState<StagedFile[]>([]);
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
  const addDocument = useDocumentStore((state) => state.addDocument);
  const pushAIMessage = useAIAdvisorStore((s) => s.pushMessage);
  const pushSuggestionMessage = useAIAdvisorStore((s) => s.pushSuggestionMessage);
  const pushFollowUpMessage = useAIAdvisorStore((s) => s.pushFollowUpMessage);
  const pushProcessingMessage = useAIAdvisorStore((s) => s.pushProcessingMessage);
  const removeProcessingMessage = useAIAdvisorStore((s) => s.removeProcessingMessage);
  const currentUser = useAuthStore((state) => state.user);
  const nativeActionsEnabled = useMemo(() => supportsNativeFileActions(), []);

  const updateUploadById = useCallback(
    (localId: string, updater: (upload: UploadProgress) => UploadProgress) => {
      setUploads((previous) =>
        previous.map((upload) => (upload.local_id === localId ? updater(upload) : upload))
      );
    },
    []
  );

  const getDocumentLink = useCallback(
    (documentId?: number | null) => (documentId ? `/documents/${documentId}` : undefined),
    []
  );

  const handleCompletedUploadOpen = useCallback(
    (documentId?: number | null) => {
      const link = getDocumentLink(documentId);
      if (link) {
        navigate(link);
      }
    },
    [getDocumentLink, navigate]
  );

  // --- Staging area helpers ---

  const addToStaging = useCallback((files: File[]) => {
    const sorted = sortFilesByName(files);
    const newStaged: StagedFile[] = sorted.map((file) => ({
      id: `${file.name}-${file.size}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      file,
      previewUrl: URL.createObjectURL(file),
    }));
    setStagedFiles((prev) => [...prev, ...newStaged]);
  }, []);

  const clearStaging = useCallback(() => {
    stagedFiles.forEach((sf) => URL.revokeObjectURL(sf.previewUrl));
    setStagedFiles([]);
  }, [stagedFiles]);

  const removeStagedFile = useCallback((id: string) => {
    setStagedFiles((prev) => {
      const removed = prev.find((sf) => sf.id === id);
      if (removed) URL.revokeObjectURL(removed.previewUrl);
      return prev.filter((sf) => sf.id !== id);
    });
  }, []);

  // Drag-to-reorder handlers for staging thumbnails
  const handleStageDragStart = useCallback((index: number) => {
    setDraggedIndex(index);
  }, []);

  const handleStageDragOver = useCallback((e: React.DragEvent, index: number) => {
    e.preventDefault();
    setDragOverIndex(index);
  }, []);

  const handleStageDrop = useCallback((targetIndex: number) => {
    if (draggedIndex === null || draggedIndex === targetIndex) {
      setDraggedIndex(null);
      setDragOverIndex(null);
      return;
    }
    setStagedFiles((prev) => {
      const next = [...prev];
      const [moved] = next.splice(draggedIndex, 1);
      next.splice(targetIndex, 0, moved);
      return next;
    });
    setDraggedIndex(null);
    setDragOverIndex(null);
  }, [draggedIndex]);

  const handleStageDragEnd = useCallback(() => {
    setDraggedIndex(null);
    setDragOverIndex(null);
  }, []);

  // --- Poll for OCR processing (unchanged logic) ---

  const pollForProcessing = useCallback(
    async (documentId: number, uploadLocalId: string, fallbackDocument: any) => {
      let latestDocument = fallbackDocument;

      // Task 14: Push processing indicator to chat panel
      pushProcessingMessage({
        idempotencyKey: `${documentId}:none:processing_phase_1`,
        type: 'processing_update',
        documentId,
        phase: 'ocr',
        message: t('ai.processing.analyzing', 'Analyzing your document...'),
        uiState: 'processing',
      });

      for (let attempt = 0; attempt < 60; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 3000));

        try {
          const updatedDocument = await documentService.getDocument(documentId);
          const resolvedDocument = fallbackDocument?.deduplicated
            ? {
                ...updatedDocument,
                deduplicated: true,
                duplicate_of_document_id: fallbackDocument.duplicate_of_document_id,
                message: fallbackDocument.message,
              }
            : updatedDocument;
          latestDocument = resolvedDocument;
          const { ocrData, isTerminal, hasSnapshot } = getDocumentPollingState(updatedDocument);

          if (hasSnapshot) {
            updateUploadById(uploadLocalId, (upload) => ({
              ...upload,
              status: isTerminal ? 'completed' : 'processing',
              document: resolvedDocument,
            }));
            addDocument(resolvedDocument);
          }

          if (isTerminal) {
            // Proactive AI notification
            const fileName = resolvedDocument.file_name || `#${documentId}`;
            const suggestion = ocrData?.import_suggestion;
            let handledPrimaryNotification = Boolean(resolvedDocument.deduplicated);
            let employerMonthPrompted = false;

            if (resolvedDocument.deduplicated) {
              pushAIMessage({
                type: 'upload_success',
                content: t('ai.proactive.duplicateUploadReused', {
                  name: fileName,
                }),
                link: getDocumentLink(documentId),
                linkLabel: t('ai.proactive.viewDocument', 'View document'),
              });
            }

            // Multi-receipt notification
            const receiptCount = ocrData?._receipt_count;
            if (receiptCount && receiptCount > 1) {
              pushAIMessage({
                type: 'upload_success',
                content: t('ai.proactive.multiReceiptDetected', { count: receiptCount, name: fileName }),
                link: getDocumentLink(documentId),
                linkLabel: t('ai.proactive.viewDocument', 'View document'),
              });
            }

            // Refresh stores when backend auto-created data from contract/receipt
            if (suggestion) {
              const { refreshProperties, refreshRecurring, refreshTransactions, refreshDashboard } =
                useRefreshStore.getState();

              if (suggestion.status === 'auto-created' || suggestion.status === 'confirmed') {
                if (suggestion.type === 'create_property') {
                  refreshProperties();
                  refreshRecurring();
                  refreshDashboard();
                  const d = suggestion.data || {};
                  pushAIMessage({
                    type: 'upload_success',
                    content: t('ai.proactive.propertyAutoCreated', {
                      address: d.address || ocrData?.property_address || fileName,
                      price: d.purchase_price || ocrData?.purchase_price || '?',
                    }),
                    link: '/properties',
                    secondaryLink: getDocumentLink(documentId),
                    secondaryLinkLabel: t('ai.proactive.viewDocument', 'View document'),
                  });
                } else if (suggestion.type === 'create_recurring_income') {
                  refreshProperties();
                  refreshRecurring();
                  refreshDashboard();
                  const d = suggestion.data || {};
                  pushAIMessage({
                    type: 'upload_success',
                    content: t('ai.proactive.recurringAutoCreated', {
                      address: d.address || d.matched_property_address || ocrData?.property_address || fileName,
                      rent: d.monthly_rent || ocrData?.monthly_rent || '?',
                    }),
                    link: '/recurring',
                    secondaryLink: getDocumentLink(documentId),
                    secondaryLinkLabel: t('ai.proactive.viewDocument', 'View document'),
                  });
                }
                if (suggestion.type === 'create_transaction' || suggestion.type === 'create_recurring_expense') {
                  refreshTransactions();
                  refreshRecurring();
                  refreshDashboard();
                }
              }

              // Also refresh when transactions were auto-created from receipts/invoices
              if (updatedDocument.transaction_id) {
                refreshTransactions();
                refreshDashboard();
                pushAIMessage({
                  type: 'upload_success',
                  content: t('ai.proactive.transactionAutoCreated'),
                  link: '/transactions',
                  secondaryLink: getDocumentLink(documentId),
                  secondaryLinkLabel: t('ai.proactive.viewDocument', 'View document'),
                });
              }
            }

            if (suggestion?.type === 'create_recurring_income' && suggestion?.status === 'pending') {
              handledPrimaryNotification = true;
              const d = suggestion.data;
              const addr = d.address || d.matched_property_address || '';

              if (d.no_property_match) {
                pushAIMessage({
                  type: 'recurring_confirm',
                  content: t('ai.proactive.recurringNoProperty', {
                    address: addr,
                    rent: d.monthly_rent,
                  }),
                  documentId: documentId,
                  actionData: { ...d, suggestion_type: 'create_recurring_income' },
                  actionStatus: 'pending',
                  link: getDocumentLink(documentId),
                  linkLabel: t('ai.proactive.viewDocument', 'View document'),
                });
              } else if (d.is_partial_match) {
                pushAIMessage({
                  type: 'recurring_confirm',
                  content: t('ai.proactive.recurringPartialMatch', {
                    rentalAddress: addr,
                    propertyAddress: d.matched_property_address || '',
                  }),
                  documentId: documentId,
                  actionData: { ...d, suggestion_type: 'create_recurring_income' },
                  actionStatus: 'pending',
                  link: getDocumentLink(documentId),
                  linkLabel: t('ai.proactive.viewDocument', 'View document'),
                });
              } else {
                pushAIMessage({
                  type: 'recurring_confirm',
                  content: t('ai.proactive.recurringFound', {
                    rent: d.monthly_rent,
                    address: addr,
                  }),
                  documentId: documentId,
                  actionData: { ...d, suggestion_type: 'create_recurring_income' },
                  actionStatus: 'pending',
                  link: getDocumentLink(documentId),
                  linkLabel: t('ai.proactive.viewDocument', 'View document'),
                });
              }
            } else if (suggestion?.type === 'create_recurring_expense' && suggestion?.status === 'pending') {
              handledPrimaryNotification = true;
              const d = suggestion.data;
              pushAIMessage({
                type: 'recurring_confirm',
                content: t('ai.proactive.recurringExpenseFound', {
                  description: d.description || fileName,
                  amount: d.amount,
                  frequency: t(`recurring.frequency.${d.frequency || 'monthly'}`),
                }),
                documentId: documentId,
                actionData: { ...d, suggestion_type: 'create_recurring_expense' },
                actionStatus: 'pending',
                link: getDocumentLink(documentId),
                linkLabel: t('ai.proactive.viewDocument', 'View document'),
              });
            } else if (suggestion?.type === 'create_asset' && suggestion?.status === 'pending') {
              handledPrimaryNotification = true;
              const d = suggestion.data;
              pushAIMessage({
                type: 'asset_confirm',
                content: t('ai.proactive.assetFound', {
                  name: d.name || d.asset_type,
                  price: d.purchase_price,
                }),
                documentId: documentId,
                link: getDocumentLink(documentId),
                linkLabel: t('ai.proactive.viewDocument', 'View document'),
              });
            } else if (suggestion?.status === 'pending' && suggestion?.type?.startsWith('import_')) {
              handledPrimaryNotification = true;
              const formData = suggestion.data || {};
              const summaryParts: string[] = [];
              if (formData.kz_245) summaryParts.push(`${t('taxFiling.kz.kz_245', 'KZ245')}: €${Number(formData.kz_245).toLocaleString(getLocaleForLanguage(i18n.language), { minimumFractionDigits: 2 })}`);
              if (formData.kz_260) summaryParts.push(`${t('taxFiling.kz.kz_260', 'KZ260')}: €${Number(formData.kz_260).toLocaleString(getLocaleForLanguage(i18n.language), { minimumFractionDigits: 2 })}`);
              if (formData.betriebseinnahmen) summaryParts.push(`${t('taxFiling.fields.betriebseinnahmen', 'Revenue')}: €${Number(formData.betriebseinnahmen).toLocaleString(getLocaleForLanguage(i18n.language), { minimumFractionDigits: 2 })}`);
              if (formData.gewinn_verlust != null) summaryParts.push(`${t('taxFiling.fields.gewinnVerlust', 'Profit/Loss')}: €${Number(formData.gewinn_verlust).toLocaleString(getLocaleForLanguage(i18n.language), { minimumFractionDigits: 2 })}`);
              if (formData.mieteinnahmen) summaryParts.push(`${t('taxFiling.fields.mieteinnahmen', 'Rental income')}: €${Number(formData.mieteinnahmen).toLocaleString(getLocaleForLanguage(i18n.language), { minimumFractionDigits: 2 })}`);
              if (formData.gesamtumsatz) summaryParts.push(`${t('taxFiling.fields.gesamtumsatz', 'Total revenue')}: €${Number(formData.gesamtumsatz).toLocaleString(getLocaleForLanguage(i18n.language), { minimumFractionDigits: 2 })}`);
              if (formData.zahllast != null) summaryParts.push(`${t('taxFiling.fields.zahllast', 'VAT payable')}: €${Number(formData.zahllast).toLocaleString(getLocaleForLanguage(i18n.language), { minimumFractionDigits: 2 })}`);
              if (formData.total_amount) summaryParts.push(`${t('taxFiling.fields.totalAmount', 'Total')}: €${Number(formData.total_amount).toLocaleString(getLocaleForLanguage(i18n.language), { minimumFractionDigits: 2 })}`);
              if (formData.transaction_count) summaryParts.push(`${t('taxFiling.fields.transactionCount', 'Transactions')}: ${formData.transaction_count}`);
              if (formData.kapitalertraege) summaryParts.push(`${t('taxFiling.fields.kapitalertraege', 'Capital income')}: €${Number(formData.kapitalertraege).toLocaleString(getLocaleForLanguage(i18n.language), { minimumFractionDigits: 2 })}`);

              pushAIMessage({
                type: 'tax_form_review',
                content: t('ai.proactive.taxFormDetected', { name: fileName }),
                documentId: documentId,
                link: getDocumentLink(documentId),
                linkLabel: t('ai.proactive.viewDocument', 'View document'),
                actionData: {
                  suggestion_type: suggestion.type,
                  tax_year: formData.tax_year,
                  summary: summaryParts.join('\n'),
                  file_name: fileName,
                },
                actionStatus: 'pending',
              });
            }

            if (!handledPrimaryNotification && shouldEnableEmployerDetection(currentUser)) {
              try {
                const employerDetection = await employerService.detectFromDocument(documentId);
                if (employerDetection.detected && employerDetection.month) {
                  employerMonthPrompted = true;
                  pushAIMessage({
                    type: 'employer_month_confirm',
                    content: t('ai.proactive.employerMonthDetected', {
                      defaultValue:
                        'I found a payroll document in "{{name}}" for {{month}}. Should I record this month as having employees?',
                      name: fileName,
                      month: employerDetection.month.year_month,
                    }),
                    documentId,
                    actionData: {
                      year_month: employerDetection.month.year_month,
                      payroll_signal: employerDetection.month.payroll_signal || 'payslip',
                      file_name: fileName,
                      employee_count: employerDetection.month.employee_count,
                      gross_wages: employerDetection.month.gross_wages,
                      net_paid: employerDetection.month.net_paid,
                      lohnsteuer: employerDetection.month.lohnsteuer,
                    },
                    actionStatus: 'pending',
                    link: getDocumentLink(documentId),
                    linkLabel: t('ai.proactive.viewDocument', 'View document'),
                  });
                } else if (employerDetection.reason === 'not_monthly_payroll_document') {
                  const annualDetection = await employerService.detectAnnualArchiveFromDocument(documentId);
                  if (annualDetection.detected && annualDetection.archive) {
                    employerMonthPrompted = true;
                    pushAIMessage({
                      type: 'employer_annual_archive_confirm',
                      content: t('ai.proactive.employerAnnualArchiveDetected', {
                        defaultValue:
                          'This looks like an annual payroll document for {{year}}. Should I archive it as the historical payroll pack?',
                        year: annualDetection.archive.tax_year,
                      }),
                      documentId,
                      actionData: {
                        tax_year: annualDetection.archive.tax_year,
                        archive_signal: annualDetection.archive.archive_signal || 'lohnzettel',
                        file_name: fileName,
                        employer_name: annualDetection.archive.employer_name,
                        gross_income: annualDetection.archive.gross_income,
                        withheld_tax: annualDetection.archive.withheld_tax,
                      },
                      actionStatus: 'pending',
                      link: getDocumentLink(documentId),
                      linkLabel: t('ai.proactive.viewDocument', 'View document'),
                    });
                  }
                }
              } catch {
                // Employer-month detection is best-effort and should not block uploads.
              }
            }

            if (!handledPrimaryNotification && !employerMonthPrompted && updatedDocument.needs_review) {
              pushAIMessage({
                type: 'upload_review',
                content: t('ai.proactive.uploadNeedsReview', { name: fileName }),
                link: getDocumentLink(documentId),
                linkLabel: t('ai.proactive.viewDocument', 'View document'),
              });
            } else if (
              !handledPrimaryNotification &&
              !employerMonthPrompted &&
              (!receiptCount || receiptCount <= 1) &&
              !(suggestion?.status === 'auto-created' && (suggestion?.type === 'create_property' || suggestion?.type === 'create_recurring_income'))
            ) {
              pushAIMessage({
                type: 'upload_success',
                content: t('ai.proactive.uploadSuccess', { name: fileName }),
                link: getDocumentLink(documentId),
                linkLabel: t('ai.proactive.viewDocument', 'View document'),
              });
            }

            // ================================================================
            // Task 14: Push structured messages to chat panel
            // Chat is primary surface — suggestion enters chat first.
            // Documents page SuggestionCard renders from same backend data (secondary).
            // ================================================================
            removeProcessingMessage(documentId);

            if (suggestion && suggestion.status === 'pending') {
              // Bug #6 fix: Get backend-generated idempotencyKey + action descriptor
              // instead of self-generating. Backend is source of truth (NFR-7).
              let backendKey = `${documentId}:${suggestion.type || 'none'}:completed`; // fallback
              let backendAction: any = null;
              try {
                const processStatus = await documentService.getProcessStatus(documentId);
                if (processStatus.idempotency_key) {
                  backendKey = processStatus.idempotency_key;
                }
                if (processStatus.action) {
                  backendAction = {
                    kind: processStatus.action.kind as any,
                    targetId: processStatus.action.target_id,
                    endpoint: processStatus.action.endpoint,
                    method: processStatus.action.method || 'POST',
                    confirmLabel: processStatus.action.confirm_label,
                    dismissLabel: processStatus.action.dismiss_label,
                  };
                }
              } catch {
                // Fallback: use self-generated key if process-status fails
              }

              const suggestionType = suggestion.type || '';
              const suggestionData = suggestion.data || {};
              const followUpQuestions = suggestion.follow_up_questions || [];
              const hasFollowUps = followUpQuestions.length > 0;

              // Fallback action descriptor if backend didn't provide one
              if (!backendAction) {
                const actionKindMap: Record<string, string> = {
                  create_property: 'confirm_property',
                  create_asset: 'confirm_asset',
                  create_recurring_income: 'confirm_recurring',
                  create_recurring_expense: 'confirm_recurring_expense',
                  create_loan: 'confirm_loan',
                  create_loan_repayment: 'confirm_loan_repayment',
                };
                const actionEndpointMap: Record<string, string> = {
                  create_property: 'confirm-property',
                  create_asset: 'confirm-asset',
                  create_recurring_income: 'confirm-recurring',
                  create_recurring_expense: 'confirm-recurring-expense',
                  create_loan: 'confirm-loan',
                  create_loan_repayment: 'confirm-loan-repayment',
                };
                const isImport = suggestionType.startsWith('import_');
                const actionKind = isImport ? 'confirm_tax_data' : (actionKindMap[suggestionType] || suggestionType);
                const actionSuffix = isImport ? 'confirm-tax-data' : (actionEndpointMap[suggestionType] || suggestionType);
                backendAction = {
                  kind: actionKind as any,
                  targetId: String(documentId),
                  endpoint: `/api/v1/documents/${documentId}/${actionSuffix}`,
                  method: 'POST',
                };
              }

              pushSuggestionMessage({
                idempotencyKey: backendKey,
                type: 'suggestion',
                suggestionType,
                documentId,
                extractedData: suggestionData,
                followUpQuestions: followUpQuestions as any,
                status: hasFollowUps ? 'needs_input' : 'pending',
                suggestionVersion: suggestion.version || 0,
                action: backendAction,
              });

              // Push follow-up questions as separate chat message
              if (hasFollowUps) {
                pushFollowUpMessage({
                  idempotencyKey: `${backendKey}:follow_up`,
                  type: 'follow_up',
                  documentId,
                  questions: followUpQuestions.map((q: any) => ({
                    id: q.id,
                    question: q.question,
                    inputType: q.input_type,
                    options: q.options,
                    defaultValue: q.default_value,
                    required: q.required ?? true,
                    fieldKey: q.field_key,
                    helpText: q.help_text,
                    validation: q.validation,
                  })),
                  suggestionVersion: suggestion.version || 0,
                });
              }
            }

            onDocumentsSubmitted?.([resolvedDocument as Document]);
            return;
          }
        } catch {
          // Ignore intermittent polling issues and keep waiting.
        }
      }

      // Polling timeout reached — cleanup processing indicator
      removeProcessingMessage(documentId);

      updateUploadById(uploadLocalId, (upload) => ({
        ...upload,
        status: 'error',
        document: latestDocument,
        error: t(
          'documents.reprocessTimeout',
          'Reprocessing is taking too long. Please try again later.'
        ),
      }));
      addDocument(latestDocument);
    },
    [
      addDocument,
      currentUser,
      onDocumentsSubmitted,
      pushAIMessage,
      pushSuggestionMessage,
      pushFollowUpMessage,
      pushProcessingMessage,
      removeProcessingMessage,
      t,
      updateUploadById,
    ]
  );

  // --- Upload execution ---

  const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB

  const queueEntries = useCallback(
    async (sourceFiles: File[]) => {
      // Client-side file size validation
      const oversizedFiles = sourceFiles.filter((f) => f.size > MAX_FILE_SIZE);
      if (oversizedFiles.length > 0) {
        setPickerError(
          oversizedFiles
            .map((f) => t('documents.upload.fileTooLarge', { name: f.name }))
            .join('\n')
        );
        return;
      }

      const entries = buildUploadEntries(sourceFiles);
      if (entries.length === 0) {
        return;
      }

      setPickerError(null);
      const queuedUploads: UploadProgress[] = entries.map((entry) => ({
        local_id: createUploadLocalId(),
        file: entry.displayFile,
        source_files: entry.sourceFiles,
        upload_mode: entry.uploadMode,
        page_count: entry.pageCount,
        progress: 0,
        status: 'pending',
      }));

      const submittedDocuments: Document[] = [];
      setUploads((previous) => [...previous, ...queuedUploads]);

      for (const [offset, entry] of entries.entries()) {
        const uploadLocalId = queuedUploads[offset].local_id!;
        const displayName = entry.displayFile.name;

        try {
          updateUploadById(uploadLocalId, (upload) => ({ ...upload, status: 'uploading' }));

          const updateProgress = (progress: number) => {
            updateUploadById(uploadLocalId, (upload) => ({ ...upload, progress }));
          };

          const document =
            entry.uploadMode === 'image_group'
              ? await documentService.uploadImageGroup(entry.sourceFiles, updateProgress, propertyId || undefined)
              : await documentService.uploadDocument(entry.sourceFiles[0], updateProgress, propertyId || undefined);

          const duplicateReusedWithoutRestart =
            Boolean((document as any)?.deduplicated) &&
            !String((document as any)?.message || '').toLowerCase().includes('restarted');

          if (duplicateReusedWithoutRestart) {
            let existingDocument: any = {
              ...document,
              deduplicated: true,
            };

            try {
              const detailedDocument = await documentService.getDocument(document.id);
              existingDocument = {
                ...detailedDocument,
                deduplicated: true,
                duplicate_of_document_id: (document as any).duplicate_of_document_id,
                message: (document as any).message,
              };
            } catch {
              // Keep the upload response as a minimal fallback.
            }

            updateUploadById(uploadLocalId, (upload) => ({
              ...upload,
              status: 'completed',
              progress: 100,
              document: existingDocument,
            }));

            addDocument(existingDocument);
            submittedDocuments.push(existingDocument as Document);
            pushAIMessage({
              type: 'upload_success',
              content: t('ai.proactive.duplicateUploadReused', {
                name: displayName,
              }),
                link: getDocumentLink(document.id),
                linkLabel: t('ai.proactive.viewDocument', 'View document'),
            });
            continue;
          }

          updateUploadById(uploadLocalId, (upload) => ({
            ...upload,
            status: 'processing',
            progress: 100,
            document,
          }));

          submittedDocuments.push(document as Document);
          void pollForProcessing(document.id, uploadLocalId, document);
        } catch (error: any) {
          updateUploadById(uploadLocalId, (upload) => ({
            ...upload,
            status: 'error',
            error: error.response?.data?.detail || t('documents.upload.error'),
          }));

          pushAIMessage({
            type: 'upload_error',
            content: t('ai.proactive.uploadError', { name: displayName }),
          });
        }
      }

      if (submittedDocuments.length > 0) {
        onDocumentsSubmitted?.(submittedDocuments);
      }
    },
    [addDocument, getDocumentLink, onDocumentsSubmitted, pollForProcessing, propertyId, pushAIMessage, t, updateUploadById]
  );

  /** Upload from staging: merge all staged files into one document */
  const uploadStagedMerged = useCallback(() => {
    if (stagedFiles.length < 2) return;
    const files = stagedFiles.map((sf) => sf.file);
    const entry = buildMergedEntry(files);
    clearStaging();

    // Directly queue the merged entry
    const queueMerged = async () => {
      setPickerError(null);
      const queuedUpload: UploadProgress = {
        local_id: createUploadLocalId(),
        file: entry.displayFile,
        source_files: entry.sourceFiles,
        upload_mode: entry.uploadMode,
        page_count: entry.pageCount,
        progress: 0,
        status: 'pending',
      };

      const uploadLocalId = queuedUpload.local_id!;
      setUploads((prev) => [...prev, queuedUpload]);

      try {
        updateUploadById(uploadLocalId, (u) => ({ ...u, status: 'uploading' }));

        const updateProgress = (progress: number) => {
          updateUploadById(uploadLocalId, (u) => ({ ...u, progress }));
        };

        const document = await documentService.uploadImageGroup(
          entry.sourceFiles,
          updateProgress,
          propertyId || undefined
        );

        const duplicateReusedWithoutRestart =
          Boolean((document as any)?.deduplicated) &&
          !String((document as any)?.message || '').toLowerCase().includes('restarted');

        if (duplicateReusedWithoutRestart) {
          let existingDocument: any = { ...document, deduplicated: true };
          try {
            const detailed = await documentService.getDocument(document.id);
            existingDocument = {
              ...detailed,
              deduplicated: true,
              duplicate_of_document_id: (document as any).duplicate_of_document_id,
              message: (document as any).message,
            };
          } catch { /* fallback */ }

          updateUploadById(uploadLocalId, (u) => ({
            ...u,
            status: 'completed',
            progress: 100,
            document: existingDocument,
          }));
          addDocument(existingDocument);
          onDocumentsSubmitted?.([existingDocument as Document]);
          pushAIMessage({
            type: 'upload_success',
            content: t('ai.proactive.duplicateUploadReused', {
              name: entry.displayFile.name,
            }),
                link: getDocumentLink(document.id),
                linkLabel: t('ai.proactive.viewDocument', 'View document'),
          });
          return;
        }

        updateUploadById(uploadLocalId, (u) => ({
          ...u,
          status: 'processing',
          progress: 100,
          document,
        }));
        onDocumentsSubmitted?.([document as Document]);
        void pollForProcessing(document.id, uploadLocalId, document);
      } catch (error: any) {
        updateUploadById(uploadLocalId, (u) => ({
          ...u,
          status: 'error',
          error: error.response?.data?.detail || t('documents.upload.error'),
        }));
        pushAIMessage({
          type: 'upload_error',
          content: t('ai.proactive.uploadError', { name: entry.displayFile.name }),
        });
      }
    };

    void queueMerged();
  }, [stagedFiles, clearStaging, propertyId, pollForProcessing, pushAIMessage, t, addDocument, onDocumentsSubmitted, getDocumentLink, updateUploadById]);

  /** Upload from staging: each file as a separate document */
  const uploadStagedIndividually = useCallback(() => {
    if (stagedFiles.length === 0) return;
    const files = stagedFiles.map((sf) => sf.file);
    clearStaging();
    void queueEntries(files);
  }, [stagedFiles, clearStaging, queueEntries]);

  // --- File input handlers ---

  const handleFileList = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0) return;

      const fileArray = Array.from(files);

      // If 2+ images: go to staging area instead of immediate upload
      if (shouldStageFiles(fileArray)) {
        addToStaging(fileArray);
        return;
      }

      await queueEntries(fileArray);
    },
    [queueEntries, addToStaging]
  );

  const handleNativeFilePicker = useCallback(async () => {
    try {
      const files = await pickNativeFiles(DOCUMENT_PICKER_TYPES);

      if (shouldStageFiles(files)) {
        addToStaging(files);
        return;
      }

      await queueEntries(files);
    } catch (error: any) {
      const message = String(error?.message || '').toLowerCase();
      if (message.includes('cancel')) return;
      setPickerError(t('documents.upload.error'));
    }
  }, [queueEntries, addToStaging, t]);

  const handleCameraCapture = useCallback(async () => {
    try {
      const file = await capturePhotoAsFile();
      if (file) {
        setCapturedPages((previous) => [...previous, file]);
      }
    } catch (error: any) {
      const message = String(error?.message || '').toLowerCase();
      if (message.includes('cancel')) return;
      setPickerError(t('documents.upload.error'));
    }
  }, [t]);

  const handleDragEnter = (event: React.DragEvent) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (event: React.DragEvent) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (event: React.DragEvent) => {
    event.preventDefault();
    event.stopPropagation();
  };

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(false);
    void handleFileList(event.dataTransfer.files);
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    void handleFileList(event.target.files);
    event.target.value = '';
  };

  const clearCompleted = () => {
    setUploads((previous) => previous.filter((upload) => upload.status !== 'completed'));
  };

  const removeUpload = (localId?: string) => {
    setUploads((previous) => previous.filter((upload) => upload.local_id !== localId));
  };

  const uploadCapturedPages = () => {
    if (capturedPages.length === 0) return;
    const pages = [...capturedPages];
    setCapturedPages([]);
    void queueEntries(pages);
  };

  const retryFailed = (localId?: string) => {
    const failedUpload = uploads.find((upload) => upload.local_id === localId);
    if (!failedUpload || failedUpload.status !== 'error') return;
    setUploads((previous) => previous.filter((upload) => upload.local_id !== localId));
    void queueEntries(failedUpload.source_files || [failedUpload.file]);
  };

  return (
    <div className="document-upload">
      <div
        className={`upload-zone ${isDragging ? 'dragging' : ''} ${nativeActionsEnabled ? 'native-ready' : ''}`}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={() => {
          if (nativeActionsEnabled) {
            void handleNativeFilePicker();
          } else {
            fileInputRef.current?.click();
          }
        }}
      >
        <div className="upload-icon">
          <ScanSearch size={44} strokeWidth={1.8} />
        </div>
        <h3>{t('documents.upload.title')}</h3>
        <p>
          {nativeActionsEnabled
            ? t('documents.upload.mobileHint')
            : t('documents.upload.dragDrop')}
        </p>
        <p className="upload-hint">{t('documents.upload.formats')}</p>
        <p className="upload-hint upload-hint-warning">{t('documents.upload.separateFilesHint')}</p>

        {nativeActionsEnabled ? (
          <div className="upload-native-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={(event) => {
                event.stopPropagation();
                void handleNativeFilePicker();
              }}
            >
              <FolderUp size={16} />
              <span>{t('documents.upload.selectFiles')}</span>
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={(event) => {
                event.stopPropagation();
                void handleCameraCapture();
              }}
            >
              <Camera size={16} />
              <span>{t('documents.upload.takePhoto')}</span>
            </button>
          </div>
        ) : null}

        <input
          ref={fileInputRef}
          type="file"
          accept="image/*,.pdf"
          capture="environment"
          multiple
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />
      </div>

      {/* === Staging Area: multi-image preview before upload === */}
      {stagedFiles.length > 0 ? (
        <div className="upload-staging">
          <div className="upload-staging-header">
            <strong>
              {t('documents.upload.stagingTitle', {
                count: stagedFiles.length,
              })}
            </strong>
            <p className="upload-staging-hint">
              {stagedFiles.length === 1
                ? t('documents.upload.stagingHintSingle', 'Review the file below, then click Upload.')
                : t('documents.upload.stagingHint', 'Drag to reorder, then choose to merge into one document or upload separately.')}
            </p>
          </div>

          <div className="upload-staging-grid">
            {stagedFiles.map((sf, index) => (
              <div
                key={sf.id}
                className={`upload-staging-item${draggedIndex === index ? ' dragging' : ''}${dragOverIndex === index ? ' drag-over' : ''}`}
                draggable
                onDragStart={() => handleStageDragStart(index)}
                onDragOver={(e) => handleStageDragOver(e, index)}
                onDrop={() => handleStageDrop(index)}
                onDragEnd={handleStageDragEnd}
              >
                <div className="staging-item-grip">
                  <GripVertical size={14} />
                </div>
                <div className="staging-item-number">{index + 1}</div>
                <img
                  src={sf.previewUrl}
                  alt={sf.file.name}
                  className="staging-item-thumb"
                  loading="lazy"
                />
                <div className="staging-item-name" title={sf.file.name}>
                  {sf.file.name}
                </div>
                <button
                  type="button"
                  className="staging-item-remove"
                  onClick={() => removeStagedFile(sf.id)}
                  title={t('common.delete')}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>

          <div className="upload-staging-actions">
            {stagedFiles.length === 1 ? (
              /* Single file — just one upload button */
              <button
                type="button"
                className="btn btn-primary"
                onClick={uploadStagedIndividually}
              >
                <Upload size={16} />
                <span>{t('documents.upload.uploadButton', 'Upload')}</span>
              </button>
            ) : (
              /* Multiple files — offer merge or separate */
              <>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={uploadStagedMerged}
                >
                  <Layers size={16} />
                  <span>
                    {t('documents.upload.mergeUpload', {
                      count: stagedFiles.length,
                    })}
                  </span>
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={uploadStagedIndividually}
                >
                  <Upload size={16} />
                  <span>
                    {t('documents.upload.uploadSeparately', {
                      count: stagedFiles.length,
                    })}
                  </span>
                </button>
              </>
            )}
            <button type="button" className="btn-link" onClick={clearStaging}>
              {t('documents.upload.clearStaging', 'Clear')}
            </button>
          </div>
        </div>
      ) : null}

      {capturedPages.length > 0 ? (
        <div className="upload-capture-session">
          <div className="upload-capture-session-copy">
            <strong>
              {t('documents.upload.captureSessionTitle', {
                count: capturedPages.length,
                defaultValue:
                  capturedPages.length === 1
                    ? '1 page captured, continue or upload now'
                    : '{{count}} pages captured, will be merged into 1 document',
              })}
            </strong>
            <p>
              {t(
                'documents.upload.captureSessionSubtitle',
                'Photos in the same group will be merged into one document before processing.'
              )}
            </p>
          </div>
          <div className="upload-capture-session-actions">
            <button type="button" className="btn btn-secondary" onClick={() => void handleCameraCapture()}>
              {t('documents.upload.addPage', 'Continue capturing')}
            </button>
            <button type="button" className="btn btn-primary" onClick={uploadCapturedPages}>
              {t('documents.upload.uploadGrouped', 'Upload this document')}
            </button>
            <button
              type="button"
              className="btn-link"
              onClick={() => setCapturedPages([])}
            >
              {t('documents.upload.clearCaptureSession', 'Clear')}
            </button>
          </div>
        </div>
      ) : null}

      {pickerError ? <div className="upload-picker-error">{pickerError}</div> : null}

      {uploads.length > 0 ? (
        <div className="upload-progress-list">
          <div className="progress-header">
            <h4>{t('documents.upload.progress')}</h4>
            {uploads.some((upload) => upload.status === 'completed') ? (
              <button type="button" className="btn-link" onClick={clearCompleted}>
                {t('documents.upload.clearCompleted')}
              </button>
            ) : null}
          </div>

          {uploads.map((upload, index) => {
            const completedDocumentId = upload.document?.id;
            const isClickableCompleted = upload.status === 'completed' && Boolean(completedDocumentId);

            return (
            <div
              key={upload.local_id || `${upload.file.name}-${index}`}
              className={`upload-item ${upload.status}${isClickableCompleted ? ' clickable' : ''}`}
              onClick={isClickableCompleted ? () => handleCompletedUploadOpen(completedDocumentId) : undefined}
              onKeyDown={isClickableCompleted ? (event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  handleCompletedUploadOpen(completedDocumentId);
                }
              } : undefined}
              role={isClickableCompleted ? 'button' : undefined}
              tabIndex={isClickableCompleted ? 0 : undefined}
              aria-label={isClickableCompleted ? t('ai.proactive.viewDocument', 'View document') : undefined}
            >
              <div className="upload-item-info">
                <span className="file-name">{upload.file.name}</span>
                <span className="file-size">
                  {upload.page_count && upload.page_count > 1
                    ? t('documents.upload.groupedPagesMeta', {
                        count: upload.page_count,
                        size: (upload.file.size / 1024).toFixed(1),
                      })
                    : `${(upload.file.size / 1024).toFixed(1)} KB`}
                </span>
              </div>

              {upload.status === 'uploading' ? (
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: `${upload.progress}%` }} />
                </div>
              ) : null}

              {upload.status === 'processing' ? (
                <div className="status-message processing">{t('documents.upload.processing')}</div>
              ) : null}

              {upload.status === 'pending' ? (
                <div className="status-message processing">
                  {t('documents.upload.pending', 'Queued for processing...')}
                </div>
              ) : null}

              {upload.status === 'completed' ? (
                <div className="status-message completed">
                  ✓ {upload.document?.deduplicated
                    ? t('documents.upload.duplicateReused', 'Duplicate file, reused existing document')
                    : t('documents.upload.completed')}
                  {isClickableCompleted ? (
                    <span className="upload-item-action-link">
                      {t('ai.proactive.viewDocument', 'View document')}
                    </span>
                  ) : null}
                  <button
                    type="button"
                    className="upload-item-remove-btn"
                    onClick={(e) => { e.stopPropagation(); removeUpload(upload.local_id); }}
                    aria-label={t('common.delete', 'Remove')}
                  >
                    <X size={14} />
                  </button>
                </div>
              ) : null}

              {upload.status === 'error' ? (
                <div className="status-message error">
                  <span>✕ {upload.error}</span>
                  <button type="button" className="btn-link" onClick={() => retryFailed(upload.local_id)}>
                    {t('documents.upload.retry')}
                  </button>
                </div>
              ) : null}
            </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
};

export default DocumentUpload;
