import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import reportService, { AuditChecklist as AuditChecklistType, AuditChecklistItem } from '../../services/reportService';
import './AuditChecklist.css';

interface AuditChecklistProps {
  taxYear: number;
}

const AuditChecklist = ({ taxYear }: AuditChecklistProps) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [checklist, setChecklist] = useState<AuditChecklistType | null>(null);
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());

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

  const toggleExpand = (category: string) => {
    setExpandedItems((prev) => {
      const next = new Set(prev);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return next;
    });
  };

  const handleAction = (action?: string) => {
    if (action === 'transactions') {
      navigate('/transactions');
    } else if (action === 'documents') {
      navigate('/documents');
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pass':
        return '\u2713';
      case 'warning':
        return '!';
      case 'fail':
        return '\u2717';
      default:
        return '?';
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'var(--color-success)';
    if (score >= 50) return 'var(--color-warning)';
    return 'var(--color-danger)';
  };

  const renderItemMessage = (item: AuditChecklistItem): string => {
    const { category, status, count } = item;

    if (status === 'pass') {
      switch (category) {
        case 'transactions':
          return t('reports.audit.messages.transactionsOk', { count });
        case 'documents':
          return t('reports.audit.messages.documentsOk', { count });
        case 'deductions':
          return t('reports.audit.messages.deductionsOk', { count });
        case 'vat':
          return item.below_threshold
            ? t('reports.audit.messages.vatBelowThreshold')
            : t('reports.audit.messages.vatOk', { count });
        case 'completeness':
          return t('reports.audit.messages.completenessOk');
        default:
          return '';
      }
    }

    switch (category) {
      case 'transactions':
        return t('reports.audit.messages.transactionsFail');
      case 'documents':
        return t('reports.audit.messages.documentsWarn', { count, required: item.required, gap: item.gap });
      case 'deductions':
        return t('reports.audit.messages.deductionsWarn', { count });
      case 'vat':
        return t('reports.audit.messages.vatFail', { income: item.income?.toLocaleString() });
      case 'completeness':
        return t('reports.audit.messages.completenessWarn', { count });
      case 'duplicates':
        return t('reports.audit.messages.duplicatesWarn', { count });
      default:
        return '';
    }
  };

  const renderRecommendation = (item: AuditChecklistItem): string | null => {
    if (item.status === 'pass') return null;

    switch (item.category) {
      case 'transactions':
        return t('reports.audit.recommendations.transactions');
      case 'documents':
        return t('reports.audit.recommendations.documents');
      case 'deductions':
        return t('reports.audit.recommendations.deductions');
      case 'vat':
        return t('reports.audit.recommendations.vat');
      case 'completeness':
        return t('reports.audit.recommendations.completeness');
      case 'duplicates':
        return t('reports.audit.recommendations.duplicates');
      default:
        return null;
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
          <span className="icon">!</span>
          {error}
        </div>
      </div>
    );
  }

  if (!checklist) {
    return null;
  }

  const scoreColor = getScoreColor(checklist.compliance_score);
  const circumference = 2 * Math.PI * 54;
  const strokeDashoffset = circumference - (checklist.compliance_score / 100) * circumference;

  return (
    <div className="audit-checklist">
      <div className="checklist-header">
        <h2>{t('reports.audit.title')}</h2>
        <p className="subtitle">{t('reports.audit.subtitle', { year: taxYear })}</p>
      </div>

      {/* Score + Status Overview */}
      <div className={`overall-status overall-${checklist.overall_status === 'ready' ? 'ready' : checklist.overall_status === 'needs_attention' ? 'warning' : 'fail'}`}>
        <div className="score-ring">
          <svg viewBox="0 0 120 120" width="120" height="120">
            <circle cx="60" cy="60" r="54" fill="none" stroke="var(--color-border-light)" strokeWidth="8" />
            <circle
              cx="60" cy="60" r="54" fill="none"
              stroke={scoreColor}
              strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              transform="rotate(-90 60 60)"
              style={{ transition: 'stroke-dashoffset 0.6s ease' }}
            />
          </svg>
          <div className="score-value" style={{ color: scoreColor }}>
            {Math.round(checklist.compliance_score)}
          </div>
        </div>

        <div className="status-content">
          <h3>{t(`reports.audit.status.${checklist.overall_status}`)}</h3>
          <div className="status-counts">
            {checklist.critical_count > 0 && (
              <span className="count-badge count-critical">
                {t('reports.audit.criticalIssues', { count: checklist.critical_count })}
              </span>
            )}
            {checklist.warning_count > 0 && (
              <span className="count-badge count-warning">
                {t('reports.audit.warningIssues', { count: checklist.warning_count })}
              </span>
            )}
            {checklist.critical_count === 0 && checklist.warning_count === 0 && (
              <span className="count-badge count-success">
                {t('reports.audit.allGood')}
              </span>
            )}
          </div>

          {/* Summary Stats */}
          <div className="summary-stats">
            <div className="stat">
              <span className="stat-value">{checklist.summary.total_transactions}</span>
              <span className="stat-label">{t('reports.audit.stats.transactions')}</span>
            </div>
            <div className="stat">
              <span className="stat-value">{checklist.summary.documentation_rate}%</span>
              <span className="stat-label">{t('reports.audit.stats.docRate')}</span>
            </div>
            <div className="stat">
              <span className="stat-value">\u20ac{checklist.summary.total_income.toLocaleString()}</span>
              <span className="stat-label">{t('reports.audit.stats.income')}</span>
            </div>
            <div className="stat">
              <span className="stat-value">\u20ac{checklist.summary.total_deductible.toLocaleString()}</span>
              <span className="stat-label">{t('reports.audit.stats.deductible')}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Checklist Items */}
      <div className="checklist-items">
        {checklist.items.map((item) => {
          const isExpanded = expandedItems.has(item.category);
          const hasDetails = item.affected && item.affected.length > 0;
          const recommendation = renderRecommendation(item);

          return (
            <div
              key={item.category}
              className={`checklist-item status-${item.status}${hasDetails ? ' expandable' : ''}`}
            >
              <div
                className="item-header"
                onClick={() => hasDetails && toggleExpand(item.category)}
                role={hasDetails ? 'button' : undefined}
                tabIndex={hasDetails ? 0 : undefined}
              >
                <span className={`item-icon item-icon-${item.status}`}>
                  {getStatusIcon(item.status)}
                </span>
                <div className="item-content">
                  <h4>{t(`reports.audit.categories.${item.category}`)}</h4>
                  <p className="item-message">{renderItemMessage(item)}</p>
                </div>
                {hasDetails && (
                  <span className={`expand-arrow ${isExpanded ? 'expanded' : ''}`}>
                    &#x25B8;
                  </span>
                )}
                {item.action && item.status !== 'pass' && (
                  <button
                    className="action-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleAction(item.action);
                    }}
                  >
                    {t('reports.audit.fix')}
                  </button>
                )}
              </div>

              {/* Recommendation */}
              {recommendation && (
                <p className="item-recommendation">{recommendation}</p>
              )}

              {/* Expanded affected items */}
              {isExpanded && item.affected && (
                <div className="affected-list">
                  {item.affected.map((a, idx) => (
                    <div key={idx} className="affected-item">
                      {a.description && (
                        <span className="affected-desc">{a.description}</span>
                      )}
                      {a.amount !== undefined && (
                        <span className="affected-amount">\u20ac{a.amount.toLocaleString()}</span>
                      )}
                      {a.date && (
                        <span className="affected-date">{a.date}</span>
                      )}
                      {a.count !== undefined && a.count > 1 && (
                        <span className="affected-count">
                          {t('reports.audit.duplicateCount', { count: a.count })}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
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
