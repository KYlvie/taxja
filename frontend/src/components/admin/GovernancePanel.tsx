import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import api from '../../services/api';
import './GovernancePanel.css';

interface RuleMetrics {
  total_rules: number;
  strict_rules: number;
  soft_rules: number;
  frozen_rules: number;
  strict_rule_ratio: number;
  soft_rule_ratio: number;
  total_hits: number;
  strict_hits: number;
  soft_hits: number;
  strict_hit_rate: number;
  soft_hit_rate: number;
  avg_soft_confidence: number;
  avg_strict_confidence: number;
}

interface CorrectionMetrics {
  total_corrections: number;
  by_source: Record<string, number>;
  trainable_count: number;
  excluded_count: number;
  human_verified_count: number;
  llm_verified_count: number;
  llm_unverified_count: number;
  llm_consensus_count: number;
  system_default_count: number;
  legacy_null_count: number;
  human_verified_ratio: number;
  llm_unverified_exclusion_rate: number;
}

interface GovernanceReport {
  rules: RuleMetrics;
  corrections: CorrectionMetrics;
  soft_to_strict_upgrades: number;
}

interface TrainingAudit {
  total_corrections: number;
  by_source: Record<string, { count: number; ratio: number }>;
  trainable_sources: string[];
  excluded_sources: string[];
  trainable_count: number;
  excluded_count: number;
  net_trainable_ratio: number;
  min_samples_for_retrain: number;
  ready_to_retrain: boolean;
}

