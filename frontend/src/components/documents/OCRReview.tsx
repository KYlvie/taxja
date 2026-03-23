import React, { useState, useEffect, useRef } from 'react';
/* eslint-disable @typescript-eslint/no-explicit-any */
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import Select from '../common/Select';
import DateInput from '../common/DateInput';
import { getLocaleForLanguage } from '../../utils/locale';
import { documentService } from '../../services/documentService';
import { OCRReviewData, ExtractedData, DocumentType } from '../../types/document';
import { aiToast } from '../../stores/aiToastStore';
import {
  formatDocumentFieldLabel,
  translateDocumentSuggestionText,
} from '../../utils/documentFieldLabel';
import { resolveDocumentPresentation } from '../../documents/presentation/resolveDocumentPresentation';
import type {
  DocumentPresentationTemplate,
} from '../../documents/presentation/types';
import BescheidImport from './BescheidImport';
import SubpageBackLink from '../common/SubpageBackLink';
import { saveBlobWithNativeShare } from '../../mobile/files';
import './OCRReview.css';

interface OCRReviewProps {
  documentId: number;
  presentationTemplate?: DocumentPresentationTemplate;
  onConfirm?: () => void;
  onCancel?: () => void;
  onPrevDocument?: () => void;
  onNextDocument?: () => void;
  hasPrevDocument?: boolean;
  hasNextDocument?: boolean;
}

const TAX_REVIEW_DOCUMENT_TYPES = new Set<string>([
  DocumentType.LOHNZETTEL,
  DocumentType.E1_FORM,
  DocumentType.L1_FORM,
  DocumentType.L1K_BEILAGE,
  DocumentType.L1AB_BEILAGE,
  DocumentType.E1A_BEILAGE,
  DocumentType.E1B_BEILAGE,
  DocumentType.E1KV_BEILAGE,
  DocumentType.U1_FORM,
  DocumentType.U30_FORM,
  DocumentType.JAHRESABSCHLUSS,
  DocumentType.SVS_NOTICE,
  DocumentType.PROPERTY_TAX,
]);

const OCR_PROCESSING_STATES = new Set([
  'processing_phase_1',
  'first_result_available',
  'finalizing',
]);

const TAX_FIELD_PRIORITY = [
  'tax_year',
  'year',
  'taxpayer_name',
  'steuernummer',
  'employer_name',
  'gewinn_verlust',
  'umsatz_20',
  'umsatz_10',
  'vorsteuer',
  'zahllast',
];

const TAX_FIELD_SKIP = new Set([
  'confidence',
  'field_confidence',
  'import_suggestion',
  'transaction_suggestion',
  'tax_analysis',
  'asset_outcome',
  'correction_history',
  'learning_data',
  'raw_text',
]);

const isTaxReviewDocumentType = (documentType?: string) =>
  !!documentType && TAX_REVIEW_DOCUMENT_TYPES.has(documentType);

const isProcessingPipelineState = (document: OCRReviewData['document'] | null) => {
  const currentState = document?.ocr_result?._pipeline?.current_state;
  return typeof currentState === 'string' && OCR_PROCESSING_STATES.has(currentState);
};

const getTaxFieldKeys = (
  editedData: ExtractedData,
  extractedData: ExtractedData
): string[] => {
  const merged: Record<string, any> = {};

  Object.entries(extractedData || {}).forEach(([key, value]) => {
    merged[key] = value;
  });
  Object.entries(editedData || {}).forEach(([key, value]) => {
    if (value !== undefined) {
      merged[key] = value;
    }
  });

  return Object.keys(merged)
    .filter((key) => {
      const value = merged[key];
      return (
        !TAX_FIELD_SKIP.has(key) &&
        !key.startsWith('_') &&
        !key.endsWith('_confidence') &&
        typeof value !== 'object' &&
        typeof value !== 'function'
      );
    })
    .sort((left, right) => {
      const leftPriority = TAX_FIELD_PRIORITY.indexOf(left);
      const rightPriority = TAX_FIELD_PRIORITY.indexOf(right);

      if (leftPriority !== -1 || rightPriority !== -1) {
        if (leftPriority === -1) return 1;
        if (rightPriority === -1) return -1;
        return leftPriority - rightPriority;
      }

      if (left.startsWith('kz_') && right.startsWith('kz_')) {
        return left.localeCompare(right, undefined, { numeric: true });
      }

      return left.localeCompare(right);
    });
};

const formatPercent = (value?: number) =>
  typeof value === 'number' && Number.isFinite(value)
    ? `${Math.round(value * 100)}%`
    : null;

const formatCurrencyValue = (value: number, language: string) =>
  value.toLocaleString(getLocaleForLanguage(language), {
    style: 'currency',
    currency: 'EUR',
  });

const resolveInitialTransactionType = (
  documentType: string | undefined,
  extractedData: ExtractedData,
  ocrResult: ExtractedData | undefined
): 'income' | 'expense' => {
  const explicitType = String(
    extractedData._transaction_type
      ?? ocrResult?._transaction_type
      ?? ''
  ).toLowerCase();
  if (explicitType === 'income' || explicitType === 'expense') {
    return explicitType;
  }

  const resolvedDirection = String(
    extractedData.document_transaction_direction
      ?? ocrResult?.document_transaction_direction
      ?? ''
  ).toLowerCase();
  if (resolvedDirection === 'income' || resolvedDirection === 'expense') {
    return resolvedDirection;
  }

  if (
    documentType === 'payslip' ||
    documentType === 'lohnzettel' ||
    documentType === 'rental_contract'
  ) {
    return 'income';
  }

  return 'expense';
};

const EVIDENCE_EXACT_KEYS: Record<string, string> = {
  'No reliable contract-side match was found between document parties and the user profile.':
    'documents.review.evidence.noMatch',
  'User explicitly marked the contract side as unknown.':
    'documents.review.evidence.userMarkedUnknown',
};

const EVIDENCE_PREFIX_KEYS: Array<[string, string]> = [
  ['Extracted', 'documents.review.evidence.extractedParty'],
  ['Detected', 'documents.review.evidence.detectedWording'],
  ['This looks more like', 'documents.review.evidence.looksLike'],
];

const translateEvidence = (evidence: string, t: (key: string, fallback: string) => string): string => {
  const exactKey = EVIDENCE_EXACT_KEYS[evidence];
  if (exactKey) {
    return t(exactKey, evidence);
  }
  for (const [prefix, key] of EVIDENCE_PREFIX_KEYS) {
    if (evidence.startsWith(prefix)) {
      return t(key, evidence);
    }
  }
  return evidence;
};

