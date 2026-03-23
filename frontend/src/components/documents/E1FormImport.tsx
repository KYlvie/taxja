import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import reportService, { E1FormImportResult, E1FormParseResult } from '../../services/reportService';
import PropertyLinkingSuggestions, { PropertyLinkingDecision } from '../properties/PropertyLinkingSuggestions';
import { getLocaleForLanguage } from '../../utils/locale';
import TaxImportDocumentPreview from './TaxImportDocumentPreview';
import SubpageBackLink from '../common/SubpageBackLink';
import './OCRReview.css';
import './BescheidImport.css';

interface E1FormImportProps {
  ocrText?: string;
  documentId?: number;
  initialParseResult?: E1FormParseResult;
  onRetry?: () => Promise<void> | void;
  retrying?: boolean;
  onImportComplete?: (result: E1FormImportResult) => void;
  onCancel?: () => void;
  onPrevDocument?: () => void;
  onNextDocument?: () => void;
  hasPrevDocument?: boolean;
  hasNextDocument?: boolean;
}

interface E1EditableData {
  tax_year: string;
  taxpayer_name: string;
  steuernummer: string;
  all_kz_values: Record<string, string>;
}

const buildEditableData = (result: E1FormParseResult | null): E1EditableData => ({
  tax_year: result?.tax_year != null ? String(result.tax_year) : '',
  taxpayer_name: result?.taxpayer_name ?? '',
  steuernummer: result?.steuernummer ?? '',
  all_kz_values: Object.fromEntries(
    Object.entries(result?.all_kz_values || {}).map(([key, value]) => [key, value != null ? String(value) : ''])
  ),
});

const getConfidenceClass = (confidence?: number) => {
  if (!confidence) return 'confidence-unknown';
  if (confidence >= 0.8) return 'confidence-high';
  if (confidence >= 0.6) return 'confidence-medium';
  return 'confidence-low';
};

const getConfidenceLabel = (
  confidence: number | undefined,
  t: (key: string) => string,
) => {
  if (!confidence) return t('documents.review.confidence.unknown');
  if (confidence >= 0.8) return t('documents.review.confidence.high');
  if (confidence >= 0.6) return t('documents.review.confidence.medium');
  return t('documents.review.confidence.low');
};

