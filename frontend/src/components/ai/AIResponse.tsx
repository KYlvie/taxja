import React from 'react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import { AlertTriangle } from 'lucide-react';
import './AIResponse.css';

interface AIResponseProps {
  content: string;
}

const AIResponse: React.FC<AIResponseProps> = ({ content }) => {
  const { t } = useTranslation();

  // Split content and disclaimer
  const disclaimerMarker = '⚠️';
  const hasDisclaimer = content.includes(disclaimerMarker);
  
  let mainContent = content;
  let disclaimerContent = '';

  if (hasDisclaimer) {
    const parts = content.split(disclaimerMarker);
    mainContent = parts[0].trim();
    disclaimerContent = parts.slice(1).join(disclaimerMarker).trim();
  }

  return (
    <div className="ai-response">
      {/* Main content with markdown rendering */}
      <div className="ai-response-content">
        <ReactMarkdown
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
          }}
        >
          {mainContent}
        </ReactMarkdown>
      </div>

      {/* Disclaimer - prominently displayed */}
      {hasDisclaimer && disclaimerContent && (
        <div className="ai-disclaimer">
          <div className="ai-disclaimer-icon">
            <AlertTriangle size={18} />
          </div>
          <div className="ai-disclaimer-content">
            <ReactMarkdown>{disclaimerContent}</ReactMarkdown>
          </div>
        </div>
      )}

      {/* Always show disclaimer if not in content */}
      {!hasDisclaimer && (
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