const OCRReview: React.FC<OCRReviewProps> = ({
  documentId,
  presentationTemplate,
  onConfirm,
  onCancel,
  onPrevDocument,
  onNextDocument,
  hasPrevDocument,
  hasNextDocument,
}) => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [reviewData, setReviewData] = useState<OCRReviewData | null>(null);
  const [editedData, setEditedData] = useState<ExtractedData>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [selectedDocType, setSelectedDocType] = useState<string>('');
  const [selectedTxnType, setSelectedTxnType] = useState<'income' | 'expense'>('expense');
  const [bescheidMode, setBescheidMode] = useState(false);
  const [bescheidOcrText, setBescheidOcrText] = useState<string>('');
  const [retryingOcr] = useState(false);
  const [reprocessPending, setReprocessPending] = useState(false);
  const retryPollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    loadReviewData();
    // Initial fetch should follow document identity, not local edit state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId]);

  useEffect(() => {
    return () => {
      if (retryPollTimeoutRef.current) {
        clearTimeout(retryPollTimeoutRef.current);
      }
    };
  }, []);

  // Load document preview as blob (needed because download endpoint requires auth)
  useEffect(() => {
    let objectUrl: string | null = null;
    documentService.downloadDocument(documentId).then((blob) => {
      objectUrl = URL.createObjectURL(blob);
      setPreviewUrl(objectUrl);
    }).catch(() => {});
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [documentId]);

  const loadReviewData = async (showSpinner = true) => {
    try {
      if (showSpinner) {
        setLoading(true);
      }
      const data = await documentService.getDocumentForReview(documentId);
      setReviewData(data);
      setEditedData(data.extracted_data || {});
      setReprocessPending(isProcessingPipelineState(data.document));
      // Initialize document type from OCR result
      setSelectedDocType(data.document.document_type || '');

      // Detect Bescheid documents and switch to specialized import view
      const dt = data.document.document_type;
      if ((dt as string) === 'einkommensteuerbescheid' && data.document.raw_text) {
        setBescheidMode(true);
        setBescheidOcrText(data.document.raw_text);
      }

      setSelectedTxnType(
        resolveInitialTransactionType(
          dt,
          data.extracted_data || {},
          data.document.ocr_result
        )
      );
    } catch (err: any) {
      setError(err.response?.data?.detail || t('documents.review.loadError'));
      setReprocessPending(false);
    } finally {
      if (showSpinner) {
        setLoading(false);
      }
    }
  };

  const pollForReprocessCompletion = (attempt = 0) => {
    if (retryPollTimeoutRef.current) {
      clearTimeout(retryPollTimeoutRef.current);
    }

    const MAX_POLL_ATTEMPTS = 20;

    retryPollTimeoutRef.current = setTimeout(async () => {
      try {
        const latestDocument = await documentService.getDocument(documentId);
        const stillProcessing = isProcessingPipelineState(
          latestDocument as OCRReviewData['document']
        );

        await loadReviewData(false);

        if (stillProcessing && attempt < MAX_POLL_ATTEMPTS) {
          pollForReprocessCompletion(attempt + 1);
        } else {
          setReprocessPending(stillProcessing);
          if (stillProcessing) {
            aiToast(t('documents.reprocessTimeout', 'Reprocessing is taking too long. Please try again later.'), 'warning');
          }
        }
      } catch {
        if (attempt < MAX_POLL_ATTEMPTS) {
          pollForReprocessCompletion(attempt + 1);
        } else {
          setReprocessPending(false);
          aiToast(t('documents.reprocessFailed', 'Reprocessing failed'), 'error');
        }
      }
    }, 2000);
  };

  const handleFieldChange = (field: string, value: any) => {
    setEditedData((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleSave = async () => {
    try {
      setSaving(true);

      const dataToSend: Record<string, any> = {
        ...editedData,
        _document_type: selectedDocType,
      };

      if (
        selectedDocType === DocumentType.RENTAL_CONTRACT ||
        selectedDocType === DocumentType.PURCHASE_CONTRACT ||
        selectedDocType === DocumentType.LOAN_CONTRACT ||
        selectedDocType === DocumentType.VERSICHERUNGSBESTAETIGUNG
      ) {
        dataToSend.user_contract_role =
          dataToSend.user_contract_role ?? editedData.user_contract_role ?? 'unknown';
      }

      const isTaxData = isTaxReviewDocumentType(selectedDocType);

      if (
        selectedDocType === DocumentType.INVOICE ||
        selectedDocType === DocumentType.RECEIPT ||
        selectedDocType === DocumentType.BANK_STATEMENT
      ) {
        dataToSend._transaction_type = selectedTxnType;
        dataToSend.document_transaction_direction =
          dataToSend.document_transaction_direction
          ?? editedData.document_transaction_direction
          ?? 'unknown';
        dataToSend.commercial_document_semantics =
          dataToSend.commercial_document_semantics
          ?? editedData.commercial_document_semantics
          ?? 'unknown';
      } else if (!isTaxData) {
        dataToSend._transaction_type = selectedTxnType;
      }

      await documentService.correctOCR(documentId, dataToSend);
      aiToast(t('documents.review.changesSaved', 'Changes saved'), 'success');
      onConfirm?.();
    } catch (err: any) {
      aiToast(t('common.saveFailed', 'Save failed'), 'error');
      setError(err.response?.data?.detail || t('documents.review.saveError'));
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    if (onCancel) {
      onCancel();
    } else {
      navigate('/documents');
    }
  };

  const handleDownloadDocument = async () => {
    try {
      const blob = await documentService.downloadDocument(documentId);
      const fileName = reviewData?.document?.file_name || `document_${documentId}`;
      await saveBlobWithNativeShare(blob, fileName, t('documents.download'));
    } catch (error) {
      console.error('Failed to download:', error);
      aiToast(t('documents.downloadFailed', 'Download failed'), 'error');
    }
  };

  const getConfidenceClass = (confidence?: number) => {
    if (!confidence) return 'confidence-unknown';
    if (confidence >= 0.8) return 'confidence-high';
    if (confidence >= 0.6) return 'confidence-medium';
    return 'confidence-low';
  };

  const getConfidenceLabel = (confidence?: number) => {
    if (!confidence) return t('documents.review.confidence.unknown');
    if (confidence >= 0.8) return t('documents.review.confidence.high');
    if (confidence >= 0.6) return t('documents.review.confidence.medium');
    return t('documents.review.confidence.low');
  };

  if (loading) {
    return (
      <div className="ocr-review loading">
        <div className="spinner"></div>
        <p>{t('documents.review.loading')}</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="ocr-review error">
        <p className="error-message">{error}</p>
        <button className="btn btn-secondary" onClick={handleCancel}>
          {t('common.back')}
        </button>
      </div>
    );
  }

  if (!reviewData) {
    return null;
  }

  // Show specialized Bescheid import view
  if (bescheidMode && bescheidOcrText) {
    const handleBescheidDone = () => {
      if (onConfirm) onConfirm();
      else navigate('/documents');
    };
    return (
      <BescheidImport
        ocrText={bescheidOcrText}
        documentId={documentId}
        onImportComplete={handleBescheidDone}
        onCancel={() => { if (onCancel) onCancel(); else navigate('/documents'); }}
      />
    );
  }

  const { document, extracted_data, suggestions } = reviewData;
  const purchaseContractKind = String(
    editedData.purchase_contract_kind
      || extracted_data.purchase_contract_kind
      || document.ocr_result?.purchase_contract_kind
      || ''
  ).toLowerCase();
  const isPurchaseContract =
    selectedDocType === 'purchase_contract' || selectedDocType === 'kaufvertrag';
  const isRentalContract =
    selectedDocType === 'rental_contract' || selectedDocType === 'mietvertrag';
  const isLoanContract =
    selectedDocType === 'loan_contract' || selectedDocType === 'kreditvertrag';
  const isInsuranceDocument =
    selectedDocType === 'versicherungsbestaetigung';
  const isInvoiceDocument = selectedDocType === 'invoice';
  const isReceiptDocument = selectedDocType === 'receipt';
  const isBankStatement = selectedDocType === 'bank_statement';
  const isAssetPurchaseContract = isPurchaseContract && purchaseContractKind === 'asset';
  const isPropertyPurchaseContract = isPurchaseContract && !isAssetPurchaseContract;
  const isContractRoleSensitive =
    isRentalContract || isPurchaseContract || isLoanContract || isInsuranceDocument;
  const isDirectionSensitive =
    isInvoiceDocument || isReceiptDocument || isBankStatement;
  const isTaxDataReview = isTaxReviewDocumentType(selectedDocType);
  const taxFieldKeys = isTaxDataReview ? getTaxFieldKeys(editedData, extracted_data) : [];
  const contractRoleResolution = isContractRoleSensitive
    ? (document.ocr_result?.contract_role_resolution as Record<string, any> | undefined)
    : undefined;
  const selectedContractRole = isContractRoleSensitive
    ? String(
        editedData.user_contract_role
          ?? extracted_data.user_contract_role
          ?? document.ocr_result?.user_contract_role
          ?? contractRoleResolution?.candidate
          ?? 'unknown'
      )
    : 'unknown';
  const transactionDirectionResolution = isDirectionSensitive
    ? (document.ocr_result?.transaction_direction_resolution as Record<string, any> | undefined)
    : undefined;
  const selectedTransactionDirection = isDirectionSensitive
    ? String(
        editedData.document_transaction_direction
          ?? extracted_data.document_transaction_direction
          ?? document.ocr_result?.document_transaction_direction
          ?? transactionDirectionResolution?.candidate
          ?? 'unknown'
      )
    : 'unknown';
  const selectedCommercialSemantics = isDirectionSensitive
    ? String(
        editedData.commercial_document_semantics
          ?? extracted_data.commercial_document_semantics
          ?? document.ocr_result?.commercial_document_semantics
          ?? transactionDirectionResolution?.semantics
          ?? (isReceiptDocument ? 'receipt' : isInvoiceDocument ? 'standard_invoice' : 'unknown')
      )
    : 'unknown';
  const currentPresentationDecision = resolveDocumentPresentation(document, {
    documentType: selectedDocType,
    transactionType: selectedTxnType,
    documentTransactionDirection: selectedTransactionDirection,
    commercialDocumentSemantics: selectedCommercialSemantics,
    isReversal: Boolean(
      editedData.is_reversal
      ?? document.ocr_result?.is_reversal
      ?? false
    ),
  });
  const templateWillSwitchAfterSave = Boolean(presentationTemplate)
    && currentPresentationDecision.template !== presentationTemplate;

  const getContractRoleLabel = (role?: string) => {
    switch (role) {
      case 'landlord':
        return t('documents.review.contractRole.landlord', '\u6211\u662f\u623f\u4e1c');
      case 'tenant':
        return t('documents.review.contractRole.tenant', '\u6211\u662f\u79df\u5ba2');
      case 'buyer':
        return t('documents.review.contractRole.buyer', '\u6211\u662f\u4e70\u65b9');
      case 'seller':
        return t('documents.review.contractRole.seller', '\u6211\u662f\u5356\u65b9');
      case 'borrower':
        return t('documents.review.contractRole.borrower', '\u6211\u662f\u501f\u6b3e\u65b9');
      case 'policy_holder':
        return t('documents.review.contractRole.policyHolder', '\u6211\u662f\u6295\u4fdd\u65b9');
      default:
        return t('documents.review.contractRole.unknown', '\u6682\u4e0d\u786e\u5b9a');
    }
  };

  const contractRoleOptions = isRentalContract
    ? [
        { value: 'landlord', label: getContractRoleLabel('landlord') },
        { value: 'tenant', label: getContractRoleLabel('tenant') },
        { value: 'unknown', label: getContractRoleLabel('unknown') },
      ]
    : isPurchaseContract
      ? [
          { value: 'buyer', label: getContractRoleLabel('buyer') },
          { value: 'seller', label: getContractRoleLabel('seller') },
          { value: 'unknown', label: getContractRoleLabel('unknown') },
        ]
      : isLoanContract
        ? [
            { value: 'borrower', label: getContractRoleLabel('borrower') },
            { value: 'unknown', label: getContractRoleLabel('unknown') },
          ]
        : [
            { value: 'policy_holder', label: getContractRoleLabel('policy_holder') },
            { value: 'unknown', label: getContractRoleLabel('unknown') },
          ];

  const getContractRoleSourceLabel = (source?: string) => {
    switch (source) {
      case 'manual_override':
        return t('documents.review.contractRoleSource.manual', '\u624b\u52a8\u9009\u62e9');
      case 'property_context':
        return t('documents.review.contractRoleSource.context', '\u8d44\u4ea7\u4e0a\u4e0b\u6587');
      case 'party_name_match':
        return t('documents.review.contractRoleSource.partyMatch', '\u5408\u540c\u53cc\u65b9\u540d\u79f0\u5339\u914d');
      case 'text_keyword_match':
      case 'text_role_inference':
        return t('documents.review.contractRoleSource.text', '\u5408\u540c\u6587\u672c\u63a8\u65ad');
      default:
        return t('documents.review.contractRoleSource.unknown', '\u672a\u77e5');
    }
  };

  const getContractRoleBlockTargetLabel = () => {
    if (isRentalContract) {
      return t('documents.review.contractRoleTarget.recurringIncome', '\u79df\u91d1\u6536\u5165');
    }
    if (isLoanContract) {
      return t('documents.review.contractRoleTarget.loan', '\u8d37\u6b3e\u8bb0\u5f55');
    }
    if (isInsuranceDocument) {
      return t('documents.review.contractRoleTarget.insurance', '\u4fdd\u9669\u5b9a\u671f\u652f\u51fa');
    }
    if (isAssetPurchaseContract) {
      return t('documents.review.contractRoleTarget.asset', '\u8d44\u4ea7');
    }
    return t('documents.review.contractRoleTarget.property', '\u623f\u4ea7');
  };

  const getDirectionLabel = (direction?: string) => {
    switch (direction) {
      case 'expense':
        return t('documents.review.direction.expense', '\u8fd9\u662f\u4e00\u7b14\u652f\u51fa');
      case 'income':
        return t('documents.review.direction.income', '\u8fd9\u662f\u4e00\u7b14\u6536\u5165');
      default:
        return t('documents.review.direction.unknown', '\u6682\u4e0d\u786e\u5b9a');
    }
  };

  const getDirectionSourceLabel = (source?: string) => {
    switch (source) {
      case 'manual_override':
        return t('documents.review.directionSource.manual', '\u624b\u52a8\u9009\u62e9');
      case 'party_name_match':
        return t('documents.review.directionSource.partyMatch', '\u5355\u636e\u53cc\u65b9\u540d\u79f0\u5339\u914d');
      case 'merchant_counterparty':
        return t('documents.review.directionSource.merchant', '\u5546\u5bb6/\u5f00\u7968\u65b9\u63a8\u65ad');
      case 'statement_mixed_flow':
        return t('documents.review.directionSource.statement', '\u94f6\u884c\u6d41\u6c34\u53ea\u8bb0\u5f55\u65b9\u5411\u5143\u6570\u636e');
      default:
        return t('documents.review.directionSource.unknown', '\u672a\u77e5');
    }
  };

  const getCommercialSemanticLabel = (semantic?: string) => {
    switch (semantic) {
      case 'receipt':
        return t('documents.review.semantic.receipt', '\u6536\u94f6\u5c0f\u7968');
      case 'standard_invoice':
        return t('documents.review.semantic.standardInvoice', '\u6b63\u5f0f\u53d1\u7968');
      case 'credit_note':
        return t('documents.review.semantic.creditNote', '\u8d37\u8bb0/\u7ea2\u5b57\u5355\u636e');
      case 'proforma':
        return t('documents.review.semantic.proforma', '\u5f62\u5f0f\u53d1\u7968');
      case 'delivery_note':
        return t('documents.review.semantic.deliveryNote', '\u9001\u8d27\u5355');
      default:
        return t('documents.review.semantic.unknown', '\u6682\u4e0d\u786e\u5b9a');
    }
  };

  const commercialSemanticsOptions = [
    { value: 'standard_invoice', label: getCommercialSemanticLabel('standard_invoice') },
    { value: 'receipt', label: getCommercialSemanticLabel('receipt') },
    { value: 'credit_note', label: getCommercialSemanticLabel('credit_note') },
    { value: 'proforma', label: getCommercialSemanticLabel('proforma') },
    { value: 'delivery_note', label: getCommercialSemanticLabel('delivery_note') },
    { value: 'unknown', label: getCommercialSemanticLabel('unknown') },
  ];

  const getDocumentTypeLabel = (type: string) => {
    if (type === 'purchase_contract' && isAssetPurchaseContract && selectedDocType === type) {
      return t('documents.review.assetPurchaseContract', 'Asset purchase contract');
    }
    return t(`documents.types.${type}`);
  };

  const directionReviewHint = isReceiptDocument
    ? t(
        'documents.review.directionHint.receipt',
        '\u4fdd\u7559\u539f\u6765\u7684\u201c\u6536\u636e\u201d\u6587\u6863\u7c7b\u578b\uff0c\u4e0b\u65b9\u7684\u201c\u4ea4\u6613\u7c7b\u578b\u201d\u4ecd\u7136\u51b3\u5b9a\u8fd9\u7b14\u8bb0\u8d26\u662f\u6536\u5165\u8fd8\u662f\u652f\u51fa\uff1b\u8fd9\u91cc\u7684\u65b9\u5411\u4e0e\u5355\u636e\u8bed\u4e49\u53ea\u662f\u989d\u5916\u7684\u5355\u636e\u5224\u65ad\u3002\u8d85\u5e02/\u5546\u6237\u5c0f\u7968\u901a\u5e38\u662f\u652f\u51fa\u4fa7\u3002'
      )
    : isInvoiceDocument
      ? t(
          'documents.review.directionHint.invoice',
          '\u4fdd\u7559\u539f\u6765\u7684\u201c\u53d1\u7968\u201d\u6587\u6863\u7c7b\u578b\uff0c\u4ea4\u6613\u7c7b\u578b\u4ecd\u7136\u51b3\u5b9a\u8fd9\u7b14\u8bb0\u8d26\u662f\u6536\u5165\u8fd8\u662f\u652f\u51fa\uff1b\u8fd9\u91cc\u7684\u5355\u636e\u8bed\u4e49\u7528\u6765\u533a\u5206\u6b63\u5f0f\u53d1\u7968\u3001\u7ea2\u5b57/\u8d37\u8bb0\u5355\u6216\u5f62\u5f0f\u53d1\u7968\u3002'
        )
      : t(
          'documents.review.directionHint.default',
          '\u8fd9\u4e9b\u65b9\u5411/\u5355\u636e\u8bed\u4e49\u5c5e\u4e8e\u9644\u52a0\u5224\u65ad\uff0c\u4e0d\u4f1a\u53d6\u4ee3\u4e0b\u65b9\u7684\u4ea4\u6613\u7c7b\u578b\u3002'
        );

  return (
    <div className="ocr-review">
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', flexWrap: 'wrap' }}>
        <SubpageBackLink to="/documents" />
        {hasPrevDocument && onPrevDocument && (
          <button className="btn btn-secondary" onClick={onPrevDocument} title={String(t('documents.prevDocument'))}>
            ← {t('documents.prev')}
          </button>
        )}
        {hasNextDocument && onNextDocument && (
          <button className="btn btn-secondary" onClick={onNextDocument} title={String(t('documents.nextDocument'))}>
            {t('documents.next')} →
          </button>
        )}
        {document.file_name && (
          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.9rem', color: 'var(--text2)', minWidth: 0 }} title={document.file_name}>
            {document.file_name}
          </span>
        )}
        <button className="btn btn-primary" onClick={handleDownloadDocument} style={{ marginLeft: 'auto', whiteSpace: 'nowrap' }}>
          {t('documents.download')}
        </button>
      </div>

      <div className="review-header">
        <div className="review-header-main">
          <h2>{t('documents.review.title')}</h2>
          <div className="confidence-badge">
            <span className={getConfidenceClass(document.confidence_score)}>
              {getConfidenceLabel(document.confidence_score)}
            </span>
            {document.confidence_score && (
              <span className="confidence-value">
                {(document.confidence_score * 100).toFixed(0)}%
              </span>
            )}
          </div>
        </div>
      </div>

      {(retryingOcr || reprocessPending) && (
        <div className="review-info-banner">
          {t('documents.reprocessStarted')}
        </div>
      )}

      {document.needs_review && (
        <div className="review-warning">
          {t('documents.review.needsReview')}
        </div>
      )}


      {templateWillSwitchAfterSave && (
        <div className="review-warning">
          {t('documents.review.templateSwitchAfterSave')}
        </div>
      )}

      {suggestions && suggestions.length > 0 && (
        <div className="review-suggestions">
          <h4>{t('documents.review.suggestions')}</h4>
          <ul>
            {suggestions.map((suggestion, index) => {
              // Translate field names in suggestions like "Please verify 'field_name' field"
              const translated = translateDocumentSuggestionText(suggestion.replace(
                /['"“”‘’\[]([A-Za-z][A-Za-z0-9_ ]{1,80})['"“”‘’\]]/g,
                (_match: string, fieldName: string) => `"${formatDocumentFieldLabel(fieldName, t)}"`
              ), t);
              return <li key={index}>{translated}</li>;
            })}
          </ul>
        </div>
      )}

      {/* ── Linked entity panels ── */}
      {(() => {
        const ocrRaw2 = document.ocr_result;
        const ocrP = typeof ocrRaw2 === 'string' ? JSON.parse(ocrRaw2) : ocrRaw2;
        const sug = ocrP?.import_suggestion;
        const entities: { type: string; id: string | number; label: string }[] = [];
        if ((document as any).transaction_id) {
          entities.push({ type: 'transaction', id: (document as any).transaction_id, label: t('documents.linkedEntity.transaction') });
        }
        if (sug && (sug.status === 'confirmed' || sug.status === 'auto-created')) {
          if (sug.recurring_id) entities.push({ type: 'recurring', id: sug.recurring_id, label: t('documents.linkedEntity.recurring') });
          if (sug.data?.matched_property_id) entities.push({ type: 'property', id: sug.data.matched_property_id, label: t('documents.linkedEntity.property') });
          if (sug.asset_id) entities.push({ type: 'asset', id: sug.asset_id, label: t('documents.linkedEntity.asset') });
        }
        if (entities.length === 0) return null;
        return (
          <div className="ocr-linked-entities">
            {entities.map((e) => (
              <div key={`${e.type}-${e.id}`} className={`ocr-linked-entity ocr-linked-entity--${e.type}`}>
                <strong>{e.label}</strong>
                <button className="btn btn-primary btn-sm" onClick={() => {
                  if (e.type === 'recurring') navigate('/recurring');
                  else if (e.type === 'property' || e.type === 'asset') navigate(`/properties/${e.id}`);
                  else navigate('/transactions');
                }}>
                  {t('documents.linkedEntity.open')}
                </button>
              </div>
            ))}
          </div>
        );
      })()}

      <div className="review-content">
        <div className="document-preview">
          <h3>{t('documents.review.preview')}</h3>
          <div className="preview-container">
            {!previewUrl ? (
              <div className="preview-loading">{t('common.loadingPreview')}</div>
            ) : document.mime_type.startsWith('image/') ? (
              <img src={previewUrl} alt={document.file_name} />
            ) : (
              <iframe src={previewUrl} title={document.file_name} />
            )}
          </div>
        </div>

        <div className="extracted-data">
          <h3>{t('documents.review.extractedData')}</h3>
          <fieldset className="review-form-fieldset" disabled={saving}>

          <div className="form-group">
            <label>{t('documents.documentType')}</label>
            <Select value={selectedDocType} onChange={setSelectedDocType}
              disabled={saving}
              options={Object.values(DocumentType).filter(v => v !== 'unknown').map(type => ({
                value: type, label: getDocumentTypeLabel(type),
              }))} />
          </div>

          {isAssetPurchaseContract && (
            <div className="review-warning">
              {t('documents.review.assetPurchaseContractHint', 'This document was recognized as an asset purchase contract. It will be confirmed as asset information rather than property information.')}
            </div>
          )}

          {isContractRoleSensitive && (
            <>
              <div className="form-group">
                <label>{t('documents.review.fields.myRole', '\u6211\u7684\u8eab\u4efd')}</label>
                <Select value={selectedContractRole}
                  disabled={saving}
                  onChange={v => handleFieldChange('user_contract_role', v)}
                  options={contractRoleOptions} />
              </div>

              {contractRoleResolution && (
                <div className="review-contract-role-card">
                  <div className="review-contract-role-card__header">
                    <h4>
                      {t(
                        'documents.review.contractRoleInsight',
                        '\u5408\u540c\u8eab\u4efd\u5224\u65ad'
                      )}
                    </h4>
                    <span className="review-contract-role-pill">
                      {getContractRoleLabel(contractRoleResolution.candidate)}
                    </span>
                  </div>
                  <p className="review-contract-role-card__summary">
                    {t(
                      'documents.review.contractRoleSummary',
                      '\u7cfb\u7edf\u5728\u8fd9\u4efd\u5408\u540c\u4e2d\u5f53\u524d\u66f4\u503e\u5411\u4e8e\u8fd9\u4e2a\u8eab\u4efd\u3002'
                    )}
                  </p>
                  <div className="review-contract-role-card__meta">
                    <span>
                      {t(
                        'documents.review.contractRoleSourceLabel',
                        '\u5224\u65ad\u6765\u6e90'
                      )}
                      {': '}
                      {getContractRoleSourceLabel(contractRoleResolution.source)}
                    </span>
                    {formatPercent(contractRoleResolution.confidence) && (
                      <span>
                        {t(
                          'documents.review.contractRoleConfidenceLabel',
                          '\u7f6e\u4fe1\u5ea6'
                        )}
                        {': '}
                        {formatPercent(contractRoleResolution.confidence)}
                      </span>
                    )}
                  </div>
                  {Array.isArray(contractRoleResolution.evidence) &&
                    contractRoleResolution.evidence.length > 0 && (
                      <ul className="review-contract-role-card__evidence">
                        {contractRoleResolution.evidence.map((item: string, index: number) => (
                          <li key={`${item}-${index}`}>{translateEvidence(item, t)}</li>
                        ))}
                      </ul>
                    )}
                  {contractRoleResolution.strict_would_block && (
                    <div className="review-warning review-warning-compact">
                      {t(
                        'documents.review.contractRoleWarning',
                        `\u7cfb\u7edf\u5bf9\u8fd9\u4efd\u6587\u6863\u4e2d\u7684\u8eab\u4efd\u5224\u65ad\u7f6e\u4fe1\u5ea6\u8f83\u4f4e\uff0c\u5efa\u8bae\u5148\u786e\u8ba4\u8eab\u4efd\uff0c\u518d\u7ee7\u7eed${getContractRoleBlockTargetLabel()}\u76f8\u5173\u64cd\u4f5c\u3002`
                      )}
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {isDirectionSensitive && (
            <>
              <div className="review-info-banner review-direction-hint">
                {directionReviewHint}
              </div>

              <div className="form-group">
                <label>{t('documents.review.transactionType')}</label>
                <div className="txn-type-toggle">
                  <button
                    type="button"
                    className={`toggle-btn ${selectedTxnType === 'income' ? 'active income' : ''}`}
                    onClick={() => { setSelectedTxnType('income'); handleFieldChange('document_transaction_direction', 'income'); }}
                  >
                    {t('transactions.types.income')}
                  </button>
                  <button
                    type="button"
                    className={`toggle-btn ${selectedTxnType === 'expense' ? 'active expense' : ''}`}
                    onClick={() => { setSelectedTxnType('expense'); handleFieldChange('document_transaction_direction', 'expense'); }}
                  >
                    {t('transactions.types.expense')}
                  </button>
                </div>
              </div>

              <div className="form-group">
                <label>{t('documents.review.fields.documentSemantics', '\u5355\u636e\u8bed\u4e49\uff08\u9644\u52a0\u5206\u7c7b\uff09')}</label>
                <Select
                  value={selectedCommercialSemantics}
                  disabled={saving}
                  onChange={(value) => handleFieldChange('commercial_document_semantics', value)}
                  options={commercialSemanticsOptions}
                />
              </div>

              {transactionDirectionResolution && (
                <div className="review-direction-card">
                  <div className="review-direction-card__header">
                    <h4>{t('documents.review.directionInsight', '\u5355\u636e\u65b9\u5411\u4e0e\u573a\u666f\u5224\u65ad')}</h4>
                    <div className="review-direction-card__pills">
                      <span className="review-contract-role-pill">
                        {getDirectionLabel(transactionDirectionResolution.candidate)}
                      </span>
                      <span className="review-contract-role-pill review-contract-role-pill--secondary">
                        {getCommercialSemanticLabel(
                          transactionDirectionResolution.semantics ?? selectedCommercialSemantics
                        )}
                      </span>
                    </div>
                  </div>
                  <p className="review-contract-role-card__summary">
                    {t(
                      'documents.review.directionSummary',
                      '\u7cfb\u7edf\u5728\u8fd9\u4efd\u5355\u636e\u4e2d\u7ed9\u51fa\u201c\u65b9\u5411 + \u5355\u636e\u573a\u666f\u201d\u7684\u9884\u5224\uff0c\u4f46\u771f\u6b63\u8fdb\u8d26\u7684\u6536\u5165/\u652f\u51fa\u4ecd\u7531\u4e0a\u65b9\u7684\u4ea4\u6613\u7c7b\u578b\u51b3\u5b9a\u3002'
                    )}
                  </p>
                  <div className="review-contract-role-card__meta">
                    <span>
                      {t('documents.review.directionSourceLabel', '\u5224\u65ad\u6765\u6e90')}
                      {': '}
                      {getDirectionSourceLabel(transactionDirectionResolution.source)}
                    </span>
                    {formatPercent(transactionDirectionResolution.confidence) && (
                      <span>
                        {t('documents.review.directionConfidenceLabel', '\u7f6e\u4fe1\u5ea6')}
                        {': '}
                        {formatPercent(transactionDirectionResolution.confidence)}
                      </span>
                    )}
                    {transactionDirectionResolution.is_reversal && (
                      <span>{t('documents.review.directionReversal', '\u8fd9\u662f\u4e00\u5f20\u51b2\u9500/\u8d37\u8bb0\u5355\u636e')}</span>
                    )}
                  </div>
                  {Array.isArray(transactionDirectionResolution.evidence) &&
                    transactionDirectionResolution.evidence.length > 0 && (
                      <ul className="review-contract-role-card__evidence">
                        {transactionDirectionResolution.evidence.map((item: string, index: number) => (
                          <li key={`${item}-${index}`}>{translateEvidence(item, t)}</li>
                        ))}
                      </ul>
                    )}
                  {transactionDirectionResolution.strict_would_block && (
                    <div className="review-warning review-warning-compact">
                      {t(
                        'documents.review.directionWarning',
                        '\u7cfb\u7edf\u5bf9\u8fd9\u4efd\u5355\u636e\u7684\u4ea4\u6613\u65b9\u5411\u5224\u65ad\u7f6e\u4fe1\u5ea6\u8f83\u4f4e\uff0c\u5efa\u8bae\u5148\u4eba\u5de5\u786e\u8ba4\u65b9\u5411\u548c\u5355\u636e\u7c7b\u578b\u3002'
                      )}
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {isTaxDataReview ? (
            <div className="review-tax-fields">
              <div className="review-info-banner tax-review-hint">
                {t(
                  'documents.review.taxImportHint',
                  '\u8fd9\u4efd\u7a0e\u8868\u6216\u7a0e\u52a1\u9644\u8868\u7684\u6570\u636e\u4f1a\u5199\u5165\u7a0e\u52a1\u6863\u6848\uff0c\u7528\u4e8e\u540e\u7eed\u7533\u62a5\u9884\u586b\uff0c\u62a5\u544a\u751f\u6210\u548c\u5ba1\u8ba1\u51c6\u5907\uff0c\u4e0d\u4f1a\u521b\u5efa\u666e\u901a\u4ea4\u6613\u3002\u8bf7\u5148\u6838\u5bf9\u6216\u4fee\u6539\u63d0\u53d6\u5b57\u6bb5\uff0c\u7136\u540e\u786e\u8ba4\u4fdd\u5b58\u3002'
                )}
              </div>

              {taxFieldKeys.length === 0 ? (
                <div className="review-warning">
                  {t(
                    'documents.review.taxFieldsUnavailable',
                    '\u5f53\u524d\u8fd8\u6ca1\u6709\u53ef\u7f16\u8f91\u7684\u7a0e\u52a1\u5b57\u6bb5\uff0c\u8bf7\u5148\u91cd\u65b0\u5904\u7406\u6587\u6863\u6216\u7a0d\u540e\u518d\u8bd5\u3002'
                  )}
                </div>
              ) : (
                taxFieldKeys.map((fieldName) => {
                  const currentValue =
                    editedData[fieldName] ?? extracted_data[fieldName] ?? '';
                  const fieldConfidence = extracted_data.confidence?.[fieldName];
                  const looksNumeric =
                    typeof currentValue === 'number' ||
                    /^kz_\d+$/i.test(fieldName) ||
                    [
                      'tax_year',
                      'year',
                      'umsatz_20',
                      'umsatz_10',
                      'vorsteuer',
                      'zahllast',
                      'gewinn_verlust',
                    ].includes(fieldName);

                  return (
                    <div className="form-group" key={fieldName}>
                      <label>{formatDocumentFieldLabel(fieldName, t)}</label>
                      <input
                        type={looksNumeric ? 'number' : 'text'}
                        step={looksNumeric ? '0.01' : undefined}
                        value={currentValue}
                        onChange={(e) => {
                          const nextValue = e.target.value;
                          handleFieldChange(
                            fieldName,
                            looksNumeric
                              ? (nextValue === '' ? null : Number(nextValue))
                              : nextValue
                          );
                        }}
                        className={getConfidenceClass(fieldConfidence)}
                      />
                      {fieldConfidence && (
                        <span className="field-confidence">
                          {(fieldConfidence * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          ) : (
            <>
              {!isDirectionSensitive && (
                <div className="form-group">
                  <label>{t('documents.review.transactionType')}</label>
                  <div className="txn-type-toggle">
                    <button
                      type="button"
                      className={`toggle-btn ${selectedTxnType === 'income' ? 'active income' : ''}`}
                      onClick={() => { setSelectedTxnType('income'); handleFieldChange('document_transaction_direction', 'income'); }}
                    >
                      {t('transactions.types.income')}
                    </button>
                    <button
                      type="button"
                      className={`toggle-btn ${selectedTxnType === 'expense' ? 'active expense' : ''}`}
                      onClick={() => { setSelectedTxnType('expense'); handleFieldChange('document_transaction_direction', 'expense'); }}
                    >
                      {t('transactions.types.expense')}
                    </button>
                  </div>
                </div>
              )}

              <div className="form-group">
                <label>{t('documents.review.fields.date')}</label>
                <DateInput
                  value={editedData.date || ''}
                  onChange={(val) => handleFieldChange('date', val)}
                  className={getConfidenceClass(extracted_data.confidence?.date)}
                  locale={getLocaleForLanguage(i18n.language)}
                  todayLabel={String(t('common.today', 'Today'))}
                />
                {extracted_data.confidence?.date && (
                  <span className="field-confidence">
                    {(extracted_data.confidence.date * 100).toFixed(0)}%
                  </span>
                )}
              </div>

              <div className="form-group">
                <label>{t('documents.review.fields.amount')}</label>
                <input
                  type="number"
                  step="0.01"
                  value={editedData.amount || ''}
                  onChange={(e) =>
                    handleFieldChange('amount', parseFloat(e.target.value))
                  }
                  className={getConfidenceClass(extracted_data.confidence?.amount)}
                />
                {extracted_data.confidence?.amount && (
                  <span className="field-confidence">
                    {(extracted_data.confidence.amount * 100).toFixed(0)}%
                  </span>
                )}
              </div>

              <div className="form-group">
                <label>{t('documents.review.fields.merchant')}</label>
                <input
                  type="text"
                  value={editedData.merchant || ''}
                  onChange={(e) => handleFieldChange('merchant', e.target.value)}
                  className={getConfidenceClass(extracted_data.confidence?.merchant)}
                />
                {extracted_data.confidence?.merchant && (
                  <span className="field-confidence">
                    {(extracted_data.confidence.merchant * 100).toFixed(0)}%
                  </span>
                )}
              </div>
            </>
          )}

          {!isTaxDataReview && extracted_data.gross_income !== undefined && (
            <div className="form-group">
              <label>{t('documents.review.fields.grossIncome')}</label>
              <input
                type="number"
                step="0.01"
                value={editedData.gross_income || ''}
                onChange={(e) =>
                  handleFieldChange('gross_income', parseFloat(e.target.value))
                }
              />
            </div>
          )}

          {!isTaxDataReview && extracted_data.net_income !== undefined && (
            <div className="form-group">
              <label>{t('documents.review.fields.netIncome')}</label>
              <input
                type="number"
                step="0.01"
                value={editedData.net_income || ''}
                onChange={(e) =>
                  handleFieldChange('net_income', parseFloat(e.target.value))
                }
              />
            </div>
          )}

          {!isTaxDataReview && extracted_data.withheld_tax !== undefined && (
            <div className="form-group">
              <label>{t('documents.review.fields.withheldTax')}</label>
              <input
                type="number"
                step="0.01"
                value={editedData.withheld_tax || ''}
                onChange={(e) =>
                  handleFieldChange('withheld_tax', parseFloat(e.target.value))
                }
              />
            </div>
          )}

          {!isTaxDataReview && extracted_data.employer && (
            <div className="form-group">
              <label>{t('documents.review.fields.employer')}</label>
              <input
                type="text"
                value={editedData.employer || ''}
                onChange={(e) => handleFieldChange('employer', e.target.value)}
              />
            </div>
          )}

          {!isTaxDataReview && extracted_data.invoice_number && (
            <div className="form-group">
              <label>{t('documents.review.fields.invoiceNumber')}</label>
              <input
                type="text"
                value={editedData.invoice_number || ''}
                onChange={(e) =>
                  handleFieldChange('invoice_number', e.target.value)
                }
              />
            </div>
          )}

          {/* Mietvertrag (rental contract) specific fields */}
          {(selectedDocType === 'rental_contract' || selectedDocType === 'mietvertrag') && (
            <>
              <div className="form-group">
                <label>{t('documents.review.fields.propertyAddress')}</label>
                <input type="text" value={editedData.property_address || ''} onChange={(e) => handleFieldChange('property_address', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.monthlyRent')}</label>
                <input type="number" step="0.01" value={editedData.monthly_rent ?? ''} onChange={(e) => handleFieldChange('monthly_rent', parseFloat(e.target.value) || null)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.startDate')}</label>
                <DateInput value={editedData.start_date ? String(editedData.start_date).substring(0, 10) : ''} onChange={(val) => handleFieldChange('start_date', val)} locale={getLocaleForLanguage(i18n.language)} todayLabel={String(t('common.today', 'Today'))} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.endDate')}</label>
                <DateInput value={editedData.end_date ? String(editedData.end_date).substring(0, 10) : ''} onChange={(val) => handleFieldChange('end_date', val)} locale={getLocaleForLanguage(i18n.language)} todayLabel={String(t('common.today', 'Today'))} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.tenantName')}</label>
                <input type="text" value={editedData.tenant_name || ''} onChange={(e) => handleFieldChange('tenant_name', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.landlordName')}</label>
                <input type="text" value={editedData.landlord_name || ''} onChange={(e) => handleFieldChange('landlord_name', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.contractType')}</label>
                <input type="text" value={editedData.contract_type || ''} onChange={(e) => handleFieldChange('contract_type', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.betriebskosten')}</label>
                <input type="number" step="0.01" value={editedData.betriebskosten ?? ''} onChange={(e) => handleFieldChange('betriebskosten', parseFloat(e.target.value) || null)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.heatingCosts')}</label>
                <input type="number" step="0.01" value={editedData.heating_costs ?? ''} onChange={(e) => handleFieldChange('heating_costs', parseFloat(e.target.value) || null)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.depositAmount')}</label>
                <input type="number" step="0.01" value={editedData.deposit_amount ?? ''} onChange={(e) => handleFieldChange('deposit_amount', parseFloat(e.target.value) || null)} />
              </div>
            </>
          )}

          {/* Kreditvertrag (loan contract) specific fields */}
          {(selectedDocType === 'loan_contract' || selectedDocType === 'kreditvertrag') && (
            <>
              <div className="form-group">
                <label>{t('documents.review.fields.loanAmount')}</label>
                <input type="number" step="0.01" value={editedData.loan_amount ?? ''} onChange={(e) => handleFieldChange('loan_amount', parseFloat(e.target.value) || null)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.interestRate')}</label>
                <input type="number" step="0.01" value={editedData.interest_rate ?? ''} onChange={(e) => handleFieldChange('interest_rate', parseFloat(e.target.value) || null)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.monthlyPayment')}</label>
                <input type="number" step="0.01" value={editedData.monthly_payment ?? ''} onChange={(e) => handleFieldChange('monthly_payment', parseFloat(e.target.value) || null)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.lenderName')}</label>
                <input type="text" value={editedData.lender_name || ''} onChange={(e) => handleFieldChange('lender_name', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.borrowerName')}</label>
                <input type="text" value={editedData.borrower_name || ''} onChange={(e) => handleFieldChange('borrower_name', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.contractNumber')}</label>
                <input type="text" value={editedData.contract_number || ''} onChange={(e) => handleFieldChange('contract_number', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.loanStartDate')}</label>
                <DateInput value={editedData.start_date ? String(editedData.start_date).substring(0, 10) : ''} onChange={(val) => handleFieldChange('start_date', val)} locale={getLocaleForLanguage(i18n.language)} todayLabel={String(t('common.today', 'Today'))} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.loanEndDate')}</label>
                <DateInput value={editedData.end_date ? String(editedData.end_date).substring(0, 10) : ''} onChange={(val) => handleFieldChange('end_date', val)} locale={getLocaleForLanguage(i18n.language)} todayLabel={String(t('common.today', 'Today'))} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.firstRateDate')}</label>
                <DateInput value={editedData.first_rate_date ? String(editedData.first_rate_date).substring(0, 10) : ''} onChange={(val) => handleFieldChange('first_rate_date', val)} locale={getLocaleForLanguage(i18n.language)} todayLabel={String(t('common.today', 'Today'))} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.termYears')}</label>
                <input type="number" step="1" value={editedData.term_years ?? ''} onChange={(e) => handleFieldChange('term_years', parseInt(e.target.value) || null)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.termMonths')}</label>
                <input type="number" step="1" value={editedData.term_months ?? ''} onChange={(e) => handleFieldChange('term_months', parseInt(e.target.value) || null)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.loanPurpose')}</label>
                <input type="text" value={editedData.purpose || ''} onChange={(e) => handleFieldChange('purpose', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.loanPropertyAddress')}</label>
                <input type="text" value={editedData.property_address || ''} onChange={(e) => handleFieldChange('property_address', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.annualInterestAmount')}</label>
                <input type="number" step="0.01" value={editedData.annual_interest_amount ?? ''} onChange={(e) => handleFieldChange('annual_interest_amount', parseFloat(e.target.value) || null)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.certificateYear')}</label>
                <input type="number" step="1" value={editedData.certificate_year ?? ''} onChange={(e) => handleFieldChange('certificate_year', parseInt(e.target.value) || null)} />
              </div>
            </>
          )}

          {/* Versicherungsbestätigung (insurance confirmation) specific fields */}
          {selectedDocType === 'versicherungsbestaetigung' && (
            <>
              <div className="form-group">
                <label>{t('documents.review.fields.insurerName')}</label>
                <input type="text" value={editedData.insurer_name || editedData.versicherer || ''} onChange={(e) => handleFieldChange('insurer_name', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.policyHolderName')}</label>
                <input type="text" value={editedData.policy_holder_name || editedData.versicherungsnehmer || ''} onChange={(e) => handleFieldChange('policy_holder_name', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.insuranceType')}</label>
                <input type="text" value={editedData.insurance_type || editedData.versicherungsart || ''} onChange={(e) => handleFieldChange('insurance_type', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.premium')}</label>
                <input type="number" step="0.01" value={editedData.praemie ?? editedData.premium ?? ''} onChange={(e) => handleFieldChange('praemie', parseFloat(e.target.value) || null)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.policyNumber')}</label>
                <input type="text" value={editedData.polizze || ''} onChange={(e) => handleFieldChange('polizze', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.paymentFrequency')}</label>
                <input type="text" value={editedData.zahlungsfrequenz || editedData.payment_frequency || ''} onChange={(e) => handleFieldChange('payment_frequency', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.startDate')}</label>
                <DateInput value={editedData.start_date ? String(editedData.start_date).substring(0, 10) : ''} onChange={(val) => handleFieldChange('start_date', val)} locale={getLocaleForLanguage(i18n.language)} todayLabel={String(t('common.today', 'Today'))} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.endDate')}</label>
                <DateInput value={editedData.end_date ? String(editedData.end_date).substring(0, 10) : ''} onChange={(val) => handleFieldChange('end_date', val)} locale={getLocaleForLanguage(i18n.language)} todayLabel={String(t('common.today', 'Today'))} />
              </div>
            </>
          )}

          {/* Kaufvertrag (purchase contract) specific fields */}
          {isPropertyPurchaseContract && (
            <>
              <div className="form-group">
                <label>{t('documents.review.fields.propertyAddress')}</label>
                <input type="text" value={editedData.property_address || ''} onChange={(e) => handleFieldChange('property_address', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.purchasePrice')}</label>
                <input type="number" step="0.01" value={editedData.purchase_price ?? ''} onChange={(e) => handleFieldChange('purchase_price', parseFloat(e.target.value) || null)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.purchaseDate')}</label>
                <DateInput value={editedData.purchase_date ? String(editedData.purchase_date).substring(0, 10) : ''} onChange={(val) => handleFieldChange('purchase_date', val)} locale={getLocaleForLanguage(i18n.language)} todayLabel={String(t('common.today', 'Today'))} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.buyerName')}</label>
                <input type="text" value={editedData.buyer_name || ''} onChange={(e) => handleFieldChange('buyer_name', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.sellerName')}</label>
                <input type="text" value={editedData.seller_name || ''} onChange={(e) => handleFieldChange('seller_name', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.buildingValue')}</label>
                <input type="number" step="0.01" value={editedData.building_value ?? ''} onChange={(e) => handleFieldChange('building_value', parseFloat(e.target.value) || null)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.landValue')}</label>
                <input type="number" step="0.01" value={editedData.land_value ?? ''} onChange={(e) => handleFieldChange('land_value', parseFloat(e.target.value) || null)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.grunderwerbsteuer')}</label>
                <input type="number" step="0.01" value={editedData.grunderwerbsteuer ?? ''} onChange={(e) => handleFieldChange('grunderwerbsteuer', parseFloat(e.target.value) || null)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.notaryName')}</label>
                <input type="text" value={editedData.notary_name || ''} onChange={(e) => handleFieldChange('notary_name', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.notaryFees')}</label>
                <input type="number" step="0.01" value={editedData.notary_fees ?? ''} onChange={(e) => handleFieldChange('notary_fees', parseFloat(e.target.value) || null)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.registryFees')}</label>
                <input type="number" step="0.01" value={editedData.registry_fees ?? ''} onChange={(e) => handleFieldChange('registry_fees', parseFloat(e.target.value) || null)} />
              </div>
            </>
          )}

          {isAssetPurchaseContract && (
            <>
              <div className="form-group">
                <label>{t('documents.review.fields.assetName', 'Asset Name')}</label>
                <input
                  type="text"
                  value={editedData.asset_name || ''}
                  onChange={(e) => handleFieldChange('asset_name', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.assetType', 'Asset Type')}</label>
                <input
                  type="text"
                  value={editedData.asset_type || ''}
                  onChange={(e) => handleFieldChange('asset_type', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.purchasePrice')}</label>
                <input
                  type="number"
                  step="0.01"
                  value={editedData.purchase_price ?? ''}
                  onChange={(e) => handleFieldChange('purchase_price', parseFloat(e.target.value) || null)}
                />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.purchaseDate')}</label>
                <DateInput
                  value={editedData.purchase_date ? String(editedData.purchase_date).substring(0, 10) : ''}
                  onChange={(val) => handleFieldChange('purchase_date', val)}
                  locale={getLocaleForLanguage(i18n.language)}
                  todayLabel={String(t('common.today', 'Today'))}
                />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.buyerName')}</label>
                <input type="text" value={editedData.buyer_name || ''} onChange={(e) => handleFieldChange('buyer_name', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.sellerName')}</label>
                <input type="text" value={editedData.seller_name || ''} onChange={(e) => handleFieldChange('seller_name', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.firstRegistrationDate', 'First Registration Date')}</label>
                <DateInput
                  value={editedData.first_registration_date ? String(editedData.first_registration_date).substring(0, 10) : ''}
                  onChange={(val) => handleFieldChange('first_registration_date', val)}
                  locale={getLocaleForLanguage(i18n.language)}
                  todayLabel={String(t('common.today', 'Today'))}
                />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.vehicleIdentificationNumber', 'VIN / Vehicle Identification Number')}</label>
                <input
                  type="text"
                  value={editedData.vehicle_identification_number || ''}
                  onChange={(e) => handleFieldChange('vehicle_identification_number', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.licensePlate', 'License Plate')}</label>
                <input
                  type="text"
                  value={editedData.license_plate || ''}
                  onChange={(e) => handleFieldChange('license_plate', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.mileageKm', 'Mileage (km)')}</label>
                <input
                  type="number"
                  step="1"
                  value={editedData.mileage_km ?? ''}
                  onChange={(e) => handleFieldChange('mileage_km', parseFloat(e.target.value) || null)}
                />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.previousOwners', 'Previous Owners')}</label>
                <input
                  type="number"
                  step="1"
                  value={editedData.previous_owners ?? ''}
                  onChange={(e) => handleFieldChange('previous_owners', parseFloat(e.target.value) || null)}
                />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.isUsedAsset', 'Used Asset')}</label>
                <Select
                  value={editedData.is_used_asset === true ? 'yes' : editedData.is_used_asset === false ? 'no' : ''}
                  disabled={saving}
                  onChange={v => handleFieldChange('is_used_asset', v === 'yes' ? true : v === 'no' ? false : null)}
                  placeholder={t('common.pleaseSelect', 'Please select...')}
                  options={[
                    { value: 'yes', label: t('common.yes', 'Yes') },
                    { value: 'no', label: t('common.no', 'No') },
                  ]} />
              </div>
            </>
          )}

          {extracted_data.vat_amounts &&
            Object.keys(extracted_data.vat_amounts).length > 0 && (
              <div className="vat-amounts">
                <h4>{t('documents.review.vatAmounts')}</h4>
                {Object.entries(extracted_data.vat_amounts).map(
                  ([rate, amount]) => (
                    <div key={rate} className="vat-item">
                      <span>{rate}:</span>
                      <span>{formatCurrencyValue(amount, i18n.language)}</span>
                    </div>
                  )
                )}
              </div>
            )}
          {/* Dynamic extra fields: show any extracted fields not already displayed by type-specific blocks */}
          {!isTaxDataReview && (() => {
            const displayedKeys = new Set([
              'date', 'amount', 'merchant', 'gross_income', 'net_income', 'withheld_tax',
              'employer', 'invoice_number', 'vat_amount', 'vat_rate', 'payment_method',
              // rental contract
              'property_address', 'monthly_rent', 'start_date', 'end_date', 'tenant_name',
              'landlord_name', 'contract_type', 'betriebskosten', 'heating_costs', 'deposit_amount',
              // purchase contract
              'purchase_price', 'purchase_date', 'buyer_name', 'seller_name', 'building_value',
              'land_value', 'grunderwerbsteuer', 'notary_name', 'notary_fees', 'registry_fees',
              'construction_year', 'property_type',
              // asset purchase
              'asset_name', 'asset_type', 'first_registration_date', 'vehicle_identification_number',
              'license_plate', 'mileage_km', 'previous_owners', 'is_used_asset',
              // loan contract
              'loan_amount', 'interest_rate', 'monthly_payment', 'lender_name', 'borrower_name',
              'contract_number', 'first_rate_date', 'term_years', 'term_months', 'purpose',
              'annual_interest_amount', 'certificate_year',
              // insurance
              'insurer_name', 'versicherer', 'policy_holder_name', 'versicherungsnehmer',
              'insurance_type', 'versicherungsart', 'praemie', 'polizze',
              'payment_frequency', 'zahlungsfrequenz',
              // internal/meta
              '_transaction_type', '_document_type', 'user_contract_role', 'user_contract_role_source',
              'document_transaction_direction', 'document_transaction_direction_source',
              'document_transaction_direction_confidence', 'commercial_document_semantics',
              'is_reversal', 'field_confidence', 'confidence', 'import_suggestion', 'asset_outcome',
              'line_items', 'items', 'vat_summary', 'vat_amounts', 'tax_analysis',
              '_additional_receipts', '_receipt_count', '_pipeline', '_validation',
              'correction_history', 'multiple_receipts', 'receipt_count', 'receipts',
              'total_amount', 'purchase_contract_kind', '_extraction_method', '_llm_supplement',
            ]);
            const extraFields = Object.entries(editedData).filter(
              ([k, v]) => !displayedKeys.has(k) && !k.startsWith('_') && v !== null && v !== undefined && typeof v !== 'object'
            );
            if (extraFields.length === 0) return null;
            return (
              <>
                <h4 style={{ marginTop: '16px', fontSize: '0.9rem', color: 'var(--color-text-secondary, #6b7280)' }}>
                  {t('documents.review.additionalFields')}
                </h4>
                {extraFields.map(([key, val]) => (
                  <div className="form-group" key={key}>
                    <label>{formatDocumentFieldLabel(key, t)}</label>
                    <input
                      type={typeof val === 'number' ? 'number' : 'text'}
                      step={typeof val === 'number' ? '0.01' : undefined}
                      value={editedData[key] ?? ''}
                      onChange={(e) => handleFieldChange(key, typeof val === 'number' ? (parseFloat(e.target.value) || null) : e.target.value)}
                    />
                  </div>
                ))}
              </>
            );
          })()}

          </fieldset>
        </div>
      </div>

      <div className="review-actions">
        <button
          className="btn btn-secondary"
          onClick={handleCancel}
          disabled={saving}
        >
          {t('common.cancel')}
        </button>
        <button
          className="btn btn-primary"
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? t('common.saving') : t('common.save')}
        </button>
      </div>

      {/* AI Chat Widget with document context */}
    </div>
  );
};

export default OCRReview;
