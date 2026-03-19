import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useConfirm } from '../../hooks/useConfirm';
import { propertyService } from '../../services/propertyService';
import { Property, PropertyStatus, PropertyType } from '../../types/property';
import './PropertyList.css';

interface PropertyListProps {
  properties: Property[];
  onEdit: (property: Property) => void;
  onArchive: (property: Property) => void;
  onDelete: (id: string) => void;
  onView: (property: Property) => void;
  isLoading?: boolean;
}

const PropertyList = ({
  properties,
  onEdit,
  onArchive,
  onDelete,
  onView,
  isLoading = false,
}: PropertyListProps) => {
  const { t } = useTranslation();
  const { confirm: showConfirm } = useConfirm();
  const [showArchived, setShowArchived] = useState(false);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('de-AT', {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('de-AT', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
  };

  const formatPercentage = (rate: number) => {
    return `${(rate * 100).toFixed(2)}%`;
  };

  const calculateAccumulatedDepreciation = (property: Property): number => {
    // Calculate accumulated depreciation based on years owned
    const purchaseDate = new Date(property.purchase_date);
    const currentDate = property.sale_date ? new Date(property.sale_date) : new Date();
    const yearsOwned = (currentDate.getTime() - purchaseDate.getTime()) / (1000 * 60 * 60 * 24 * 365.25);
    
    // Only calculate for rental properties
    if (property.property_type === PropertyType.OWNER_OCCUPIED) {
      return 0;
    }

    const depreciableValue = property.building_value * (property.rental_percentage / 100);
    const totalDepreciation = depreciableValue * property.depreciation_rate * yearsOwned;
    
    // Cap at building value
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
        
        const ok = await showConfirm(confirmMessage, { variant: 'danger', confirmText: t('common.delete') });
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
    : properties.filter((p) => p.status !== PropertyStatus.ARCHIVED);

  const getAssetIcon = (property: Property): string => {
    const at = (property as any).asset_type || 'real_estate';
    const icons: Record<string, string> = {
      real_estate: '🏠', vehicle: '🚗', electric_vehicle: '⚡🚗',
      computer: '💻', phone: '📱', office_furniture: '🪑',
      machinery: '⚙️', tools: '🔧', software: '💿', other_equipment: '📦',
    };
    return icons[at] || '🏠';
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
        <div className="empty-icon">🏠</div>
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
          <div className="empty-icon">📦</div>
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
          <span className="stat-item">
            <strong>{filteredProperties.length}</strong> {t('properties.propertiesCount')}
          </span>
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

          return (
            <div
              key={property.id}
              className={`property-card ${property.status}`}
              onClick={() => onView(property)}
            >
              <div className="property-card-header">
                <div className="property-address">
                  <h3>{getAssetIcon(property)} {isRE ? property.address : ((property as any).name || property.address)}</h3>
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
                    ✏️
                  </button>
                  {property.status === PropertyStatus.ACTIVE && (
                    <button
                      className="btn-icon"
                      onClick={(e) => handleArchiveClick(property, e)}
                      title={t('properties.archive')}
                    >
                      📦
                    </button>
                  )}
                  <button
                    className="btn-icon btn-danger"
                    onClick={(e) => handleDeleteClick(property, e)}
                    title={t('common.delete')}
                  >
                    🗑️
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
                    📅 {t('properties.soldOn', { date: formatDate(property.sale_date) })}
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
              <th>{t('properties.assetName', '名称')}</th>
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

              return (
                <tr
                  key={property.id}
                  className={`property-row ${property.status}`}
                  onClick={() => onView(property)}
                >
                  <td className="address-cell">
                    <div className="address-content">
                      <strong>{getAssetIcon(property)} {isRE ? property.address : ((property as any).name || property.address)}</strong>
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
                      ✏️
                    </button>
                    {property.status === PropertyStatus.ACTIVE && (
                      <button
                        className="btn-icon"
                        onClick={(e) => handleArchiveClick(property, e)}
                        title={t('properties.archive')}
                      >
                        📦
                      </button>
                    )}
                    <button
                      className="btn-icon btn-danger"
                      onClick={(e) => handleDeleteClick(property, e)}
                      title={t('common.delete')}
                    >
                      🗑️
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
