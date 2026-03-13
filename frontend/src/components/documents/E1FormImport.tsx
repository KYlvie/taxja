import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import reportService, { E1FormParseResult, E1FormImportResult } from '../../services/reportService';
import PropertyLinkingSuggestions, { PropertyLinkingDecision } from '../properties/PropertyLinkingSuggestions';
import './BescheidImport.css'; // Reuse Bescheid styles

interface E1FormImportProps {
  ocrText?: string;
  documentId?: number;
  initialParseResult?: E1FormParseResult;
  onImportComplete?: (result: E1FormImportResult) => void;
  onCancel?: () => void;
}

const E1FormImport = ({ ocrText, documentId, initialParseResult, onImportComplete, onCancel }: E1FormImportProps) => {
  const { t } = useTranslation();
  const [parseResult, setParseResult] = useState<E1FormParseResult | null>(initialParseResult ?? null);
  const [importResult, setImportResult] = useState<E1FormImportResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<'preview' | 'imported'>('preview');
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

  const handleImport = async () => {
    if (!ocrText) return;
    setLoading(true);
    setError(null);
    try {
      const result = await reportService.importE1Form(ocrText, documentId);
      setImportResult(result);
      setStep('imported');
      onImportComplete?.(result);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('documents.e1.importError'));
    } finally {
      setLoading(false);
    }
  };

  // Auto-parse on mount if not yet parsed and no initial result provided
  if (ocrText && !parseResult && !loading && !error) {
    handleParse();
  }

  const fmt = (val: number | null | undefined) =>
    val != null ? val.toLocaleString('de-AT', { style: 'currency', currency: 'EUR' }) : '—';

  const confidencePct = parseResult?.confidence != null
    ? `${(parseResult.confidence * 100).toFixed(0)}%`
    : '—';

  if (step === 'imported' && importResult) {
    return (
      <div className="bescheid-import">
        <div className="bescheid-success">
          <h3>✅ {t('documents.e1.importSuccess')}</h3>
          <p>{t('documents.e1.transactionsCreated', { count: importResult.transactions_created })}</p>
          <div className="bescheid-transactions">
            {importResult.transactions.map((txn: any) => (
              <div key={txn.id} className="bescheid-txn-row">
                <span className={`txn-type ${txn.type}`}>{txn.type === 'income' ? '📈' : '📉'}</span>
                <span className="txn-desc">{txn.description}</span>
                <span className="txn-amount">{fmt(txn.amount)}</span>
                <span className="txn-kz">KZ {txn.kz}</span>
              </div>
            ))}
          </div>
          {onCancel && (
            <button className="btn btn-primary" onClick={onCancel}>
              {t('common.close')}
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="bescheid-import">
      <h3>📋 {t('documents.e1.title')}</h3>
      <p className="bescheid-desc">{t('documents.e1.description')}</p>

      {error && <div className="bescheid-error">{error}</div>}

      {loading && <div className="bescheid-loading">{t('common.loading')}</div>}

      {parseResult && !loading && (
        <div className="bescheid-preview">
          <h4>{t('documents.e1.parsePreview')}</h4>

          <div className="bescheid-confidence">
            {t('documents.e1.confidence')}: {confidencePct}
          </div>

          <div className="bescheid-grid">
            <div className="bescheid-field">
              <label>{t('documents.e1.taxYear')}</label>
              <span>{parseResult.tax_year ?? '—'}</span>
            </div>
            <div className="bescheid-field">
              <label>{t('documents.e1.taxpayerName')}</label>
              <span>{parseResult.taxpayer_name ?? '—'}</span>
            </div>
            <div className="bescheid-field">
              <label>{t('documents.e1.steuernummer')}</label>
              <span>{parseResult.steuernummer ?? '—'}</span>
            </div>
          </div>

          {parseResult.all_kz_values && Object.keys(parseResult.all_kz_values).length > 0 && (
            <div className="bescheid-section">
              <h5>{t('documents.e1.extractedKZ')}</h5>
              <div className="bescheid-grid">
                {Object.entries(parseResult.all_kz_values).map(([kz, value]: [string, any]) => (
                  <div key={kz} className="bescheid-field">
                    <label>KZ {kz}</label>
                    <span>{fmt(value)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="bescheid-actions">
            <button className="btn btn-primary" onClick={handleImport} disabled={loading}>
              ✅ {t('documents.e1.importConfirm')}
            </button>
            {onCancel && (
              <button className="btn btn-secondary" onClick={onCancel}>
                {t('common.cancel')}
              </button>
            )}
          </div>

          {/* Property Linking Suggestions */}
          {parseResult.requires_property_linking && parseResult.property_linking_suggestions && (
            <PropertyLinkingSuggestions
              suggestions={parseResult.property_linking_suggestions}
              onDecisionsChange={setLinkingDecisions}
            />
          )}
        </div>
      )}
    </div>
  );
};

export default E1FormImport;
