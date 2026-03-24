import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useConfirm } from '../../hooks/useConfirm';
import { useForm } from 'react-hook-form';
import { recurringService } from '../../services/recurringService';
import { loanService } from '../../services/loanService';
import Select from '../common/Select';
import '../transactions/RecurringTransactionEditor.css';

interface Loan {
  id: number;
  lender_name: string;
  property_address: string;
}

interface FormData {
  loan_id: number;
  monthly_interest: number;
  start_date: string;
  day_of_month: number;
  end_date?: string;
}

interface CreateLoanInterestModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

export const CreateLoanInterestModal: React.FC<CreateLoanInterestModalProps> = ({
  onClose,
  onSuccess,
}) => {
  const { t } = useTranslation();
  const { alert: showAlert } = useConfirm();
  const { register, handleSubmit, watch, formState: { errors } } = useForm<FormData>();
  const [loans, setLoans] = useState<Loan[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const loadLoans = async () => {
      try {
        const [loansData, propertiesRes] = await Promise.all([
          loanService.list(),
          import('../../services/propertyService').then(m => m.propertyService.getProperties(false)),
        ]);
        const propertyMap = new Map<string, string>();
        for (const p of propertiesRes.properties ?? propertiesRes) {
          propertyMap.set(String((p as any).id), (p as any).address ?? `Property ${(p as any).id}`);
        }
        const activeLoans = loansData
          .filter((loan: any) => loan.is_active)
          .map((loan: any) => ({
            id: loan.id,
            lender_name: loan.lender_name,
            property_address: propertyMap.get(loan.property_id) ?? `Property ${loan.property_id}`,
          }));
        setLoans(activeLoans);
      } catch (error) {
        console.error('Failed to load loans:', error);
      }
    };
    loadLoans();
  }, []);

  const onSubmit = async (data: FormData) => {
    try {
      setLoading(true);
      await recurringService.createLoanInterest({
        loan_id: data.loan_id,
        monthly_interest: data.monthly_interest,
        start_date: data.start_date,
        day_of_month: data.day_of_month,
        end_date: data.end_date || undefined,
      });
      onSuccess();
    } catch (error) {
      console.error('Failed to create loan interest:', error);
      await showAlert(t('recurring.errors.createFailed'), { variant: 'danger' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="recurring-editor-overlay" onClick={onClose}>
      <div className="recurring-editor" onClick={(e) => e.stopPropagation()}>
        <div className="recurring-editor-header">
          <h2>🏦 {t('recurring.create.loanInterest')}</h2>
          <button className="btn-close" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="recurring-editor-form">
          <div className="form-group">
            <label>{t('recurring.form.loan')}</label>
            <Select {...register('loan_id', { required: true, valueAsNumber: true })} value={watch('loan_id')?.toString() || ''}
              placeholder={t('recurring.form.selectLoan')}
              options={loans.map(loan => ({
                value: String(loan.id),
                label: `${loan.lender_name} - ${loan.property_address}`,
              }))} />
            {errors.loan_id && (
              <span className="field-error">{t('recurring.errors.loanRequired')}</span>
            )}
          </div>

          <div className="form-group">
            <label>{t('recurring.form.monthlyInterest')} (€)</label>
            <input
              type="number"
              step="0.01"
              {...register('monthly_interest', { required: true, min: 0 })}
            />
            {errors.monthly_interest && (
              <span className="field-error">{t('recurring.errors.amountRequired')}</span>
            )}
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>{t('recurring.form.startDate')}</label>
              <input type="date" {...register('start_date', { required: true })} />
              {errors.start_date && (
                <span className="field-error">{t('recurring.errors.dateRequired')}</span>
              )}
            </div>
            <div className="form-group">
              <label>{t('recurring.form.dayOfMonth')}</label>
              <input
                type="number"
                min="1"
                max="31"
                {...register('day_of_month', { required: true, min: 1, max: 31 })}
              />
            </div>
          </div>

          <div className="form-group">
            <label>{t('recurring.form.endDate')} ({t('common.optional')})</label>
            <input type="date" {...register('end_date')} />
          </div>

          <div className="form-actions">
            <div style={{ flex: 1 }} />
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onClose}
              disabled={loading}
            >
              {t('common.cancel')}
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading}
            >
              {loading ? t('common.saving') : t('common.create')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
