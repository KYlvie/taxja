import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { Property, PropertyType, PropertyFormData } from '../../types/property';
import './PropertyForm.css';

// Zod validation schema matching backend validation rules
const propertySchema = z.object({
  property_type: z.nativeEnum(PropertyType),
  rental_percentage: z.string().optional(),
  street: z.string().min(1, 'Street is required'),
  city: z.string().min(1, 'City is required'),
  postal_code: z.string().min(1, 'Postal code is required'),
  purchase_date: z.string().min(1, 'Purchase date is required'),
  purchase_price: z.string().min(1, 'Purchase price is required'),
  building_value: z.string().optional(),
  construction_year: z.string().optional(),
  depreciation_rate: z.string().optional(),
  grunderwerbsteuer: z.string().optional(),
  notary_fees: z.string().optional(),
  registry_fees: z.string().optional(),
  monthly_rent: z.string().optional(),
}).refine(
  (data) => {
    const price = parseFloat(data.purchase_price);
    return price > 0 && price <= 100000000;
  },
  {
    message: 'Purchase price must be between 0 and 100,000,000',
    path: ['purchase_price'],
  }
).refine(
  (data) => {
    if (!data.building_value) return true;
    const buildingValue = parseFloat(data.building_value);
    const purchasePrice = parseFloat(data.purchase_price);
    return buildingValue > 0 && buildingValue <= purchasePrice;
  },
  {
    message: 'Building value must be greater than 0 and less than or equal to purchase price',
    path: ['building_value'],
  }
).refine(
  (data) => {
    if (!data.depreciation_rate) return true;
    const rate = parseFloat(data.depreciation_rate);
    return rate >= 0.001 && rate <= 0.10;
  },
  {
    message: 'Depreciation rate must be between 0.1% and 10%',
    path: ['depreciation_rate'],
  }
);

type PropertyFormSchema = z.infer<typeof propertySchema>;

interface PropertyFormProps {
  property?: Property;
  onSubmit: (data: PropertyFormData) => void;
  onCancel: () => void;
}

