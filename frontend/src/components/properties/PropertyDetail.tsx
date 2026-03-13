import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Property, PropertyType, PropertyStatus } from '../../types/property';
import { Transaction, TransactionType } from '../../types/transaction';
import { propertyService } from '../../services/propertyService';
import HistoricalDepreciationBackfill from './HistoricalDepreciationBackfill';
import PropertyReports from './PropertyReports';
import './PropertyDetail.css';

interface PropertyDetailProps {
  property: Property;
  onEdit: (property: Property) => void;
  onArchive: (property: Property) => void;
  onBack: () => void;
}

interface PropertyWarning {
  property_id: string;
  property_address: string;
  year: number;
  level: 'info' | 'warning' | 'error';
  type: string;
  months_vacant: number;
  message_de: string;
  message_en: string;
  message_zh: string;
}

interface TransactionsByYear {
  [year: string]: {
    transactions: Transaction[];
    rental_income: number;
    expenses: number;
    net_income: number;
  };
}

const PropertyDetail = ({
  property,
  onEdit,
  onArchive,
  onBack,
}: PropertyDetailProps) => {
  const { t, i18n } = useTranslation();
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [isLoadingTransactions, setIsLoadingTransactions] = useState(false);
  const [showLinkModal, setShowLinkModal] = useState(false);
  const [warnings, setWarnings] = useState<PropertyWarning[]>([]);

  useEffect(() => {
    loadTransactions();
    loadWarnings();
  }, [property.id]);

  const loadTransactions = async () => {
    setIsLoadingTransactions(true);
    try {
      const data = await propertyService.getPropertyTransactions(property.id);
      setTransactions(data);
    } catch (error) {
      console.error('Failed to load transactions:', error);
    } finally {
      setIsLoadingTransactions(false);
    }
  };

  const loadWarnings = async () => {
    try {
      const currentYear = new Date().getFullYear();
      const metrics = await propertyService.getPropertyMetrics(property.id, currentYear);
      if (metrics.warnings && metrics.warnings.length > 0) {
        setWarnings(metrics.warnings);
      }
    } catch (error) {
      console.error('Failed to load warnings:', error);
    }
  };

  const handleBackfillComplete = () => {
    // Reload transactions to show newly created depreciation transactions
    loadTransactions();
  };

  const getWarningMessage = (warning: PropertyWarning): string => {
    const lang = i18n.language;
    if (lang === 'de') return warning.message_de;
    if (lang === 'zh') return warning.message_zh;
    return warning.message_en;
  };

  const getWarningIcon = (level: string): string => {
    switch (level) {
      case 'error': return '🚨';
      case 'warning': return '⚠️';
      case 'info': return 'ℹ️';
      default: return 'ℹ️';
    }
  };

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

  const calculateAccumulatedDepreciation = (): number => {
    const purchaseDate = new Date(property.purchase_date);
    const currentDate = property.sale_date ? new Date(property.sale_date) : new Date();
    const yearsOwned = (currentDate.getTime() - purchaseDate.getTime()) / (1000 * 60 * 60 * 24 * 365.25);
    
    if (property.property_type === PropertyType.OWNER_OCCUPIED) {
      return 0;
    }

    const depreciableValue = property.building_value * (property.rental_percentage / 100);
    const totalDepreciation = depreciableValue * property.depreciation_rate * yearsOwned;
    
    return Math.min(totalDepreciation, depreciableValue);
  };

  const calculateRemainingValue = (): number => {
    const depreciableValue = property.building_value * (property.rental_percentage / 100);
    const accumulated = calculateAccumulatedDepreciation();
    return Math.max(0, depreciableValue - accumulated);
  };

  const calculateYearsRemaining = (): number | null => {
    if (property.property_type === PropertyType.OWNER_OCCUPIED) {
      return null;
    }

    const remaining = calculateRemainingValue();
    if (remaining === 0) {
      return 0;
    }

    const depreciableValue = property.building_value * (property.rental_percentage / 100);
    const annualDepreciation = depreciableValue * property.depreciation_rate;
    
    if (annualDepreciation === 0) {
      return null;
    }

    return Math.ceil(remaining / annualDepreciation);
  };

  const groupTransactionsByYear = (): TransactionsByYear => {
    const grouped: TransactionsByYear = {};

    transactions.forEach((transaction) => {
      const dateObj = new Date(transaction.date);
      const year = isNaN(dateObj.getTime()) ? 'unknown' : dateObj.getFullYear().toString();
      
      if (!grouped[year]) {
        grouped[year] = {
          transactions: [],
          rental_income: 0,
          expenses: 0,
          net_income: 0,
        };
      }

      grouped[year].transactions.push(transaction);

      if (transaction.type === TransactionType.INCOME) {
        grouped[year].rental_income += transaction.amount;
      } else {
        grouped[year].expenses += transaction.amount;
      }

      grouped[year].net_income = grouped[year].rental_income - grouped[year].expenses;
    });

    return grouped;
  };

  const handleUnlinkTransaction = async (transactionId: number) => {
    const confirmMessage = t('properties.confirmUnlink');
    if (!window.confirm(confirmMessage)) {
      return;
    }

    try {
      await propertyService.unlinkTransaction(property.id, transactionId);
      await loadTransactions();
    } catch (error) {
      console.error('Failed to unlink transaction:', error);
      alert(t('properties.unlinkError'));
    }
  };

  const handleArchiveClick = () => {
    const confirmMessage = t('properties.confirmArchive', {
      address: property.address,
    });
    
    if (window.confirm(confirmMessage)) {
      onArchive(property);
    }
  };

  const transactionsByYear = groupTransactionsByYear();
  const years = Object.keys(transactionsByYear).sort((a, b) => parseInt(b) - parseInt(a));
  const accumulated = calculateAccumulatedDepreciation();
  const remaining = calculateRemainingValue();
  const yearsRemaining = calculateYearsRemaining();
  const isRental = property.property_type !== PropertyType.OWNER_OCCUPIED;

  return (
    <div className="property-detail">
      {/* Breadcrumb Navigation */}
      <div className="breadcrumb">
        <button className="breadcrumb-link" onClick={onBack}>
          ← {t('properties.title')}
        </button>
        <span className="breadcrumb-separator">/</span>
        <span className="breadcrumb-current">{property.address}</span>
      </div>

      {/* Property Header */}
      <div className="property-detail-header">
        <div className="header-content">
          <h1>{property.address}</h1>
          <div className="property-badges">
            <span className={`status-badge ${property.status}`}>
              {t(`properties.status.${property.status}`)}
            </span>
            <span className={`type-badge ${property.property_type}`}>
              {t(`properties.types.${property.property_type}`)}
            </span>
          </div>
        </div>
        <div className="header-actions">
          <button className="btn btn-secondary" onClick={() => onEdit(property)}>
            ✏️ {t('common.edit')}
          </button>
          {property.status === PropertyStatus.ACTIVE && (
            <button className="btn btn-secondary" onClick={handleArchiveClick}>
              📦 {t('properties.archive')}
            </button>
          )}
        </div>
      </div>

      {/* Property Information Grid */}
      <div className="property-info-section">
        <h2>{t('properties.propertyDetails')}</h2>
        
        <div className="info-grid">
          <div className="info-card">
            <h3>{t('properties.addressSection')}</h3>
            <div className="info-rows">
              <div className="info-row">
                <span className="label">{t('properties.street')}</span>
                <span className="value">{property.street}</span>
              </div>
              <div className="info-row">
                <span className="label">{t('properties.city')}</span>
                <span className="value">{property.city}</span>
              </div>
              <div className="info-row">
                <span className="label">{t('properties.postalCode')}</span>
                <span className="value">{property.postal_code}</span>
              </div>
            </div>
          </div>

          <div className="info-card">
            <h3>{t('properties.purchaseSection')}</h3>
            <div className="info-rows">
              <div className="info-row">
                <span className="label">{t('properties.purchaseDate')}</span>
                <span className="value">{formatDate(property.purchase_date)}</span>
              </div>
              <div className="info-row">
                <span className="label">{t('properties.purchasePrice')}</span>
                <span className="value">{formatCurrency(property.purchase_price)}</span>
              </div>
              <div className="info-row">
                <span className="label">{t('properties.buildingValue')}</span>
                <span className="value">{formatCurrency(property.building_value)}</span>
              </div>
              {property.land_value && (
                <div className="info-row">
                  <span className="label">{t('properties.landValue')}</span>
                  <span className="value">{formatCurrency(property.land_value)}</span>
                </div>
              )}
              {property.construction_year && (
                <div className="info-row">
                  <span className="label">{t('properties.constructionYear')}</span>
                  <span className="value">{property.construction_year}</span>
                </div>
              )}
            </div>
          </div>

          {isRental && (
            <div className="info-card">
              <h3>{t('properties.depreciationInfo')}</h3>
              <div className="info-rows">
                <div className="info-row">
                  <span className="label">{t('properties.depreciationRate')}</span>
                  <span className="value">{formatPercentage(property.depreciation_rate)}</span>
                </div>
                {property.property_type === PropertyType.MIXED_USE && (
                  <div className="info-row">
                    <span className="label">{t('properties.rentalPercentage')}</span>
                    <span className="value">{property.rental_percentage}%</span>
                  </div>
                )}
                <div className="info-row highlight">
                  <span className="label">{t('properties.accumulatedDepreciation')}</span>
                  <span className="value">{formatCurrency(accumulated)}</span>
                </div>
                <div className="info-row highlight">
                  <span className="label">{t('properties.remainingValue')}</span>
                  <span className="value">{formatCurrency(remaining)}</span>
                </div>
                {yearsRemaining !== null && (
                  <div className="info-row">
                    <span className="label">{t('properties.yearsRemaining')}</span>
                    <span className="value">
                      {yearsRemaining === 0
                        ? t('properties.fullyDepreciated')
                        : t('properties.yearsRemainingValue', { years: yearsRemaining })}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          {(property.grunderwerbsteuer || property.notary_fees || property.registry_fees) && (
            <div className="info-card">
              <h3>{t('properties.purchaseCostsSection')}</h3>
              <div className="info-rows">
                {property.grunderwerbsteuer && (
                  <div className="info-row">
                    <span className="label">{t('properties.grunderwerbsteuer')}</span>
                    <span className="value">{formatCurrency(property.grunderwerbsteuer)}</span>
                  </div>
                )}
                {property.notary_fees && (
                  <div className="info-row">
                    <span className="label">{t('properties.notaryFees')}</span>
                    <span className="value">{formatCurrency(property.notary_fees)}</span>
                  </div>
                )}
                {property.registry_fees && (
                  <div className="info-row">
                    <span className="label">{t('properties.registryFees')}</span>
                    <span className="value">{formatCurrency(property.registry_fees)}</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {property.sale_date && (
          <div className="sale-notice">
            📅 {t('properties.soldOn', { date: formatDate(property.sale_date) })}
          </div>
        )}
      </div>

      {/* Tax Warnings Section */}
      {warnings.length > 0 && (
        <div className="warnings-section">
          <h2>{t('properties.warnings.title')}</h2>
          <div className="warnings-list">
            {warnings.map((warning, index) => (
              <div key={index} className={`warning-card warning-${warning.level}`}>
                <div className="warning-header">
                  <span className="warning-icon">{getWarningIcon(warning.level)}</span>
                  <span className="warning-level">
                    {t(`properties.warnings.level.${warning.level}`)}
                  </span>
                  <span className="warning-year">
                    {warning.year}
                  </span>
                </div>
                <div className="warning-message">
                  {getWarningMessage(warning)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Historical Depreciation Backfill Section */}
      <HistoricalDepreciationBackfill
        property={property}
        onBackfillComplete={handleBackfillComplete}
      />

      {/* Property Reports Section */}
      <PropertyReports property={property} />

      {/* Linked Transactions Section */}
      <div className="transactions-section">
        <div className="section-header">
          <h2>{t('properties.linkedTransactions')}</h2>
          <button
            className="btn btn-primary"
            onClick={() => setShowLinkModal(true)}
          >
            🔗 {t('properties.linkTransaction')}
          </button>
        </div>

        {isLoadingTransactions ? (
          <div className="loading-state">
            <div className="loading-spinner"></div>
            <p>{t('common.loading')}</p>
          </div>
        ) : transactions.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📋</div>
            <h3>{t('properties.noTransactions')}</h3>
            <p>{t('properties.noTransactionsDescription')}</p>
          </div>
        ) : (
          <div className="transactions-by-year">
            {years.map((year) => {
              const yearData = transactionsByYear[year];
              return (
                <div key={year} className="year-section">
                  <div className="year-header">
                    <h3>{year}</h3>
                    <div className="year-summary">
                      <div className="summary-item income">
                        <span className="summary-label">{t('properties.rentalIncome')}</span>
                        <span className="summary-value">{formatCurrency(yearData.rental_income)}</span>
                      </div>
                      <div className="summary-item expense">
                        <span className="summary-label">{t('properties.expenses')}</span>
                        <span className="summary-value">{formatCurrency(yearData.expenses)}</span>
                      </div>
                      <div className="summary-item net">
                        <span className="summary-label">{t('properties.netIncome')}</span>
                        <span className={`summary-value ${yearData.net_income >= 0 ? 'positive' : 'negative'}`}>
                          {formatCurrency(yearData.net_income)}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="transactions-table">
                    <table>
                      <thead>
                        <tr>
                          <th>{t('transactions.date')}</th>
                          <th>{t('transactions.description')}</th>
                          <th>{t('transactions.category')}</th>
                          <th>{t('transactions.type')}</th>
                          <th className="amount-col">{t('transactions.amount')}</th>
                          <th className="actions-col">{t('common.actions')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {yearData.transactions.map((transaction) => (
                          <tr key={transaction.id} className={transaction.type}>
                            <td>{formatDate(transaction.date)}</td>
                            <td className="description-col">{transaction.description}</td>
                            <td>
                              <span className="category-badge">
                                {t(`transactions.categories.${transaction.category}`)}
                              </span>
                            </td>
                            <td>
                              <span className={`type-badge ${transaction.type}`}>
                                {t(`transactions.types.${transaction.type}`)}
                              </span>
                            </td>
                            <td className={`amount-col ${transaction.type}`}>
                              {formatCurrency(transaction.amount)}
                            </td>
                            <td className="actions-col">
                              <button
                                className="btn-icon btn-danger"
                                onClick={() => handleUnlinkTransaction(transaction.id)}
                                title={t('properties.unlinkTransaction')}
                              >
                                🔗✖️
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Link Transaction Modal (placeholder) */}
      {showLinkModal && (
        <div className="modal-overlay" onClick={() => setShowLinkModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{t('properties.linkTransaction')}</h2>
              <button className="modal-close" onClick={() => setShowLinkModal(false)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              <p>{t('properties.linkTransactionDescription')}</p>
              <p className="info-message">
                ℹ️ {t('properties.linkTransactionHint')}
              </p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowLinkModal(false)}>
                {t('common.close')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PropertyDetail;
