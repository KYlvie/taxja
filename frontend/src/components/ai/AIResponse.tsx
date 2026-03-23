import React from 'react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { AlertTriangle, Info } from 'lucide-react';
import './AIResponse.css';

interface AIResponseProps {
  content: string;
  intent?: string;
  showDisclaimer?: boolean;
  sourceTier?: string;
}

// Keywords that indicate tax-related content — used as fallback when showDisclaimer is undefined
// (e.g. for messages loaded from history that predate the show_disclaimer field)
const TAX_KEYWORDS = /steuer|tax|abset|deduct|finanz|einkommen|income|umsatz|vat|mwst|vorsteuer|svs|sozialversicher|pendlerpauschale|werbungskosten|sonderausgaben|absetzbetr|freibetr|steuererklär|lohnzettel|arbeitnehmerveranlagung|einkommensteuer|körperschaftsteuer|grundsteuer|immobilien.*steuer|kapitalertrag|kest|est |e1 |l1 |u1 |u30|afa|abschreibung|betriebsausgab|gewinn|verlust|verlustvortr|税|扣除|退税|报税|所得税|增值税|社保|抵扣/i;

const NO_DISCLAIMER_INTENTS = new Set(['unknown', 'system_help']);

const AIResponse: React.FC<AIResponseProps> = ({ content, intent, showDisclaimer, sourceTier }) => {
  const { t } = useTranslation();

  // Strip HTML tags (e.g. <br>, <br/>) that LLMs sometimes generate
  let cleanedContent = content.replace(/<br\s*\/?>/gi, '\n').replace(/<\/?[^>]+(>|$)/g, '');

  // Always strip backend-appended disclaimer text (⚠️ marker) from content
  // The disclaimer is now controlled by the showDisclaimer flag, not embedded text
  if (cleanedContent.includes('⚠️')) {
    cleanedContent = cleanedContent.split('⚠️')[0].trim();
  }

  // Determine whether to show disclaimer:
  // 1. If showDisclaimer is explicitly set by backend, use that
  // 2. Otherwise fall back to keyword detection (for old messages from history)
  const shouldShowDisclaimer = showDisclaimer !== undefined
    ? showDisclaimer
    : (intent && NO_DISCLAIMER_INTENTS.has(intent) ? false : TAX_KEYWORDS.test(cleanedContent));

  // Determine source tier hint
  const showSourceHint = sourceTier === 'lightweight' || sourceTier === 'rule_based';

  return (
    <div className="ai-response">
      {/* Source tier hint for degraded responses */}
      {showSourceHint && (
        <div className="ai-source-tier-hint">
          <Info size={14} />
          <span>{t(sourceTier === 'lightweight' ? 'ai.sourceTierLightweight' : 'ai.sourceTierRuleBased')}</span>
        </div>
      )}

      {/* Main content with markdown rendering */}
      <div className="ai-response-content">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            // Custom rendering for markdown elements
            p: ({ children }) => <p className="ai-paragraph">{children}</p>,
            ul: ({ children }) => <ul className="ai-list">{children}</ul>,
            ol: ({ children }) => <ol className="ai-list ai-list-ordered">{children}</ol>,
            li: ({ children }) => <li className="ai-list-item">{children}</li>,
            strong: ({ children }) => <strong className="ai-bold">{children}</strong>,
            em: ({ children }) => <em className="ai-italic">{children}</em>,
            code: ({ children, ...props }) =>
              (props as any).inline ? (
                <code className="ai-code-inline">{children}</code>
              ) : (
                <pre className="ai-code-block">
                  <code>{children}</code>
                </pre>
              ),
            a: ({ href, children }) => (
              <a
                href={href}
                className="ai-link"
                target="_blank"
                rel="noopener noreferrer"
              >
                {children}
              </a>
            ),
            h1: ({ children }) => <h1 className="ai-heading ai-h1">{children}</h1>,
            h2: ({ children }) => <h2 className="ai-heading ai-h2">{children}</h2>,
            h3: ({ children }) => <h3 className="ai-heading ai-h3">{children}</h3>,
            blockquote: ({ children }) => (
              <blockquote className="ai-blockquote">{children}</blockquote>
            ),
            table: ({ children }) => (
              <div className="ai-table-wrapper">
                <table className="ai-table">{children}</table>
              </div>
            ),
            thead: ({ children }) => <thead className="ai-thead">{children}</thead>,
            tbody: ({ children }) => <tbody>{children}</tbody>,
            tr: ({ children }) => <tr className="ai-tr">{children}</tr>,
            th: ({ children }) => <th className="ai-th">{children}</th>,
            td: ({ children }) => <td className="ai-td">{children}</td>,
          }}
        >
          {cleanedContent}
        </ReactMarkdown>
      </div>

      {/* Single disclaimer — controlled by backend flag with keyword fallback */}
      {shouldShowDisclaimer && (
        <div className="ai-disclaimer">
          <div className="ai-disclaimer-icon">
            <AlertTriangle size={18} />
          </div>
          <div className="ai-disclaimer-content">
            <p>{t('ai.disclaimer')}</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default AIResponse;
