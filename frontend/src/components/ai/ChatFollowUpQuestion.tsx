/**
 * ChatFollowUpQuestion — Task 10
 *
 * Renders follow-up questions with inline input controls in the chat panel.
 * Supports: date picker, number input, select dropdown, boolean toggle.
 * Validates inputs per question.validation rules.
 *
 * Requirements: FR-8, FR-9
 */
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, SkipForward, Loader2 } from 'lucide-react';
import Select from '../common/Select';
import DateInput from '../common/DateInput';
import { getLocaleForLanguage } from '../../utils/locale';
import { documentService } from '../../services/documentService';
import { useAIAdvisorStore } from '../../stores/aiAdvisorStore';
import AIAvatar from './AIAvatar';
import type { FollowUpChatMessage, FollowUpQuestion } from '../../stores/aiAdvisorStore';

interface ChatFollowUpQuestionProps {
  message: FollowUpChatMessage;
}

/** Get localized string from a trilingual object or plain string */
function localize(value: any, lang: string): string {
  if (!value) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'object') return value[lang] || value.en || value.de || Object.values(value)[0] || '';
  return String(value);
}

export default function ChatFollowUpQuestion({ message }: ChatFollowUpQuestionProps) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language?.slice(0, 2) || 'en';
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(message.answered);
  const [error, setError] = useState<string | null>(null);
  const [versionConflict, setVersionConflict] = useState(false);

  const markFollowUpAnswered = useAIAdvisorStore((s) => s.markFollowUpAnswered);
  const updateSuggestionStatus = useAIAdvisorStore((s) => s.updateSuggestionStatus);

  // Bug #4 fix: Sync submitted state with message.answered changes
  React.useEffect(() => {
    if (message.answered && !submitted) setSubmitted(true);
  }, [message.answered, submitted]);

  const updateAnswer = (fieldKey: string, value: any) => {
    setAnswers((prev) => ({ ...prev, [fieldKey]: value }));
    setVersionConflict(false); // Clear conflict on new input
  };

  /** Bug #20 fix: Client-side validation before submission */
  const validateAnswers = (): boolean => {
    for (const q of message.questions) {
      if (q.required && (answers[q.fieldKey] === undefined || answers[q.fieldKey] === '' || answers[q.fieldKey] === null)) {
        setError(t('ai.followUp.required', 'Please fill in all required fields.'));
        return false;
      }
      if (q.inputType === 'number' && answers[q.fieldKey] !== undefined) {
        const num = Number(answers[q.fieldKey]);
        if (isNaN(num)) {
          setError(t('ai.followUp.invalidNumber', 'Please enter a valid number.'));
          return false;
        }
        if (q.validation?.min !== undefined && num < q.validation.min) {
          setError(t('ai.followUp.tooLow', 'Value is below minimum ({{min}}).', { min: q.validation.min }));
          return false;
        }
        if (q.validation?.max !== undefined && num > q.validation.max) {
          setError(t('ai.followUp.tooHigh', 'Value exceeds maximum ({{max}}).', { max: q.validation.max }));
          return false;
        }
      }
    }
    return true;
  };

  const handleSubmit = async () => {
    if (!validateAnswers()) return;
    setLoading(true);
    setError(null);
    try {
      await documentService.submitFollowUp(message.documentId, answers, {
        suggestionVersion: message.suggestionVersion,
      });
      markFollowUpAnswered(message.documentId);
      setSubmitted(true);
      // Always update suggestion to pending (ready to confirm)
      // Backend auto-applies defaults for non-required remaining questions
      updateSuggestionStatus(message.documentId, 'pending');
    } catch (err: any) {
      if (err?.response?.status === 409) {
        setError(t('ai.followUp.versionMismatch', 'This was modified elsewhere. Please refresh.'));
        setVersionConflict(true);
      } else {
        setError(err?.response?.data?.detail || t('ai.followUp.submitError', 'Failed to submit answers'));
      }
    } finally {
      setLoading(false);
    }
  };

  const handleUseDefaults = async () => {
    setLoading(true);
    setError(null);
    try {
      await documentService.submitFollowUp(message.documentId, answers, {
        useDefaults: true,
        suggestionVersion: message.suggestionVersion,
      });
      markFollowUpAnswered(message.documentId);
      setSubmitted(true);
      updateSuggestionStatus(message.documentId, 'pending');
    } catch (err: any) {
      setError(err?.response?.data?.detail || t('ai.followUp.submitError', 'Failed to apply defaults'));
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <div className="chat-msg assistant">
        <AIAvatar className="invisible" />
        <div className="chat-msg-bubble">
          <div style={{ fontSize: '0.84rem', opacity: 0.8 }}>
            <Check size={14} style={{ verticalAlign: 'middle' }} />{' '}
            {t('ai.followUp.answered', 'Answers submitted. You can now confirm above.')}
          </div>
          <span className="chat-msg-time">
            {message.timestamp instanceof Date
              ? message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
              : new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-msg assistant">
      <AIAvatar className="invisible" />
      <div className="chat-msg-bubble">
        <p style={{ margin: '0 0 8px', fontSize: '0.84rem' }}>
          {t('ai.followUp.header', 'I need a few more details:')}
        </p>

        <div className="chat-recurring-card" style={{ padding: '10px 12px' }}>
          {message.questions.map((q) => (
            <FollowUpField
              key={q.id}
              question={q}
              lang={lang}
              value={answers[q.fieldKey]}
              onChange={(val) => updateAnswer(q.fieldKey, val)}
            />
          ))}

          <div className="chat-recurring-actions" style={{ marginTop: 10 }}>
            <button
              className="chat-recurring-btn confirm"
              onClick={handleSubmit}
              disabled={loading || versionConflict}
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
              {' '}{t('ai.followUp.submit', 'Submit answers')}
            </button>
            <button
              className="chat-recurring-btn dismiss"
              onClick={handleUseDefaults}
              disabled={loading}
            >
              <SkipForward size={14} /> {t('ai.followUp.useDefaults', 'Use defaults')}
            </button>
          </div>

          {error && (
            <div style={{ fontSize: '0.78rem', color: 'var(--color-error, #e53e3e)', marginTop: 6 }}>
              {error}
            </div>
          )}
        </div>

        <span className="chat-msg-time">
          {message.timestamp instanceof Date
            ? message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            : new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
    </div>
  );
}

// =============================================================================
// Individual Follow-Up Field Renderer
// =============================================================================

interface FollowUpFieldProps {
  question: FollowUpQuestion;
  lang: string;
  value: any;
  onChange: (value: any) => void;
}

function FollowUpField({ question, lang, value, onChange }: FollowUpFieldProps) {
  const { t } = useTranslation();
  const questionText = localize(question.question, lang);
  const helpText = question.helpText ? localize(question.helpText, lang) : undefined;

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '6px 8px',
    border: '1px solid var(--color-border)',
    borderRadius: 6,
    fontSize: '0.82rem',
    background: 'var(--color-bg)',
    color: 'var(--color-text)',
    marginTop: 4,
  };

  return (
    <div style={{ marginBottom: 10 }}>
      <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500 }}>
        {questionText}
        {question.required && <span style={{ color: 'var(--color-error, #e53e3e)', marginLeft: 2 }}>*</span>}
      </label>

      {question.inputType === 'date' && (
        <DateInput
          value={value || ''}
          onChange={(val) => onChange(val)}
          locale={getLocaleForLanguage(lang)}
          todayLabel={t('common.today', 'Today')}
        />
      )}

      {question.inputType === 'number' && (
        <input
          type="number"
          style={inputStyle}
          value={value ?? question.defaultValue ?? ''}
          min={question.validation?.min}
          max={question.validation?.max}
          onChange={(e) => onChange(e.target.value ? Number(e.target.value) : undefined)}
          placeholder={question.defaultValue != null ? `Default: ${question.defaultValue}` : ''}
        />
      )}

      {question.inputType === 'text' && (
        <input
          type="text"
          style={inputStyle}
          value={value || ''}
          onChange={(e) => onChange(e.target.value)}
        />
      )}

      {question.inputType === 'select' && question.options && (
        <Select
          value={String(value ?? question.defaultValue ?? '')}
          onChange={onChange}
          size="sm"
          options={question.options.map(opt => ({
            value: typeof opt.value === 'string' ? opt.value : JSON.stringify(opt.value),
            label: typeof opt.label === 'string' ? opt.label : localize(opt.label, lang),
          }))}
        />
      )}

      {question.inputType === 'boolean' && (
        <div style={{ marginTop: 4, display: 'flex', gap: 12, fontSize: '0.82rem' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}>
            <input
              type="radio"
              name={question.fieldKey}
              checked={value === true}
              onChange={() => onChange(true)}
            />
            {t('common.yes', 'Yes')}
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}>
            <input
              type="radio"
              name={question.fieldKey}
              checked={value === false}
              onChange={() => onChange(false)}
            />
            {t('common.no', 'No')}
          </label>
        </div>
      )}

      {helpText && (
        <div style={{ fontSize: '0.7rem', opacity: 0.6, marginTop: 3, lineHeight: 1.3 }}>
          {helpText}
        </div>
      )}
    </div>
  );
}
