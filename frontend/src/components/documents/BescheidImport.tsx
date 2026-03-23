import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import reportService, { BescheidImportResult, BescheidParseResult } from '../../services/reportService';
import PropertyLinkingSuggestions, { PropertyLinkingDecision } from '../properties/PropertyLinkingSuggestions';
import { getLocaleForLanguage } from '../../utils/locale';
import TaxImportDocumentPreview from './TaxImportDocumentPreview';
import SubpageBackLink from '../common/SubpageBackLink';
import './OCRReview.css';
import './BescheidImport.css';

interface BescheidImportProps {
  ocrText: string;
  documentId?: number;
  initialParseResult?: BescheidParseResult | null;
  onRetry?: () => Promise<void> | void;
  retrying?: boolean;
  onImportComplete?: (result: BescheidImportResult) => void;
  onCancel?: () => void;
  onPrevDocument?: () => void;
  onNextDocument?: () => void;
  hasPrevDocument?: boolean;
  hasNextDocument?: boolean;
}

interface BescheidEditableData {
  tax_year: string;
  taxpayer_name: string;
  finanzamt: string;
  steuernummer: string;
  einkommen: string;
  festgesetzte_einkommensteuer: string;
  abgabengutschrift: string;
  abgabennachforderung: string;
  einkuenfte_nichtselbstaendig: string;
  einkuenfte_vermietung: string;
  werbungskosten_pauschale: string;
  telearbeitspauschale: string;
}

