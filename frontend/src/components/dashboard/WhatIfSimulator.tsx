import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useForm } from 'react-hook-form';
import { MessageCircle } from 'lucide-react';
import { dashboardService } from '../../services/dashboardService';
import { aiService } from '../../services/aiService';
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
}

const WhatIfSimulator = () => {
  const { t } = useTranslation();
  const { register, handleSubmit, watch, formState: { errors } } = useForm<SimulationForm>();
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aiSuggestions, setAISuggestions] = useState<string | null>(null);
  const [loadingAI, setLoadingAI] = useState(false);

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
    return new Intl.NumberFormat('de-AT', {
      style: 'currency',
      currency: 'EUR',
    }).format(amount);
  };

  const formatDifference = (amount: number) => {
    const sign = amount > 0 ? '+' : '';
    return `${sign}${formatCurrency(amount)}`;
  };

  const handleAskAI = async () => {
    try {
      setLoadingAI(true);
      setAISuggestions(null);
      const response = await aiService.askForSuggestions({
        currentTax: result?.currentTax,
        currentNetIncome: result?.currentNetIncome,
        simulationResult: result,
      });
      setAISuggestions(response.content);
    } catch (err: any) {
      console.error('Failed to get AI suggestions:', err);
      const status = err?.response?.status;
      if (status === 503 || status === 500) {
        setAISuggestions(t('ai.serviceUnavailable', 'AI-Dienst ist derzeit nicht verf\u00fcgbar. Bitte versuchen Sie es sp\u00e4ter erneut.'));
      } else {
        setAISuggestions(t('ai.suggestionError', 'Vorschl\u00e4ge konnten nicht geladen werden.'));
      }
    } finally {
      setLoadingAI(false);
    }
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
          <select {...register('changeType', { required: true })}>
            <option value="add_expense">
              {t('dashboard.addExpense')}
            </option>
            <option value="add_income">
              {t('dashboard.addIncome')}
            </option>
            <option value="remove_expense">
              {t('dashboard.removeExpense')}
            </option>
          </select>
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
            <select {...register('category')}>
              <option value="">{t('dashboard.selectCategory')}</option>
              <option value="office_supplies">
                {t('transactions.categories.office_supplies')}
              </option>
              <option value="equipment">{t('transactions.categories.equipment')}</option>
              <option value="travel">{t('transactions.categories.travel')}</option>
              <option value="marketing">{t('transactions.categories.marketing')}</option>
              <option value="maintenance">{t('transactions.categories.maintenance')}</option>
              <option value="insurance">{t('transactions.categories.insurance')}</option>
            </select>
          </div>
        )}

        <button
          type="submit"
          className="simulate-button"
          disabled={isLoading}
        >
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
                  <span className="result-label">
                    {t('dashboard.currentTax')}:
                  </span>
                  <span className="result-value">
                    {formatCurrency(result.currentTax)}
                  </span>
                </div>
                <div className="result-item">
                  <span className="result-label">
                    {t('dashboard.simulatedTax')}:
                  </span>
                  <span className="result-value">
                    {formatCurrency(result.simulatedTax)}
                  </span>
                </div>
                <div className="result-item difference">
                  <span className="result-label">
                    {t('dashboard.difference')}:
                  </span>
                  <span
                    className={`result-value ${
                      result.taxDifference > 0 ? 'negative' : 'positive'
                    }`}
                  >
                    {formatDifference(result.taxDifference)}
                  </span>
                </div>
              </div>
            </div>

            <div className="result-card">
              <h5>{t('dashboard.netIncomeImpact')}</h5>
              <div className="result-comparison">
                <div className="result-item">
                  <span className="result-label">
                    {t('dashboard.currentNetIncome')}:
                  </span>
                  <span className="result-value">
                    {formatCurrency(result.currentNetIncome)}
                  </span>
                </div>
                <div className="result-item">
                  <span className="result-label">
                    {t('dashboard.simulatedNetIncome')}:
                  </span>
                  <span className="result-value">
                    {formatCurrency(result.simulatedNetIncome)}
                  </span>
                </div>
                <div className="result-item difference">
                  <span className="result-label">
                    {t('dashboard.difference')}:
                  </span>
                  <span
                    className={`result-value ${
                      result.netIncomeDifference > 0 ? 'positive' : 'negative'
                    }`}
                  >
                    {formatDifference(result.netIncomeDifference)}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="explanation-box">
            <h5>{t('dashboard.explanation')}</h5>
            <p>{result.explanation}</p>
          </div>

          <div className="ai-suggestions-section">
            <button
              className="btn btn-ai"
              onClick={handleAskAI}
              disabled={loadingAI}
            >
              <MessageCircle size={18} />
              {loadingAI ? t('ai.loading') : t('ai.askForSuggestions')}
            </button>
            {aiSuggestions && (
              <div className="ai-suggestions-box">
                <h5>{t('ai.suggestions')}</h5>
                <p>{aiSuggestions}</p>
              </div>
            )}
          </div>
        </div>
      )}

    </div>
  );
};

export default WhatIfSimulator;
