import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { RecurringSuggestionCard } from './RecurringSuggestionCard';
import api from '../../services/api';

interface Suggestion {
  description: string;
  amount: number;
  transaction_type: string;
  category: string;
  frequency: string;
  occurrences: number;
  confidence: number;
  suggested_day_of_month: number;
  property_id?: string;
  already_automated: boolean;
}

export const RecurringSuggestionsList: React.FC = () => {
  const { t } = useTranslation();
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [, setDismissedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadSuggestions();
  }, []);

  const loadSuggestions = async () => {
    try {
      setLoading(true);
      const response = await api.get('/recurring-suggestions/suggestions', {
        params: {
          lookback_months: 6,
          min_confidence: 0.7
        }
      });
      
      // Filter out already automated suggestions
      const filtered = response.data.filter((s: Suggestion) => !s.already_automated);
      setSuggestions(filtered);
    } catch (error) {
      console.error('Failed to load suggestions:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAccept = async (suggestion: Suggestion) => {
    try {
      await api.post('/recurring-suggestions/accept', {
        description: suggestion.description,
        amount: suggestion.amount,
        transaction_type: suggestion.transaction_type,
        category: suggestion.category,
        frequency: suggestion.frequency,
        suggested_day_of_month: suggestion.suggested_day_of_month,
        property_id: suggestion.property_id
      });

      // Remove from list
      setSuggestions(prev => prev.filter(s => s.description !== suggestion.description));
      
      // Show success message
      alert(t('recurring.suggestions.acceptSuccess'));
    } catch (error) {
      throw error;
    }
  };

  const handleDismiss = (suggestion: Suggestion, index: number) => {
    // Add to dismissed set
    const key = `${suggestion.description}-${suggestion.amount}`;
    setDismissedIds(prev => new Set(prev).add(key));
    
    // Remove from list
    setSuggestions(prev => prev.filter((_, i) => i !== index));
    
    // Call API to dismiss (optional, for future reference)
    api.post(`/recurring-suggestions/${index}/dismiss`).catch(console.error);
  };

  if (loading) {
    return (
      <div className="text-center py-8">
        <div className="animate-spin text-4xl mb-2">⏳</div>
        <p className="text-gray-600">{t('recurring.suggestions.loading')}</p>
      </div>
    );
  }

  if (suggestions.length === 0) {
    return (
      <div className="text-center py-8 bg-gray-50 rounded-lg">
        <div className="text-4xl mb-2">✓</div>
        <p className="text-gray-600">{t('recurring.suggestions.noSuggestions')}</p>
        <p className="text-sm text-gray-500 mt-1">
          {t('recurring.suggestions.noSuggestionsHint')}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">
          {t('recurring.suggestions.title')} ({suggestions.length})
        </h2>
        <button
          onClick={loadSuggestions}
          className="text-sm text-blue-600 hover:text-blue-700"
        >
          🔄 {t('common.refresh')}
        </button>
      </div>

      {suggestions.map((suggestion, index) => (
        <RecurringSuggestionCard
          key={`${suggestion.description}-${index}`}
          description={suggestion.description}
          amount={suggestion.amount}
          frequency={suggestion.frequency}
          occurrences={suggestion.occurrences}
          confidence={suggestion.confidence}
          suggestedDayOfMonth={suggestion.suggested_day_of_month}
          transactionType={suggestion.transaction_type}
          category={suggestion.category}
          propertyId={suggestion.property_id}
          onAccept={() => handleAccept(suggestion)}
          onDismiss={() => handleDismiss(suggestion, index)}
        />
      ))}
    </div>
  );
};
