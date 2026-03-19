import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import reportService from '../../services/reportService';
import './DataExport.css';

const DataExport = () => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);

  const handleExport = async () => {
    setLoading(true);
    setError(null);
    setSuccess(false);

    try {
      const response = await reportService.exportUserDataDirect();
      downloadBlob(response, 'taxja-user-data.json');

      setSuccess(true);
      setShowConfirmation(false);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('reports.export.error'));
    } finally {
      setLoading(false);
    }
  };

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="data-export">
      <div className="export-header">
        <h2>{t('reports.export.title')}</h2>
        <p className="subtitle">{t('reports.export.subtitle')}</p>
      </div>

      <div className="export-info">
        <div className="info-section">
          <h3>{t('reports.export.whatIsIncluded')}</h3>
          <ul>
            <li>{t('reports.export.includes.profile')}</li>
            <li>{t('reports.export.includes.transactions')}</li>
            <li>{t('reports.export.includes.documents')}</li>
            <li>{t('reports.export.includes.reports')}</li>
            <li>{t('reports.export.includes.settings')}</li>
          </ul>
        </div>

        <div className="info-section">
          <h3>{t('reports.export.format')}</h3>
          <p>{t('reports.export.formatDescription')}</p>
        </div>

        <div className="info-section gdpr-notice">
          <h3>{t('reports.export.gdprTitle')}</h3>
          <p>{t('reports.export.gdprText')}</p>
        </div>
      </div>

      {error && (
        <div className="alert alert-error">
          <span className="icon">{'\u26A0'}</span>
          {error}
        </div>
      )}

      {success && (
        <div className="alert alert-success">
          <span className="icon">{'\u2713'}</span>
          {t('reports.export.success')}
        </div>
      )}

      {!showConfirmation ? (
        <div className="export-actions">
          <button
            onClick={() => setShowConfirmation(true)}
            className="btn btn-primary"
            disabled={loading}
          >
            {t('reports.export.startExport')}
          </button>
        </div>
      ) : (
        <div className="confirmation-dialog">
          <div className="confirmation-content">
            <h3>{t('reports.export.confirmTitle')}</h3>
            <p>{t('reports.export.confirmText')}</p>
            <div className="confirmation-actions">
              <button
                onClick={handleExport}
                className="btn btn-primary"
                disabled={loading}
              >
                {loading ? t('common.loading') : t('common.confirm')}
              </button>
              <button
                onClick={() => setShowConfirmation(false)}
                className="btn btn-secondary"
                disabled={loading}
              >
                {t('common.cancel')}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="export-footer">
        <div className="security-notice">
          <span className="icon">{'\uD83D\uDD12'}</span>
          <div>
            <strong>{t('reports.export.securityTitle')}</strong>
            <p>{t('reports.export.securityText')}</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DataExport;