const PropertyForm = ({ property, onSubmit, onCancel }: PropertyFormProps) => {
  const { t } = useTranslation();
  const [autoCalculatedBuilding, setAutoCalculatedBuilding] = useState(false);
  const [autoDeterminedRate, setAutoDeterminedRate] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<PropertyFormSchema>({
    resolver: zodResolver(propertySchema),
    defaultValues: property
      ? {
          property_type: property.property_type,
          rental_percentage: property.rental_percentage.toString(),
          street: property.street,
          city: property.city,
          postal_code: property.postal_code,
          purchase_date: property.purchase_date.split('T')[0],
          purchase_price: property.purchase_price.toString(),
          building_value: property.building_value.toString(),
          construction_year: property.construction_year?.toString() || '',
          depreciation_rate: (property.depreciation_rate * 100).toString(),
          grunderwerbsteuer: property.grunderwerbsteuer?.toString() || '',
          notary_fees: property.notary_fees?.toString() || '',
          registry_fees: property.registry_fees?.toString() || '',
        }
      : {
          property_type: PropertyType.RENTAL,
          rental_percentage: '100',
          purchase_date: new Date().toISOString().split('T')[0],
        },
  });

  const propertyType = watch('property_type');
  const purchasePrice = watch('purchase_price');
  const buildingValue = watch('building_value');
  const constructionYear = watch('construction_year');
  const depreciationRate = watch('depreciation_rate');

  // Auto-calculate building_value as 80% of purchase_price if not provided
  useEffect(() => {
    if (!property && purchasePrice && !buildingValue) {
      const price = parseFloat(purchasePrice);
      if (!isNaN(price) && price > 0) {
        const calculated = (price * 0.8).toFixed(2);
        setValue('building_value', calculated);
        setAutoCalculatedBuilding(true);
      }
    }
  }, [purchasePrice, buildingValue, property, setValue]);

  // Auto-determine depreciation_rate based on construction_year
  useEffect(() => {
    if (!property && constructionYear && !depreciationRate) {
      const year = parseInt(constructionYear);
      if (!isNaN(year)) {
        const rate = year < 1915 ? '1.5' : '2.0';
        setValue('depreciation_rate', rate);
        setAutoDeterminedRate(true);
      }
    }
  }, [constructionYear, depreciationRate, property, setValue]);

  // Clear auto-calculation flags when user manually edits
  const handleBuildingValueChange = () => {
    setAutoCalculatedBuilding(false);
  };

  const handleDepreciationRateChange = () => {
    setAutoDeterminedRate(false);
  };

  const handleFormSubmit = (data: PropertyFormSchema) => {
    // Convert string values to numbers for API
    const formData: PropertyFormData = {
      property_type: data.property_type,
      rental_percentage: data.rental_percentage || '100',
      street: data.street,
      city: data.city,
      postal_code: data.postal_code,
      purchase_date: data.purchase_date,
      purchase_price: data.purchase_price,
      building_value: data.building_value,
      construction_year: data.construction_year,
      depreciation_rate: data.depreciation_rate,
      grunderwerbsteuer: data.grunderwerbsteuer,
      notary_fees: data.notary_fees,
      registry_fees: data.registry_fees,
      monthly_rent: data.monthly_rent,
    };

    onSubmit(formData);
  };

  return (
    <form className="property-form" onSubmit={handleSubmit(handleFormSubmit)}>
      <h2>
        {property
          ? t('properties.editProperty')
          : t('properties.addProperty')}
      </h2>

      <div className="form-group">
        <label htmlFor="property_type">
          {t('properties.propertyType')} <span className="required">*</span>
        </label>
        <select id="property_type" {...register('property_type')}>
          <option value={PropertyType.RENTAL}>
            {t('properties.types.rental')}
          </option>
          <option value={PropertyType.OWNER_OCCUPIED}>
            {t('properties.types.ownerOccupied')}
          </option>
          <option value={PropertyType.MIXED_USE}>
            {t('properties.types.mixedUse')}
          </option>
        </select>
        {errors.property_type && (
          <span className="error">{errors.property_type.message}</span>
        )}
      </div>

      {propertyType === PropertyType.MIXED_USE && (
        <div className="form-group">
          <label htmlFor="rental_percentage">
            {t('properties.rentalPercentage')} <span className="required">*</span>
          </label>
          <input
            id="rental_percentage"
            type="number"
            step="0.01"
            min="0"
            max="100"
            placeholder="100"
            {...register('rental_percentage')}
          />
          <span className="field-hint">{t('properties.rentalPercentageHint')}</span>
          {errors.rental_percentage && (
            <span className="error">{errors.rental_percentage.message}</span>
          )}
        </div>
      )}

      <div className="form-section">
        <h3>{t('properties.addressSection')}</h3>

        <div className="form-group">
          <label htmlFor="street">
            {t('properties.street')} <span className="required">*</span>
          </label>
          <input
            id="street"
            type="text"
            placeholder={t('properties.streetPlaceholder')}
            {...register('street')}
          />
          {errors.street && <span className="error">{errors.street.message}</span>}
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="postal_code">
              {t('properties.postalCode')} <span className="required">*</span>
            </label>
            <input
              id="postal_code"
              type="text"
              placeholder="1010"
              {...register('postal_code')}
            />
            {errors.postal_code && (
              <span className="error">{errors.postal_code.message}</span>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="city">
              {t('properties.city')} <span className="required">*</span>
            </label>
            <input
              id="city"
              type="text"
              placeholder="Wien"
              {...register('city')}
            />
            {errors.city && <span className="error">{errors.city.message}</span>}
          </div>
        </div>
      </div>

      <div className="form-section">
        <h3>{t('properties.purchaseSection')}</h3>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="purchase_date">
              {t('properties.purchaseDate')} <span className="required">*</span>
            </label>
            <input
              id="purchase_date"
              type="date"
              {...register('purchase_date')}
            />
            {errors.purchase_date && (
              <span className="error">{errors.purchase_date.message}</span>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="purchase_price">
              {t('properties.purchasePrice')} <span className="required">*</span>
            </label>
            <input
              id="purchase_price"
              type="number"
              step="0.01"
              min="0"
              placeholder="350000.00"
              {...register('purchase_price')}
            />
            {errors.purchase_price && (
              <span className="error">{errors.purchase_price.message}</span>
            )}
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="building_value">
              {t('properties.buildingValue')}
            </label>
            <input
              id="building_value"
              type="number"
              step="0.01"
              min="0"
              placeholder="280000.00"
              {...register('building_value', {
                onChange: handleBuildingValueChange,
              })}
            />
            {autoCalculatedBuilding && (
              <span className="auto-suggest-hint">
                🤖 {t('properties.autoCalculated80Percent')}
              </span>
            )}
            {errors.building_value && (
              <span className="error">{errors.building_value.message}</span>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="construction_year">
              {t('properties.constructionYear')}
            </label>
            <input
              id="construction_year"
              type="number"
              min="1800"
              max={new Date().getFullYear()}
              placeholder="1985"
              {...register('construction_year')}
            />
            {errors.construction_year && (
              <span className="error">{errors.construction_year.message}</span>
            )}
          </div>
        </div>

        {propertyType !== PropertyType.OWNER_OCCUPIED && (
          <div className="form-group">
            <label htmlFor="depreciation_rate">
              {t('properties.depreciationRate')}
            </label>
            <input
              id="depreciation_rate"
              type="number"
              step="0.01"
              min="0.1"
              max="10"
              placeholder="2.0"
              {...register('depreciation_rate', {
                onChange: handleDepreciationRateChange,
              })}
            />
            <span className="field-hint">{t('properties.depreciationRateHint')}</span>
            {autoDeterminedRate && (
              <span className="auto-suggest-hint">
                🤖 {t('properties.autoDeterminedRate')}
              </span>
            )}
            {errors.depreciation_rate && (
              <span className="error">{errors.depreciation_rate.message}</span>
            )}
          </div>
        )}
      </div>

      <div className="form-section">
        <h3>{t('properties.purchaseCostsSection')}</h3>
        <p className="section-description">{t('properties.purchaseCostsDescription')}</p>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="grunderwerbsteuer">
              {t('properties.grunderwerbsteuer')}
            </label>
            <input
              id="grunderwerbsteuer"
              type="number"
              step="0.01"
              min="0"
              placeholder="0.00"
              {...register('grunderwerbsteuer')}
            />
            {errors.grunderwerbsteuer && (
              <span className="error">{errors.grunderwerbsteuer.message}</span>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="notary_fees">
              {t('properties.notaryFees')}
            </label>
            <input
              id="notary_fees"
              type="number"
              step="0.01"
              min="0"
              placeholder="0.00"
              {...register('notary_fees')}
            />
            {errors.notary_fees && (
              <span className="error">{errors.notary_fees.message}</span>
            )}
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="registry_fees">
            {t('properties.registryFees')}
          </label>
          <input
            id="registry_fees"
            type="number"
            step="0.01"
            min="0"
            placeholder="0.00"
            {...register('registry_fees')}
          />
          {errors.registry_fees && (
            <span className="error">{errors.registry_fees.message}</span>
          )}
        </div>
      </div>

      {(propertyType === PropertyType.RENTAL || propertyType === PropertyType.MIXED_USE) && !property && (
        <div className="form-section">
          <h3>{t('properties.rentalIncomeSection', 'Mieteinnahmen')}</h3>
          <div className="form-group">
            <label htmlFor="monthly_rent">
              {t('properties.monthlyRent', 'Monatliche Miete (€)')}
            </label>
            <input
              id="monthly_rent"
              type="number"
              step="0.01"
              min="0"
              placeholder={t('properties.monthlyRentPlaceholder', 'z.B. 1200.00')}
              {...register('monthly_rent')}
            />
            <span className="field-hint">
              {t('properties.monthlyRentHint', 'Wenn angegeben, wird automatisch eine monatliche Mieteinnahme eingerichtet.')}
            </span>
          </div>
        </div>
      )}

      {propertyType === PropertyType.OWNER_OCCUPIED && (
        <div className="form-info disclaimer">
          <strong>⚠️ {t('properties.ownerOccupiedDisclaimer')}</strong>
          <p>{t('properties.ownerOccupiedDisclaimerText')}</p>
        </div>
      )}

      <div className="form-actions">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={onCancel}
          disabled={isSubmitting}
        >
          {t('common.cancel')}
        </button>
        <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
          {isSubmitting ? t('common.saving') : t('common.save')}
        </button>
      </div>
    </form>
  );
};

export default PropertyForm;
