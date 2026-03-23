import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useConfirm } from '../../hooks/useConfirm';
import { useForm } from 'react-hook-form';
import { recurringService } from '../../services/recurringService';
import Select from '../common/Select';

interface QuickSetupLoanInterestProps {
  loanId: number;
  lenderName: string;
  onSuccess: () => void;
  onCancel: () => void;
}

interface FormData {
  monthly_interest: number;
  day_of_month: number;
  start_date: string;
}

export const QuickSetupLoanInterest: React.FC<QuickSetupLoanInterestProps> = ({
  loanId,
  lenderName: _lenderName,
  onSuccess,
  onCancel,
}) => {
  const { t } = useTranslation();
  const { alert: showAlert } = useConfirm();
  const { register, handleSubmit, watch, formState: { errors } } = useForm<FormData>({
    defaultValues: {
      day_of_month: 15,
      start_date: new Date(new Date().setMonth(new Date().getMonth() + 1)).toISOString().split('T')[0],
    },
  });
  const [loading, setLoading] = useState(false);

  const onSubmit = async (data: FormData) => {
    try {
      setLoading(true);
      await recurringService.createLoanInterest({
        loan_id: loanId,
        monthly_interest: data.monthly_interest,
        start_date: data.start_date,
        day_of_month: data.day_of_month,
      });
      onSuccess();
    } catch (error) {
      console.error('Failed to setup loan interest:', error);
      await showAlert(t('recurring.errors.createFailed'), { variant: 'danger' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-orange-50 border border-orange-200 rounded-lg p-4 mb-4">
      <div className="flex items-start gap-3">
        <span className="text-2xl">💡</span>
        <div className="flex-1">
          <h3 className="font-semibold text-orange-900 mb-2">
            {t('recurring.quickSetup.loanInterest.title')}
          </h3>
          <p className="text-sm text-orange-700 mb-3">
            {t('recurring.quickSetup.loanInterest.description')}
          </p>
          
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('recurring.form.monthlyInterest')}
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-2 text-gray-500">€</span>
                  <input
                    type="number"
                    step="0.01"
                    {...register('monthly_interest', { required: true, min: 0 })}
                    className="w-full border rounded px-3 py-2 pl-7"
                    placeholder="450.00"
                  />
                </div>
                {errors.monthly_interest && (
                  <span className="text-red-500 text-xs">{t('recurring.errors.amountRequired')}</span>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('recurring.quickSetup.paymentDay')}
                </label>
                <Select
                  {...register('day_of_month', { required: true })}
                  value={watch('day_of_month')?.toString() || ''}
                  className="w-full border rounded px-3 py-2"
                  options={Array.from({ length: 28 }, (_, i) => i + 1).map(day => ({
                    value: String(day),
                    label: `${day}. ${t('recurring.quickSetup.dayOfMonthSuffix')}`,
                  }))} />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t('recurring.quickSetup.startDate')}
              </label>
              <input
                type="date"
                {...register('start_date', { required: true })}
                className="w-full border rounded px-3 py-2"
              />
            </div>

            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={onCancel}
                className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded"
                disabled={loading}
              >
                {t('recurring.quickSetup.skip')}
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-orange-600 text-white rounded hover:bg-orange-700"
                disabled={loading}
              >
                {loading ? t('common.saving') : t('recurring.quickSetup.enable')}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};
