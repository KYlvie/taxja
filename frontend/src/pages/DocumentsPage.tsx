import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import DocumentUpload from '../components/documents/DocumentUpload';
import DocumentList from '../components/documents/DocumentList';
import OCRReview from '../components/documents/OCRReview';
import BescheidImport from '../components/documents/BescheidImport';
import E1FormImport from '../components/documents/E1FormImport';
import { documentService } from '../services/documentService';
import { Document } from '../types/document';
import './DocumentsPage.css';

const DocumentsPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { documentId } = useParams<{ documentId: string }>();
  const [reviewingDocument, setReviewingDocument] = useState<number | null>(null);
  const [bescheidOcrText, setBescheidOcrText] = useState<string | null>(null);
  const [bescheidDocId, setBescheidDocId] = useState<number | null>(null);
  const [bescheidParseResult, setBescheidParseResult] = useState<any>(null);
  const [e1OcrText, setE1OcrText] = useState<string | null>(null);
  const [e1DocId, setE1DocId] = useState<number | null>(null);
  const [e1ParseResult, setE1ParseResult] = useState<any>(null);
  const [viewingDocument, setViewingDocument] = useState<Document | null>(null);
  const [viewerBlobUrl, setViewerBlobUrl] = useState<string | null>(null);
  const [confirmingAction, setConfirmingAction] = useState<string | null>(null);
  const [confirmResult, setConfirmResult] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  // When navigated with a documentId param, load and show that document
  useEffect(() => {
    if (documentId) {
      const id = parseInt(documentId);
      if (!isNaN(id)) {
        documentService.getDocument(id).then((doc) => {
          if ((doc.document_type as string) === 'einkommensteuerbescheid') {
            const rawText = doc.raw_text || (typeof doc.ocr_result === 'string' ? doc.ocr_result : '');
            if (rawText) {
              setBescheidOcrText(rawText);
              setBescheidDocId(id);
              return;
            }
          }
          if (doc.needs_review) {
            setReviewingDocument(id);
          } else {
            setViewingDocument(doc);
          }
        }).catch((err) => {
          console.error('Failed to load document:', err);
        });
      }
    }
  }, [documentId]);

  // Load document blob for preview
  useEffect(() => {
    if (!viewingDocument) {
      if (viewerBlobUrl) { URL.revokeObjectURL(viewerBlobUrl); setViewerBlobUrl(null); }
      return;
    }
    let url: string | null = null;
    documentService.downloadDocument(viewingDocument.id).then((blob) => {
      url = URL.createObjectURL(blob);
      setViewerBlobUrl(url);
    }).catch(() => {});
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [viewingDocument]);

  const handleDocumentSelect = async (document: Document) => {
    if (document.document_type === 'einkommensteuerbescheid' as any) {
      try {
        const detail = await documentService.getDocument(document.id);
        const rawText = detail.raw_text || (typeof detail.ocr_result === 'string' ? detail.ocr_result : '');
        if (rawText) {
          setBescheidOcrText(rawText);
          setBescheidDocId(document.id);
          return;
        }
      } catch (err) {
        console.error('Failed to load Bescheid document:', err);
      }
    }
    if (document.needs_review) {
      setReviewingDocument(document.id);
    } else {
      setViewingDocument(document);
      navigate(`/documents/${document.id}`, { replace: true });
    }
  };

  const handleReviewComplete = () => {
    setReviewingDocument(null);
    navigate('/documents', { replace: true });
    setRefreshKey((k) => k + 1);
  };

  const handleReviewCancel = () => {
    setReviewingDocument(null);
    navigate('/documents', { replace: true });
  };

  const handleCloseViewer = () => {
    setViewingDocument(null);
    setConfirmResult(null);
    navigate('/documents', { replace: true });
  };

  const handleConfirmProperty = useCallback(async () => {
    if (!viewingDocument) return;
    setConfirmingAction('property');
    setConfirmResult(null);
    try {
      await documentService.confirmProperty(viewingDocument.id);
      setConfirmResult({ type: 'success', message: t('documents.suggestion.propertyCreated') });
      const updated = await documentService.getDocument(viewingDocument.id);
      setViewingDocument(updated);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Error';
      setConfirmResult({ type: 'error', message: detail });
    } finally {
      setConfirmingAction(null);
    }
  }, [viewingDocument, t]);

  const handleConfirmRecurring = useCallback(async () => {
    if (!viewingDocument) return;
    setConfirmingAction('recurring');
    setConfirmResult(null);
    try {
      await documentService.confirmRecurring(viewingDocument.id);
      setConfirmResult({ type: 'success', message: t('documents.suggestion.recurringCreated') });
      const updated = await documentService.getDocument(viewingDocument.id);
      setViewingDocument(updated);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Error';
      setConfirmResult({ type: 'error', message: detail });
    } finally {
      setConfirmingAction(null);
    }
  }, [viewingDocument, t]);

  const handleDismissSuggestion = useCallback(async () => {
    if (!viewingDocument) return;
    setConfirmingAction('dismiss');
    try {
      await documentService.dismissSuggestion(viewingDocument.id);
      const updated = await documentService.getDocument(viewingDocument.id);
      setViewingDocument(updated);
      setConfirmResult(null);
    } catch (err: any) {
      console.error('Failed to dismiss suggestion:', err);
    } finally {
      setConfirmingAction(null);
    }
  }, [viewingDocument]);

  const handleDownloadDocument = async () => {
    if (!viewingDocument) return;
    try {
      const blob = await documentService.downloadDocument(viewingDocument.id);
      const url = window.URL.createObjectURL(blob);
      const a = window.document.createElement('a');
      a.href = url;
      a.download = viewingDocument.file_name;
      window.document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      window.document.body.removeChild(a);
    } catch (error) {
      console.error('Failed to download:', error);
    }
  };

  const handleBescheidComplete = () => {
    setBescheidOcrText(null);
    setBescheidDocId(null);
    setBescheidParseResult(null);
    navigate('/documents', { replace: true });
    setRefreshKey((k) => k + 1);
  };

  const handleE1Complete = () => {
    setE1OcrText(null);
    setE1DocId(null);
    setE1ParseResult(null);
    navigate('/documents', { replace: true });
    setRefreshKey((k) => k + 1);
  };

  // Bescheid / E1 import views (triggered when OCR detects these document types)
  if (bescheidOcrText) {
    return (
      <div className="documents-page">
        <BescheidImport
          ocrText={bescheidOcrText}
          documentId={bescheidDocId ?? undefined}
          initialParseResult={bescheidParseResult}
          onImportComplete={handleBescheidComplete}
          onCancel={handleBescheidComplete}
        />
      </div>
    );
  }

  if (e1OcrText) {
    return (
      <div className="documents-page">
        <E1FormImport
          ocrText={e1OcrText}
          documentId={e1DocId ?? undefined}
          initialParseResult={e1ParseResult}
          onImportComplete={handleE1Complete}
          onCancel={handleE1Complete}
        />
      </div>
    );
  }

  if (reviewingDocument) {
    return (
      <div className="documents-page">
        <OCRReview
          documentId={reviewingDocument}
          onConfirm={handleReviewComplete}
          onCancel={handleReviewCancel}
        />
      </div>
    );
  }

  if (viewingDocument) {
    const isImage = viewingDocument.mime_type?.startsWith('image/');
    const isPdf = viewingDocument.mime_type === 'application/pdf';

    return (
      <div className="documents-page">
        <div className="document-viewer">
          <div className="viewer-header">
            <button className="btn btn-secondary" onClick={handleCloseViewer}>
              ← {t('common.back')}
            </button>
            <h2>{viewingDocument.file_name}</h2>
            <button className="btn btn-primary" onClick={handleDownloadDocument}>
              ⬇️ {t('documents.download')}
            </button>
          </div>
          <div className="viewer-meta">
            <span>{t(`documents.types.${viewingDocument.document_type}`)}</span>
            <span>{new Date(viewingDocument.created_at).toLocaleDateString('de-AT')}</span>
            {viewingDocument.confidence_score != null && (
              <span>{t('documents.confidence')}: {(viewingDocument.confidence_score * 100).toFixed(0)}%</span>
            )}
          </div>
          <div className="viewer-content">
            {!viewerBlobUrl ? (
              <div className="viewer-fallback"><p>{t('common.loadingPreview')}</p></div>
            ) : isImage ? (
              <img src={viewerBlobUrl} alt={viewingDocument.file_name} className="viewer-image" />
            ) : isPdf ? (
              <iframe src={viewerBlobUrl} title={viewingDocument.file_name} className="viewer-pdf" />
            ) : (
              <div className="viewer-fallback">
                <p>{t('documents.previewNotAvailable')}</p>
                <button className="btn btn-primary" onClick={handleDownloadDocument}>
                  ⬇️ {t('documents.download')}
                </button>
              </div>
            )}
          </div>
          {viewingDocument.ocr_result && (
            <div className="viewer-ocr-result">
              <h3>{t('documents.ocrResult')}</h3>
              <div className="ocr-fields-grid">
                {(() => {
                  const data = typeof viewingDocument.ocr_result === 'string'
                    ? (() => { try { return JSON.parse(viewingDocument.ocr_result); } catch { return null; } })()
                    : viewingDocument.ocr_result;
                  if (!data || typeof data !== 'object') {
                    return <pre>{String(viewingDocument.ocr_result)}</pre>;
                  }

                  const labels: Record<string, string> = {
                    property_address: t('documents.ocr.propertyAddress'),
                    street: t('documents.ocr.street'),
                    city: t('documents.ocr.city'),
                    postal_code: t('documents.ocr.postalCode'),
                    purchase_price: t('documents.ocr.purchasePrice'),
                    purchase_date: t('documents.ocr.purchaseDate'),
                    building_value: t('documents.ocr.buildingValue'),
                    land_value: t('documents.ocr.landValue'),
                    grunderwerbsteuer: t('documents.ocr.transferTax'),
                    notary_fees: t('documents.ocr.notaryFees'),
                    registry_fees: t('documents.ocr.registryFees'),
                    buyer_name: t('documents.ocr.buyerName'),
                    seller_name: t('documents.ocr.sellerName'),
                    notary_name: t('documents.ocr.notaryName'),
                    notary_location: t('documents.ocr.notaryLocation'),
                    construction_year: t('documents.ocr.constructionYear'),
                    property_type: t('documents.ocr.propertyType'),
                    monthly_rent: t('documents.ocr.monthlyRent'),
                    start_date: t('documents.ocr.startDate'),
                    end_date: t('documents.ocr.endDate'),
                    betriebskosten: t('documents.ocr.operatingCosts'),
                    heating_costs: t('documents.ocr.heatingCosts'),
                    deposit_amount: t('documents.ocr.deposit'),
                    utilities_included: t('documents.ocr.utilitiesIncluded'),
                    tenant_name: t('documents.ocr.tenantName'),
                    landlord_name: t('documents.ocr.landlordName'),
                    contract_type: t('documents.ocr.contractType'),
                  };

                  const formatValue = (key: string, val: unknown): string => {
                    if (val === null || val === undefined) return '—';
                    if (typeof val === 'boolean') return val ? '✓' : '✗';
                    const s = String(val);
                    if (key.includes('date') && s.match(/^\d{4}-\d{2}-\d{2}/)) {
                      try { return new Date(s).toLocaleDateString('de-AT'); } catch { return s; }
                    }
                    if (['purchase_price', 'building_value', 'land_value', 'grunderwerbsteuer',
                         'notary_fees', 'registry_fees', 'monthly_rent', 'betriebskosten',
                         'heating_costs', 'deposit_amount'].includes(key) && !isNaN(Number(val))) {
                      return `€ ${Number(val).toLocaleString('de-AT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                    }
                    return s;
                  };

                  const skipKeys = ['field_confidence', 'confidence', 'import_suggestion', 'line_items', 'vat_summary'];
                  const entries = Object.entries(data).filter(
                    ([k, v]) => !skipKeys.includes(k) && v !== null && v !== undefined
                      && typeof v !== 'object'
                  );

                  const lineItems = Array.isArray(data.line_items) ? data.line_items : [];
                  const vatSummary = Array.isArray(data.vat_summary) ? data.vat_summary : [];

                  const fmtEur = (v: unknown) =>
                    v != null && !isNaN(Number(v))
                      ? `€ ${Number(v).toLocaleString('de-AT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                      : '—';
                  const fmtPct = (v: unknown) => {
                    if (v == null || isNaN(Number(v))) return '—';
                    const n = Number(v);
                    // VLM may return 10/20 (whole %) or 0.10/0.20 (decimal)
                    const pct = n >= 1 ? n : n * 100;
                    return `${pct.toFixed(0)}%`;
                  };

                  return (
                    <>
                      {entries.length > 0 && (
                        <div className="ocr-fields-table">
                          {entries.map(([key, val]) => (
                            <div key={key} className="ocr-field-row">
                              <span className="ocr-field-label">{labels[key] || key}</span>
                              <span className="ocr-field-value">{formatValue(key, val)}</span>
                            </div>
                          ))}
                        </div>
                      )}

                      {lineItems.length > 0 && (
                        <div className="ocr-line-items">
                          <h4>🧾 {t('documents.ocr.lineItems')}</h4>
                          <div className="line-items-table">
                            <div className="line-items-header">
                              <span className="li-col-name">{t('documents.ocr.itemName')}</span>
                              <span className="li-col-qty">{t('documents.ocr.quantity')}</span>
                              <span className="li-col-price">{t('documents.ocr.unitPrice')}</span>
                              <span className="li-col-total">{t('documents.ocr.totalPrice')}</span>
                              <span className="li-col-vat">{t('documents.ocr.vatRate')}</span>
                              <span className="li-col-ind">{t('documents.ocr.vatIndicator')}</span>
                            </div>
                            {lineItems.map((item: any, idx: number) => (
                              <div key={idx} className="line-items-row">
                                <span className="li-col-name">{item.name || '—'}</span>
                                <span className="li-col-qty">{item.quantity ?? 1}</span>
                                <span className="li-col-price">{fmtEur(item.unit_price)}</span>
                                <span className="li-col-total">{fmtEur(item.total_price)}</span>
                                <span className="li-col-vat">{fmtPct(item.vat_rate)}</span>
                                <span className="li-col-ind">{item.vat_indicator || '—'}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {vatSummary.length > 0 && (
                        <div className="ocr-vat-summary">
                          <h4>📊 {t('documents.ocr.vatSummary')}</h4>
                          <div className="vat-summary-table">
                            <div className="vat-summary-header">
                              <span>{t('documents.ocr.indicator')}</span>
                              <span>{t('documents.ocr.vatRate')}</span>
                              <span>{t('documents.ocr.netAmount')}</span>
                              <span>{t('documents.ocr.vatAmount')}</span>
                            </div>
                            {vatSummary.map((row: any, idx: number) => (
                              <div key={idx} className="vat-summary-row">
                                <span>{row.indicator || '—'}</span>
                                <span>{fmtPct(row.rate)}</span>
                                <span>{fmtEur(row.net_amount)}</span>
                                <span>{fmtEur(row.vat_amount)}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {entries.length === 0 && lineItems.length === 0 && (
                        <p style={{ color: '#999' }}>{t('documents.ocr.noData')}</p>
                      )}
                    </>
                  );
                })()}
              </div>
            </div>
          )}

          {/* Import Suggestion Confirmation Card */}
          {(() => {
            const data = typeof viewingDocument.ocr_result === 'string'
              ? (() => { try { return JSON.parse(viewingDocument.ocr_result as string); } catch { return null; } })()
              : viewingDocument.ocr_result;
            const suggestion = data?.import_suggestion;
            if (!suggestion || suggestion.status !== 'pending') return null;

            const fmt = (v: number | null | undefined) =>
              v != null ? `€ ${v.toLocaleString('de-AT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—';
            const fmtDate = (d: string | null | undefined) => {
              if (!d) return '—';
              try { return new Date(d).toLocaleDateString('de-AT'); } catch { return d; }
            };

            if (suggestion.type === 'create_property') {
              const d = suggestion.data;
              return (
                <div className="import-suggestion-card">
                  <div className="suggestion-header">
                    <span className="suggestion-icon">🏠</span>
                    <h3>{t('documents.suggestion.createProperty')}</h3>
                  </div>
                  <div className="suggestion-details">
                    <div className="suggestion-row"><span>{t('documents.ocr.propertyAddress')}</span><span>{d.address}</span></div>
                    <div className="suggestion-row"><span>{t('documents.ocr.purchasePrice')}</span><span>{fmt(d.purchase_price)}</span></div>
                    <div className="suggestion-row"><span>{t('documents.ocr.purchaseDate')}</span><span>{fmtDate(d.purchase_date)}</span></div>
                    <div className="suggestion-row"><span>{t('documents.ocr.buildingValue')}</span><span>{fmt(d.building_value)}</span></div>
                    {d.grunderwerbsteuer && <div className="suggestion-row"><span>{t('documents.ocr.transferTax')}</span><span>{fmt(d.grunderwerbsteuer)}</span></div>}
                  </div>
                  {confirmResult && (
                    <div className={`suggestion-result ${confirmResult.type}`}>{confirmResult.message}</div>
                  )}
                  <div className="suggestion-actions">
                    <button className="btn btn-primary" onClick={handleConfirmProperty} disabled={confirmingAction !== null}>
                      {confirmingAction === 'property' ? '⏳' : '✅'} {t('documents.suggestion.confirm')}
                    </button>
                    <button className="btn btn-secondary" onClick={handleDismissSuggestion} disabled={confirmingAction !== null}>
                      {t('documents.suggestion.dismiss')}
                    </button>
                  </div>
                </div>
              );
            }

            if (suggestion.type === 'create_recurring_income') {
              const d = suggestion.data;
              return (
                <div className="import-suggestion-card">
                  <div className="suggestion-header">
                    <span className="suggestion-icon">🔄</span>
                    <h3>{t('documents.suggestion.createRecurring')}</h3>
                  </div>
                  <div className="suggestion-details">
                    <div className="suggestion-row"><span>{t('documents.ocr.monthlyRent')}</span><span>{fmt(d.monthly_rent)}</span></div>
                    <div className="suggestion-row"><span>{t('documents.ocr.startDate')}</span><span>{fmtDate(d.start_date)}</span></div>
                    {d.end_date && <div className="suggestion-row"><span>{t('documents.ocr.endDate')}</span><span>{fmtDate(d.end_date)}</span></div>}
                    {d.address && <div className="suggestion-row"><span>{t('documents.ocr.propertyAddress')}</span><span>{d.address}</span></div>}
                    {d.matched_property_address && (
                      <div className="suggestion-row suggestion-match">
                        <span>{t('documents.suggestion.matchedProperty')}</span>
                        <span>{d.matched_property_address}</span>
                      </div>
                    )}
                    {!d.matched_property_id && (
                      <div className="suggestion-warning">{t('documents.suggestion.noPropertyMatch')}</div>
                    )}
                  </div>
                  {confirmResult && (
                    <div className={`suggestion-result ${confirmResult.type}`}>{confirmResult.message}</div>
                  )}
                  <div className="suggestion-actions">
                    <button className="btn btn-primary" onClick={handleConfirmRecurring} disabled={confirmingAction !== null || !d.matched_property_id}>
                      {confirmingAction === 'recurring' ? '⏳' : '✅'} {t('documents.suggestion.confirm')}
                    </button>
                    <button className="btn btn-secondary" onClick={handleDismissSuggestion} disabled={confirmingAction !== null}>
                      {t('documents.suggestion.dismiss')}
                    </button>
                  </div>
                </div>
              );
            }

            return null;
          })()}
        </div>
      </div>
    );
  }

  // Main view: upload zone at top + document list below (no tabs)
  return (
    <div className="documents-page">
      <div className="page-header">
        <h1>{t('documents.title')}</h1>
      </div>

      <div className="upload-section">
        <DocumentUpload />
      </div>

      <div className="documents-list-section">
        <DocumentList key={refreshKey} onDocumentSelect={handleDocumentSelect} />
      </div>
    </div>
  );
};

export default DocumentsPage;
