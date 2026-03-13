import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useForm } from 'react-hook-form';
import { RecurringTransaction } from '../../types/recurring';
import { recurringService } from '../../services/recurringService';

interface FormData {
  amount: number;
  end_date?: string;
  notes?: string;
}

interface EditRecurringModalProps {
  transaction: RecurringTransaction;
  onClose: () => void;
  onSuccess: () => void;
}

export const EditRecurringModal: React.FC<EditRecurringModalProps> = ({
  transaction,
  onClose,
  onSuccess,
}) => {
  const { t } = useTranslation();
  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    defaultValues: {
      amount: transaction.amount,
      end_date: transaction.end_date || '',
      notes: transaction.notes || '',
    },
  });
  const [loading, setLoading] = useState(false);

  const onSubmit = async (data: FormData) => {
    try {
      setLoading(true);
      await recurringService.update(transaction.id, {
        amount: data.amount,
        end_date: data.end_date || undefined,
        notes: data.notes || undefined,
      });
      onSuccess();
    } catch (error) {
      console.error('Failed to update recurring transaction:', error);
      alert(t('recurring.errors.updateFailed'));
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    if (window.confirm(t('recurring.confirmStop'))) {
      try {
        setLoading(true);
        await recurringService.stop(transaction.id);
        onSuccess();
      } catch (error) {
        console.error('Failed to stop recurring transaction:', error);
        alert(t('recurring.errors.stopFailed'));
      } finally {
        setLoading(false);
      }
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full">
        <h2 className="text-xl font-bold mb-4">{t('recurring.edit.title')}</h2>
        
        <div className="mb-4 p-3 bg-gray-100 rounded">
          <p className="text-sm text-gray-600">{transaction.description}</p>
          <p className="text-xs text-gray-500 mt-1">
            {t('recurring.frequency.label')}: {t(`recurring.frequency.${transaction.frequency}`)}
          </p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">
              {t('recurring.form.amount')}
            </label>
            <input
              type="number"
              step="0.01"
              {...register('amount', { required: true, min: 0 })}
              className="w-full border rounded px-3 py-2"
            />
            {errors.amount && (
              <span className="text-red-500 text-sm">{t('recurring.errors.amountRequired')}</span>
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
            <p className="text-xs text-gray-500 mt-1">
              {t('recurring.form.endDateHelp')}
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              {t('recurring.form.notes')} ({t('common.optional')})
            </label>
            <textarea
              {...register('notes')}
              rows={3}
              className="w-full border rounded px-3 py-2"
            />
          </div>

          <div className="flex gap-2 justify-between">
            <button
              type="button"
              onClick={handleStop}
              className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
              disabled={loading}
            >
              {t('recurring.actions.stop')}
            </button>
            
            <div className="flex gap-2">
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
                {loading ? t('common.saving') : t('common.save')}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
