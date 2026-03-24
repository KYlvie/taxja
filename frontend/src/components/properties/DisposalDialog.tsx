import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Property, DisposalRequest, DisposalReason } from '../../types/property';
import DateInput from '../common/DateInput';
import { getLocaleForLanguage } from '../../utils/locale';
import './DisposalDialog.css';

interface DisposalDialogProps {
  open: boolean;
  property: Property;
  onClose: () => void;
  onConfirm: (data: DisposalRequest) => Promise<void>;
}

const DisposalDialog = ({ open, property, onClose, onConfirm }: DisposalDialogProps) => {
  const { t, i18n } = useTranslation();
  const isRealEstate = !property.asset_type || property.asset_type === 'real_estate';

  const [disposalReason, setDisposalReason] = useState<DisposalReason>('sold');
  const [disposalDate, setDisposalDate] = useState(new Date().toISOString().split('T')[0]);
  const [salePrice, setSalePrice] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!open) return null;

  const showPriceField = isRealEstate || disposalReason === 'sold';

  const handleSubmit = async () => {
    setError('');

    if (!disposalDate) {
      setError(t('properties.disposalDate') + ' is required');
      return;
    }

    if (showPriceField && (!salePrice || Number(salePrice) < 0)) {
      setError(t('properties.salePriceRequired'));
      return;
    }

    const data: DisposalRequest = {
      disposal_reason: isRealEstate ? 'sold' : disposalReason,
      disposal_date: disposalDate,
    };

    if (showPriceField && salePrice) {
      data.sale_price = Number(salePrice);
    }

    setIsSubmitting(true);
    try {
      await onConfirm(data);
    } catch {
      setError(t('properties.disposalError'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const disposalReasons: { value: DisposalReason; labelKey: string }[] = [
    { value: 'sold', labelKey: 'properties.disposalReasons.sold' },
    { value: 'scrapped', labelKey: 'properties.disposalReasons.scrapped' },
    { value: 'fully_depreciated', labelKey: 'properties.disposalReasons.fully_depreciated' },
    { value: 'private_withdrawal', labelKey: 'properties.disposalReasons.private_withdrawal' },
  ];

  return (
    <div className="cfd-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="disposal-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="disposal-dialog-header">
          <h2>{isRealEstate ? t('properties.sellProperty') : t('properties.disposeAsset')}</h2>
          <span className="disposal-dialog-property-name">
            {isRealEstate ? property.address : (property.name || property.address)}
          </span>
        </div>

        <div className="disposal-dialog-body">
          {/* Disposal reason radio buttons (non-real-estate only) */}
          {!isRealEstate && (
            <div className="disposal-field">
              <label className="disposal-label">{t('properties.disposalReason')}</label>
              <div className="disposal-reasons">
                {disposalReasons.map((reason) => (
                  <label key={reason.value} className="disposal-reason-option">
                    <input
                      type="radio"
                      name="disposal_reason"
                      value={reason.value}
                      checked={disposalReason === reason.value}
                      onChange={() => setDisposalReason(reason.value)}
                    />
                    <span>{t(reason.labelKey)}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Disposal date */}
          <div className="disposal-field">
            <label className="disposal-label" htmlFor="disposal-date">
              {t('properties.disposalDate')}
            </label>
            <DateInput
              id="disposal-date"
              className="disposal-input"
              value={disposalDate}
              onChange={(val) => setDisposalDate(val)}
              locale={getLocaleForLanguage(i18n.language)}
              todayLabel={String(t('common.today', 'Today'))}
            />
          </div>

          {/* Sale price (real estate always, other assets only when sold) */}
          {showPriceField && (
            <div className="disposal-field">
              <label className="disposal-label" htmlFor="sale-price">
                {t('properties.salePrice')}
              </label>
              <input
                id="sale-price"
                type="number"
                className="disposal-input"
                min="0"
                step="0.01"
                value={salePrice}
                onChange={(e) => setSalePrice(e.target.value)}
                placeholder="0.00"
              />
              <span className="disposal-hint">{t('properties.salePriceHint')}</span>
            </div>
          )}

          {error && <div className="disposal-error">{error}</div>}
        </div>

        <div className="disposal-dialog-footer">
          <button
            className="cfd-btn cfd-btn--cancel"
            onClick={onClose}
            disabled={isSubmitting}
          >
            {t('common.cancel')}
          </button>
          <button
            className="cfd-btn cfd-btn--warning"
            onClick={handleSubmit}
            disabled={isSubmitting}
          >
            {isSubmitting
              ? t('common.loading')
              : isRealEstate
                ? t('properties.confirmSale')
                : t('properties.confirmDisposal')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default DisposalDialog;
