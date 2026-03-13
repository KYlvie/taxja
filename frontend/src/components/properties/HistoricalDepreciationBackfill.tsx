import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Property, PropertyType } from '../../types/property';
import { HistoricalDepreciationPreview, BackfillResult } from '../../types/historicalDepreciation';
import { propertyService } from '../../services/propertyService';
import './HistoricalDepreciationBackfill.css';

interface HistoricalDepreciationBackfillProps {
  property: Property;
  onBackfillComplete?: () => void;
}

const HistoricalDepreciationBackfill = ({
  property,
  onBackfillComplete,
}: HistoricalDepreciationBackfillProps) => {
  const { t } = useTranslation();
  const [showModal, setShowModal] = useState(false);
  const [preview, setPreview] = useState<HistoricalDepreciationPreview | null>(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);
  const [isBackfilling, setIsBackfilling] = useState(false);
  const [backfillResult, setBackfillResult] = useState<BackfillResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Check if property needs backfill
  const needsBackfill = (): boolean => {
    if (property.property_type === PropertyType.OWNER_OCCUPIED) {
      return false; // Owner-occupied properties don't have depreciation
    }

    const purchaseDate = new Date(property.purchase_date);
    const currentYear = new Date().getFullYear();
    const purchaseYear = purchaseDate.getFullYear();

    // Needs backfill if purchased in a previous year
    return purchaseYear < currentYear;
  };

  const handlePreviewClick = async () => {
    setIsLoadingPreview(true);
    setError(null);
    setBackfillResult(null);

    try {
      const data = await propertyService.previewHistoricalDepreciation(property.id);
      setPreview(data);
      setShowModal(true);
    } catch (err: any) {
      console.error('Error loading preview:', err);
      setError(err.response?.data?.detail || t('properties.backfill.previewError'));
    } finally {
      setIsLoadingPreview(false);
    }
  };

  const handleConfirmBackfill = async () => {
    setIsBackfilling(true);
    setError(null);

    try {
      const result = await propertyService.backfillDepreciation(property.id);
      setBackfillResult(result);
      
      // Call the callback to refresh property data
      if (onBackfillComplete) {
        onBackfillComplete();
      }
    } catch (err: any) {
      console.error('Error backfilling depreciation:', err);
      setError(err.response?.data?.detail || t('properties.backfill.error'));
    } finally {
      setIsBackfilling(false);
    }
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setPreview(null);
    setBackfillResult(null);
    setError(null);
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('de-AT', {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  };

  // Don't show component if backfill is not needed
  if (!needsBackfill()) {
    return null;
  }

  return (
    <div className="historical-backfill-section">
      <div className="backfill-notice">
        <div className="notice-icon">ℹ️</div>
        <div className="notice-content">
          <h3>{t('properties.backfill.title')}</h3>
          <p>{t('properties.backfill.notice')}</p>
        </div>
        <button
          className="btn btn-primary"
          onClick={handlePreviewClick}
          disabled={isLoadingPreview}
        >
          {isLoadingPreview ? (
            <>
              <span className="loading-spinner-small"></span>
              {t('common.loading')}
            </>
          ) : (
            <>
              📊 {t('properties.backfill.previewButton')}
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="error-message">
          <span className="error-icon">⚠️</span>
          {error}
        </div>
      )}

      {/* Preview/Confirm Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={handleCloseModal}>
          <div className="modal-content backfill-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                {backfillResult
                  ? t('properties.backfill.successTitle')
                  : t('properties.backfill.previewTitle')}
              </h2>
              <button className="modal-close" onClick={handleCloseModal}>
                ✕
              </button>
            </div>

            <div className="modal-body">
              {backfillResult ? (
                // Success view
                <div className="backfill-success">
                  <div className="success-icon">✅</div>
                  <p className="success-message">
                    {t('properties.backfill.successMessage', {
                      count: backfillResult.years_backfilled,
                      total: formatCurrency(backfillResult.total_amount),
                    })}
                  </p>

                  <div className="backfill-summary">
                    <h3>{t('properties.backfill.createdTransactions')}</h3>
                    <table className="backfill-table">
                      <thead>
                        <tr>
                          <th>{t('properties.backfill.year')}</th>
                          <th>{t('properties.backfill.amount')}</th>
                          <th>{t('properties.backfill.date')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {backfillResult.transactions_created.map((txn) => (
                          <tr key={txn.year}>
                            <td>{txn.year}</td>
                            <td className="amount">{formatCurrency(txn.amount)}</td>
                            <td>{new Date(txn.transaction_date).toLocaleDateString('de-AT')}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : preview && preview.years.length > 0 ? (
                // Preview view
                <div className="backfill-preview">
                  <div className="warning-box">
                    <div className="warning-icon">⚠️</div>
                    <div className="warning-content">
                      <strong>{t('properties.backfill.warningTitle')}</strong>
                      <p>{t('properties.backfill.warningMessage')}</p>
                    </div>
                  </div>

                  <div className="preview-description">
                    <p>
                      {t('properties.backfill.previewDescription', {
                        count: preview.years_count,
                      })}
                    </p>
                  </div>

                  <table className="backfill-table">
                    <thead>
                      <tr>
                        <th>{t('properties.backfill.year')}</th>
                        <th>{t('properties.backfill.amount')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.years.map((year) => (
                        <tr key={year.year}>
                          <td>{year.year}</td>
                          <td className="amount">{formatCurrency(year.amount)}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr className="total-row">
                        <td>
                          <strong>{t('properties.backfill.total')}</strong>
                        </td>
                        <td className="amount">
                          <strong>{formatCurrency(preview.total_amount)}</strong>
                        </td>
                      </tr>
                    </tfoot>
                  </table>

                  {error && (
                    <div className="error-message">
                      <span className="error-icon">⚠️</span>
                      {error}
                    </div>
                  )}
                </div>
              ) : (
                // No depreciation to backfill
                <div className="no-backfill">
                  <div className="info-icon">ℹ️</div>
                  <p>{t('properties.backfill.noBackfillNeeded')}</p>
                </div>
              )}
            </div>

            <div className="modal-footer">
              {backfillResult ? (
                // Success state - just close button
                <button className="btn btn-primary" onClick={handleCloseModal}>
                  {t('common.close')}
                </button>
              ) : preview && preview.years.length > 0 ? (
                // Preview state - cancel and confirm buttons
                <>
                  <button
                    className="btn btn-secondary"
                    onClick={handleCloseModal}
                    disabled={isBackfilling}
                  >
                    {t('common.cancel')}
                  </button>
                  <button
                    className="btn btn-primary"
                    onClick={handleConfirmBackfill}
                    disabled={isBackfilling}
                  >
                    {isBackfilling ? (
                      <>
                        <span className="loading-spinner-small"></span>
                        {t('properties.backfill.backfilling')}
                      </>
                    ) : (
                      <>
                        ✓ {t('properties.backfill.confirmButton')}
                      </>
                    )}
                  </button>
                </>
              ) : (
                // No backfill needed - just close button
                <button className="btn btn-secondary" onClick={handleCloseModal}>
                  {t('common.close')}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default HistoricalDepreciationBackfill;
