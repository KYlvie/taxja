import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useConfirm } from '../../hooks/useConfirm';
import { useForm } from 'react-hook-form';
import { recurringService } from '../../services/recurringService';
import { propertyService } from '../../services/propertyService';
import Select from '../common/Select';
import '../transactions/RecurringTransactionEditor.css';

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
  const { alert: showAlert } = useConfirm();
  const { register, handleSubmit, watch, formState: { errors } } = useForm<FormData>();
  const [properties, setProperties] = useState<Property[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const loadProperties = async () => {
      try {
        const response = await propertyService.getProperties(false);
        const activeProperties = response.properties
          .filter((p: any) => p.status === 'active')
          .map((p: any) => ({ id: p.id, address: p.address, status: p.status }));
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
      await showAlert(t('recurring.errors.createFailed'), { variant: 'danger' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="recurring-editor-overlay" onClick={onClose}>
      <div className="recurring-editor" onClick={(e) => e.stopPropagation()}>
        <div className="recurring-editor-header">
          <h2>💰 {t('recurring.create.rentalIncome')}</h2>
          <button className="btn-close" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="recurring-editor-form">
          <div className="form-group">
            <label>{t('recurring.form.property')}</label>
            <Select {...register('property_id', { required: true })} value={watch('property_id') || ''}
              placeholder={t('recurring.form.selectProperty')}
              options={properties.map(p => ({
                value: p.id,
                label: p.address,
              }))} />
            {errors.property_id && (
              <span className="field-error">{t('recurring.errors.propertyRequired')}</span>
            )}
          </div>

          <div className="form-group">
            <label>{t('recurring.form.monthlyRent')} (€)</label>
            <input
              type="number"
              step="0.01"
              {...register('monthly_rent', { required: true, min: 0 })}
            />
            {errors.monthly_rent && (
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
