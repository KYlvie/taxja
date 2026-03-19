import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import api from '../../services/api';
import { aiToast } from '../../stores/aiToastStore';
import './ClassificationRules.css';

interface ClassificationRule {
  id: number;
  normalized_description: string;
  original_description: string | null;
  txn_type: string;
  category: string;
  hit_count: number;
  confidence: number;
  rule_type: string;
  frozen: boolean;
  conflict_count: number;
  last_hit_at: string | null;
  created_at: string | null;
}

const ClassificationRules = () => {
  const { t } = useTranslation();
  const [rules, setRules] = useState<ClassificationRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<number | null>(null);

  useEffect(() => { fetchRules(); }, []);

  const fetchRules = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get('/classification-rules/');
      setRules(res.data);
    } catch {
      setError(t('classificationRules.fetchError', 'Failed to load rules'));
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (ruleId: number) => {
    if (!confirm(t('classificationRules.confirmDelete', 'Delete this rule?'))) return;
    setDeleting(ruleId);
    try {
      await api.delete(`/classification-rules/${ruleId}`);
      setRules(prev => prev.filter(r => r.id !== ruleId));
      aiToast(t('classificationRules.deleteSuccess', 'Rule deleted'), 'success');
    } catch {
      const msg = t('classificationRules.deleteError', 'Failed to delete rule');
      setError(msg);
      aiToast(msg, 'error');
    } finally {
      setDeleting(null);
    }
  };

  if (loading) return <div className="cr-loading">{t('common.loading')}</div>;
  if (error) return (
    <div className="cr-error">
      <p>{error}</p>
      <button type="button" onClick={fetchRules}>{t('common.retry')}</button>
    </div>
  );

  if (rules.length === 0) {
    return (
      <div className="cr-empty">
        <p>{t('classificationRules.empty', 'No classification rules yet. Rules are created automatically when you correct a transaction category.')}</p>
      </div>
    );
  }

  return (
    <div className="classification-rules">
      <div className="cr-header">
        <h3>{t('classificationRules.title', 'My Classification Rules')}</h3>
        <span className="cr-count">{rules.length} {t('classificationRules.rules', 'rules')}</span>
      </div>
      <div className="cr-table-wrap">
        <table className="cr-table">
          <thead>
            <tr>
              <th>{t('classificationRules.description', 'Description')}</th>
              <th>{t('classificationRules.type', 'Type')}</th>
              <th>{t('classificationRules.category', 'Category')}</th>
              <th>{t('classificationRules.ruleType', 'Rule')}</th>
              <th>{t('classificationRules.hits', 'Hits')}</th>
              <th>{t('classificationRules.confidence', 'Conf.')}</th>
              <th>{t('classificationRules.status', 'Status')}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rules.map(rule => (
              <tr key={rule.id} className={rule.frozen ? 'frozen-row' : ''}>
                <td className="cr-desc" title={rule.original_description || rule.normalized_description}>
                  {rule.original_description || rule.normalized_description}
                </td>
                <td>
                  <span className={`cr-type-badge ${rule.txn_type}`}>
                    {t(`transactions.types.${rule.txn_type}`, rule.txn_type)}
                  </span>
                </td>
                <td>
                  <span className="cr-category">
                    {t(`transactions.categories.${rule.category}`, rule.category)}
                  </span>
                </td>
                <td>
                  <span className={`cr-rule-type ${rule.rule_type}`}>
                    {rule.rule_type === 'strict' ? '🔒' : '🔓'} {rule.rule_type}
                  </span>
                </td>
                <td className="cr-center">{rule.hit_count}</td>
                <td className="cr-center">{(rule.confidence * 100).toFixed(0)}%</td>
                <td>
                  {rule.frozen && <span className="cr-badge frozen">❄️ {t('classificationRules.frozen', 'Frozen')}</span>}
                  {rule.conflict_count > 0 && !rule.frozen && (
                    <span className="cr-badge conflict">⚠️ {rule.conflict_count}</span>
                  )}
                  {!rule.frozen && rule.conflict_count === 0 && (
                    <span className="cr-badge active">✓</span>
                  )}
                </td>
                <td>
                  <button
                    type="button"
                    className="cr-delete-btn"
                    onClick={() => handleDelete(rule.id)}
                    disabled={deleting === rule.id}
                    title={t('classificationRules.delete', 'Delete')}
                  >
                    {deleting === rule.id ? '⏳' : '🗑️'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default ClassificationRules;
