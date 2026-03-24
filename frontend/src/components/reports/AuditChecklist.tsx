import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import reportService, { AuditChecklist as AuditChecklistType } from '../../services/reportService';
import './AuditChecklist.css';

interface AuditChecklistProps {
  taxYear: number;
}

const AuditChecklist = ({ taxYear }: AuditChecklistProps) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [checklist, setChecklist] = useState<AuditChecklistType | null>(null);

  useEffect(() => {
    loadChecklist();
  }, [taxYear]);

  const loadChecklist = async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await reportService.getAuditChecklist(taxYear);
      setChecklist(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('reports.audit.loadError'));
    } finally {
      setLoading(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pass':
        return '✓';
      case 'warning':
        return '⚠️';
      case 'fail':
        return '✗';
      default:
        return '?';
    }
  };

  const getStatusClass = (status: string) => {
    switch (status) {
      case 'pass':
        return 'status-pass';
      case 'warning':
        return 'status-warning';
      case 'fail':
        return 'status-fail';
      default:
        return '';
    }
  };

  const getOverallStatusClass = (status: string) => {
    switch (status) {
      case 'ready':
        return 'overall-ready';
      case 'needs_attention':
        return 'overall-warning';
      case 'not_ready':
        return 'overall-fail';
      default:
        return '';
    }
  };

  if (loading) {
    return (
      <div className="audit-checklist loading">
        <div className="spinner"></div>
        <p>{t('common.loading')}</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="audit-checklist error">
        <div className="alert alert-error">
          <span className="icon">⚠️</span>
          {error}
        </div>
      </div>
    );
  }

  if (!checklist) {
    return null;
  }

  return (
    <div className="audit-checklist">
      <div className="checklist-header">
        <h2>{t('reports.audit.title')}</h2>
        <p className="subtitle">{t('reports.audit.subtitle', { year: taxYear })}</p>
      </div>

      <div className={`overall-status ${getOverallStatusClass(checklist.overall_status)}`}>
        <div className="status-icon">
          {checklist.overall_status === 'ready' && '✓'}
          {checklist.overall_status === 'needs_attention' && '⚠️'}
          {checklist.overall_status === 'not_ready' && '✗'}
        </div>
        <div className="status-content">
          <h3>{t(`reports.audit.status.${checklist.overall_status}`)}</h3>
          <div className="status-summary">
            {checklist.missing_documents > 0 && (
              <span className="summary-item warning">
                {t('reports.audit.missingDocuments', { count: checklist.missing_documents })}
              </span>
            )}
            {checklist.compliance_issues > 0 && (
              <span className="summary-item error">
                {t('reports.audit.complianceIssues', { count: checklist.compliance_issues })}
              </span>
            )}
            {checklist.overall_status === 'ready' && (
              <span className="summary-item success">
                {t('reports.audit.allGood')}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="checklist-items">
        {checklist.items.map((item, index) => (
          <div key={index} className={`checklist-item ${getStatusClass(item.status)}`}>
            <div className="item-header">
              <span className="item-icon">{getStatusIcon(item.status)}</span>
              <h4>{t(`reports.audit.categories.${item.category}`)}</h4>
            </div>
            <p className="item-message">{item.message}</p>
            {item.details && item.details.length > 0 && (
              <ul className="item-details">
                {item.details.map((detail, idx) => (
                  <li key={idx}>{detail}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>

      <div className="checklist-footer">
        <div className="disclaimer">
          <strong>{t('reports.audit.disclaimer.title')}</strong>
          <p>{t('reports.audit.disclaimer.text')}</p>
        </div>
      </div>
    </div>
  );
};

export default AuditChecklist;
