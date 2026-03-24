import React from 'react';
import { resolveDocumentPresentation } from '../../documents/presentation/resolveDocumentPresentation';
import type {
  DocumentLike,
  DocumentPresentationDecision,
  DocumentPresentationMode,
} from '../../documents/presentation/types';

type RenderContext = {
  decision: DocumentPresentationDecision;
  initialMode: DocumentPresentationMode;
};

interface DocumentPresentationRouterProps {
  document: DocumentLike;
  decision?: DocumentPresentationDecision;
  renderReceiptWorkbench: (context: RenderContext) => React.ReactNode;
  renderContractReview: (context: RenderContext) => React.ReactNode;
  renderBankStatementReview?: (context: RenderContext) => React.ReactNode;
  renderGenericReview: (context: RenderContext) => React.ReactNode;
  renderTaxImport?: (context: RenderContext) => React.ReactNode;
  onFallback?: (error: unknown) => React.ReactNode;
}

const emitRouterEvent = (name: string, detail: Record<string, unknown>) => {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(name, { detail }));
  }

  if (import.meta.env.DEV) {
    console.debug(`[document-presentation] ${name}`, detail);
  }
};

const readOcrMetaValue = (document: DocumentLike, key: string): unknown => {
  if (!document.ocr_result || typeof document.ocr_result !== 'object') {
    return null;
  }

  return (document.ocr_result as Record<string, unknown>)[key] ?? null;
};

const buildFallbackDecision = (document: DocumentLike): DocumentPresentationDecision => ({
  normalizedType: 'generic',
  template: 'generic_review',
  initialMode: 'readonly',
  controlPolicy: {
    transactionType: 'unknown',
    isPostable: true,
    isExpenseLike: false,
    isReversalLike: false,
    hideDeductibility: true,
    hideCreateActions: false,
    allowCreateActions: true,
    allowSyncActions: true,
    allowSuggestionCreateActions: true,
  },
  badges: [],
  helpers: ['The document presentation fell back to the generic readonly view.'],
  reason: 'Resolver fallback',
  source: {
    rawDocumentType: document.document_type ?? null,
    matchedAlias: null,
    taxImportMatched: false,
  },
});

const DocumentPresentationRouter: React.FC<DocumentPresentationRouterProps> = ({
  document,
  decision,
  renderReceiptWorkbench,
  renderContractReview,
  renderBankStatementReview,
  renderGenericReview,
  renderTaxImport,
  onFallback,
}) => {
  try {
    const effectiveDecision = decision ?? resolveDocumentPresentation(document);
    const context = {
      decision: effectiveDecision,
      initialMode: effectiveDecision.initialMode,
    };

    emitRouterEvent('document_presentation_resolved', {
      document_id: document.id ?? null,
      raw_document_type: document.document_type ?? null,
      normalized_type: effectiveDecision.normalizedType,
      template: effectiveDecision.template,
      initial_mode: effectiveDecision.initialMode,
      semantic: readOcrMetaValue(document, 'commercial_document_semantics'),
      transaction_type:
        readOcrMetaValue(document, '_transaction_type')
        ?? readOcrMetaValue(document, 'transaction_type'),
    });

    emitRouterEvent('document_template_rendered', {
      document_id: document.id ?? null,
      raw_document_type: document.document_type ?? null,
      normalized_type: effectiveDecision.normalizedType,
      template: effectiveDecision.template,
      initial_mode: effectiveDecision.initialMode,
    });

    switch (effectiveDecision.template) {
      case 'tax_import':
        if (renderTaxImport) return <>{renderTaxImport(context)}</>;
        return <>{renderGenericReview(context)}</>;
      case 'receipt_workbench':
        return <>{renderReceiptWorkbench(context)}</>;
      case 'contract_review':
        return <>{renderContractReview(context)}</>;
      case 'bank_statement_review':
        if (renderBankStatementReview) return <>{renderBankStatementReview(context)}</>;
        return <>{renderGenericReview(context)}</>;
      case 'generic_review':
      default:
        return <>{renderGenericReview(context)}</>;
    }
  } catch (error) {
    emitRouterEvent('document_fallback_triggered', {
      document_id: document.id ?? null,
      raw_document_type: document.document_type ?? null,
      fallback_reason: error instanceof Error ? error.message : 'unknown_error',
    });

    if (onFallback) {
      return <>{onFallback(error)}</>;
    }

    return <>{renderGenericReview({ decision: buildFallbackDecision(document), initialMode: 'readonly' })}</>;
  }
};

export default DocumentPresentationRouter;
