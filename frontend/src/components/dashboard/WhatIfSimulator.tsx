import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useForm } from 'react-hook-form';
import { dashboardService } from '../../services/dashboardService';
import { getLocaleForLanguage } from '../../utils/locale';
import Select from '../common/Select';
import './WhatIfSimulator.css';

interface SimulationForm {
  changeType: 'add_income' | 'add_expense' | 'remove_expense';
  amount: number;
  description: string;
  category?: string;
}

interface SimulationResult {
  currentTax: number;
  simulatedTax: number;
  taxDifference: number;
  currentNetIncome: number;
  simulatedNetIncome: number;
  netIncomeDifference: number;
  explanation: string;
  classification?: {
    category: string;
    category_type: string;
    legal_basis: string;
    is_deductible?: boolean;
    vat_rate?: number | null;
    vat_note?: string | null;
    confidence: number;
    explanation: string;
    verified?: boolean;
    correction_note?: string | null;
  };
}

const WhatIfSimulator = () => {
  const { t, i18n } = useTranslation();
  const { register, handleSubmit, watch, formState: { errors } } = useForm<SimulationForm>();
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const changeType = watch('changeType', 'add_expense');

  const onSubmit = async (data: SimulationForm) => {
    setIsLoading(true);
    setError(null);
    try {
      const simulationResult = await dashboardService.simulateTax(data);
      setResult(simulationResult);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('dashboard.simulationError'));
    } finally {
      setIsLoading(false);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat(getLocaleForLanguage(i18n.language), {
      style: 'currency',
      currency: 'EUR',
    }).format(amount);
  };

  const formatDifference = (amount: number) => {
    const sign = amount > 0 ? '+' : '';
    return `${sign}${formatCurrency(amount)}`;
  };

  return (
    <div className="what-if-simulator">
      <h3>{t('dashboard.whatIfSimulator')}</h3>
      <p className="simulator-description">
        {t('dashboard.simulatorDescription')}
      </p>

      <form onSubmit={handleSubmit(onSubmit)} className="simulator-form">
        <div className="form-group">
          <label>{t('dashboard.changeType')}</label>
          <Select {...register('changeType', { required: true })} value={watch('changeType') || ''}
            options={[
              { value: 'add_expense', label: t('dashboard.addExpense') },
              { value: 'add_income', label: t('dashboard.addIncome') },
              { value: 'remove_expense', label: t('dashboard.removeExpense') },
            ]} />
        </div>

        <div className="form-group">
          <label>{t('dashboard.amount')}</label>
          <input
            type="number"
            step="0.01"
            {...register('amount', {
              required: t('dashboard.amountRequired'),
              min: { value: 0.01, message: t('dashboard.amountPositive') },
            })}
            placeholder="0.00"
          />
          {errors.amount && (
            <span className="error-message">{errors.amount.message}</span>
          )}
        </div>

        <div className="form-group">
          <label>{t('dashboard.description')}</label>
          <input
            type="text"
            {...register('description', {
              required: t('dashboard.descriptionRequired'),
            })}
            placeholder={t('dashboard.descriptionPlaceholder')}
          />
          {errors.description && (
            <span className="error-message">{errors.description.message}</span>
          )}
        </div>

        {(changeType === 'add_expense' || changeType === 'remove_expense') && (
          <div className="form-group">
            <label>{t('dashboard.category')}</label>
            <Select {...register('category')} value={watch('category') || ''}
              placeholder={t('dashboard.selectCategory')}
              options={[
                { value: 'office_supplies', label: t('transactions.categories.office_supplies') },
                { value: 'equipment', label: t('transactions.categories.equipment') },
                { value: 'travel', label: t('transactions.categories.travel') },
                { value: 'marketing', label: t('transactions.categories.marketing') },
                { value: 'maintenance', label: t('transactions.categories.maintenance') },
                { value: 'insurance', label: t('transactions.categories.insurance') },
              ]} />
          </div>
        )}

        <button type="submit" className="simulate-button" disabled={isLoading}>
          {isLoading ? t('common.loading') : t('dashboard.simulate')}
        </button>
      </form>

      {error && <div className="error-box">{error}</div>}

      {result && (
        <div className="simulation-result">
          <h4>{t('dashboard.simulationResult')}</h4>

          <div className="result-grid">
            <div className="result-card">
              <h5>{t('dashboard.taxImpact')}</h5>
              <div className="result-comparison">
                <div className="result-item">
                  <span className="result-label">{t('dashboard.currentTax')}:</span>
                  <span className="result-value">{formatCurrency(result.currentTax)}</span>
                </div>
                <div className="result-item">
                  <span className="result-label">{t('dashboard.simulatedTax')}:</span>
                  <span className="result-value">{formatCurrency(result.simulatedTax)}</span>
                </div>
                <div className="result-item difference">
                  <span className="result-label">{t('dashboard.difference')}:</span>
                  <span className={`result-value ${result.taxDifference > 0 ? 'negative' : 'positive'}`}>
                    {formatDifference(result.taxDifference)}
                  </span>
                </div>
              </div>
            </div>

            <div className="result-card">
              <h5>{t('dashboard.netIncomeImpact')}</h5>
              <div className="result-comparison">
                <div className="result-item">
                  <span className="result-label">{t('dashboard.currentNetIncome')}:</span>
                  <span className="result-value">{formatCurrency(result.currentNetIncome)}</span>
                </div>
                <div className="result-item">
                  <span className="result-label">{t('dashboard.simulatedNetIncome')}:</span>
                  <span className="result-value">{formatCurrency(result.simulatedNetIncome)}</span>
                </div>
                <div className="result-item difference">
                  <span className="result-label">{t('dashboard.difference')}:</span>
                  <span className={`result-value ${result.netIncomeDifference > 0 ? 'positive' : 'negative'}`}>
                    {formatDifference(result.netIncomeDifference)}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {result.classification && (
            <div className="classification-box">
              <h5>🤖 {t('dashboard.aiClassification')}
                {result.classification.verified && <span className="verified-badge"> ✓ {t('dashboard.verified')}</span>}
              </h5>
              <div className="classification-details">
                <div className="classification-row">
                  <span className="classification-label">{t('dashboard.classifiedCategory')}:</span>
                  <span className="classification-value category-badge">
                    {t(`transactions.categories.${result.classification.category}`, result.classification.category)}
                  </span>
                </div>
                <div className="classification-row">
                  <span className="classification-label">{t('dashboard.legalBasis')}:</span>
                  <span className="classification-value">{result.classification.legal_basis}</span>
                </div>
                {result.classification.vat_rate != null && (
                  <div className="classification-row">
                    <span className="classification-label">{t('dashboard.vatRate')}:</span>
                    <span className="classification-value">
                      {(result.classification.vat_rate * 100).toFixed(0)}%
                      {result.classification.vat_note && ` — ${result.classification.vat_note}`}
                    </span>
                  </div>
                )}
                {result.classification.is_deductible !== undefined && (
                  <div className="classification-row">
                    <span className="classification-label">{t('transactions.deductible')}:</span>
                    <span className="classification-value">
                      {result.classification.is_deductible ? '✓' : '✗'}
                    </span>
                  </div>
                )}
                <div className="classification-row">
                  <span className="classification-label">{t('documents.confidence')}:</span>
                  <span className="classification-value">
                    {(result.classification.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
              {result.classification.correction_note && (
                <p className="classification-correction">⚠ {result.classification.correction_note}</p>
              )}
              {result.classification.explanation && (
                <p className="classification-explanation">{result.classification.explanation}</p>
              )}
            </div>
          )}

          <div className="explanation-box">
            <h5>{t('dashboard.explanation')}</h5>
            <p>{result.explanation}</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default WhatIfSimulator;
