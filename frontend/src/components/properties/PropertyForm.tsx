import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { Property, PropertyType, PropertyFormData, ASSET_USEFUL_LIFE } from '../../types/property';
import './PropertyForm.css';

const ASSET_TYPE_OPTIONS = [
  { value: 'vehicle', icon: '🚗' },
  { value: 'electric_vehicle', icon: '⚡🚗' },
  { value: 'computer', icon: '💻' },
  { value: 'phone', icon: '📱' },
  { value: 'office_furniture', icon: '🪑' },
  { value: 'machinery', icon: '⚙️' },
  { value: 'tools', icon: '🔧' },
  { value: 'software', icon: '💿' },
  { value: 'other_equipment', icon: '📦' },
];

// Zod schema for real estate
const realEstateSchema = z.object({
  asset_category: z.literal('real_estate'),
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
  // unused but needed for union
  asset_type: z.string().optional(),
  asset_name: z.string().optional(),
  sub_category: z.string().optional(),
  supplier: z.string().optional(),
  business_use_percentage: z.string().optional(),
  useful_life_years: z.string().optional(),
});

// Zod schema for non-real-estate assets
const assetSchema = z.object({
  asset_category: z.literal('other'),
  asset_type: z.string().min(1, 'Asset type is required'),
  asset_name: z.string().min(1, 'Name is required'),
  sub_category: z.string().optional(),
  purchase_date: z.string().min(1, 'Purchase date is required'),
  purchase_price: z.string().min(1, 'Purchase price is required'),
  supplier: z.string().optional(),
  business_use_percentage: z.string().optional(),
  useful_life_years: z.string().optional(),
  // unused but needed for union
  property_type: z.nativeEnum(PropertyType).optional(),
  rental_percentage: z.string().optional(),
  street: z.string().optional(),
  city: z.string().optional(),
  postal_code: z.string().optional(),
  building_value: z.string().optional(),
  construction_year: z.string().optional(),
  depreciation_rate: z.string().optional(),
  grunderwerbsteuer: z.string().optional(),
  notary_fees: z.string().optional(),
  registry_fees: z.string().optional(),
  monthly_rent: z.string().optional(),
});

