import React, { useCallback, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Camera, FolderUp, ScanSearch, GripVertical, Trash2, Layers, Upload } from 'lucide-react';
import { documentService } from '../../services/documentService';
import { employerService } from '../../services/employerService';
import { useDocumentStore } from '../../stores/documentStore';
import { useAIAdvisorStore } from '../../stores/aiAdvisorStore';
import { useAuthStore } from '../../stores/authStore';
import { useRefreshStore } from '../../stores/refreshStore';
import { UploadProgress } from '../../types/document';
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

interface StagedFile {
  id: string;
  file: File;
  previewUrl: string;
}

interface DocumentUploadProps {
  propertyId?: string | null;
}

const DocumentUpload: React.FC<DocumentUploadProps> = ({ propertyId }) => {
  const { t } = useTranslation();
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
    async (documentId: number, uploadIndex: number, fallbackDocument: any) => {
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
          const ocrDone =
            updatedDocument.ocr_result ||
            updatedDocument.confidence_score > 0 ||
            (updatedDocument as any).processed_at;

          if (ocrDone) {
            setUploads((previous) =>
              previous.map((upload, index) =>
                index === uploadIndex
                  ? { ...upload, status: 'completed', document: resolvedDocument }
                  : upload
              )
            );
            addDocument(resolvedDocument);

            // Proactive AI notification
            const fileName = resolvedDocument.file_name || `#${documentId}`;
            const ocrData = typeof resolvedDocument.ocr_result === 'string'
              ? (() => { try { return JSON.parse(resolvedDocument.ocr_result as string); } catch { return null; } })()
              : resolvedDocument.ocr_result;
            const suggestion = ocrData?.import_suggestion;
            let handledPrimaryNotification = Boolean(resolvedDocument.deduplicated);
            let employerMonthPrompted = false;

            if (resolvedDocument.deduplicated) {
              pushAIMessage({
                type: 'upload_success',
                content: t('ai.proactive.duplicateUploadReused', {
                  defaultValue: '{{name}} 已经上传过，系统已复用现有文档。',
                  name: fileName,
                }),
                link: `/documents/${documentId}`,
              });
            }

            // Multi-receipt notification
            const receiptCount = ocrData?._receipt_count;
            if (receiptCount && receiptCount > 1) {
              pushAIMessage({
                type: 'upload_success',
                content: t('ai.proactive.multiReceiptDetected', { count: receiptCount, name: fileName }),
                link: `/documents/${documentId}`,
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
                link: `/documents/${documentId}`,
              });
            } else if (suggestion?.status === 'pending' && suggestion?.type?.startsWith('import_')) {
              handledPrimaryNotification = true;
              const formData = suggestion.data || {};
              const summaryParts: string[] = [];
              if (formData.kz_245) summaryParts.push(`${t('taxFiling.kz.kz_245', 'KZ245')}: €${Number(formData.kz_245).toLocaleString('de-AT', { minimumFractionDigits: 2 })}`);
              if (formData.kz_260) summaryParts.push(`${t('taxFiling.kz.kz_260', 'KZ260')}: €${Number(formData.kz_260).toLocaleString('de-AT', { minimumFractionDigits: 2 })}`);
              if (formData.betriebseinnahmen) summaryParts.push(`${t('taxFiling.fields.betriebseinnahmen', 'Revenue')}: €${Number(formData.betriebseinnahmen).toLocaleString('de-AT', { minimumFractionDigits: 2 })}`);
              if (formData.gewinn_verlust != null) summaryParts.push(`${t('taxFiling.fields.gewinnVerlust', 'Profit/Loss')}: €${Number(formData.gewinn_verlust).toLocaleString('de-AT', { minimumFractionDigits: 2 })}`);
              if (formData.mieteinnahmen) summaryParts.push(`${t('taxFiling.fields.mieteinnahmen', 'Rental income')}: €${Number(formData.mieteinnahmen).toLocaleString('de-AT', { minimumFractionDigits: 2 })}`);
              if (formData.gesamtumsatz) summaryParts.push(`${t('taxFiling.fields.gesamtumsatz', 'Total revenue')}: €${Number(formData.gesamtumsatz).toLocaleString('de-AT', { minimumFractionDigits: 2 })}`);
              if (formData.zahllast != null) summaryParts.push(`${t('taxFiling.fields.zahllast', 'VAT payable')}: €${Number(formData.zahllast).toLocaleString('de-AT', { minimumFractionDigits: 2 })}`);
              if (formData.total_amount) summaryParts.push(`${t('taxFiling.fields.totalAmount', 'Total')}: €${Number(formData.total_amount).toLocaleString('de-AT', { minimumFractionDigits: 2 })}`);
              if (formData.transaction_count) summaryParts.push(`${t('taxFiling.fields.transactionCount', 'Transactions')}: ${formData.transaction_count}`);
              if (formData.kapitalertraege) summaryParts.push(`${t('taxFiling.fields.kapitalertraege', 'Capital income')}: €${Number(formData.kapitalertraege).toLocaleString('de-AT', { minimumFractionDigits: 2 })}`);

              pushAIMessage({
                type: 'tax_form_review',
                content: t('ai.proactive.taxFormDetected', { name: fileName }),
                documentId: documentId,
                link: `/documents/${documentId}`,
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
                    link: `/documents/${documentId}`,
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
                      link: `/documents/${documentId}`,
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
                link: `/documents/${documentId}`,
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
              });
            }

            // ================================================================
            // Task 14: Push structured messages to chat panel
            // Chat is primary surface — suggestion enters chat first.
            // Documents page SuggestionCard renders from same backend data (secondary).
            // ================================================================
            removeProcessingMessage(documentId);

            if (suggestion && suggestion.status === 'pending') {
              const suggestionType = suggestion.type || '';
              const suggestionData = suggestion.data || {};
              const followUpQuestions = suggestion.follow_up_questions || [];
              const hasFollowUps = followUpQuestions.length > 0;

              // Build action descriptor for generic dispatch
              const actionKindMap: Record<string, string> = {
                create_property: 'confirm_property',
                create_asset: 'confirm_asset',
                create_recurring_income: 'confirm_recurring',
                create_recurring_expense: 'confirm_recurring_expense',
                create_loan: 'confirm_loan',
              };
              const actionEndpointMap: Record<string, string> = {
                create_property: 'confirm-property',
                create_asset: 'confirm-asset',
                create_recurring_income: 'confirm-recurring',
                create_recurring_expense: 'confirm-recurring-expense',
                create_loan: 'confirm-loan',
              };
              const isImport = suggestionType.startsWith('import_');
              const actionKind = isImport ? 'confirm_tax_data' : (actionKindMap[suggestionType] || suggestionType);
              const actionSuffix = isImport ? 'confirm-tax-data' : (actionEndpointMap[suggestionType] || suggestionType);

              pushSuggestionMessage({
                idempotencyKey: `${documentId}:${suggestionType}:completed`,
                type: 'suggestion',
                suggestionType,
                documentId,
                extractedData: suggestionData,
                followUpQuestions: followUpQuestions as any,
                status: hasFollowUps ? 'needs_input' : 'pending',
                suggestionVersion: suggestion.version || 0,
                action: {
                  kind: actionKind as any,
                  targetId: String(documentId),
                  endpoint: `/api/v1/documents/${documentId}/${actionSuffix}`,
                  method: 'POST',
                },
              });

              // Push follow-up questions as separate chat message
              if (hasFollowUps) {
                pushFollowUpMessage({
                  idempotencyKey: `${documentId}:${suggestionType}:follow_up`,
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

            return;
          }
        } catch {
          // Ignore intermittent polling issues and keep waiting.
        }
      }

      // Polling timeout reached — cleanup processing indicator
      removeProcessingMessage(documentId);

      setUploads((previous) =>
        previous.map((upload, index) =>
          index === uploadIndex ? { ...upload, status: 'completed', document: fallbackDocument } : upload
        )
      );
      addDocument(fallbackDocument);
    },
    [addDocument, currentUser, pushAIMessage, pushSuggestionMessage, pushFollowUpMessage, pushProcessingMessage, removeProcessingMessage, t]
  );

  // --- Upload execution ---

  const queueEntries = useCallback(
    async (sourceFiles: File[]) => {
      const entries = buildUploadEntries(sourceFiles);
      if (entries.length === 0) {
        return;
      }

      setPickerError(null);
      const queuedUploads: UploadProgress[] = entries.map((entry) => ({
        file: entry.displayFile,
        source_files: entry.sourceFiles,
        upload_mode: entry.uploadMode,
        page_count: entry.pageCount,
        progress: 0,
        status: 'pending',
      }));

      let startIndex = 0;
      setUploads((previous) => {
        startIndex = previous.length;
        return [...previous, ...queuedUploads];
      });

      for (const [offset, entry] of entries.entries()) {
        const uploadIndex = startIndex + offset;
        const displayName = entry.displayFile.name;

        try {
          setUploads((previous) =>
            previous.map((upload, index) =>
              index === uploadIndex ? { ...upload, status: 'uploading' } : upload
            )
          );

          const updateProgress = (progress: number) => {
            setUploads((previous) =>
              previous.map((upload, index) =>
                index === uploadIndex ? { ...upload, progress } : upload
              )
            );
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

            setUploads((previous) =>
              previous.map((upload, index) =>
                index === uploadIndex
                  ? {
                      ...upload,
                      status: 'completed',
                      progress: 100,
                      document: existingDocument,
                    }
                  : upload
              )
            );

            addDocument(existingDocument);
            pushAIMessage({
              type: 'upload_success',
              content: t('ai.proactive.duplicateUploadReused', {
                defaultValue: '{{name}} 已经上传过，系统已复用现有文档。',
                name: displayName,
              }),
              link: `/documents/${document.id}`,
            });
            continue;
          }

          setUploads((previous) =>
            previous.map((upload, index) =>
              index === uploadIndex
                ? {
                    ...upload,
                    status: 'processing',
                    progress: 100,
                    document,
                  }
                : upload
            )
          );

          void pollForProcessing(document.id, uploadIndex, document);
        } catch (error: any) {
          setUploads((previous) =>
            previous.map((upload, index) =>
              index === uploadIndex
                ? {
                    ...upload,
                    status: 'error',
                    error: error.response?.data?.detail || t('documents.upload.error'),
                  }
                : upload
            )
          );

          pushAIMessage({
            type: 'upload_error',
            content: t('ai.proactive.uploadError', { name: displayName }),
          });
        }
      }
    },
    [pollForProcessing, propertyId, pushAIMessage, t]
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
        file: entry.displayFile,
        source_files: entry.sourceFiles,
        upload_mode: entry.uploadMode,
        page_count: entry.pageCount,
        progress: 0,
        status: 'pending',
      };

      let uploadIndex = 0;
      setUploads((prev) => {
        uploadIndex = prev.length;
        return [...prev, queuedUpload];
      });

      try {
        setUploads((prev) =>
          prev.map((u, i) => (i === uploadIndex ? { ...u, status: 'uploading' } : u))
        );

        const updateProgress = (progress: number) => {
          setUploads((prev) =>
            prev.map((u, i) => (i === uploadIndex ? { ...u, progress } : u))
          );
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

          setUploads((prev) =>
            prev.map((u, i) =>
              i === uploadIndex ? { ...u, status: 'completed', progress: 100, document: existingDocument } : u
            )
          );
          addDocument(existingDocument);
          pushAIMessage({
            type: 'upload_success',
            content: t('ai.proactive.duplicateUploadReused', {
              defaultValue: '{{name}} 已经上传过，系统已复用现有文档。',
              name: entry.displayFile.name,
            }),
            link: `/documents/${document.id}`,
          });
          return;
        }

        setUploads((prev) =>
          prev.map((u, i) =>
            i === uploadIndex ? { ...u, status: 'processing', progress: 100, document } : u
          )
        );
        void pollForProcessing(document.id, uploadIndex, document);
      } catch (error: any) {
        setUploads((prev) =>
          prev.map((u, i) =>
            i === uploadIndex
              ? { ...u, status: 'error', error: error.response?.data?.detail || t('documents.upload.error') }
              : u
          )
        );
        pushAIMessage({
          type: 'upload_error',
          content: t('ai.proactive.uploadError', { name: entry.displayFile.name }),
        });
      }
    };

    void queueMerged();
  }, [stagedFiles, clearStaging, propertyId, pollForProcessing, pushAIMessage, t, addDocument]);

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

  const uploadCapturedPages = () => {
    if (capturedPages.length === 0) return;
    const pages = [...capturedPages];
    setCapturedPages([]);
    void queueEntries(pages);
  };

  const retryFailed = (index: number) => {
    const failedUpload = uploads[index];
    if (failedUpload.status !== 'error') return;
    setUploads((previous) => previous.filter((_, uploadIndex) => uploadIndex !== index));
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
                defaultValue: '{{count}} 张照片待处理',
              })}
            </strong>
            <p className="upload-staging-hint">
              {t(
                'documents.upload.stagingHint',
                '拖拽调整顺序，然后选择合并为一个文档上传，或分别上传。'
              )}
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
            <button
              type="button"
              className="btn btn-primary"
              onClick={uploadStagedMerged}
              disabled={stagedFiles.length < 2}
            >
              <Layers size={16} />
              <span>
                {t('documents.upload.mergeUpload', {
                  count: stagedFiles.length,
                  defaultValue: '合并为 1 个文档上传 ({{count}} 页)',
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
                  defaultValue: '分别上传 ({{count}} 个文档)',
                })}
              </span>
            </button>
            <button type="button" className="btn-link" onClick={clearStaging}>
              {t('documents.upload.clearStaging', '清空')}
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
                    ? '已拍 1 页，可继续拍摄或直接上传'
                    : '已拍 {{count}} 页，将合并为 1 个文档上传',
              })}
            </strong>
            <p>
              {t(
                'documents.upload.captureSessionSubtitle',
                '同一组照片会先合并成一个文档，再进入识别流程。'
              )}
            </p>
          </div>
          <div className="upload-capture-session-actions">
            <button type="button" className="btn btn-secondary" onClick={() => void handleCameraCapture()}>
              {t('documents.upload.addPage', '继续拍照')}
            </button>
            <button type="button" className="btn btn-primary" onClick={uploadCapturedPages}>
              {t('documents.upload.uploadGrouped', '上传这个文档')}
            </button>
            <button
              type="button"
              className="btn-link"
              onClick={() => setCapturedPages([])}
            >
              {t('documents.upload.clearCaptureSession', '清空')}
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

          {uploads.map((upload, index) => (
            <div key={`${upload.file.name}-${index}`} className={`upload-item ${upload.status}`}>
              <div className="upload-item-info">
                <span className="file-name">{upload.file.name}</span>
                <span className="file-size">
                  {upload.page_count && upload.page_count > 1
                    ? t('documents.upload.groupedPagesMeta', {
                        count: upload.page_count,
                        size: (upload.file.size / 1024).toFixed(1),
                        defaultValue: '{{count}} 页 · {{size}} KB',
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

              {upload.status === 'completed' ? (
                <div className="status-message completed">
                  ✓ {upload.document?.deduplicated
                    ? t('documents.upload.duplicateReused', '重复文件，已复用现有文档')
                    : t('documents.upload.completed')}
                </div>
              ) : null}

              {upload.status === 'error' ? (
                <div className="status-message error">
                  <span>✕ {upload.error}</span>
                  <button type="button" className="btn-link" onClick={() => retryFailed(index)}>
                    {t('documents.upload.retry')}
                  </button>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
};

export default DocumentUpload;
