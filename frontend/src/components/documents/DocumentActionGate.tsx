import React, { useEffect } from 'react';
import type {
  ActionGateDisplayMode,
  DocumentControlPolicy,
  DocumentPresentationAction,
} from '../../documents/presentation/types';

const DEFAULT_BLOCK_REASON = 'This action is unavailable for the current document semantics.';

const getDocumentActionDisplayMode = (
  policy: DocumentControlPolicy,
  action: DocumentPresentationAction
): ActionGateDisplayMode => {
  switch (action) {
    case 'suggestion_create':
      return policy.allowSuggestionCreateActions ? 'enabled' : 'disabled';
    case 'sync_transaction':
      return policy.allowSyncActions ? 'enabled' : 'hidden';
    case 'create_transaction':
    case 'confirm_and_create':
      return policy.allowCreateActions ? 'enabled' : 'hidden';
    case 'bulk_expense_quick_actions':
    case 'deductibility_controls':
      return policy.hideDeductibility ? 'hidden' : 'enabled';
    default:
      return 'enabled';
  }
};

const getDocumentActionBlockReason = (
  policy: DocumentControlPolicy,
  action: DocumentPresentationAction,
  helpers: string[] = []
): string => {
  if (policy.isPostable) {
    return helpers[0] || DEFAULT_BLOCK_REASON;
  }

  if (action === 'suggestion_create') {
    return helpers[0] || DEFAULT_BLOCK_REASON;
  }

  return helpers[0] || DEFAULT_BLOCK_REASON;
};

interface DocumentActionGateProps {
  action: DocumentPresentationAction;
  policy: DocumentControlPolicy;
  helpers?: string[];
  telemetryContext?: Record<string, unknown>;
  children: (state: {
    displayMode: ActionGateDisplayMode;
    disabled: boolean;
    hidden: boolean;
    reason: string;
  }) => React.ReactNode;
}

const DocumentActionGate: React.FC<DocumentActionGateProps> = ({
  action,
  policy,
  helpers = [],
  telemetryContext,
  children,
}) => {
  const displayMode = getDocumentActionDisplayMode(policy, action);
  const hidden = displayMode === 'hidden';
  const disabled = displayMode === 'disabled';
  const reason = getDocumentActionBlockReason(policy, action, helpers);

  useEffect(() => {
    if (displayMode === 'enabled' || typeof window === 'undefined') {
      return;
    }

    const detail = {
      action,
      display_mode: displayMode,
      reason,
      ...telemetryContext,
    };

    window.dispatchEvent(new CustomEvent('document_action_blocked', { detail }));

    if (import.meta.env.DEV) {
      console.debug('[document-presentation] document_action_blocked', detail);
    }
  }, [action, displayMode, reason, telemetryContext]);

  return (
    <>
      {children({
        displayMode,
        disabled,
        hidden,
        reason,
      })}
    </>
  );
};

export default DocumentActionGate;
