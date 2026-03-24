/* eslint-disable react-refresh/only-export-components */
/* eslint-disable @typescript-eslint/no-explicit-any */
import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  Banknote,
  Building2,
  CheckCircle2,
  ClipboardList,
  FileText,
  House,
  Landmark,
  Loader2,
  MessageCircle,
  ReceiptText,
  Repeat2,
  Wallet,
  type LucideIcon,
} from 'lucide-react';
import { useAIAdvisorStore } from '../../../stores/aiAdvisorStore';
import FuturisticIcon, { type FuturisticIconTone } from '../../common/FuturisticIcon';
import { getLocaleForLanguage } from '../../../utils/locale';
import i18nInstance from '../../../i18n';
import './SuggestionCardBase.css';

export interface SuggestionCardProps {
  suggestion: { type: string; data: Record<string, any>; status?: string };
  confirmResult: { type: 'success' | 'error'; message: string } | null;
  confirmingAction: string | null;
  onConfirm: (payload?: unknown) => void;
  onDismiss: () => void;
  confirmActionKey?: string;
  confirmLabel?: string;
  confirmDisabled?: boolean;
  confirmDisabledReason?: string;
  documentId?: number;
}

export const fmtEur = (value: number | null | undefined) =>
  value != null
    ? `EUR ${value.toLocaleString(getLocaleForLanguage(i18nInstance.language), { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : '-';

export const fmtDate = (value: string | null | undefined) => {
  if (!value) return '-';
  try {
    return new Date(value).toLocaleDateString(getLocaleForLanguage(i18nInstance.language));
  } catch {
    return value;
  }
};

const legacySuggestionIconMap: Record<string, { icon: LucideIcon; tone: FuturisticIconTone }> = {
  '🏠': { icon: House, tone: 'cyan' },
  '🚗': { icon: Building2, tone: 'emerald' },
  '💰': { icon: Wallet, tone: 'emerald' },
  '💸': { icon: Banknote, tone: 'rose' },
  '🏦': { icon: Landmark, tone: 'amber' },
  '📄': { icon: FileText, tone: 'cyan' },
  '📋': { icon: ClipboardList, tone: 'amber' },
  '🏧': { icon: ReceiptText, tone: 'violet' },
  '🔄': { icon: Repeat2, tone: 'violet' },
  '📈': { icon: Wallet, tone: 'emerald' },
  '📉': { icon: Banknote, tone: 'rose' },
  '🧾': { icon: ReceiptText, tone: 'amber' },
};

const renderSuggestionIcon = (icon: string | React.ReactNode) => {
  if (typeof icon !== 'string') {
    return icon;
  }

  const mapped = legacySuggestionIconMap[icon];
  if (mapped) {
    return <FuturisticIcon icon={mapped.icon} tone={mapped.tone} size="sm" />;
  }

  return icon;
};

export const SuggestionCardShell: React.FC<{
  icon: string | React.ReactNode;
  title: string;
  confirmResult: SuggestionCardProps['confirmResult'];
  confirmingAction: string | null;
  confirmActionKey: string;
  onConfirm: (payload?: unknown) => void;
  onDismiss: () => void;
  disableConfirm?: boolean;
  disableConfirmReason?: string;
  confirmLabel?: string;
  documentId?: number;
  suggestionType?: string;
  suggestionData?: Record<string, any>;
  children: React.ReactNode;
}> = ({
  icon,
  title,
  confirmResult,
  confirmingAction,
  confirmActionKey,
  onConfirm,
  onDismiss,
  disableConfirm = false,
  disableConfirmReason,
  confirmLabel,
  documentId,
  suggestionType,
  suggestionData,
  children,
}) => {
  const { t } = useTranslation();
  const pushSuggestionMessage = useAIAdvisorStore((state) => state.pushSuggestionMessage);

  const handleAskAI = () => {
    if (!documentId || !suggestionType) return;

    pushSuggestionMessage({
      idempotencyKey: `${documentId}:${suggestionType}:completed`,
      type: 'suggestion',
      suggestionType,
      documentId,
      extractedData: suggestionData || {},
      status: 'pending',
    });
  };

  return (
    <div className="import-suggestion-card">
      <div className="suggestion-header">
        <span className="suggestion-icon">{renderSuggestionIcon(icon)}</span>
        <h3>{title}</h3>
      </div>
      {children}
      {confirmResult && (
        <div className={`suggestion-result ${confirmResult.type}`}>{confirmResult.message}</div>
      )}
      <div className="suggestion-actions">
        <button
          className="btn btn-primary"
          onClick={onConfirm}
          disabled={confirmingAction !== null || disableConfirm}
          title={disableConfirm ? disableConfirmReason : undefined}
        >
          {confirmingAction === confirmActionKey ? (
            <Loader2 size={14} className="spin" />
          ) : (
            <CheckCircle2 size={14} />
          )}{' '}
          {confirmLabel || t('documents.suggestion.confirm')}
        </button>
        <button className="btn btn-secondary" onClick={onDismiss} disabled={confirmingAction !== null}>
          {t('documents.suggestion.dismiss')}
        </button>
      </div>
      {disableConfirm && disableConfirmReason && (
        <div className="suggestion-result info">{disableConfirmReason}</div>
      )}
      {documentId && suggestionType && (
        <button
          type="button"
          className="suggestion-ask-ai-link"
          onClick={handleAskAI}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            marginTop: 8,
            padding: 0,
            background: 'none',
            border: 'none',
            color: 'var(--color-primary, #6366f1)',
            fontSize: '0.78rem',
            cursor: 'pointer',
            opacity: 0.8,
          }}
        >
          <MessageCircle size={13} />
          {t('ai.askAboutDocument', 'Ask AI about this')}
        </button>
      )}
    </div>
  );
};

export const Row: React.FC<{ label: string; value: React.ReactNode; className?: string }> = ({
  label,
  value,
  className,
}) => (
  <div className={`suggestion-row ${className || ''}`}>
    <span>{label}</span>
    <span>{value}</span>
  </div>
);

export default SuggestionCardShell;