const GovernancePanel = () => {
  const { t } = useTranslation();
  const [report, setReport] = useState<GovernanceReport | null>(null);
  const [audit, setAudit] = useState<TrainingAudit | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [decayLoading, setDecayLoading] = useState(false);
  const [archiveLoading, setArchiveLoading] = useState(false);
  const [actionResult, setActionResult] = useState<string | null>(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [metricsRes, auditRes] = await Promise.allSettled([
        api.get('/admin/governance/metrics'),
        api.get('/admin/governance/training-audit'),
      ]);
      if (metricsRes.status === 'fulfilled') setReport(metricsRes.value.data);
      if (auditRes.status === 'fulfilled') setAudit(auditRes.value.data);
      if (metricsRes.status === 'rejected' && auditRes.status === 'rejected') {
        setError(t('admin.governance.fetchError', 'Failed to load governance data'));
      }
    } catch {
      setError(t('admin.governance.fetchError', 'Failed to load governance data'));
    } finally {
      setLoading(false);
    }
  };

  const handleDecay = async () => {
    setDecayLoading(true);
    setActionResult(null);
    try {
      // Decay all users — use user_id=0 as a sentinel; backend will need to handle
      // For now we pass a prompt for user_id
      const userId = prompt(t('admin.governance.enterUserId', 'Enter user ID to decay stale rules:'));
      if (!userId) { setDecayLoading(false); return; }
      const res = await api.post(`/admin/governance/decay-rules?user_id=${userId}&stale_days=90`);
      setActionResult(t('admin.governance.decayResult', 'Decayed {{count}} rules', { count: res.data.decayed_count }));
      fetchData();
    } catch {
      setActionResult(t('admin.governance.actionError', 'Action failed'));
    } finally {
      setDecayLoading(false);
    }
  };

  const handleArchive = async () => {
    setArchiveLoading(true);
    setActionResult(null);
    try {
      const userId = prompt(t('admin.governance.enterUserId', 'Enter user ID to archive low-hit rules:'));
      if (!userId) { setArchiveLoading(false); return; }
      const res = await api.post(`/admin/governance/archive-rules?user_id=${userId}&min_hits=1&stale_days=180`);
      setActionResult(t('admin.governance.archiveResult', 'Archived {{count}} rules', { count: res.data.archived_count }));
      fetchData();
    } catch {
      setActionResult(t('admin.governance.actionError', 'Action failed'));
    } finally {
      setArchiveLoading(false);
    }
  };

  const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

  if (loading) return <div className="gov-loading">{t('common.loading')}</div>;
  if (error) return (
    <div className="gov-error">
      <p>{error}</p>
      <button type="button" onClick={fetchData}>{t('common.retry')}</button>
    </div>
  );

  const rules = report?.rules;
  const corrections = report?.corrections;

  return (
    <div className="governance-panel">
      {/* Rule System KPIs */}
      <div className="gov-section">
        <h3 className="gov-section-title">
          <span className="gov-icon">📏</span>
          {t('admin.governance.ruleMetrics', 'Classification Rules')}
        </h3>
        <div className="gov-kpi-grid">
          <div className="gov-kpi">
            <span className="gov-kpi-value">{rules?.total_rules ?? 0}</span>
            <span className="gov-kpi-label">{t('admin.governance.totalRules', 'Total Rules')}</span>
          </div>
          <div className="gov-kpi">
            <span className="gov-kpi-value strict">{rules?.strict_rules ?? 0}</span>
            <span className="gov-kpi-label">{t('admin.governance.strictRules', 'Strict')}</span>
          </div>
          <div className="gov-kpi">
            <span className="gov-kpi-value soft">{rules?.soft_rules ?? 0}</span>
            <span className="gov-kpi-label">{t('admin.governance.softRules', 'Soft')}</span>
          </div>
          <div className="gov-kpi">
            <span className="gov-kpi-value frozen">{rules?.frozen_rules ?? 0}</span>
            <span className="gov-kpi-label">{t('admin.governance.frozenRules', 'Frozen')}</span>
          </div>
        </div>
      </div>

      {/* Hit Rates */}
      <div className="gov-grid-2">
        <div className="gov-section">
          <h3 className="gov-section-title">
            <span className="gov-icon">🎯</span>
            {t('admin.governance.hitRates', 'Hit Rates')}
          </h3>
          <div className="gov-metric-rows">
            <div className="gov-metric-row">
              <span className="gov-metric-label">{t('admin.governance.strictHitRate', 'Strict Hit Rate')}</span>
              <span className="gov-metric-value">{pct(rules?.strict_hit_rate ?? 0)}</span>
            </div>
            <div className="gov-metric-row">
              <span className="gov-metric-label">{t('admin.governance.softHitRate', 'Soft Hit Rate')}</span>
              <span className="gov-metric-value">{pct(rules?.soft_hit_rate ?? 0)}</span>
            </div>
            <div className="gov-metric-row">
              <span className="gov-metric-label">{t('admin.governance.totalHits', 'Total Hits')}</span>
              <span className="gov-metric-value">{rules?.total_hits ?? 0}</span>
            </div>
            <div className="gov-metric-row">
              <span className="gov-metric-label">{t('admin.governance.softToStrict', 'Soft→Strict Upgrades')}</span>
              <span className="gov-metric-value highlight">{report?.soft_to_strict_upgrades ?? 0}</span>
            </div>
          </div>
        </div>

        <div className="gov-section">
          <h3 className="gov-section-title">
            <span className="gov-icon">📊</span>
            {t('admin.governance.confidence', 'Avg Confidence')}
          </h3>
          <div className="gov-metric-rows">
            <div className="gov-metric-row">
              <span className="gov-metric-label">{t('admin.governance.avgStrictConf', 'Strict Avg')}</span>
              <span className="gov-metric-value">{pct(rules?.avg_strict_confidence ?? 0)}</span>
            </div>
            <div className="gov-metric-row">
              <span className="gov-metric-label">{t('admin.governance.avgSoftConf', 'Soft Avg')}</span>
              <span className="gov-metric-value">{pct(rules?.avg_soft_confidence ?? 0)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Training Data Audit */}
      <div className="gov-section">
        <h3 className="gov-section-title">
          <span className="gov-icon">🧪</span>
          {t('admin.governance.trainingAudit', 'Training Data Audit')}
        </h3>
        {audit && (
          <>
            <div className="gov-kpi-grid">
              <div className="gov-kpi">
                <span className="gov-kpi-value">{audit.total_corrections}</span>
                <span className="gov-kpi-label">{t('admin.governance.totalCorrections', 'Total Corrections')}</span>
              </div>
              <div className="gov-kpi">
                <span className="gov-kpi-value trainable">{audit.trainable_count}</span>
                <span className="gov-kpi-label">{t('admin.governance.trainable', 'Trainable')}</span>
              </div>
              <div className="gov-kpi">
                <span className="gov-kpi-value excluded">{audit.excluded_count}</span>
                <span className="gov-kpi-label">{t('admin.governance.excluded', 'Excluded')}</span>
              </div>
              <div className="gov-kpi">
                <span className={`gov-kpi-value ${audit.ready_to_retrain ? 'ready' : 'not-ready'}`}>
                  {audit.ready_to_retrain ? '✓' : '✗'}
                </span>
                <span className="gov-kpi-label">{t('admin.governance.readyToRetrain', 'Ready to Retrain')}</span>
              </div>
            </div>

            {/* Source distribution bar */}
            <div className="gov-source-dist">
              <h4 className="gov-subtitle">{t('admin.governance.sourceDistribution', 'Source Distribution')}</h4>
              {Object.entries(audit.by_source).map(([source, data]) => (
                <div className="gov-source-row" key={source}>
                  <span className="gov-source-label">
                    <span className={`gov-source-dot ${audit.trainable_sources.includes(source) ? 'trainable' : 'excluded'}`} />
                    {source}
                  </span>
                  <div className="gov-source-bar-track">
                    <div
                      className={`gov-source-bar-fill ${audit.trainable_sources.includes(source) ? 'trainable' : 'excluded'}`}
                      style={{ width: `${data.ratio * 100}%` }}
                    />
                  </div>
                  <span className="gov-source-count">{data.count} ({pct(data.ratio)})</span>
                </div>
              ))}
            </div>

            <div className="gov-metric-rows" style={{ marginTop: '1rem' }}>
              <div className="gov-metric-row">
                <span className="gov-metric-label">{t('admin.governance.netTrainableRatio', 'Net Trainable Ratio')}</span>
                <span className="gov-metric-value highlight">{pct(audit.net_trainable_ratio)}</span>
              </div>
              <div className="gov-metric-row">
                <span className="gov-metric-label">{t('admin.governance.minSamples', 'Min Samples for Retrain')}</span>
                <span className="gov-metric-value">{audit.min_samples_for_retrain}</span>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Correction Source Breakdown (from governance metrics) */}
      {corrections && (
        <div className="gov-section">
          <h3 className="gov-section-title">
            <span className="gov-icon">📋</span>
            {t('admin.governance.correctionBreakdown', 'Correction Source Breakdown')}
          </h3>
          <div className="gov-metric-rows">
            <div className="gov-metric-row">
              <span className="gov-metric-label">human_verified</span>
              <span className="gov-metric-value">{corrections.human_verified_count}</span>
            </div>
            <div className="gov-metric-row">
              <span className="gov-metric-label">llm_consensus</span>
              <span className="gov-metric-value">{corrections.llm_consensus_count}</span>
            </div>
            <div className="gov-metric-row">
              <span className="gov-metric-label">llm_verified</span>
              <span className="gov-metric-value">{corrections.llm_verified_count}</span>
            </div>
            <div className="gov-metric-row">
              <span className="gov-metric-label">llm_unverified</span>
              <span className="gov-metric-value excluded-text">{corrections.llm_unverified_count}</span>
            </div>
            <div className="gov-metric-row">
              <span className="gov-metric-label">system_default</span>
              <span className="gov-metric-value excluded-text">{corrections.system_default_count}</span>
            </div>
            <div className="gov-metric-row">
              <span className="gov-metric-label">legacy_null</span>
              <span className="gov-metric-value">{corrections.legacy_null_count}</span>
            </div>
          </div>
        </div>
      )}

      {/* Lifecycle Actions */}
      <div className="gov-section">
        <h3 className="gov-section-title">
          <span className="gov-icon">⚙️</span>
          {t('admin.governance.lifecycleActions', 'Rule Lifecycle Actions')}
        </h3>
        <div className="gov-actions">
          <button
            type="button"
            className="gov-action-btn decay"
            onClick={handleDecay}
            disabled={decayLoading}
          >
            {decayLoading ? '⏳' : '📉'} {t('admin.governance.decayStale', 'Decay Stale Soft Rules')}
          </button>
          <button
            type="button"
            className="gov-action-btn archive"
            onClick={handleArchive}
            disabled={archiveLoading}
          >
            {archiveLoading ? '⏳' : '🗑️'} {t('admin.governance.archiveLowHit', 'Archive Low-Hit Rules')}
          </button>
        </div>
        {actionResult && <p className="gov-action-result">{actionResult}</p>}
      </div>
    </div>
  );
};

export default GovernancePanel;
