import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { MessageCircle } from 'lucide-react';
import { documentService } from '../../services/documentService';
import { aiService } from '../../services/aiService';
import { OCRReviewData, ExtractedData, DocumentType } from '../../types/document';
import BescheidImport from './BescheidImport';
import './OCRReview.css';

interface OCRReviewProps {
  documentId: number;
  onConfirm?: () => void;
  onCancel?: () => void;
}

const OCRReview: React.FC<OCRReviewProps> = ({
  documentId,
  onConfirm,
  onCancel,
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [reviewData, setReviewData] = useState<OCRReviewData | null>(null);
  const [editedData, setEditedData] = useState<ExtractedData>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aiExplanation, setAIExplanation] = useState<string | null>(null);
  const [loadingAI, setLoadingAI] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [selectedDocType, setSelectedDocType] = useState<string>('');
  const [selectedTxnType, setSelectedTxnType] = useState<'income' | 'expense'>('expense');
  const [bescheidMode, setBescheidMode] = useState(false);
  const [bescheidOcrText, setBescheidOcrText] = useState<string>('');

  useEffect(() => {
    loadReviewData();
  }, [documentId]);

  // Load document preview as blob (needed because download endpoint requires auth)
  useEffect(() => {
    let objectUrl: string | null = null;
    documentService.downloadDocument(documentId).then((blob) => {
      objectUrl = URL.createObjectURL(blob);
      setPreviewUrl(objectUrl);
    }).catch(() => {});
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [documentId]);

  const loadReviewData = async () => {
    try {
      setLoading(true);
      const data = await documentService.getDocumentForReview(documentId);
      setReviewData(data);
      setEditedData(data.extracted_data || {});
      // Initialize document type from OCR result
      setSelectedDocType(data.document.document_type || '');

      // Detect Bescheid documents and switch to specialized import view
      const dt = data.document.document_type;
      if ((dt as string) === 'einkommensteuerbescheid' && data.document.raw_text) {
        setBescheidMode(true);
        setBescheidOcrText(data.document.raw_text);
      }

      // Guess transaction type: payslip/lohnzettel/rental = income, rest = expense
      if (dt === 'payslip' || dt === 'lohnzettel' || dt === 'rental_contract' || dt === 'bank_statement') {
        setSelectedTxnType('income');
      } else {
        setSelectedTxnType('expense');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || t('documents.review.loadError'));
    } finally {
      setLoading(false);
    }
  };

  const handleFieldChange = (field: string, value: any) => {
    setEditedData((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleConfirm = async () => {
    try {
      setSaving(true);
      
      // Always send corrections with doc type and txn type info
      const dataToSend = {
        ...editedData,
        _document_type: selectedDocType,
        _transaction_type: selectedTxnType,
      };
      
      await documentService.correctOCR(documentId, dataToSend);

      if (onConfirm) {
        onConfirm();
      } else {
        navigate('/documents');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || t('documents.review.saveError'));
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    if (onCancel) {
      onCancel();
    } else {
      navigate('/documents');
    }
  };

  const handleAskAI = async () => {
    try {
      setLoadingAI(true);
      const response = await aiService.explainOCRResult(String(documentId), editedData);
      setAIExplanation(response.content);
    } catch (err) {
      console.error('Failed to get AI explanation:', err);
    } finally {
      setLoadingAI(false);
    }
  };

  const getConfidenceClass = (confidence?: number) => {
    if (!confidence) return 'confidence-unknown';
    if (confidence >= 0.8) return 'confidence-high';
    if (confidence >= 0.6) return 'confidence-medium';
    return 'confidence-low';
  };

  const getConfidenceLabel = (confidence?: number) => {
    if (!confidence) return t('documents.review.confidence.unknown');
    if (confidence >= 0.8) return t('documents.review.confidence.high');
    if (confidence >= 0.6) return t('documents.review.confidence.medium');
    return t('documents.review.confidence.low');
  };

  if (loading) {
    return (
      <div className="ocr-review loading">
        <div className="spinner"></div>
        <p>{t('documents.review.loading')}</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="ocr-review error">
        <p className="error-message">{error}</p>
        <button className="btn btn-secondary" onClick={handleCancel}>
          {t('common.back')}
        </button>
      </div>
    );
  }

  if (!reviewData) {
    return null;
  }

  // Show specialized Bescheid import view
  if (bescheidMode && bescheidOcrText) {
    const handleBescheidDone = () => {
      if (onConfirm) onConfirm();
      else navigate('/documents');
    };
    return (
      <BescheidImport
        ocrText={bescheidOcrText}
        documentId={documentId}
        onImportComplete={handleBescheidDone}
        onCancel={() => { if (onCancel) onCancel(); else navigate('/documents'); }}
      />
    );
  }

  const { document, extracted_data, suggestions } = reviewData;

  return (
    <div className="ocr-review">
      <div className="review-header">
        <h2>{t('documents.review.title')}</h2>
        <div className="confidence-badge">
          <span className={getConfidenceClass(document.confidence_score)}>
            {getConfidenceLabel(document.confidence_score)}
          </span>
          {document.confidence_score && (
            <span className="confidence-value">
              {(document.confidence_score * 100).toFixed(0)}%
            </span>
          )}
        </div>
      </div>

      {document.needs_review && (
        <div className="review-warning">
          ⚠️ {t('documents.review.needsReview')}
        </div>
      )}

      {suggestions && suggestions.length > 0 && (
        <div className="review-suggestions">
          <h4>{t('documents.review.suggestions')}</h4>
          <ul>
            {suggestions.map((suggestion, index) => (
              <li key={index}>{suggestion}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="ai-help-section">
        <button
          className="btn btn-ai"
          onClick={handleAskAI}
          disabled={loadingAI}
        >
          <MessageCircle size={18} />
          {loadingAI ? t('ai.loading') : t('ai.askAboutDocument')}
        </button>
        {aiExplanation && (
          <div className="ai-explanation">
            <h4>{t('ai.explanation')}</h4>
            <p>{aiExplanation}</p>
          </div>
        )}
      </div>

      <div className="review-content">
        <div className="document-preview">
          <h3>{t('documents.review.preview')}</h3>
          <div className="preview-container">
            {!previewUrl ? (
              <div className="preview-loading">{t('common.loadingPreview')}</div>
            ) : document.mime_type.startsWith('image/') ? (
              <img src={previewUrl} alt={document.file_name} />
            ) : (
              <iframe src={previewUrl} title={document.file_name} />
            )}
          </div>
        </div>

        <div className="extracted-data">
          <h3>{t('documents.review.extractedData')}</h3>

          <div className="form-group">
            <label>{t('documents.documentType')}</label>
            <select
              value={selectedDocType}
              onChange={(e) => setSelectedDocType(e.target.value)}
              className="doc-type-select"
            >
              {Object.values(DocumentType).filter(v => v !== 'unknown').map((type) => (
                <option key={type} value={type}>
                  {t(`documents.types.${type}`)}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>{t('documents.review.transactionType')}</label>
            <div className="txn-type-toggle">
              <button
                type="button"
                className={`toggle-btn ${selectedTxnType === 'income' ? 'active income' : ''}`}
                onClick={() => setSelectedTxnType('income')}
              >
                {t('transactions.types.income')}
              </button>
              <button
                type="button"
                className={`toggle-btn ${selectedTxnType === 'expense' ? 'active expense' : ''}`}
                onClick={() => setSelectedTxnType('expense')}
              >
                {t('transactions.types.expense')}
              </button>
            </div>
          </div>

          <div className="form-group">
            <label>{t('documents.review.fields.date')}</label>
            <input
              type="date"
              value={editedData.date || ''}
              onChange={(e) => handleFieldChange('date', e.target.value)}
              className={getConfidenceClass(extracted_data.confidence?.date)}
            />
            {extracted_data.confidence?.date && (
              <span className="field-confidence">
                {(extracted_data.confidence.date * 100).toFixed(0)}%
              </span>
            )}
          </div>

          <div className="form-group">
            <label>{t('documents.review.fields.amount')}</label>
            <input
              type="number"
              step="0.01"
              value={editedData.amount || ''}
              onChange={(e) =>
                handleFieldChange('amount', parseFloat(e.target.value))
              }
              className={getConfidenceClass(extracted_data.confidence?.amount)}
            />
            {extracted_data.confidence?.amount && (
              <span className="field-confidence">
                {(extracted_data.confidence.amount * 100).toFixed(0)}%
              </span>
            )}
          </div>

          <div className="form-group">
            <label>{t('documents.review.fields.merchant')}</label>
            <input
              type="text"
              value={editedData.merchant || ''}
              onChange={(e) => handleFieldChange('merchant', e.target.value)}
              className={getConfidenceClass(extracted_data.confidence?.merchant)}
            />
            {extracted_data.confidence?.merchant && (
              <span className="field-confidence">
                {(extracted_data.confidence.merchant * 100).toFixed(0)}%
              </span>
            )}
          </div>

          {extracted_data.gross_income !== undefined && (
            <div className="form-group">
              <label>{t('documents.review.fields.grossIncome')}</label>
              <input
                type="number"
                step="0.01"
                value={editedData.gross_income || ''}
                onChange={(e) =>
                  handleFieldChange('gross_income', parseFloat(e.target.value))
                }
              />
            </div>
          )}

          {extracted_data.net_income !== undefined && (
            <div className="form-group">
              <label>{t('documents.review.fields.netIncome')}</label>
              <input
                type="number"
                step="0.01"
                value={editedData.net_income || ''}
                onChange={(e) =>
                  handleFieldChange('net_income', parseFloat(e.target.value))
                }
              />
            </div>
          )}

          {extracted_data.withheld_tax !== undefined && (
            <div className="form-group">
              <label>{t('documents.review.fields.withheldTax')}</label>
              <input
                type="number"
                step="0.01"
                value={editedData.withheld_tax || ''}
                onChange={(e) =>
                  handleFieldChange('withheld_tax', parseFloat(e.target.value))
                }
              />
            </div>
          )}

          {extracted_data.employer && (
            <div className="form-group">
              <label>{t('documents.review.fields.employer')}</label>
              <input
                type="text"
                value={editedData.employer || ''}
                onChange={(e) => handleFieldChange('employer', e.target.value)}
              />
            </div>
          )}

          {extracted_data.invoice_number && (
            <div className="form-group">
              <label>{t('documents.review.fields.invoiceNumber')}</label>
              <input
                type="text"
                value={editedData.invoice_number || ''}
                onChange={(e) =>
                  handleFieldChange('invoice_number', e.target.value)
                }
              />
            </div>
          )}

          {/* Mietvertrag (rental contract) specific fields */}
          {(selectedDocType === 'rental_contract' || selectedDocType === 'mietvertrag') && (
            <>
              <div className="form-group">
                <label>{t('documents.review.fields.propertyAddress')}</label>
                <input type="text" value={editedData.property_address || ''} onChange={(e) => handleFieldChange('property_address', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.monthlyRent')}</label>
                <input type="number" step="0.01" value={editedData.monthly_rent ?? ''} onChange={(e) => handleFieldChange('monthly_rent', parseFloat(e.target.value) || null)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.startDate')}</label>
                <input type="date" value={editedData.start_date ? String(editedData.start_date).substring(0, 10) : ''} onChange={(e) => handleFieldChange('start_date', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.endDate')}</label>
                <input type="date" value={editedData.end_date ? String(editedData.end_date).substring(0, 10) : ''} onChange={(e) => handleFieldChange('end_date', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.tenantName')}</label>
                <input type="text" value={editedData.tenant_name || ''} onChange={(e) => handleFieldChange('tenant_name', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.landlordName')}</label>
                <input type="text" value={editedData.landlord_name || ''} onChange={(e) => handleFieldChange('landlord_name', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.contractType')}</label>
                <input type="text" value={editedData.contract_type || ''} onChange={(e) => handleFieldChange('contract_type', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.betriebskosten')}</label>
                <input type="number" step="0.01" value={editedData.betriebskosten ?? ''} onChange={(e) => handleFieldChange('betriebskosten', parseFloat(e.target.value) || null)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.heatingCosts')}</label>
                <input type="number" step="0.01" value={editedData.heating_costs ?? ''} onChange={(e) => handleFieldChange('heating_costs', parseFloat(e.target.value) || null)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.depositAmount')}</label>
                <input type="number" step="0.01" value={editedData.deposit_amount ?? ''} onChange={(e) => handleFieldChange('deposit_amount', parseFloat(e.target.value) || null)} />
              </div>
            </>
          )}

          {/* Kaufvertrag (purchase contract) specific fields */}
          {(selectedDocType === 'purchase_contract' || selectedDocType === 'kaufvertrag') && (
            <>
              <div className="form-group">
                <label>{t('documents.review.fields.propertyAddress')}</label>
                <input type="text" value={editedData.property_address || ''} onChange={(e) => handleFieldChange('property_address', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.purchasePrice')}</label>
                <input type="number" step="0.01" value={editedData.purchase_price ?? ''} onChange={(e) => handleFieldChange('purchase_price', parseFloat(e.target.value) || null)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.purchaseDate')}</label>
                <input type="date" value={editedData.purchase_date ? String(editedData.purchase_date).substring(0, 10) : ''} onChange={(e) => handleFieldChange('purchase_date', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.buyerName')}</label>
                <input type="text" value={editedData.buyer_name || ''} onChange={(e) => handleFieldChange('buyer_name', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.sellerName')}</label>
                <input type="text" value={editedData.seller_name || ''} onChange={(e) => handleFieldChange('seller_name', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.buildingValue')}</label>
                <input type="number" step="0.01" value={editedData.building_value ?? ''} onChange={(e) => handleFieldChange('building_value', parseFloat(e.target.value) || null)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.landValue')}</label>
                <input type="number" step="0.01" value={editedData.land_value ?? ''} onChange={(e) => handleFieldChange('land_value', parseFloat(e.target.value) || null)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.grunderwerbsteuer')}</label>
                <input type="number" step="0.01" value={editedData.grunderwerbsteuer ?? ''} onChange={(e) => handleFieldChange('grunderwerbsteuer', parseFloat(e.target.value) || null)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.notaryName')}</label>
                <input type="text" value={editedData.notary_name || ''} onChange={(e) => handleFieldChange('notary_name', e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.notaryFees')}</label>
                <input type="number" step="0.01" value={editedData.notary_fees ?? ''} onChange={(e) => handleFieldChange('notary_fees', parseFloat(e.target.value) || null)} />
              </div>
              <div className="form-group">
                <label>{t('documents.review.fields.registryFees')}</label>
                <input type="number" step="0.01" value={editedData.registry_fees ?? ''} onChange={(e) => handleFieldChange('registry_fees', parseFloat(e.target.value) || null)} />
              </div>
            </>
          )}

          {extracted_data.vat_amounts &&
            Object.keys(extracted_data.vat_amounts).length > 0 && (
              <div className="vat-amounts">
                <h4>{t('documents.review.vatAmounts')}</h4>
                {Object.entries(extracted_data.vat_amounts).map(
                  ([rate, amount]) => (
                    <div key={rate} className="vat-item">
                      <span>{rate}:</span>
                      <span>€{amount.toFixed(2)}</span>
                    </div>
                  )
                )}
              </div>
            )}
        </div>
      </div>

      <div className="review-actions">
        <button
          className="btn btn-secondary"
          onClick={handleCancel}
          disabled={saving}
        >
          {t('common.cancel')}
        </button>
        <button
          className="btn btn-primary"
          onClick={handleConfirm}
          disabled={saving}
        >
          {saving ? t('common.saving') : t('documents.review.confirmAndCreate')}
        </button>
      </div>

      {/* AI Chat Widget with document context */}
    </div>
  );
};

export default OCRReview;
