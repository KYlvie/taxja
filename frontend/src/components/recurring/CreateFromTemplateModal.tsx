import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useConfirm } from '../../hooks/useConfirm';
import { useForm } from 'react-hook-form';
import { RecurringTemplate } from '../../types/template';
import { templateService } from '../../services/templateService';

interface CreateFromTemplateModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

interface FormData {
  template_id: string;
  amount: number;
  start_date: string;
  end_date?: string;
  day_of_month?: number;
  notes?: string;
}

export const CreateFromTemplateModal: React.FC<CreateFromTemplateModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const { t, i18n } = useTranslation();
  const { alert: showAlert } = useConfirm();
  const [templates, setTemplates] = useState<RecurringTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<RecurringTemplate | null>(null);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState<'select' | 'details'>('select');

  const { register, handleSubmit, formState: { errors }, setValue } = useForm<FormData>({
    defaultValues: {
      start_date: new Date(new Date().setMonth(new Date().getMonth() + 1)).toISOString().split('T')[0],
    },
  });

  useEffect(() => {
    if (isOpen) {
      loadTemplates();
    }
  }, [isOpen]);

  const loadTemplates = async () => {
    try {
      const data = await templateService.getAllTemplates();
      setTemplates(data);
    } catch (error) {
      console.error('Failed to load templates:', error);
    }
  };

  const handleTemplateSelect = (template: RecurringTemplate) => {
    setSelectedTemplate(template);
    setValue('template_id', template.id);
    setValue('day_of_month', template.default_day_of_month);
    setStep('details');
  };

  const onSubmit = async (data: FormData) => {
    try {
      setLoading(true);
      await templateService.createFromTemplate(data);
      onSuccess();
      onClose();
      resetModal();
    } catch (error) {
      console.error('Failed to create from template:', error);
      await showAlert(t('recurring.errors.createFailed'), { variant: 'danger' });
    } finally {
      setLoading(false);
    }
  };

  const resetModal = () => {
    setStep('select');
    setSelectedTemplate(null);
  };

  const handleClose = () => {
    onClose();
    resetModal();
  };

  const getTemplateName = (template: RecurringTemplate) => {
    switch (i18n.language) {
      case 'de': return template.name_de;
      case 'zh': return template.name_zh;
      default: return template.name_en;
    }
  };

  const getTemplateDescription = (template: RecurringTemplate) => {
    switch (i18n.language) {
      case 'de': return template.description_de;
      case 'zh': return template.description_zh;
      default: return template.description_en;
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {step === 'select' ? (
          <>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">{t('recurring.template.selectTitle')}</h2>
              <button onClick={handleClose} className="text-gray-500 hover:text-gray-700">
                ✕
              </button>
            </div>

            <p className="text-sm text-gray-600 mb-4">
              {t('recurring.template.selectDescription')}
            </p>

            <div className="space-y-2">
              {templates.map((template) => (
                <button
                  key={template.id}
                  onClick={() => handleTemplateSelect(template)}
                  className="w-full text-left p-4 border rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-start gap-3">
                    <span className="text-2xl">{template.icon}</span>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className="font-medium">{getTemplateName(template)}</h3>
                        {template.priority >= 90 && (
                          <span className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded">
                            {t('recurring.template.recommended')}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-600 mt-1">
                        {getTemplateDescription(template)}
                      </p>
                      <div className="flex gap-3 mt-2 text-xs text-gray-500">
                        <span>📅 {t(`recurring.frequency.${template.frequency}`)}</span>
                        <span>📂 {template.category}</span>
                      </div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </>
        ) : (
          <>
            <div className="flex justify-between items-center mb-4">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setStep('select')}
                  className="text-gray-500 hover:text-gray-700"
                >
                  ← {t('common.back')}
                </button>
                <h2 className="text-xl font-semibold">
                  {selectedTemplate?.icon} {getTemplateName(selectedTemplate!)}
                </h2>
              </div>
              <button onClick={handleClose} className="text-gray-500 hover:text-gray-700">
                ✕
              </button>
            </div>

            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('recurring.form.amount')} *
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-2 text-gray-500">€</span>
                  <input
                    type="number"
                    step="0.01"
                    {...register('amount', { required: true, min: 0.01 })}
                    className="w-full border rounded px-3 py-2 pl-7"
                    placeholder="1000.00"
                  />
                </div>
                {errors.amount && (
                  <span className="text-red-500 text-xs">{t('recurring.errors.amountRequired')}</span>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('recurring.form.startDate')} *
                  </label>
                  <input
                    type="date"
                    {...register('start_date', { required: true })}
                    className="w-full border rounded px-3 py-2"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('recurring.form.dayOfMonth')}
                  </label>
                  <select
                    {...register('day_of_month')}
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
                  {t('recurring.form.endDate')} ({t('common.optional')})
                </label>
                <input
                  type="date"
                  {...register('end_date')}
                  className="w-full border rounded px-3 py-2"
                />
                <p className="text-xs text-gray-500 mt-1">
                  {t('recurring.form.endDateHint')}
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('recurring.form.notes')} ({t('common.optional')})
                </label>
                <textarea
                  {...register('notes')}
                  className="w-full border rounded px-3 py-2"
                  rows={3}
                  placeholder={t('recurring.form.notesPlaceholder')}
                />
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded p-3 text-sm">
                <p className="text-blue-900">
                  <strong>{t('recurring.template.summary')}:</strong>
                </p>
                <ul className="mt-2 space-y-1 text-blue-800">
                  <li>📅 {t(`recurring.frequency.${selectedTemplate?.frequency}`)}</li>
                  <li>📂 {selectedTemplate?.category}</li>
                  <li>💰 {selectedTemplate?.transaction_type === 'expense' ? t('recurring.type.expense') : t('recurring.type.income')}</li>
                </ul>
              </div>

              <div className="flex gap-2 justify-end pt-4">
                <button
                  type="button"
                  onClick={handleClose}
                  className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded"
                  disabled={loading}
                >
                  {t('common.cancel')}
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                  disabled={loading}
                >
                  {loading ? t('common.saving') : t('recurring.create')}
                </button>
              </div>
            </form>
          </>
        )}
      </div>
    </div>
  );
};