const buildEditableData = (result: BescheidParseResult | null): BescheidEditableData => ({
  tax_year: result?.tax_year != null ? String(result.tax_year) : '',
  taxpayer_name: result?.taxpayer_name ?? '',
  finanzamt: result?.finanzamt ?? '',
  steuernummer: result?.steuernummer ?? '',
  einkommen: result?.einkommen != null ? String(result.einkommen) : '',
  festgesetzte_einkommensteuer: result?.festgesetzte_einkommensteuer != null ? String(result.festgesetzte_einkommensteuer) : '',
  abgabengutschrift: result?.abgabengutschrift != null ? String(result.abgabengutschrift) : '',
  abgabennachforderung: result?.abgabennachforderung != null ? String(result.abgabennachforderung) : '',
  einkuenfte_nichtselbstaendig: result?.einkuenfte_nichtselbstaendig != null ? String(result.einkuenfte_nichtselbstaendig) : '',
  einkuenfte_vermietung: result?.einkuenfte_vermietung != null ? String(result.einkuenfte_vermietung) : '',
  werbungskosten_pauschale: result?.werbungskosten_pauschale != null ? String(result.werbungskosten_pauschale) : '',
  telearbeitspauschale: result?.telearbeitspauschale != null ? String(result.telearbeitspauschale) : '',
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

const BescheidImport = ({
  ocrText,
  documentId,
  initialParseResult,
  onImportComplete,
  onCancel,
  onPrevDocument,
  onNextDocument,
  hasPrevDocument,
  hasNextDocument,
}: BescheidImportProps) => {
  const { t, i18n } = useTranslation();
  const language = i18n?.language || 'en';
  const [mode, setMode] = useState<'readonly' | 'edit'>('edit');
  const [parseResult, setParseResult] = useState<BescheidParseResult | null>(initialParseResult ?? null);
  const [importResult, setImportResult] = useState<BescheidImportResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<'preview' | 'imported'>('preview');
  const [editableData, setEditableData] = useState<BescheidEditableData>(buildEditableData(initialParseResult ?? null));
  const [, setLinkingDecisions] = useState<PropertyLinkingDecision[]>([]);

  const handleParse = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await reportService.parseBescheid(ocrText, documentId);
      setParseResult(result);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('documents.bescheid.importError'));
    } finally {
      setLoading(false);
    }
  };

  const updateField = (field: keyof BescheidEditableData, value: string) => {
    setEditableData((current) => ({ ...current, [field]: value }));
  };

  const handleImport = async () => {
    setLoading(true);
    setError(null);
    try {
      const editedData = {
        tax_year: editableData.tax_year,
        taxpayer_name: editableData.taxpayer_name,
        finanzamt: editableData.finanzamt,
        steuernummer: editableData.steuernummer,
        einkommen: editableData.einkommen,
        festgesetzte_einkommensteuer: editableData.festgesetzte_einkommensteuer,
        abgabengutschrift: editableData.abgabengutschrift,
        abgabennachforderung: editableData.abgabennachforderung,
        einkuenfte_nichtselbstaendig: editableData.einkuenfte_nichtselbstaendig,
        einkuenfte_vermietung: editableData.einkuenfte_vermietung,
        werbungskosten_pauschale: editableData.werbungskosten_pauschale,
        telearbeitspauschale: editableData.telearbeitspauschale,
        vermietung_details: parseResult?.vermietung_details ?? [],
      };

      const result = await reportService.importBescheid(ocrText, documentId, editedData);
      setImportResult(result);
      setStep('imported');
      onImportComplete?.(result);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('documents.bescheid.importError'));
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
    ['tax_year', editableData.tax_year, t('documents.bescheid.taxYear')],
    ['taxpayer_name', editableData.taxpayer_name, t('documents.bescheid.taxpayerName')],
    ['steuernummer', editableData.steuernummer, t('documents.bescheid.steuernummer')],
    ['finanzamt', editableData.finanzamt, t('documents.bescheid.finanzamt')],
  ]
    .filter(([, value]) => !String(value ?? '').trim())
    .map(([, , label]) => t('documents.review.verifyFieldSuggestion', { field: label }));

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
                <label>{t('documents.bescheid.taxYear')}</label>
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
          <h2>{t('documents.bescheid.title')}</h2>
          <div className="confidence-badge">
            <span className={getConfidenceClass(parseResult?.confidence)}>
              {getConfidenceLabel(parseResult?.confidence, t)}
            </span>
            <span className="confidence-value">{confidencePct}</span>
          </div>
        </div>
      </div>

      <div className="review-info-banner">
        {t('documents.bescheid.description')}
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
              <fieldset className="review-form-fieldset" disabled={mode === 'readonly' || loading}>
                <section className="bescheid-section">
                  <div className="bescheid-section-header">
                    <h5>{t('documents.bescheid.parsePreview')}</h5>
                  </div>
                  <div className="bescheid-form-grid">
                    <div className="bescheid-field">
                      <label>{t('documents.bescheid.taxYear')}</label>
                      <input className="bescheid-input" value={editableData.tax_year} onChange={(event) => updateField('tax_year', event.target.value)} />
                    </div>
                    <div className="bescheid-field">
                      <label>{t('documents.bescheid.taxpayerName')}</label>
                      <input className="bescheid-input" value={editableData.taxpayer_name} onChange={(event) => updateField('taxpayer_name', event.target.value)} />
                    </div>
                    <div className="bescheid-field">
                      <label>{t('documents.bescheid.steuernummer')}</label>
                      <input className="bescheid-input" value={editableData.steuernummer} onChange={(event) => updateField('steuernummer', event.target.value)} />
                    </div>
                    <div className="bescheid-field">
                      <label>{t('documents.bescheid.finanzamt')}</label>
                      <input className="bescheid-input" value={editableData.finanzamt} onChange={(event) => updateField('finanzamt', event.target.value)} />
                    </div>
                  </div>
                </section>

                <section className="bescheid-section">
                  <div className="bescheid-section-header">
                    <h5>{t('documents.bescheid.einkommen')}</h5>
                  </div>
                  <div className="bescheid-form-grid">
                    <div className="bescheid-field">
                      <label>{t('documents.bescheid.einkommen')}</label>
                      <input className="bescheid-input" value={editableData.einkommen} onChange={(event) => updateField('einkommen', event.target.value)} />
                    </div>
                    <div className="bescheid-field">
                      <label>{t('documents.bescheid.employmentIncome')}</label>
                      <input className="bescheid-input" value={editableData.einkuenfte_nichtselbstaendig} onChange={(event) => updateField('einkuenfte_nichtselbstaendig', event.target.value)} />
                    </div>
                    <div className="bescheid-field">
                      <label>{t('documents.bescheid.rentalIncome')}</label>
                      <input className="bescheid-input" value={editableData.einkuenfte_vermietung} onChange={(event) => updateField('einkuenfte_vermietung', event.target.value)} />
                    </div>
                  </div>

                  {parseResult.vermietung_details && parseResult.vermietung_details.length > 0 && (
                    <div className="bescheid-subsection">
                      <div className="bescheid-subsection-title">{t('documents.bescheid.rentalIncome')}</div>
                      <div className="bescheid-summary-list">
                        {parseResult.vermietung_details.map((detail, index) => (
                          <div key={`${detail.address}-${index}`} className="bescheid-vv-row">
                            <span>{detail.address}</span>
                            <span>{fmt(detail.amount)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </section>

                <section className="bescheid-section">
                  <div className="bescheid-section-header">
                    <h5>{t('documents.bescheid.festgesetzteSteuer')}</h5>
                  </div>
                  <div className="bescheid-form-grid">
                    <div className="bescheid-field">
                      <label>{t('documents.bescheid.festgesetzteSteuer')}</label>
                      <input className="bescheid-input" value={editableData.festgesetzte_einkommensteuer} onChange={(event) => updateField('festgesetzte_einkommensteuer', event.target.value)} />
                    </div>
                    <div className="bescheid-field highlight-green">
                      <label>{t('documents.bescheid.abgabengutschrift')}</label>
                      <input className="bescheid-input" value={editableData.abgabengutschrift} onChange={(event) => updateField('abgabengutschrift', event.target.value)} />
                    </div>
                    <div className="bescheid-field highlight-red">
                      <label>{t('documents.bescheid.abgabennachforderung')}</label>
                      <input className="bescheid-input" value={editableData.abgabennachforderung} onChange={(event) => updateField('abgabennachforderung', event.target.value)} />
                    </div>
                  </div>
                </section>

                <section className="bescheid-section">
                  <div className="bescheid-section-header">
                    <h5>{t('documents.bescheid.werbungskosten')}</h5>
                  </div>
                  <div className="bescheid-form-grid">
                    <div className="bescheid-field">
                      <label>{t('documents.bescheid.werbungskosten')}</label>
                      <input className="bescheid-input" value={editableData.werbungskosten_pauschale} onChange={(event) => updateField('werbungskosten_pauschale', event.target.value)} />
                    </div>
                    <div className="bescheid-field">
                      <label>{t('documents.bescheid.telearbeitspauschale')}</label>
                      <input className="bescheid-input" value={editableData.telearbeitspauschale} onChange={(event) => updateField('telearbeitspauschale', event.target.value)} />
                    </div>
                  </div>
                </section>
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

export default BescheidImport;