const E1FormImport = ({
  ocrText,
  documentId,
  initialParseResult,
  onImportComplete,
  onCancel,
  onPrevDocument,
  onNextDocument,
  hasPrevDocument,
  hasNextDocument,
}: E1FormImportProps) => {
  const { t, i18n } = useTranslation();
  const language = i18n?.language || 'en';
  const [mode, setMode] = useState<'readonly' | 'edit'>('edit');
  const [parseResult, setParseResult] = useState<E1FormParseResult | null>(initialParseResult ?? null);
  const [importResult, setImportResult] = useState<E1FormImportResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<'preview' | 'imported'>('preview');
  const [editableData, setEditableData] = useState<E1EditableData>(buildEditableData(initialParseResult ?? null));
  const [, setLinkingDecisions] = useState<PropertyLinkingDecision[]>([]);

  const handleParse = async () => {
    if (!ocrText) return;
    setLoading(true);
    setError(null);
    try {
      const result = await reportService.parseE1Form(ocrText, documentId);
      setParseResult(result);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('documents.e1.importError'));
    } finally {
      setLoading(false);
    }
  };

  const updateField = (field: keyof Omit<E1EditableData, 'all_kz_values'>, value: string) => {
    setEditableData((current) => ({ ...current, [field]: value }));
  };

  const updateKzField = (key: string, value: string) => {
    setEditableData((current) => ({
      ...current,
      all_kz_values: {
        ...current.all_kz_values,
        [key]: value,
      },
    }));
  };

  const handleImport = async () => {
    if (!ocrText) return;
    setLoading(true);
    setError(null);
    try {
      const editedData = {
        tax_year: editableData.tax_year,
        taxpayer_name: editableData.taxpayer_name,
        steuernummer: editableData.steuernummer,
        all_kz_values: Object.fromEntries(
          Object.entries(editableData.all_kz_values).filter(([, value]) => value.trim() !== '')
        ),
      };

      const result = await reportService.importE1Form(ocrText, documentId, editedData);
      setImportResult(result);
      setStep('imported');
      onImportComplete?.(result);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('documents.e1.importError'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setParseResult(initialParseResult ?? null);
    setImportResult(null);
    setError(null);
    setStep('preview');
    setMode('edit');
  }, [initialParseResult, ocrText, documentId]);

  useEffect(() => {
    setEditableData(buildEditableData(parseResult));
  }, [parseResult]);

  useEffect(() => {
    if (initialParseResult || !ocrText || loading || error || parseResult) {
      return;
    }
    void handleParse();
  }, [initialParseResult, ocrText, loading, error, parseResult]);

  const fmt = (val: number | string | null | undefined) => {
    if (val == null || val === '') return '-';
    const numeric = typeof val === 'number' ? val : Number(val);
    return Number.isFinite(numeric)
      ? numeric.toLocaleString(getLocaleForLanguage(language), { style: 'currency', currency: 'EUR' })
      : String(val);
  };

  const confidencePct = parseResult?.confidence != null
    ? `${(parseResult.confidence * 100).toFixed(0)}%`
    : '-';
  const missingFieldSuggestions = [
    ['tax_year', editableData.tax_year, t('documents.e1.taxYear')],
    ['taxpayer_name', editableData.taxpayer_name, t('documents.e1.taxpayerName')],
    ['steuernummer', editableData.steuernummer, t('documents.e1.steuernummer')],
  ]
    .filter(([, value]) => !String(value ?? '').trim())
    .map(([, , label]) => t('documents.review.verifyFieldSuggestion', { field: label }));

  const kzLabel = (key: string): string => {
    const labels: Record<string, string> = {
      gesamtbetrag_einkuenfte: t('documents.bescheid.einkommen'),
    };

    if (labels[key]) {
      return labels[key];
    }

    return `KZ ${key.replace(/^kz_/, '')}`;
  };

  const handleReviewCancel = () => {
    if (mode === 'edit' && parseResult) {
      setEditableData(buildEditableData(parseResult));
      setMode('readonly');
      return;
    }

    onCancel?.();
  };

  if (step === 'imported' && importResult) {
    return (
      <div className="bescheid-import">
        <div className="bescheid-shell">
          <div className="bescheid-surface bescheid-success">
            <h3>{t('documents.taxData.savedTitle')}</h3>
            <p>{t('documents.taxData.savedDescription')}</p>
            <div className="bescheid-form-grid">
              <div className="bescheid-field">
                <label>{t('documents.e1.taxYear')}</label>
                <span>{importResult.tax_year ?? '-'}</span>
              </div>
              <div className="bescheid-field">
                <label>{t('documents.taxData.recordId')}</label>
                <span>{importResult.tax_filing_data_id}</span>
              </div>
              <div className="bescheid-field">
                <label>{t('documents.taxData.dataType')}</label>
                <span>{importResult.data_type}</span>
              </div>
            </div>
            {onCancel && (
              <button className="btn btn-primary" onClick={onCancel}>
                {t('common.close')}
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="ocr-review tax-import-review">
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', flexWrap: 'wrap' }}>
        <SubpageBackLink to="/documents" />
        {hasPrevDocument && onPrevDocument && (
          <button className="btn btn-secondary" onClick={onPrevDocument} title={String(t('documents.prevDocument'))}>
            &larr; {t('documents.prev')}
          </button>
        )}
        {hasNextDocument && onNextDocument && (
          <button className="btn btn-secondary" onClick={onNextDocument} title={String(t('documents.nextDocument'))}>
            {t('documents.next')} &rarr;
          </button>
        )}
      </div>

      <div className="review-header">
        <div className="review-header-main">
          <h2>{t('documents.e1.title')}</h2>
          <div className="confidence-badge">
            <span className={getConfidenceClass(parseResult?.confidence)}>
              {getConfidenceLabel(parseResult?.confidence, t)}
            </span>
            <span className="confidence-value">{confidencePct}</span>
          </div>
        </div>
      </div>

      <div className="review-info-banner">
        {t('documents.e1.description')}
      </div>

      <div className="review-mode-toolbar">
        <button
          type="button"
          className={`btn ${mode === 'readonly' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setMode('readonly')}
          disabled={loading}
        >
          {t('documents.review.readonlyMode')}
        </button>
        <button
          type="button"
          className={`btn ${mode === 'edit' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setMode('edit')}
          disabled={loading}
        >
          {t('common.edit')}
        </button>
      </div>

      {error && <div className="bescheid-error">{error}</div>}

      {loading && <div className="bescheid-loading">{t('common.loading')}</div>}

      {parseResult && missingFieldSuggestions.length > 0 && (
        <div className="review-suggestions">
          <h4>{t('documents.review.suggestions')}</h4>
          <ul>
            {missingFieldSuggestions.map((suggestion) => (
              <li key={suggestion}>{suggestion}</li>
            ))}
          </ul>
        </div>
      )}

      {parseResult && !loading && (
        <>
          <div className="review-content">
            <div className="document-preview">
              <h3>{t('documents.review.preview')}</h3>
              <TaxImportDocumentPreview documentId={documentId} embedded />
            </div>
            <div className="extracted-data">
              <h3>{t('documents.review.extractedData')}</h3>
              <fieldset className="review-form-fieldset" disabled={loading}>
              <fieldset className="review-form-fieldset" disabled={mode === 'readonly' || loading}>
                <section className="bescheid-section">
                  <div className="bescheid-section-header">
                    <h5>{t('documents.e1.parsePreview')}</h5>
                  </div>
                  <div className="bescheid-form-grid">
                    <div className="bescheid-field">
                      <label>{t('documents.e1.taxYear')}</label>
                      <input
                        className="bescheid-input"
                        value={editableData.tax_year}
                        onChange={(event) => updateField('tax_year', event.target.value)}
                      />
                    </div>
                    <div className="bescheid-field">
                      <label>{t('documents.e1.taxpayerName')}</label>
                      <input
                        className="bescheid-input"
                        value={editableData.taxpayer_name}
                        onChange={(event) => updateField('taxpayer_name', event.target.value)}
                      />
                    </div>
                    <div className="bescheid-field">
                      <label>{t('documents.e1.steuernummer')}</label>
                      <input
                        className="bescheid-input"
                        value={editableData.steuernummer}
                        onChange={(event) => updateField('steuernummer', event.target.value)}
                      />
                    </div>
                  </div>
                </section>

                {Object.keys(editableData.all_kz_values).length > 0 && (
                  <section className="bescheid-section">
                    <div className="bescheid-section-header">
                      <h5>{t('documents.e1.extractedKZ')}</h5>
                    </div>
                    <div className="bescheid-form-grid">
                      {Object.entries(editableData.all_kz_values).map(([kz, value]) => (
                        <div key={kz} className="bescheid-field">
                          <label>{kzLabel(kz)}</label>
                          <input
                            className="bescheid-input"
                            value={value}
                            onChange={(event) => updateKzField(kz, event.target.value)}
                            placeholder={fmt(parseResult.all_kz_values[kz])}
                          />
                        </div>
                      ))}
                    </div>
                  </section>
                )}
              </fieldset>
            </div>
          </div>

          {parseResult.requires_property_linking && parseResult.property_linking_suggestions && (
            <PropertyLinkingSuggestions
              suggestions={parseResult.property_linking_suggestions}
              onDecisionsChange={setLinkingDecisions}
            />
          )}
        </>
      )}

      {parseResult && !loading && (
        <div className="review-actions">
          <button className="btn btn-secondary" onClick={handleReviewCancel} disabled={loading}>
            {t('common.cancel')}
          </button>
          {mode === 'edit' ? (
            <button className="btn btn-primary" onClick={handleImport} disabled={loading}>
              {t('documents.taxData.confirmButton')}
            </button>
          ) : (
            <button className="btn btn-primary" onClick={() => setMode('edit')} disabled={loading}>
              {t('common.edit')}
            </button>
          )}
        </div>
      )}
    </div>
  );
};

export default E1FormImport;
