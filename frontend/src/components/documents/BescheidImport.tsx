import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import reportService, { BescheidParseResult, BescheidImportResult } from '../../services/reportService';
import PropertyLinkingSuggestions, { PropertyLinkingDecision } from '../properties/PropertyLinkingSuggestions';
import './BescheidImport.css';

interface BescheidImportProps {
  ocrText: string;
  documentId?: number;
  /** Pre-parsed result from upload-bescheid endpoint (skips separate parse call) */
  initialParseResult?: BescheidParseResult | null;
  onImportComplete?: (result: BescheidImportResult) => void;
  onCancel?: () => void;
}

const BescheidImport = ({ ocrText, documentId, initialParseResult, onImportComplete, onCancel }: BescheidImportProps) => {
  const { t } = useTranslation();
  const [parseResult, setParseResult] = useState<BescheidParseResult | null>(initialParseResult ?? null);
  const [importResult, setImportResult] = useState<BescheidImportResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<'preview' | 'imported'>('preview');
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

  const handleImport = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await reportService.importBescheid(ocrText, documentId);
      setImportResult(result);
      setStep('imported');
      onImportComplete?.(result);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('documents.bescheid.importError'));
    } finally {
      setLoading(false);
    }
  };

  // Auto-parse on mount if not yet parsed and no initial result provided
  if (!parseResult && !loading && !error) {
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
          <h3>✅ {t('documents.bescheid.importSuccess')}</h3>
          <p>{t('documents.bescheid.transactionsCreated', { count: importResult.transactions_created })}</p>
          <div className="bescheid-transactions">
            {importResult.transactions.map((txn) => (
              <div key={txn.id} className="bescheid-txn-row">
                <span className={`txn-type ${txn.type}`}>{txn.type === 'income' ? '📈' : '📉'}</span>
                <span className="txn-desc">{txn.description}</span>
                <span className="txn-amount">{fmt(txn.amount)}</span>
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
      <h3>📋 {t('documents.bescheid.title')}</h3>
      <p className="bescheid-desc">{t('documents.bescheid.description')}</p>

      {error && <div className="bescheid-error">{error}</div>}

      {loading && <div className="bescheid-loading">{t('common.loading')}</div>}

      {parseResult && !loading && (
        <div className="bescheid-preview">
          <h4>{t('documents.bescheid.parsePreview')}</h4>

          <div className="bescheid-confidence">
            {t('documents.bescheid.confidence')}: {confidencePct}
          </div>

          <div className="bescheid-grid">
            <div className="bescheid-field">
              <label>{t('documents.bescheid.taxYear')}</label>
              <span>{parseResult.tax_year ?? '—'}</span>
            </div>
            <div className="bescheid-field">
              <label>{t('documents.bescheid.taxpayerName')}</label>
              <span>{parseResult.taxpayer_name ?? '—'}</span>
            </div>
            <div className="bescheid-field">
              <label>{t('documents.bescheid.steuernummer')}</label>
              <span>{parseResult.steuernummer ?? '—'}</span>
            </div>
            <div className="bescheid-field">
              <label>{t('documents.bescheid.finanzamt')}</label>
              <span>{parseResult.finanzamt ?? '—'}</span>
            </div>
          </div>

          <div className="bescheid-section">
            <h5>{t('documents.bescheid.einkommen')}</h5>
            <div className="bescheid-grid">
              <div className="bescheid-field">
                <label>{t('documents.bescheid.einkommen')}</label>
                <span>{fmt(parseResult.einkommen)}</span>
              </div>
              <div className="bescheid-field">
                <label>{t('documents.bescheid.employmentIncome')}</label>
                <span>{fmt(parseResult.einkuenfte_nichtselbstaendig)}</span>
              </div>
              <div className="bescheid-field">
                <label>{t('documents.bescheid.rentalIncome')}</label>
                <span>{fmt(parseResult.einkuenfte_vermietung)}</span>
              </div>
            </div>
          </div>

          {parseResult.vermietung_details && parseResult.vermietung_details.length > 0 && (
            <div className="bescheid-section">
              <h5>V+V Details (E1b)</h5>
              {parseResult.vermietung_details.map((d, i) => (
                <div key={i} className="bescheid-vv-row">
                  <span>{d.address}</span>
                  <span>{fmt(d.amount)}</span>
                </div>
              ))}
            </div>
          )}

          <div className="bescheid-section">
            <h5>{t('documents.bescheid.festgesetzteSteuer')}</h5>
            <div className="bescheid-grid">
              <div className="bescheid-field">
                <label>{t('documents.bescheid.festgesetzteSteuer')}</label>
                <span>{fmt(parseResult.festgesetzte_einkommensteuer)}</span>
              </div>
              <div className="bescheid-field highlight-green">
                <label>{t('documents.bescheid.abgabengutschrift')}</label>
                <span>{fmt(parseResult.abgabengutschrift)}</span>
              </div>
              <div className="bescheid-field highlight-red">
                <label>{t('documents.bescheid.abgabennachforderung')}</label>
                <span>{fmt(parseResult.abgabennachforderung)}</span>
              </div>
            </div>
          </div>

          {(parseResult.werbungskosten_pauschale || parseResult.telearbeitspauschale) && (
            <div className="bescheid-section">
              <h5>{t('documents.bescheid.werbungskosten')}</h5>
              <div className="bescheid-grid">
                {parseResult.werbungskosten_pauschale && (
                  <div className="bescheid-field">
                    <label>{t('documents.bescheid.werbungskosten')}</label>
                    <span>{fmt(parseResult.werbungskosten_pauschale)}</span>
                  </div>
                )}
                {parseResult.telearbeitspauschale && (
                  <div className="bescheid-field">
                    <label>{t('documents.bescheid.telearbeitspauschale')}</label>
                    <span>{fmt(parseResult.telearbeitspauschale)}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="bescheid-actions">
            <button className="btn btn-primary" onClick={handleImport} disabled={loading}>
              ✅ {t('documents.bescheid.importConfirm')}
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

export default BescheidImport;
