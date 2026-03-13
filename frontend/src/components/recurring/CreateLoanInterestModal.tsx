import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useForm } from 'react-hook-form';
import { recurringService } from '../../services/recurringService';
import { loanService } from '../../services/loanService';

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
  const { register, handleSubmit, formState: { errors } } = useForm<FormData>();
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
          .filter(loan => loan.is_active)
          .map(loan => ({
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
      alert(t('recurring.errors.createFailed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full">
        <h2 className="text-xl font-bold mb-4">{t('recurring.create.loanInterest')}</h2>
        
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">
              {t('recurring.form.loan')}
            </label>
            <select
              {...register('loan_id', { required: true, valueAsNumber: true })}
              className="w-full border rounded px-3 py-2"
            >
              <option value="">{t('recurring.form.selectLoan')}</option>
              {loans.map(loan => (
                <option key={loan.id} value={loan.id}>
                  {loan.lender_name} - {loan.property_address}
                </option>
              ))}
            </select>
            {errors.loan_id && (
              <span className="text-red-500 text-sm">{t('recurring.errors.loanRequired')}</span>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              {t('recurring.form.monthlyInterest')}
            </label>
            <input
              type="number"
              step="0.01"
              {...register('monthly_interest', { required: true, min: 0 })}
              className="w-full border rounded px-3 py-2"
            />
            {errors.monthly_interest && (
              <span className="text-red-500 text-sm">{t('recurring.errors.amountRequired')}</span>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              {t('recurring.form.startDate')}
            </label>
            <input
              type="date"
              {...register('start_date', { required: true })}
              className="w-full border rounded px-3 py-2"
            />
            {errors.start_date && (
              <span className="text-red-500 text-sm">{t('recurring.errors.dateRequired')}</span>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              {t('recurring.form.dayOfMonth')}
            </label>
            <input
              type="number"
              min="1"
              max="31"
              {...register('day_of_month', { required: true, min: 1, max: 31 })}
              className="w-full border rounded px-3 py-2"
            />
            {errors.day_of_month && (
              <span className="text-red-500 text-sm">{t('recurring.errors.dayRequired')}</span>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              {t('recurring.form.endDate')} ({t('common.optional')})
            </label>
            <input
              type="date"
              {...register('end_date')}
              className="w-full border rounded px-3 py-2"
            />
          </div>

          <div className="flex gap-2 justify-end">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border rounded hover:bg-gray-100"
              disabled={loading}
            >
              {t('common.cancel')}
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
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
