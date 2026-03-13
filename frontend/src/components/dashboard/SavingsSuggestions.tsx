import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import './SavingsSuggestions.css';

interface Suggestion {
  id: number;
  title: string;
  description: string;
  potentialSavings: number;
  actionLink: string;
  actionLabel?: string;
}

interface SavingsSuggestionsProps {
  suggestions: Suggestion[];
}

const SavingsSuggestions = ({ suggestions }: SavingsSuggestionsProps) => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('de-AT', {
      style: 'currency',
      currency: 'EUR',
    }).format(amount);
  };

  const handleAction = (actionLink: string) => {
    navigate(actionLink);
  };

  // Show top 3 suggestions
  const topSuggestions = suggestions.slice(0, 3);

  if (topSuggestions.length === 0) {
    return (
      <div className="savings-suggestions">
        <h3>{t('dashboard.savingsSuggestions')}</h3>
        <div className="no-suggestions">
          <p>🎉 {t('dashboard.noSuggestions')}</p>
          <p className="subtitle">{t('dashboard.optimizedTaxes')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="savings-suggestions">
      <div className="suggestions-header">
        <h3>{t('dashboard.savingsSuggestions')}</h3>
        <span className="suggestions-badge">{t('dashboard.top3')}</span>
      </div>

      <div className="suggestions-list">
        {topSuggestions.map((suggestion, index) => (
          <div key={suggestion.id} className="suggestion-card">
            <div className="suggestion-rank">{index + 1}</div>
            <div className="suggestion-content">
              <h4>{suggestion.title}</h4>
              <p className="suggestion-description">{suggestion.description}</p>
              <div className="suggestion-footer">
                <div className="potential-savings">
                  <span className="savings-label">
                    {t('dashboard.potentialSavings')}:
                  </span>
                  <span className="savings-amount">
                    {formatCurrency(suggestion.potentialSavings)}
                  </span>
                </div>
                <button
                  className="action-button"
                  onClick={() => handleAction(suggestion.actionLink)}
                >
                  {suggestion.actionLabel || t('dashboard.takeAction')}
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {suggestions.length > 3 && (
        <div className="more-suggestions">
          <p>
            {t('dashboard.moreSuggestions', {
              count: suggestions.length - 3,
            })}
          </p>
        </div>
      )}
    </div>
  );
};

export default SavingsSuggestions;
