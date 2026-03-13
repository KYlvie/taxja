import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useForm } from 'react-hook-form';
import { recurringService } from '../../services/recurringService';

interface QuickSetupRentalIncomeProps {
  propertyId: string;
  propertyAddress: string;
  onSuccess: () => void;
  onCancel: () => void;
}

interface FormData {
  monthly_rent: number;
  day_of_month: number;
  start_date: string;
}

export const QuickSetupRentalIncome: React.FC<QuickSetupRentalIncomeProps> = ({
  propertyId,
  propertyAddress: _propertyAddress,
  onSuccess,
  onCancel,
}) => {
  const { t } = useTranslation();
  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    defaultValues: {
      day_of_month: 1,
      start_date: new Date(new Date().setMonth(new Date().getMonth() + 1)).toISOString().split('T')[0],
    },
  });
  const [loading, setLoading] = useState(false);

  const onSubmit = async (data: FormData) => {
    try {
      setLoading(true);
      await recurringService.createRentalIncome({
        property_id: propertyId,
        monthly_rent: data.monthly_rent,
        start_date: data.start_date,
        day_of_month: data.day_of_month,
      });
      onSuccess();
    } catch (error) {
      console.error('Failed to setup rental income:', error);
      alert(t('recurring.errors.createFailed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
      <div className="flex items-start gap-3">
        <span className="text-2xl">💡</span>
        <div className="flex-1">
          <h3 className="font-semibold text-blue-900 mb-2">
            {t('recurring.quickSetup.rentalIncome.title')}
          </h3>
          <p className="text-sm text-blue-700 mb-3">
            {t('recurring.quickSetup.rentalIncome.description')}
          </p>
          
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('recurring.form.monthlyRent')}
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-2 text-gray-500">€</span>
                  <input
                    type="number"
                    step="0.01"
                    {...register('monthly_rent', { required: true, min: 0 })}
                    className="w-full border rounded px-3 py-2 pl-7"
                    placeholder="1200.00"
                  />
                </div>
                {errors.monthly_rent && (
                  <span className="text-red-500 text-xs">{t('recurring.errors.amountRequired')}</span>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('recurring.quickSetup.dayOfMonth')}
                </label>
                <select
                  {...register('day_of_month', { required: true })}
                  className="w-full border rounded px-3 py-2"
                >
                  {Array.from({ length: 28 }, (_, i) => i + 1).map(day => (
                    <option key={day} value={day}>
                      {day}. {t('recurring.quickSetup.dayOfMonthSuffix')}
                    </option>
                  ))}
                </select>
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
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
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
