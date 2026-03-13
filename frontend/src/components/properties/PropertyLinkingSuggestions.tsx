import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import './PropertyLinkingSuggestions.css';

export interface PropertySuggestion {
  property_id?: string;
  address: string;
  confidence?: number;
  confidence_score?: number;
  suggested_action: 'auto_link' | 'suggest' | 'manual_select' | 'create_new';
  match_details?: {
    street_match?: boolean;
    postal_code_match?: boolean;
    city_match?: boolean;
  };
}

export interface LinkingSuggestion {
  extracted_address?: string;
  matched_property_id?: string | null;
  confidence_score?: number;
  suggested_action?: string;
  match_details?: {
    street_match?: boolean;
    postal_code_match?: boolean;
    city_match?: boolean;
  };
  // For E1 imports (multiple properties)
  property_id?: string;
  address?: string;
  confidence?: number;
}

export interface PropertyLinkingDecision {
  extracted_address: string;
  action: 'link' | 'create' | 'skip';
  property_id?: string;
}

interface PropertyLinkingSuggestionsProps {
  suggestions: LinkingSuggestion[];
  onDecisionsChange: (decisions: PropertyLinkingDecision[]) => void;
}

const PropertyLinkingSuggestions = ({ suggestions, onDecisionsChange }: PropertyLinkingSuggestionsProps) => {
  const { t } = useTranslation();
  const [decisions, setDecisions] = useState<Map<string, PropertyLinkingDecision>>(new Map());

  // Normalize suggestion structure (handle both E1 and Bescheid formats)
  const normalizedSuggestions = suggestions.map(s => {
    // Bescheid format (single matched property)
    if (s.matched_property_id !== undefined) {
      return {
        extracted_address: s.extracted_address,
        matched_property_id: s.matched_property_id,
        confidence_score: s.confidence_score || 0,
        suggested_action: s.suggested_action || 'manual_select',
        match_details: s.match_details
      };
    }
    // E1 format (property list for manual selection)
    return {
      extracted_address: s.extracted_address || 'Rental Income',
      matched_property_id: s.property_id,
      confidence_score: s.confidence || 0,
      suggested_action: s.suggested_action || 'manual_select',
      address: s.address
    };
  });

  const handleActionChange = (extractedAddress: string, action: 'link' | 'create' | 'skip', propertyId?: string) => {
    const newDecisions = new Map(decisions);
    newDecisions.set(extractedAddress, {
      extracted_address: extractedAddress,
      action,
      property_id: propertyId
    });
    setDecisions(newDecisions);
    onDecisionsChange(Array.from(newDecisions.values()));
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence > 0.9) return 'high';
    if (confidence >= 0.7) return 'medium';
    return 'low';
  };

  const getConfidenceLabel = (confidence: number) => {
    if (confidence > 0.9) return t('properties.linking.confidenceHigh');
    if (confidence >= 0.7) return t('properties.linking.confidenceMedium');
    if (confidence > 0) return t('properties.linking.confidenceLow');
    return t('properties.linking.confidenceNone');
  };

  // Group suggestions by extracted address (for E1 with multiple properties)
  const groupedSuggestions = normalizedSuggestions.reduce((acc, suggestion) => {
    const key = suggestion.extracted_address || 'unknown';
    if (!acc[key]) {
      acc[key] = [];
    }
    acc[key].push(suggestion);
    return acc;
  }, {} as Record<string, typeof normalizedSuggestions>);

  if (suggestions.length === 0) {
    return null;
  }

  return (
    <div className="property-linking-suggestions">
      <h4>🏠 {t('properties.linking.title')}</h4>
      <p className="linking-description">{t('properties.linking.description')}</p>

      {Object.entries(groupedSuggestions).map(([extractedAddress, groupSuggestions]) => {
        const decision = decisions.get(extractedAddress);
        const hasMultipleOptions = groupSuggestions.length > 1;
        const primarySuggestion = groupSuggestions[0];
        const isHighConfidence = (primarySuggestion.confidence_score || 0) > 0.9;

        return (
          <div key={extractedAddress} className="linking-suggestion-card">
            <div className="suggestion-header">
              <div className="extracted-address">
                <span className="label">{t('properties.linking.extractedAddress')}:</span>
                <span className="address">{extractedAddress}</span>
              </div>
            </div>

            {/* Single matched property (Bescheid format) */}
            {!hasMultipleOptions && primarySuggestion.matched_property_id && (
              <div className="matched-property">
                <div className="match-info">
                  <span className="label">{t('properties.linking.matchedProperty')}:</span>
                  <span className="property-address">{primarySuggestion.address || extractedAddress}</span>
                  <span className={`confidence-badge ${getConfidenceColor(primarySuggestion.confidence_score || 0)}`}>
                    {getConfidenceLabel(primarySuggestion.confidence_score || 0)}
                    {primarySuggestion.confidence_score ? ` (${(primarySuggestion.confidence_score * 100).toFixed(0)}%)` : ''}
                  </span>
                </div>

                {primarySuggestion.match_details && (
                  <div className="match-details">
                    {primarySuggestion.match_details.street_match && <span className="match-tag">✓ {t('properties.linking.streetMatch')}</span>}
                    {primarySuggestion.match_details.postal_code_match && <span className="match-tag">✓ {t('properties.linking.postalMatch')}</span>}
                    {primarySuggestion.match_details.city_match && <span className="match-tag">✓ {t('properties.linking.cityMatch')}</span>}
                  </div>
                )}

                <div className="action-buttons">
                  <button
                    className={`btn ${decision?.action === 'link' ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => handleActionChange(extractedAddress, 'link', primarySuggestion.matched_property_id || undefined)}
                  >
                    {isHighConfidence ? '✓ ' : ''}{t('properties.linking.linkToExisting')}
                  </button>
                  <button
                    className={`btn ${decision?.action === 'create' ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => handleActionChange(extractedAddress, 'create')}
                  >
                    {t('properties.linking.createNew')}
                  </button>
                  <button
                    className={`btn ${decision?.action === 'skip' ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => handleActionChange(extractedAddress, 'skip')}
                  >
                    {t('properties.linking.skip')}
                  </button>
                </div>
              </div>
            )}

            {/* No match found (Bescheid format) */}
            {!hasMultipleOptions && !primarySuggestion.matched_property_id && (
              <div className="no-match">
                <p className="no-match-message">⚠️ {t('properties.linking.noMatchFound')}</p>
                <div className="action-buttons">
                  <button
                    className={`btn ${decision?.action === 'create' ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => handleActionChange(extractedAddress, 'create')}
                  >
                    {t('properties.linking.createNew')}
                  </button>
                  <button
                    className={`btn ${decision?.action === 'skip' ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => handleActionChange(extractedAddress, 'skip')}
                  >
                    {t('properties.linking.skip')}
                  </button>
                </div>
              </div>
            )}

            {/* Multiple properties for manual selection (E1 format) */}
            {hasMultipleOptions && (
              <div className="property-selection">
                <p className="selection-prompt">{t('properties.linking.selectProperty')}:</p>
                <div className="property-options">
                  {groupSuggestions.map((suggestion) => (
                    <button
                      key={suggestion.matched_property_id}
                      className={`property-option ${decision?.property_id === suggestion.matched_property_id ? 'selected' : ''}`}
                      onClick={() => handleActionChange(extractedAddress, 'link', suggestion.matched_property_id || undefined)}
                    >
                      <span className="property-address">{suggestion.address}</span>
                    </button>
                  ))}
                </div>
                <div className="action-buttons">
                  <button
                    className={`btn ${decision?.action === 'create' ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => handleActionChange(extractedAddress, 'create')}
                  >
                    {t('properties.linking.createNew')}
                  </button>
                  <button
                    className={`btn ${decision?.action === 'skip' ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => handleActionChange(extractedAddress, 'skip')}
                  >
                    {t('properties.linking.skip')}
                  </button>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default PropertyLinkingSuggestions;
