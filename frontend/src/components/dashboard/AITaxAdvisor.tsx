import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Sparkles } from 'lucide-react';
import { aiService } from '../../services/aiService';
import './AITaxAdvisor.css';

const AITaxAdvisor = () => {
  const { t } = useTranslation();
  const [suggestions, setSuggestions] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleAsk = async () => {
    try {
      setLoading(true);
      setSuggestions(null);
      const response = await aiService.askForSuggestions({});
      setSuggestions(response.content);
    } catch (err: any) {
      const status = err?.response?.status;
      if (status === 503 || status === 500) {
        setSuggestions(t('ai.serviceUnavailable'));
      } else {
        setSuggestions(t('ai.suggestionError'));
      }
    } finally {
      setLoading(false);
    }
  };

  const renderContent = (text: string) => {
    return text.split('\n').map((line, i) => {
      const trimmed = line.trim();
      if (!trimmed) return null;

      // Heading: ### or ## lines
      if (/^#{1,4}\s/.test(trimmed)) {
        return <h6 key={i} className="ai-advisor-heading">{trimmed.replace(/^#+\s*/, '')}</h6>;
      }

      // Bullet / numbered list item
      if (/^\s*[-•*]\s/.test(trimmed) || /^\s*\d+[.)]\s/.test(trimmed)) {
        const content = trimmed.replace(/^\s*[-•*\d]+[.)]\s*/, '');
        return <li key={i}>{renderInline(content)}</li>;
      }

      // Separator
      if (/^---+$/.test(trimmed)) {
        return <hr key={i} className="ai-advisor-separator" />;
      }

      // Regular paragraph
      return <p key={i} className="ai-advisor-paragraph">{renderInline(trimmed)}</p>;
    });
  };

  const renderInline = (text: string) => {
    // Handle **bold** markers
    const parts = text.split(/\*\*(.*?)\*\*/g);
    return parts.map((part, k) =>
      k % 2 === 1 ? <strong key={k}>{part}</strong> : part
    );
  };

  return (
    <div className="ai-tax-advisor">
      <div className="ai-advisor-header">
        <h3>
          <Sparkles size={20} />
          {t('ai.taxAdvisorTitle', 'AI Tax Optimization')}
        </h3>
        <p className="ai-advisor-description">
          {t('ai.taxAdvisorDesc', 'Get personalized tax optimization suggestions based on your data')}
        </p>
      </div>

      <button className="ai-advisor-button" onClick={handleAsk} disabled={loading}>
        <Sparkles size={16} />
        {loading ? t('ai.loading') : t('ai.askForSuggestions')}
      </button>

      {suggestions && (
        <div className="ai-advisor-result">
          <ul className="ai-advisor-list">
            {renderContent(suggestions)}
          </ul>
          <p className="ai-advisor-disclaimer">
            {t('ai.disclaimer', 'This answer is for general reference only and does not constitute tax advice.')}
          </p>
        </div>
      )}
    </div>
  );
};

export default AITaxAdvisor;
