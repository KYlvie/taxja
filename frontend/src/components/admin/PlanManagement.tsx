import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { getLocaleForLanguage } from '../../utils/locale';
import './PlanManagement.css';

interface Plan {
  id: number;
  plan_type: string;
  name: string;
  monthly_price: number;
  yearly_price: number;
  features: Record<string, boolean>;
  quotas: Record<string, number>;
}

const PlanManagement: React.FC = () => {
  const { t, i18n } = useTranslation();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [editingPlan, setEditingPlan] = useState<Plan | null>(null);
  const [loading, setLoading] = useState(true);
  const locale = getLocaleForLanguage(i18n.resolvedLanguage || i18n.language);

  useEffect(() => {
    fetchPlans();
  }, []);

  const fetchPlans = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/v1/subscriptions/plans');
      const data = await response.json();
      setPlans(data);
    } catch (error) {
      console.error('Failed to fetch plans:', error);
    } finally {
      setLoading(false);
    }
  };

  const getPlanLabel = (planType: string, fallbackName: string) => {
    const key = `pricing.plans.${planType}.name`;
    const label = t(key);
    return label === key ? fallbackName : label;
  };

  const formatCurrency = (value: number) =>
    new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);

  const translateFeature = (featureKey: string) => {
    const key = `pricing.features.${featureKey}`;
    const label = t(key);
    return label === key ? featureKey : label;
  };

  const translateQuota = (quotaKey: string) => {
    const key = `admin.plans.quotas_labels.${quotaKey}`;
    const label = t(key);
    return label === key ? quotaKey : label;
  };

  const handleEdit = (plan: Plan) => {
    setEditingPlan({ ...plan });
  };

  const handleSave = async () => {
    if (!editingPlan) return;

    try {
      await fetch(`/api/v1/admin/plans/${editingPlan.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: editingPlan.name,
          monthly_price: editingPlan.monthly_price,
          yearly_price: editingPlan.yearly_price,
          features: editingPlan.features,
          quotas: editingPlan.quotas,
        }),
      });

      fetchPlans();
      setEditingPlan(null);
    } catch (error) {
      console.error('Failed to update plan:', error);
    }
  };

  const handleCancel = () => {
    setEditingPlan(null);
  };

  const updateFeature = (key: string, value: boolean) => {
    if (!editingPlan) return;
    setEditingPlan({
      ...editingPlan,
      features: { ...editingPlan.features, [key]: value },
    });
  };

  const updateQuota = (key: string, value: number) => {
    if (!editingPlan) return;
    setEditingPlan({
      ...editingPlan,
      quotas: { ...editingPlan.quotas, [key]: value },
    });
  };

  if (loading) {
    return <div className="loading">{t('common.loading')}</div>;
  }

  return (
    <div className="plan-management">
      <h2>{t('admin.plans.title')}</h2>

      <div className="plans-grid">
        {plans.map((plan) => (
          <div key={plan.id} className="plan-card">
            <div className="plan-header">
              <h3>{getPlanLabel(plan.plan_type, plan.name)}</h3>
              <span className={`plan-type ${plan.plan_type}`}>
                {getPlanLabel(plan.plan_type, plan.plan_type)}
              </span>
            </div>

            <div className="plan-pricing">
              <div className="price-item">
                <span>{t('admin.plans.monthly')}</span>
                <strong>{formatCurrency(plan.monthly_price)}</strong>
              </div>
              <div className="price-item">
                <span>{t('admin.plans.yearly')}</span>
                <strong>{formatCurrency(plan.yearly_price)}</strong>
              </div>
            </div>

            <div className="plan-features">
              <h4>{t('admin.plans.features')}</h4>
              <ul>
                {Object.entries(plan.features).map(([key, value]) => (
                  <li key={key} className={value ? 'enabled' : 'disabled'}>
                    {value ? '✓' : '✕'} {translateFeature(key)}
                  </li>
                ))}
              </ul>
            </div>

            <div className="plan-quotas">
              <h4>{t('admin.plans.quotas')}</h4>
              <ul>
                {Object.entries(plan.quotas).map(([key, value]) => (
                  <li key={key}>
                    {translateQuota(key)}: {value === -1 ? t('admin.plans.unlimited') : value}
                  </li>
                ))}
              </ul>
            </div>

            <button type="button" onClick={() => handleEdit(plan)} className="btn-edit">
              {t('admin.actions.edit')}
            </button>
          </div>
        ))}
      </div>

      {editingPlan && (
        <div className="modal-overlay" onClick={handleCancel}>
          <div className="modal-content" onClick={(event) => event.stopPropagation()}>
            <h3>
              {t('admin.plans.edit_plan')}: {getPlanLabel(editingPlan.plan_type, editingPlan.name)}
            </h3>

            <div className="form-group">
              <label>{t('admin.plans.name')}</label>
              <input
                type="text"
                value={editingPlan.name}
                onChange={(event) =>
                  setEditingPlan({ ...editingPlan, name: event.target.value })
                }
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>{t('admin.plans.monthly_price')}</label>
                <input
                  type="number"
                  step="0.01"
                  value={editingPlan.monthly_price}
                  onChange={(event) =>
                    setEditingPlan({
                      ...editingPlan,
                      monthly_price: parseFloat(event.target.value),
                    })
                  }
                />
              </div>
              <div className="form-group">
                <label>{t('admin.plans.yearly_price')}</label>
                <input
                  type="number"
                  step="0.01"
                  value={editingPlan.yearly_price}
                  onChange={(event) =>
                    setEditingPlan({
                      ...editingPlan,
                      yearly_price: parseFloat(event.target.value),
                    })
                  }
                />
              </div>
            </div>

            <div className="form-group">
              <label>{t('admin.plans.features')}</label>
              {Object.entries(editingPlan.features).map(([key, value]) => (
                <div key={key} className="checkbox-item">
                  <input
                    type="checkbox"
                    checked={value}
                    onChange={(event) => updateFeature(key, event.target.checked)}
                  />
                  <span>{translateFeature(key)}</span>
                </div>
              ))}
            </div>

            <div className="form-group">
              <label>{t('admin.plans.quotas')}</label>
              {Object.entries(editingPlan.quotas).map(([key, value]) => (
                <div key={key} className="quota-item">
                  <span>{translateQuota(key)}</span>
                  <input
                    type="number"
                    value={value}
                    onChange={(event) => updateQuota(key, parseInt(event.target.value, 10))}
                  />
                </div>
              ))}
            </div>

            <div className="modal-actions">
              <button type="button" onClick={handleCancel} className="btn-cancel">
                {t('common.cancel')}
              </button>
              <button type="button" onClick={handleSave} className="btn-save">
                {t('common.save')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PlanManagement;
