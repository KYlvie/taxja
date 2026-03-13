import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useForm } from 'react-hook-form';
import { recurringService } from '../../services/recurringService';
import { propertyService } from '../../services/propertyService';

interface Property {
  id: string;
  address: string;
  status: string;
}

interface FormData {
  property_id: string;
  monthly_rent: number;
  start_date: string;
  day_of_month: number;
  end_date?: string;
}

interface CreateRentalIncomeModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

export const CreateRentalIncomeModal: React.FC<CreateRentalIncomeModalProps> = ({
  onClose,
  onSuccess,
}) => {
  const { t } = useTranslation();
  const { register, handleSubmit, formState: { errors } } = useForm<FormData>();
  const [properties, setProperties] = useState<Property[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const loadProperties = async () => {
      try {
        const response = await propertyService.getProperties(false);
        // Filter only active properties
        const activeProperties = response.properties
          .filter(p => p.status === 'active')
          .map(p => ({
            id: p.id,
            address: p.address,
            status: p.status,
          }));
        setProperties(activeProperties);
      } catch (error) {
        console.error('Failed to load properties:', error);
      }
    };

    loadProperties();
  }, []);

  const onSubmit = async (data: FormData) => {
    try {
      setLoading(true);
      await recurringService.createRentalIncome({
        property_id: data.property_id,
        monthly_rent: data.monthly_rent,
        start_date: data.start_date,
        day_of_month: data.day_of_month,
        end_date: data.end_date || undefined,
      });
      onSuccess();
    } catch (error) {
      console.error('Failed to create rental income:', error);
      alert(t('recurring.errors.createFailed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full">
        <h2 className="text-xl font-bold mb-4">{t('recurring.create.rentalIncome')}</h2>
        
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">
              {t('recurring.form.property')}
            </label>
            <select
              {...register('property_id', { required: true })}
              className="w-full border rounded px-3 py-2"
            >
              <option value="">{t('recurring.form.selectProperty')}</option>
              {properties.map(p => (
                <option key={p.id} value={p.id}>{p.address}</option>
              ))}
            </select>
            {errors.property_id && (
              <span className="text-red-500 text-sm">{t('recurring.errors.propertyRequired')}</span>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              {t('recurring.form.monthlyRent')}
            </label>
            <input
              type="number"
              step="0.01"
              {...register('monthly_rent', { required: true, min: 0 })}
              className="w-full border rounded px-3 py-2"
            />
            {errors.monthly_rent && (
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
              className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
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
