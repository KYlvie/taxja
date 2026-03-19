import React from 'react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { AlertTriangle } from 'lucide-react';
import './AIResponse.css';

interface AIResponseProps {
  content: string;
}

// Keywords that indicate tax-related content (multi-language)
const TAX_KEYWORDS = /steuer|tax|abset|deduct|finanz|einkommen|income|umsatz|vat|mwst|vorsteuer|svs|sozialversicher|pendlerpauschale|werbungskosten|sonderausgaben|absetzbetr|freibetr|steuererklär|lohnzettel|arbeitnehmerveranlagung|einkommensteuer|körperschaftsteuer|grundsteuer|immobilien.*steuer|kapitalertrag|kest|est |e1 |l1 |u1 |u30|afa|abschreibung|betriebsausgab|gewinn|verlust|verlustvortr|税|扣除|退税|报税|所得税|增值税|社保|抵扣/i;

const AIResponse: React.FC<AIResponseProps> = ({ content }) => {
  const { t } = useTranslation();

  // Split content and disclaimer
  const disclaimerMarker = '⚠️';
  const hasDisclaimer = content.includes(disclaimerMarker);
  
  // Strip HTML tags (e.g. <br>, <br/>) that LLMs sometimes generate
  const cleanedContent = content.replace(/<br\s*\/?>/gi, '\n').replace(/<\/?[^>]+(>|$)/g, '');

  let mainContent = cleanedContent;
  let disclaimerContent = '';

  if (hasDisclaimer) {
    const parts = cleanedContent.split(disclaimerMarker);
    mainContent = parts[0].trim();
    disclaimerContent = parts.slice(1).join(disclaimerMarker).trim();
  }

  // Check if the actual response (without disclaimer) is tax-related
  const isTaxRelated = TAX_KEYWORDS.test(mainContent);

  return (
    <div className="ai-response">
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
          {mainContent}
        </ReactMarkdown>
      </div>

      {/* Disclaimer - prominently displayed only for tax-related content */}
      {hasDisclaimer && disclaimerContent && isTaxRelated && (
        <div className="ai-disclaimer">
          <div className="ai-disclaimer-icon">
            <AlertTriangle size={18} />
          </div>
          <div className="ai-disclaimer-content">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{disclaimerContent}</ReactMarkdown>
          </div>
        </div>
      )}

      {/* Show disclaimer only for tax-related responses without existing disclaimer */}
      {!hasDisclaimer && isTaxRelated && (
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