const propertySchema = z.discriminatedUnion('asset_category', [realEstateSchema, assetSchema]);

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

  const isEditingRealEstate = property && (!property.asset_type || property.asset_type === 'real_estate');

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<PropertyFormSchema>({
    resolver: zodResolver(propertySchema),
    defaultValues: property
      ? (isEditingRealEstate
        ? {
            asset_category: 'real_estate' as const,
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
            asset_category: 'other' as const,
            asset_type: property.asset_type || 'other_equipment',
            asset_name: property.name || '',
            purchase_date: property.purchase_date.split('T')[0],
            purchase_price: property.purchase_price.toString(),
          })
      : {
          asset_category: 'real_estate' as const,
          property_type: PropertyType.RENTAL,
          rental_percentage: '100',
          purchase_date: new Date().toISOString().split('T')[0],
        },
  });

  const assetCategory = watch('asset_category');
  const propertyType = watch('property_type');
  const purchasePrice = watch('purchase_price');
  const buildingValue = watch('building_value');
  const constructionYear = watch('construction_year');
  const depreciationRate = watch('depreciation_rate');
  const assetType = watch('asset_type');

  // Auto-calculate building_value as 80% of purchase_price if not provided
  useEffect(() => {
    if (assetCategory === 'real_estate' && !property && purchasePrice && !buildingValue) {
      const price = parseFloat(purchasePrice);
      if (!isNaN(price) && price > 0) {
        setValue('building_value', (price * 0.8).toFixed(2));
        setAutoCalculatedBuilding(true);
      }
    }
  }, [purchasePrice, buildingValue, property, setValue, assetCategory]);

  // Auto-determine depreciation_rate based on construction_year
  useEffect(() => {
    if (assetCategory === 'real_estate' && !property && constructionYear && !depreciationRate) {
      const year = parseInt(constructionYear);
      if (!isNaN(year)) {
        setValue('depreciation_rate', year < 1915 ? '1.5' : '2.0');
        setAutoDeterminedRate(true);
      }
    }
  }, [constructionYear, depreciationRate, property, setValue, assetCategory]);

  // Auto-fill useful_life when asset_type changes
  useEffect(() => {
    if (assetCategory === 'other' && assetType && !property) {
      const life = ASSET_USEFUL_LIFE[assetType];
      if (life) setValue('useful_life_years', life.toString());
    }
  }, [assetType, assetCategory, property, setValue]);

  const handleFormSubmit = (data: PropertyFormSchema) => {
    const formData: PropertyFormData = {
      asset_category: data.asset_category,
      property_type: data.property_type || PropertyType.RENTAL,
      rental_percentage: data.rental_percentage || '100',
      street: data.street || '',
      city: data.city || '',
      postal_code: data.postal_code || '',
      purchase_date: data.purchase_date,
      purchase_price: data.purchase_price,
      building_value: data.building_value,
      construction_year: data.construction_year,
      depreciation_rate: data.depreciation_rate,
      grunderwerbsteuer: data.grunderwerbsteuer,
      notary_fees: data.notary_fees,
      registry_fees: data.registry_fees,
      monthly_rent: data.monthly_rent,
      asset_type: data.asset_type,
      asset_name: data.asset_name,
      sub_category: data.sub_category,
      supplier: data.supplier,
      business_use_percentage: data.business_use_percentage,
      useful_life_years: data.useful_life_years,
    };
    onSubmit(formData);
  };

  return (
    <form className="property-form" onSubmit={handleSubmit(handleFormSubmit)}>
      <h2>
        {property ? t('properties.editProperty') : t('properties.addProperty')}
      </h2>

      {/* Asset category selector — only for new assets */}
      {!property && (
        <div className="form-group">
          <label>{t('properties.assetCategory', '资产大类')}</label>
          <div className="asset-category-toggle">
            <button
              type="button"
              className={`toggle-btn ${assetCategory === 'real_estate' ? 'active' : ''}`}
              onClick={() => setValue('asset_category', 'real_estate' as any)}
            >
              🏠 {t('properties.realEstate', '不动产')}
            </button>
            <button
              type="button"
              className={`toggle-btn ${assetCategory === 'other' ? 'active' : ''}`}
              onClick={() => setValue('asset_category', 'other' as any)}
            >
              📦 {t('properties.otherAsset', '其他资产')}
            </button>
          </div>
        </div>
      )}

      {assetCategory === 'real_estate' ? (
        /* ========== REAL ESTATE FORM ========== */
        <>
          <div className="form-group">
            <label htmlFor="property_type">
              {t('properties.propertyType')} <span className="required">*</span>
            </label>
            <select id="property_type" {...register('property_type')}>
              <option value={PropertyType.RENTAL}>{t('properties.types.rental')}</option>
              <option value={PropertyType.OWNER_OCCUPIED}>{t('properties.types.ownerOccupied')}</option>
              <option value={PropertyType.MIXED_USE}>{t('properties.types.mixedUse')}</option>
            </select>
          </div>

          {propertyType === PropertyType.MIXED_USE && (
            <div className="form-group">
              <label htmlFor="rental_percentage">
                {t('properties.rentalPercentage')} <span className="required">*</span>
              </label>
              <input id="rental_percentage" type="number" step="0.01" min="0" max="100" placeholder="100" {...register('rental_percentage')} />
              <span className="field-hint">{t('properties.rentalPercentageHint')}</span>
            </div>
          )}

          <div className="form-section">
            <h3>{t('properties.addressSection')}</h3>
            <div className="form-group">
              <label htmlFor="street">{t('properties.street')} <span className="required">*</span></label>
              <input id="street" type="text" placeholder={t('properties.streetPlaceholder')} {...register('street')} />
              {errors.street && <span className="error">{errors.street.message}</span>}
            </div>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="postal_code">{t('properties.postalCode')} <span className="required">*</span></label>
                <input id="postal_code" type="text" placeholder="1010" {...register('postal_code')} />
              </div>
              <div className="form-group">
                <label htmlFor="city">{t('properties.city')} <span className="required">*</span></label>
                <input id="city" type="text" placeholder="Wien" {...register('city')} />
              </div>
            </div>
          </div>

          <div className="form-section">
            <h3>{t('properties.purchaseSection')}</h3>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="purchase_date">{t('properties.purchaseDate')} <span className="required">*</span></label>
                <input id="purchase_date" type="date" {...register('purchase_date')} />
              </div>
              <div className="form-group">
                <label htmlFor="purchase_price">{t('properties.purchasePrice')} <span className="required">*</span></label>
                <input id="purchase_price" type="number" step="0.01" min="0" placeholder="350000.00" {...register('purchase_price')} />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="building_value">{t('properties.buildingValue')}</label>
                <input id="building_value" type="number" step="0.01" min="0" placeholder="280000.00" {...register('building_value', { onChange: () => setAutoCalculatedBuilding(false) })} />
                {autoCalculatedBuilding && <span className="auto-suggest-hint">🤖 {t('properties.autoCalculated80Percent')}</span>}
              </div>
              <div className="form-group">
                <label htmlFor="construction_year">{t('properties.constructionYear')}</label>
                <input id="construction_year" type="number" min="1800" max={new Date().getFullYear()} placeholder="1985" {...register('construction_year')} />
              </div>
            </div>
            {propertyType !== PropertyType.OWNER_OCCUPIED && (
              <div className="form-group">
                <label htmlFor="depreciation_rate">{t('properties.depreciationRate')}</label>
                <input id="depreciation_rate" type="number" step="0.01" min="0.1" max="10" placeholder="2.0" {...register('depreciation_rate', { onChange: () => setAutoDeterminedRate(false) })} />
                <span className="field-hint">{t('properties.depreciationRateHint')}</span>
                {autoDeterminedRate && <span className="auto-suggest-hint">🤖 {t('properties.autoDeterminedRate')}</span>}
              </div>
            )}
          </div>

          <div className="form-section">
            <h3>{t('properties.purchaseCostsSection')}</h3>
            <p className="section-description">{t('properties.purchaseCostsDescription')}</p>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="grunderwerbsteuer">{t('properties.grunderwerbsteuer')}</label>
                <input id="grunderwerbsteuer" type="number" step="0.01" min="0" placeholder="0.00" {...register('grunderwerbsteuer')} />
              </div>
              <div className="form-group">
                <label htmlFor="notary_fees">{t('properties.notaryFees')}</label>
                <input id="notary_fees" type="number" step="0.01" min="0" placeholder="0.00" {...register('notary_fees')} />
              </div>
            </div>
            <div className="form-group">
              <label htmlFor="registry_fees">{t('properties.registryFees')}</label>
              <input id="registry_fees" type="number" step="0.01" min="0" placeholder="0.00" {...register('registry_fees')} />
            </div>
          </div>

          {(propertyType === PropertyType.RENTAL || propertyType === PropertyType.MIXED_USE) && !property && (
            <div className="form-section">
              <h3>{t('properties.rentalIncomeSection', 'Mieteinnahmen')}</h3>
              <div className="form-group">
                <label htmlFor="monthly_rent">{t('properties.monthlyRent', 'Monatliche Miete (€)')}</label>
                <input id="monthly_rent" type="number" step="0.01" min="0" placeholder={t('properties.monthlyRentPlaceholder', 'z.B. 1200.00')} {...register('monthly_rent')} />
                <span className="field-hint">{t('properties.monthlyRentHint', 'Wenn angegeben, wird automatisch eine monatliche Mieteinnahme eingerichtet.')}</span>
              </div>
            </div>
          )}

          {propertyType === PropertyType.OWNER_OCCUPIED && (
            <div className="form-info disclaimer">
              <strong>⚠️ {t('properties.ownerOccupiedDisclaimer')}</strong>
              <p>{t('properties.ownerOccupiedDisclaimerText')}</p>
            </div>
          )}
        </>
      ) : (
        /* ========== NON-REAL-ESTATE ASSET FORM ========== */
        <>
          <div className="form-group">
            <label htmlFor="asset_type">{t('properties.assetType', '资产类型')} <span className="required">*</span></label>
            <select id="asset_type" {...register('asset_type')}>
              <option value="">{t('properties.selectAssetType', '请选择资产类型')}</option>
              {ASSET_TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.icon} {t(`properties.assetTypes.${opt.value}`, opt.value)}
                </option>
              ))}
            </select>
            {errors.asset_type && <span className="error">{errors.asset_type.message}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="asset_name">{t('properties.assetName', '资产名称')} <span className="required">*</span></label>
            <input id="asset_name" type="text" placeholder={t('properties.assetNamePlaceholder', '例如：VW Golf 2024, MacBook Pro 16')} {...register('asset_name')} />
            {errors.asset_name && <span className="error">{errors.asset_name.message}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="sub_category">{t('properties.subCategory', '子类别')}</label>
            <input id="sub_category" type="text" placeholder={t('properties.subCategoryPlaceholder', '例如：PKW, Laptop, CNC-Maschine')} {...register('sub_category')} />
          </div>

          <div className="form-section">
            <h3>{t('properties.purchaseSection')}</h3>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="purchase_date">{t('properties.purchaseDate')} <span className="required">*</span></label>
                <input id="purchase_date" type="date" {...register('purchase_date')} />
              </div>
              <div className="form-group">
                <label htmlFor="purchase_price">{t('properties.purchasePrice')} <span className="required">*</span></label>
                <input id="purchase_price" type="number" step="0.01" min="0" placeholder="25000.00" {...register('purchase_price')} />
              </div>
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="supplier">{t('properties.supplier', '供应商')}</label>
            <input id="supplier" type="text" placeholder={t('properties.supplierPlaceholder', '例如：MediaMarkt, Autohaus')} {...register('supplier')} />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="business_use_percentage">{t('properties.businessUse', '业务使用比例 (%)')}</label>
              <input id="business_use_percentage" type="number" step="0.01" min="0" max="100" placeholder="100" {...register('business_use_percentage')} />
              <span className="field-hint">{t('properties.businessUseHint', '用于业务的百分比（影响折旧抵扣）')}</span>
            </div>
            <div className="form-group">
              <label htmlFor="useful_life_years">{t('properties.usefulLife', '使用年限')}</label>
              <input id="useful_life_years" type="number" min="1" max="50" {...register('useful_life_years')} />
              <span className="field-hint">{t('properties.usefulLifeHint', '根据资产类型自动确定，可手动调整')}</span>
            </div>
          </div>
        </>
      )}

      <div className="form-actions">
        <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={isSubmitting}>
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
