import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Archive, Building2, Car, Cpu, House, Package, Pencil, Smartphone, Trash2, Wrench, type LucideIcon } from 'lucide-react';
import { useConfirm } from '../../hooks/useConfirm';
import { propertyService } from '../../services/propertyService';
import { Property, PropertyStatus, PropertyType } from '../../types/property';
import FuturisticIcon, { type FuturisticIconTone } from '../common/FuturisticIcon';
import { getLocaleForLanguage } from '../../utils/locale';
import './PropertyList.css';

interface PropertyListProps {
  properties: Property[];
  onEdit: (property: Property) => void;
  onArchive: (property: Property) => void;
  onDelete: (id: string) => void;
  onView: (property: Property) => void;
  isLoading?: boolean;
  showArchived?: boolean;
  onShowArchivedChange?: (showArchived: boolean) => void;
}

const PropertyList = ({
  properties,
  onEdit,
  onArchive,
  onDelete,
  onView,
  isLoading = false,
  showArchived: showArchivedProp,
  onShowArchivedChange,
}: PropertyListProps) => {
  const { t, i18n } = useTranslation();
  const { confirm: showConfirm } = useConfirm();
  const [showArchivedLocal, setShowArchivedLocal] = useState(false);

  // Use controlled props if provided, otherwise fall back to local state
  const showArchived = showArchivedProp !== undefined ? showArchivedProp : showArchivedLocal;
  const setShowArchived = (value: boolean) => {
    if (onShowArchivedChange) {
      onShowArchivedChange(value);
    } else {
      setShowArchivedLocal(value);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat(getLocaleForLanguage(i18n.language), {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString(getLocaleForLanguage(i18n.language), {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
  };

  const formatPercentage = (rate: number) => {
    return `${(rate * 100).toFixed(2)}%`;
  };

  const calculateAccumulatedDepreciation = (property: Property): number => {
    const startDate = property.put_into_use_date
      ? new Date(property.put_into_use_date)
      : new Date(property.purchase_date);
    const currentDate = property.sale_date ? new Date(property.sale_date) : new Date();
    const yearsOwned = (currentDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24 * 365.25);

    const isRE = !property.asset_type || property.asset_type === 'real_estate';

    if (isRE && property.property_type === PropertyType.OWNER_OCCUPIED) {
      return 0;
    }

    const depreciableValue = isRE
      ? property.building_value * (property.rental_percentage / 100)
      : property.building_value;
    const totalDepreciation = depreciableValue * property.depreciation_rate * Math.max(0, yearsOwned);

    return Math.min(totalDepreciation, depreciableValue);
  };

  const calculateRemainingValue = (property: Property): number => {
    const depreciableValue = property.building_value * (property.rental_percentage / 100);
    const accumulated = calculateAccumulatedDepreciation(property);
    return Math.max(0, depreciableValue - accumulated);
  };

  const handleDeleteClick = async (property: Property, e: React.MouseEvent) => {
    e.stopPropagation();
    
    try {
      // First check impact without deleting (force=false)
      const result = await propertyService.checkDeleteImpact(property.id);
      
      // Property already gone (404 handled gracefully)
      if (result.deleted) {
        onDelete(property.id);
        return;
      }

      const { transaction_count, recurring_count, loan_count } = result.impact || { transaction_count: 0, recurring_count: 0, loan_count: 0 };
      const hasLinkedData = transaction_count > 0 || recurring_count > 0 || loan_count > 0;

      if (hasLinkedData) {
        const impactLines: string[] = [];
        if (transaction_count > 0) {
          impactLines.push(t('properties.deleteImpactTransactions', { count: transaction_count }));
        }
        if (recurring_count > 0) {
          impactLines.push(t('properties.deleteImpactRecurring', { count: recurring_count }));
        }
        if (loan_count > 0) {
          impactLines.push(t('properties.deleteImpactLoans', { count: loan_count }));
        }
        
        const confirmMessage = t('properties.confirmDeleteWithImpact', {
          address: property.address,
          impact: impactLines.join('\n'),
        });
        
        const recurringLink = recurring_count > 0 ? React.createElement(
          'a',
          { href: '/recurring', style: { color: '#7c3aed', textDecoration: 'underline', fontSize: '0.85rem', display: 'inline-block', marginTop: '4px' } },
          `→ ${t('recurring.title', 'Recurring Transactions')}`
        ) : undefined;

        const ok = await showConfirm(confirmMessage, { variant: 'danger', confirmText: t('common.delete'), messageNode: recurringLink });
        if (ok) {
          onDelete(property.id);
        }
      } else {
        // No linked data, simple confirm
        const confirmMessage = t('properties.confirmDelete', { address: property.address });
        const ok = await showConfirm(confirmMessage, { variant: 'danger', confirmText: t('common.delete') });
        if (ok) {
          onDelete(property.id);
        }
      }
    } catch {
      // If impact check fails, fall back to simple confirm
      const confirmMessage = t('properties.confirmDelete', { address: property.address });
      const ok = await showConfirm(confirmMessage, { variant: 'danger', confirmText: t('common.delete') });
      if (ok) {
        onDelete(property.id);
      }
    }
  };

  const handleArchiveClick = async (property: Property, e: React.MouseEvent) => {
    e.stopPropagation();
    
    const confirmMessage = t('properties.confirmArchive', {
      address: property.address,
    });
    
    const ok2 = await showConfirm(confirmMessage, { variant: 'warning', confirmText: t('properties.archive') });
    if (ok2) {
      onArchive(property);
    }
  };

  const filteredProperties = showArchived
    ? properties
    : properties.filter((p) => p.status === PropertyStatus.ACTIVE);

  const getAssetIcon = (property: Property): { icon: LucideIcon; tone: FuturisticIconTone } => {
    const at = (property as any).asset_type || 'real_estate';
    const icons: Record<string, { icon: LucideIcon; tone: FuturisticIconTone }> = {
      real_estate: { icon: House, tone: 'cyan' },
      vehicle: { icon: Car, tone: 'emerald' },
      electric_vehicle: { icon: Car, tone: 'violet' },
      computer: { icon: Cpu, tone: 'violet' },
      phone: { icon: Smartphone, tone: 'amber' },
      office_furniture: { icon: Package, tone: 'amber' },
      machinery: { icon: Wrench, tone: 'rose' },
      tools: { icon: Wrench, tone: 'rose' },
      software: { icon: Cpu, tone: 'violet' },
      other_equipment: { icon: Package, tone: 'slate' },
    };
    return icons[at] || { icon: Building2, tone: 'slate' };
  };

  const isRealEstate = (property: Property): boolean => {
    const at = (property as any).asset_type;
    return !at || at === 'real_estate';
  };

  if (isLoading) {
    return (
      <div className="property-list-loading">
        <div className="loading-spinner"></div>
        <p>{t('common.loading')}</p>
      </div>
    );
  }

  if (properties.length === 0) {
    return (
      <div className="property-list-empty">
        <div className="empty-icon">
          <FuturisticIcon icon={House} tone="cyan" size="xl" />
        </div>
        <h3>{t('properties.noProperties')}</h3>
        <p>{t('properties.noPropertiesDescription')}</p>
      </div>
    );
  }

  if (filteredProperties.length === 0 && !showArchived) {
    return (
      <div className="property-list">
        <div className="list-header">
          <div className="toggle-archived">
            <label>
              <input
                type="checkbox"
                checked={showArchived}
                onChange={(e) => setShowArchived(e.target.checked)}
              />
              {t('properties.showArchived')}
            </label>
          </div>
        </div>
        <div className="property-list-empty">
          <div className="empty-icon">
            <FuturisticIcon icon={Package} tone="slate" size="xl" />
          </div>
          <h3>{t('properties.allPropertiesArchived')}</h3>
          <p>{t('properties.allPropertiesArchivedDescription')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="property-list">
      <div className="list-header">
        <div className="list-stats">
          {(() => {
            const reCount = filteredProperties.filter(p => isRealEstate(p)).length;
            const otherCount = filteredProperties.length - reCount;
            return (
              <>
                <span className="stat-item">
                  <strong>{reCount}</strong> {t('properties.propertiesCount')}
                </span>
                {otherCount > 0 && (
                  <span className="stat-item" style={{ marginLeft: '8px' }}>
                    · <strong>{otherCount}</strong> {t('properties.otherAssetsCount', 'other asset(s)')}
                  </span>
                )}
              </>
            );
          })()}
          {properties.length !== filteredProperties.length && (
            <span className="stat-item muted">
              ({properties.length - filteredProperties.length} {t('properties.archived')})
            </span>
          )}
        </div>
        <div className="toggle-archived">
          <label>
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(e) => setShowArchived(e.target.checked)}
            />
            {t('properties.showArchived')}
          </label>
        </div>
      </div>

      <div className="property-cards">
        {filteredProperties.map((property) => {
          const accumulated = calculateAccumulatedDepreciation(property);
          const remaining = calculateRemainingValue(property);
          const isRental = property.property_type !== PropertyType.OWNER_OCCUPIED;
          const isRE = isRealEstate(property);
          const assetIcon = getAssetIcon(property);

          return (
            <div
              key={property.id}
              className={`property-card ${property.status}`}
              onClick={() => onView(property)}
            >
              <div className="property-card-header">
                <div className="property-address">
                  <h3>
                    <FuturisticIcon icon={assetIcon.icon} tone={assetIcon.tone} size="sm" className="property-title-icon" />
                    <span>{isRE ? property.address : ((property as any).name || property.address)}</span>
                  </h3>
                  <div className="property-badges">
                    <span className={`status-badge ${property.status}`}>
                      {t(`properties.status.${property.status}`)}
                    </span>
                    {isRE ? (
                      <span className={`type-badge ${property.property_type}`}>
                        {t(`properties.types.${property.property_type}`)}
                      </span>
                    ) : (
                      <span className="type-badge other-asset">
                        {String(
                          t(`properties.assetTypes.${(property as any).asset_type}`, (property as any).asset_type)
                        )}
                      </span>
                    )}
                    {property.purchase_price <= 0.01 && (
                      <span className="type-badge placeholder" title={t('properties.placeholderWarning.title', 'Incomplete data')}>
                        ⚠️ {t('properties.placeholderWarning.badge', 'Needs data')}
                      </span>
                    )}
                  </div>
                </div>
                <div className="property-actions">
                  <button
                    className="btn-icon"
                    onClick={(e) => {
                      e.stopPropagation();
                      onEdit(property);
                    }}
                    title={t('common.edit')}
                  >
                    <Pencil size={15} />
                  </button>
                  {property.status === PropertyStatus.ACTIVE && (
                    <button
                      className="btn-icon"
                      onClick={(e) => handleArchiveClick(property, e)}
                      title={isRE ? t('properties.sellProperty') : t('properties.disposeAsset')}
                    >
                      <Archive size={15} />
                    </button>
                  )}
                  <button
                    className="btn-icon"
                    onClick={(e) => handleDeleteClick(property, e)}
                    title={t('common.delete')}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>

              <div className="property-card-body">
                <div className="property-info-grid">
                  <div className="info-item">
                    <span className="info-label">{t('properties.purchaseDate')}</span>
                    <span className="info-value">{formatDate(property.purchase_date)}</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">{isRE ? t('properties.buildingValue') : t('properties.purchasePrice')}</span>
                    <span className="info-value">{formatCurrency(isRE ? property.building_value : property.purchase_price)}</span>
                  </div>
                  {isRE && isRental && (
                    <>
                      <div className="info-item">
                        <span className="info-label">{t('properties.depreciationRate')}</span>
                        <span className="info-value">{formatPercentage(property.depreciation_rate)}</span>
                      </div>
                      <div className="info-item">
                        <span className="info-label">{t('properties.accumulatedDepreciation')}</span>
                        <span className="info-value depreciation">{formatCurrency(accumulated)}</span>
                      </div>
                      <div className="info-item">
                        <span className="info-label">{t('properties.remainingValue')}</span>
                        <span className="info-value remaining">{formatCurrency(remaining)}</span>
                      </div>
                    </>
                  )}
                  {isRE && property.property_type === PropertyType.MIXED_USE && (
                    <div className="info-item">
                      <span className="info-label">{t('properties.rentalPercentage')}</span>
                      <span className="info-value">{property.rental_percentage}%</span>
                    </div>
                  )}
                </div>

                {isRE && isRental && (
                  <div className="depreciation-progress">
                    <div className="progress-bar">
                      <div
                        className="progress-fill"
                        style={{
                          width: `${Math.min(100, (accumulated / (property.building_value * (property.rental_percentage / 100))) * 100)}%`,
                        }}
                      ></div>
                    </div>
                    <span className="progress-label">
                      {t('properties.depreciationProgress', {
                        percent: Math.min(100, ((accumulated / (property.building_value * (property.rental_percentage / 100))) * 100)).toFixed(1),
                      })}
                    </span>
                  </div>
                )}
              </div>

              {property.sale_date && (
                <div className="property-card-footer">
                  <span className="sale-info">
                    {t('properties.soldOn', { date: formatDate(property.sale_date) })}
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Responsive table view for larger screens */}
      <div className="property-table-view">
        <table className="property-table">
          <thead>
            <tr>
              <th>{t('properties.assetName', 'Asset Name')}</th>
              <th>{t('properties.type')}</th>
              <th>{t('properties.purchaseDate')}</th>
              <th>{t('properties.purchasePrice')}</th>
              <th>{t('properties.depreciationRate')}</th>
              <th>{t('properties.accumulatedDepreciation')}</th>
              <th>{t('properties.remainingValue')}</th>
              <th>{t('properties.statusLabel')}</th>
              <th>{t('common.actions')}</th>
            </tr>
          </thead>
          <tbody>
            {filteredProperties.map((property) => {
              const accumulated = calculateAccumulatedDepreciation(property);
              const remaining = calculateRemainingValue(property);
              const isRental = property.property_type !== PropertyType.OWNER_OCCUPIED;
              const isRE = isRealEstate(property);
              const assetIcon = getAssetIcon(property);

              return (
                <tr
                  key={property.id}
                  className={`property-row ${property.status}`}
                  onClick={() => onView(property)}
                >
                  <td className="address-cell">
                    <div className="address-content">
                      <strong className="property-table-title">
                        <FuturisticIcon icon={assetIcon.icon} tone={assetIcon.tone} size="xs" />
                        <span>{isRE ? property.address : ((property as any).name || property.address)}</span>
                      </strong>
                      {property.sale_date && (
                        <span className="sale-date-small">
                          {t('properties.soldOn', { date: formatDate(property.sale_date) })}
                        </span>
                      )}
                    </div>
                  </td>
                  <td>
                    {isRE ? (
                      <span className={`type-badge ${property.property_type}`}>
                        {t(`properties.types.${property.property_type}`)}
                      </span>
                    ) : (
                      <span className="type-badge other-asset">
                        {String(
                          t(`properties.assetTypes.${(property as any).asset_type}`, (property as any).asset_type)
                        )}
                      </span>
                    )}
                  </td>
                  <td>{formatDate(property.purchase_date)}</td>
                  <td className="amount">{formatCurrency(isRE ? property.building_value : property.purchase_price)}</td>
                  <td>{isRE && isRental ? formatPercentage(property.depreciation_rate) : '—'}</td>
                  <td className="amount depreciation">
                    {isRE && isRental ? formatCurrency(accumulated) : '—'}
                  </td>
                  <td className="amount remaining">
                    {isRE && isRental ? formatCurrency(remaining) : '—'}
                  </td>
                  <td>
                    <span className={`status-badge ${property.status}`}>
                      {t(`properties.status.${property.status}`)}
                    </span>
                  </td>
                  <td className="actions">
                    <button
                      className="btn-icon"
                      onClick={(e) => {
                        e.stopPropagation();
                        onEdit(property);
                      }}
                      title={t('common.edit')}
                    >
                      <Pencil size={15} />
                    </button>
                    {property.status === PropertyStatus.ACTIVE && (
                      <button
                        className="btn-icon"
                        onClick={(e) => handleArchiveClick(property, e)}
                        title={isRE ? t('properties.sellProperty') : t('properties.disposeAsset')}
                      >
                        <Archive size={15} />
                      </button>
                    )}
                    <button
                      className="btn-icon"
                      onClick={(e) => handleDeleteClick(property, e)}
                      title={t('common.delete')}
                    >
                      <Trash2 size={15} />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default PropertyList;
