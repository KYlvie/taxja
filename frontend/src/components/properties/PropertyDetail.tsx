import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useConfirm } from '../../hooks/useConfirm';
import { Link } from 'react-router-dom';
import {
  AlertCircle,
  AlertTriangle,
  Archive,
  ArrowLeft,
  CalendarDays,
  FileSearch,
  FileText,
  Files,
  Info,
  PencilLine,
  Plus,
  ReceiptText,
  ScrollText,
  Trash2,
} from 'lucide-react';
import FuturisticIcon from '../common/FuturisticIcon';
import { Property, PropertyType, PropertyStatus, RentalContract } from '../../types/property';
import { Transaction, TransactionType } from '../../types/transaction';
import { propertyService } from '../../services/propertyService';
import { recurringService } from '../../services/recurringService';
import {
  formatCurrency as formatCurrencyForLanguage,
  formatDate as formatDateForLanguage,
  getLocaleForLanguage,
  normalizeLanguage,
  type SupportedLanguage,
} from '../../utils/locale';
import DateInput from '../common/DateInput';
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

const transactionSectionCopy = {
  de: {
    title: 'Einnahmen und Ausgaben dieser Immobilie',
    description:
      'Hier sehen Sie alle Buchungen, die bereits dieser Immobilie zugeordnet sind. Wenn Sie etwas aendern moechten, bearbeiten Sie die Buchung in der Transaktionsliste.',
    manageLinkLabel: 'Zur Transaktionsliste',
    emptyTitle: 'Noch keine Einnahmen oder Ausgaben erfasst',
    emptyDescription:
      'Sobald Sie in der Transaktionsliste Mieteinnahmen oder Immobilienkosten dieser Immobilie zuordnen, erscheinen sie hier automatisch.',
  },
  en: {
    title: 'Income and expenses for this property',
    description:
      'This section shows the entries already assigned to this property. If something is wrong, update the entry in your transactions list.',
    manageLinkLabel: 'Open transactions',
    emptyTitle: 'No income or expenses recorded yet',
    emptyDescription:
      'Once you assign rent income or property costs to this property in the transactions list, they will appear here automatically.',
  },
  zh: {
    title: '这套房产的收入与支出',
    description:
      '这里只展示已经关联到这套房产名下的收支记录。如果归属不对，请到交易记录里修改那一笔。',
    manageLinkLabel: '去交易记录查看',
    emptyTitle: '这套房产还没有收支记录',
    emptyDescription:
      '当你在交易记录里把租金收入或房产相关支出关联到这套房产后，这里会自动显示。',
  },
  fr: {
    title: 'Revenus et dépenses de ce bien',
    description:
      'Cette section affiche les écritures déjà associées à ce bien. Pour corriger une attribution, modifiez l\'écriture dans la liste des transactions.',
    manageLinkLabel: 'Ouvrir les transactions',
    emptyTitle: 'Aucun revenu ou dépense enregistré',
    emptyDescription:
      'Les revenus locatifs et les charges associés à ce bien apparaîtront ici automatiquement une fois attribués dans la liste des transactions.',
  },
  ru: {
    title: 'Доходы и расходы по этому объекту',
    description:
      'Здесь отображаются записи, уже привязанные к этому объекту. Для исправления отредактируйте запись в списке транзакций.',
    manageLinkLabel: 'Открыть транзакции',
    emptyTitle: 'Доходы и расходы ещё не записаны',
    emptyDescription:
      'Арендный доход и расходы по объекту появятся здесь автоматически после привязки в списке транзакций.',
  },
} as const;

const assetTransactionSectionCopy = {
  de: {
    title: 'Verknuepfte Buchungen dieses Wirtschaftsguts',
    description:
      'Hier sehen Sie bereits verknuepfte Buchungen und Abschreibungen dieses Assets. Anpassungen nehmen Sie in der Transaktionsliste vor.',
    manageLinkLabel: 'Zur Transaktionsliste',
    emptyTitle: 'Noch keine Buchungen zu diesem Asset',
    emptyDescription:
      'Sobald Anschaffung, AfA oder Folgekosten diesem Asset zugeordnet sind, erscheinen sie hier automatisch.',
  },
  en: {
    title: 'Linked entries for this asset',
    description:
      'This section shows transactions and depreciation entries already linked to this asset. Update them from the transactions list if needed.',
    manageLinkLabel: 'Open transactions',
    emptyTitle: 'No entries linked to this asset yet',
    emptyDescription:
      'Once acquisition, depreciation, or follow-up costs are linked to this asset, they will appear here automatically.',
  },
  zh: {
    title: '这项资产的关联记录',
    description:
      '这里展示已经关联到这项资产的购置、折旧和后续支出记录。如需调整，请到交易记录里修改。',
    manageLinkLabel: '去交易记录查看',
    emptyTitle: '这项资产还没有关联记录',
    emptyDescription:
      '当购置、折旧或后续成本关联到这项资产后，这里会自动显示。',
  },
  fr: {
    title: 'Écritures liées à cet actif',
    description:
      'Cette section affiche les transactions et amortissements déjà liés à cet actif. Modifiez-les depuis la liste des transactions si nécessaire.',
    manageLinkLabel: 'Ouvrir les transactions',
    emptyTitle: 'Aucune écriture liée à cet actif',
    emptyDescription:
      'Les acquisitions, amortissements et coûts de suivi liés à cet actif apparaîtront ici automatiquement.',
  },
  ru: {
    title: 'Связанные записи по этому активу',
    description:
      'Здесь отображаются транзакции и амортизация, уже привязанные к этому активу. При необходимости отредактируйте их в списке транзакций.',
    manageLinkLabel: 'Открыть транзакции',
    emptyTitle: 'Нет записей по этому активу',
    emptyDescription:
      'Приобретения, амортизация и последующие расходы по этому активу появятся здесь автоматически.',
  },
} as const;

type PropertySectionCopy = {
  title: string;
  description: string;
  manageLinkLabel: string;
  emptyTitle: string;
  emptyDescription: string;
};

const PropertyDetail = ({
  property,
  onEdit,
  onArchive,
  onBack,
}: PropertyDetailProps) => {
  const { t, i18n } = useTranslation();
  const { confirm: showConfirm } = useConfirm();
  const language = normalizeLanguage(i18n.language);
  const localizedText = <T extends string>(
    values: Partial<Record<SupportedLanguage, T>> & { de: T; en: T; zh: T }
  ) => values[language] ?? values.en;
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [isLoadingTransactions, setIsLoadingTransactions] = useState(false);
  const [warnings, setWarnings] = useState<PropertyWarning[]>([]);
  const [rentalContracts, setRentalContracts] = useState<RentalContract[]>([]);
  const [isLoadingContracts, setIsLoadingContracts] = useState(false);
  const [editingPercentages, setEditingPercentages] = useState<Record<number, string>>({});
  const [savingContractId, setSavingContractId] = useState<number | null>(null);
  const [editingContractId, setEditingContractId] = useState<number | null>(null);
  const [editingContractData, setEditingContractData] = useState<{
    amount: string;
    start_date: string;
    end_date: string;
    is_active: boolean;
  }>({ amount: '', start_date: '', end_date: '', is_active: true });
  const isRealEstate = !property.asset_type || property.asset_type === 'real_estate';
  const sectionCopySource: Partial<Record<SupportedLanguage, PropertySectionCopy>> =
    isRealEstate ? transactionSectionCopy : assetTransactionSectionCopy;
  const sectionCopy = sectionCopySource[language] ?? sectionCopySource.en!;
  const displayName = isRealEstate
    ? property.address
    : property.name || t(`properties.assetTypes.${property.asset_type}`, property.asset_type || 'Asset');
  const assetTypeLabel = property.asset_type
    ? t(`properties.assetTypes.${property.asset_type}`, property.asset_type)
    : t('properties.assetDetails.asset', localizedText({ de: 'Asset', en: 'Asset', zh: '资产' }));

  useEffect(() => {
    loadTransactions();
    if (isRealEstate) {
      loadWarnings();
      loadRentalContracts();
    } else {
      setWarnings([]);
      setRentalContracts([]);
    }
  }, [property.id, isRealEstate]);

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

  const loadRentalContracts = async () => {
    setIsLoadingContracts(true);
    try {
      const data = await propertyService.getRentalContracts(property.id);
      setRentalContracts(data);
      const initial: Record<number, string> = {};
      data.forEach((c) => {
        if (c.unit_percentage != null) {
          initial[c.id] = String(c.unit_percentage);
        }
      });
      setEditingPercentages(initial);
    } catch (error) {
      console.error('Failed to load rental contracts:', error);
    } finally {
      setIsLoadingContracts(false);
    }
  };

  const saveUnitPercentage = async (contractId: number) => {
    const val = editingPercentages[contractId];
    if (!val || isNaN(Number(val)) || Number(val) <= 0 || Number(val) > 100) return;
    setSavingContractId(contractId);
    try {
      await recurringService.update(contractId, { unit_percentage: Number(val) } as any);
      await loadRentalContracts();
    } catch (error) {
      console.error('Failed to save unit percentage:', error);
    } finally {
      setSavingContractId(null);
    }
  };

  const startEditContract = (contract: RentalContract) => {
    setEditingContractId(contract.id);
    setEditingContractData({
      amount: String(contract.amount),
      start_date: contract.start_date || '',
      end_date: contract.end_date || '',
      is_active: contract.is_active,
    });
  };

  const cancelEditContract = () => {
    setEditingContractId(null);
  };

  const saveEditContract = async (contractId: number) => {
    setSavingContractId(contractId);
    try {
      const updateData: any = {};
      const orig = rentalContracts.find((c) => c.id === contractId);
      if (!orig) return;

      const newAmount = Number(editingContractData.amount);
      if (newAmount > 0 && newAmount !== orig.amount) {
        updateData.amount = newAmount;
      }
      if (editingContractData.start_date && editingContractData.start_date !== orig.start_date) {
        updateData.start_date = editingContractData.start_date;
      }
      // Allow clearing end_date (set to null for indefinite)
      if (editingContractData.end_date !== (orig.end_date || '')) {
        updateData.end_date = editingContractData.end_date || null;
      }
      if (editingContractData.is_active !== orig.is_active) {
        updateData.is_active = editingContractData.is_active;
      }

      if (Object.keys(updateData).length > 0) {
        await recurringService.update(contractId, updateData);
      }
      setEditingContractId(null);
      await loadRentalContracts();
      // Recalculate after edit
      try {
        await propertyService.recalculateRental(property.id);
        onEdit(property);
      } catch (_) { /* ignore */ }
    } catch (error) {
      console.error('Failed to save contract:', error);
    } finally {
      setSavingContractId(null);
    }
  };

  const handleDeleteContract = async (contractId: number) => {
    const ok = await showConfirm(t('properties.rentalContracts.confirmDelete'), { variant: 'warning' });
    if (!ok) return;
    try {
      await recurringService.delete(contractId);
      await loadRentalContracts();
      try {
        await propertyService.recalculateRental(property.id);
        onEdit(property);
      } catch (_) { /* ignore */ }
    } catch (error) {
      console.error('Failed to delete contract:', error);
    }
  };


  const getWarningMessage = (warning: PropertyWarning): string => {
    const lang = language;
    if (lang === 'de') return warning.message_de;
    if (lang === 'zh') return warning.message_zh;
    return warning.message_en;
  };

  const getWarningIcon = (level: string) => {
    switch (level) {
      case 'error':
        return { icon: AlertCircle, tone: 'rose' as const };
      case 'warning':
        return { icon: AlertTriangle, tone: 'amber' as const };
      case 'info':
        return { icon: Info, tone: 'cyan' as const };
      default:
        return { icon: Info, tone: 'cyan' as const };
    }
  };

  const formatCurrency = (amount: number) => {
    return formatCurrencyForLanguage(amount, language);
  };

  const formatDate = (dateString: string) => {
    return formatDateForLanguage(dateString, language, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
  };

  const formatPercentage = (rate: number) => {
    return `${(rate * 100).toFixed(2)}%`;
  };

  const formatAssetTaxValue = (group: string, value?: string | null) => {
    if (!value) return '-';
    return t(`properties.assetDetails.${group}.${value}`, value);
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

  const handleArchiveClick = async () => {
    const confirmMessage = t('properties.confirmArchive', {
      address: displayName,
    });
    
    const ok = await showConfirm(confirmMessage, { variant: 'warning', confirmText: t('properties.archive') });
    if (ok) {
      onArchive(property);
    }
  };

  const transactionsByYear = groupTransactionsByYear();
  const years = Object.keys(transactionsByYear).sort((a, b) => parseInt(b) - parseInt(a));
  const accumulated = calculateAccumulatedDepreciation();
  const remaining = calculateRemainingValue();
  const yearsRemaining = calculateYearsRemaining();
  const isRental = isRealEstate && property.property_type !== PropertyType.OWNER_OCCUPIED;
  const assetAccumulated = property.accumulated_depreciation ?? accumulated;
  const assetRemaining = property.remaining_value ?? Math.max(0, property.building_value - assetAccumulated);
  const assetAnnualDepreciation = property.annual_depreciation ?? (property.building_value * property.depreciation_rate);
  const assetUsageLabel = property.business_use_percentage != null
    ? `${Number(property.business_use_percentage).toFixed(0)}%`
    : '-';
  const openEndedLabel = localizedText({
    de: 'Unbefristet',
    en: 'Open-ended',
    zh: '长期',
  });

  const purchaseDocumentUploadLink = `/documents?property_id=${property.id}&type=purchase_contract`;
  const documentsHubLink = `/documents?property_id=${property.id}`;
  const linkedPurchaseDocumentLabel = isRealEstate
    ? t('properties.documents.viewPurchaseContract', '\u67e5\u770b\u8d2d\u623f\u5408\u540c')
    : t('properties.documents.viewSourceDocument', '\u67e5\u770b\u8d2d\u7f6e\u6587\u4ef6');
  const uploadPurchaseDocumentLabel = isRealEstate
    ? t('properties.documents.uploadPurchaseContract', '\u4e0a\u4f20\u8d2d\u623f\u5408\u540c')
    : t('properties.documents.uploadSourceDocument', '\u4e0a\u4f20\u8d2d\u7f6e\u6587\u4ef6');
  const showRentalDocumentAction = isRealEstate && (isRental || Boolean(property.mietvertrag_document_id));
  const rentalDocumentLabel = property.mietvertrag_document_id
    ? t('properties.documents.viewRentalContract', '\u67e5\u770b\u79df\u8d41\u5408\u540c')
    : t('properties.documents.addRentalContract', '\u6dfb\u52a0\u5408\u540c');
  const rentalDocumentLink = property.mietvertrag_document_id
    ? `/documents/${property.mietvertrag_document_id}`
    : `/documents?property_id=${property.id}&type=rental_contract`;

  return (
    <div className="property-detail">
      {/* Breadcrumb Navigation */}
      <div className="breadcrumb">
        <button className="breadcrumb-link" onClick={onBack}>
          <FuturisticIcon icon={ArrowLeft} tone="slate" size="xs" />
          <span>{t('properties.title')}</span>
        </button>
        <span className="breadcrumb-separator">/</span>
        <span className="breadcrumb-current">{displayName}</span>
      </div>

      {/* Property Header */}
      <div className="property-detail-header">
        <div className="header-content">
          <h1>{displayName}</h1>
          <div className="property-badges">
            <span className={`status-badge ${property.status}`}>
              {t(`properties.status.${property.status}`)}
            </span>
            {isRealEstate ? (
              <span className={`type-badge ${property.property_type}`}>
                {t(`properties.types.${property.property_type}`)}
              </span>
            ) : (
              <span className="type-badge asset">
                {assetTypeLabel}
              </span>
            )}
          </div>
        </div>
        <div className="header-actions">
          <div className="header-action-group">
            {property.kaufvertrag_document_id ? (
              <Link className="btn btn-secondary btn-icon" to={`/documents/${property.kaufvertrag_document_id}`}>
                <FuturisticIcon icon={FileSearch} tone="cyan" size="xs" />
                <span>{linkedPurchaseDocumentLabel}</span>
              </Link>
            ) : (
              <Link className="btn btn-primary btn-icon" to={purchaseDocumentUploadLink}>
                <FuturisticIcon icon={ReceiptText} tone="violet" size="xs" />
                <span>{uploadPurchaseDocumentLabel}</span>
              </Link>
            )}

            {showRentalDocumentAction ? (
              <Link className="btn btn-secondary btn-icon" to={rentalDocumentLink}>
                <FuturisticIcon
                  icon={property.mietvertrag_document_id ? ScrollText : Files}
                  tone={property.mietvertrag_document_id ? 'emerald' : 'slate'}
                  size="xs"
                />
                <span>{rentalDocumentLabel}</span>
              </Link>
            ) : !isRealEstate ? (
              <Link className="btn btn-secondary btn-icon" to={documentsHubLink}>
                <FuturisticIcon icon={Files} tone="slate" size="xs" />
                <span>{t('properties.documents.manageFiles', '\u7ba1\u7406\u5173\u8054\u6587\u4ef6')}</span>
              </Link>
            ) : null}
          </div>
          <button className="btn btn-secondary btn-icon" onClick={() => onEdit(property)}>
            <FuturisticIcon icon={PencilLine} tone="slate" size="xs" />
            <span>{t('common.edit')}</span>
          </button>
          {property.status === PropertyStatus.ACTIVE && (
            <button className="btn btn-secondary btn-icon" onClick={handleArchiveClick}>
              <FuturisticIcon icon={Archive} tone="slate" size="xs" />
              <span>{isRealEstate ? t('properties.sellProperty') : t('properties.disposeAsset')}</span>
            </button>
          )}
        </div>
      </div>

      {/* Placeholder property warning */}
      {property.purchase_price <= 0.01 && (
        <div className="warning-banner" style={{ margin: '0 0 16px', padding: '12px 16px', background: '#fef3c7', border: '1px solid #f59e0b', borderRadius: '8px', fontSize: '0.9rem', color: '#92400e', display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
          <span>⚠️</span>
          <div>
            <strong>{t('properties.placeholderWarning.title', 'Incomplete data')}</strong>
            <p style={{ margin: '4px 0 0' }}>{t('properties.placeholderWarning.message', 'This property was auto-created from a rental contract with placeholder values. Please upload the purchase contract or edit the property to add the real purchase price, building value, and construction year for accurate depreciation calculations.')}</p>
          </div>
        </div>
      )}

      {/* Property Information Grid */}
      <div className="property-info-section">
        <h2>
          {isRealEstate
            ? t('properties.propertyDetails')
            : t(
                'properties.assetDetails.title',
                localizedText({ de: 'Asset-Details', en: 'Asset details', zh: '资产详情' })
              )}
        </h2>
        
        <div className="info-grid">
          {isRealEstate ? (
            <>
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
            </>
          ) : (
            <>
              <div className="info-card">
                <h3>{t('properties.assetDetails.acquisition', localizedText({ de: 'Anschaffung', en: 'Acquisition', zh: '购置信息' }))}</h3>
                <div className="info-rows">
                  <div className="info-row">
                    <span className="label">{t('properties.assetDetails.assetType', localizedText({ de: 'Assettyp', en: 'Asset type', zh: '资产类型' }))}</span>
                    <span className="value">{assetTypeLabel}</span>
                  </div>
                  {property.sub_category && (
                    <div className="info-row">
                      <span className="label">{t('properties.assetDetails.subCategory', localizedText({ de: 'Unterkategorie', en: 'Sub-category', zh: '子类型' }))}</span>
                      <span className="value">{property.sub_category}</span>
                    </div>
                  )}
                  {property.supplier && (
                    <div className="info-row">
                      <span className="label">{t('properties.assetDetails.supplier', localizedText({ de: 'Lieferant', en: 'Supplier', zh: '供应商' }))}</span>
                      <span className="value">{property.supplier}</span>
                    </div>
                  )}
                  <div className="info-row">
                    <span className="label">{t('properties.purchaseDate')}</span>
                    <span className="value">{formatDate(property.purchase_date)}</span>
                  </div>
                  <div className="info-row">
                    <span className="label">{t('properties.purchasePrice')}</span>
                    <span className="value">{formatCurrency(property.purchase_price)}</span>
                  </div>
                  {property.put_into_use_date && (
                    <div className="info-row">
                      <span className="label">{t('properties.assetDetails.putIntoUseDate', localizedText({ de: 'Inbetriebnahme', en: 'Put into use', zh: '投入使用日期' }))}</span>
                      <span className="value">{formatDate(property.put_into_use_date)}</span>
                    </div>
                  )}
                  {property.acquisition_kind && (
                    <div className="info-row">
                      <span className="label">{t('properties.assetDetails.acquisitionKind', localizedText({ de: 'Erwerbsart', en: 'Acquisition kind', zh: '取得方式' }))}</span>
                      <span className="value">{formatAssetTaxValue('acquisitionKinds', property.acquisition_kind)}</span>
                    </div>
                  )}
                </div>
              </div>

              <div className="info-card">
                <h3>{t('properties.assetDetails.taxHandling', localizedText({ de: 'Steuerliche Behandlung', en: 'Tax handling', zh: '税务处理' }))}</h3>
                <div className="info-rows">
                  <div className="info-row">
                    <span className="label">{t('properties.assetDetails.businessUse', localizedText({ de: 'Betriebliche Nutzung', en: 'Business use', zh: '业务使用比例' }))}</span>
                    <span className="value">{assetUsageLabel}</span>
                  </div>
                  {property.comparison_basis && (
                    <div className="info-row">
                      <span className="label">{t('properties.assetDetails.comparisonBasis', localizedText({ de: 'GWG-Vergleichsbasis', en: 'GWG comparison basis', zh: 'GWG 比较基数' }))}</span>
                      <span className="value">{formatAssetTaxValue('comparisonBasisOptions', property.comparison_basis)}</span>
                    </div>
                  )}
                  {property.comparison_amount != null && (
                    <div className="info-row">
                      <span className="label">{t('properties.assetDetails.comparisonAmount', localizedText({ de: 'Vergleichsbetrag', en: 'Comparison amount', zh: '比较金额' }))}</span>
                      <span className="value">{formatCurrency(property.comparison_amount)}</span>
                    </div>
                  )}
                  <div className="info-row">
                    <span className="label">{t('properties.assetDetails.depreciationMethod', localizedText({ de: 'Abschreibungsmethode', en: 'Depreciation method', zh: '折旧方式' }))}</span>
                    <span className="value">
                      {property.gwg_elected
                        ? t('properties.assetDetails.gwg', localizedText({ de: 'GWG Sofortaufwand', en: 'GWG immediate expense', zh: 'GWG 一次性费用化' }))
                          : formatAssetTaxValue('depreciationMethods', property.depreciation_method)}
                    </span>
                  </div>
                  {property.degressive_afa_rate != null && (
                    <div className="info-row">
                      <span className="label">{t('properties.assetDetails.degressiveRate', localizedText({ de: 'Degressive AfA', en: 'Declining-balance rate', zh: '递减折旧比例' }))}</span>
                      <span className="value">{formatPercentage(property.degressive_afa_rate)}</span>
                    </div>
                  )}
                  {property.vat_recoverable_status && (
                    <div className="info-row">
                      <span className="label">{t('properties.assetDetails.vatStatus', localizedText({ de: 'Vorsteuerstatus', en: 'VAT recovery status', zh: '进项税预判' }))}</span>
                      <span className="value">{formatAssetTaxValue('vatStatuses', property.vat_recoverable_status)}</span>
                    </div>
                  )}
                  <div className="info-row">
                    <span className="label">{t('properties.assetDetails.ifb', 'IFB')}</span>
                    <span className="value">
                      {property.ifb_candidate
                        ? property.ifb_rate != null
                          ? `${property.ifb_rate}%`
                          : t('properties.assetDetails.ifbCandidate', localizedText({ de: 'Kandidat', en: 'Candidate', zh: '候选' }))
                        : t('properties.assetDetails.ifbNotEligible', localizedText({ de: 'Aktuell nicht anwendbar', en: 'Not applicable right now', zh: '当前不适用' }))}
                    </span>
                  </div>
                  {property.income_tax_cost_cap != null && (
                    <div className="info-row">
                      <span className="label">{t('properties.assetDetails.incomeTaxCap', localizedText({ de: 'ESt-Kostenobergrenze', en: 'Income tax cap', zh: '所得税可计提上限' }))}</span>
                      <span className="value">{formatCurrency(property.income_tax_cost_cap)}</span>
                    </div>
                  )}
                </div>
              </div>

              <div className="info-card">
                <h3>{t('properties.assetDetails.depreciation', localizedText({ de: 'Abschreibungsuebersicht', en: 'Depreciation summary', zh: '折旧摘要' }))}</h3>
                <div className="info-rows">
                  {property.useful_life_years != null && (
                    <div className="info-row">
                      <span className="label">{t('properties.assetDetails.usefulLife', localizedText({ de: 'Nutzungsdauer', en: 'Useful life', zh: '使用年限' }))}</span>
                      <span className="value">{property.useful_life_years} {t('properties.assetDetails.years', localizedText({ de: 'Jahre', en: 'years', zh: '年' }))}</span>
                    </div>
                  )}
                  <div className="info-row highlight">
                    <span className="label">{t('properties.accumulatedDepreciation')}</span>
                    <span className="value">{formatCurrency(assetAccumulated)}</span>
                  </div>
                  <div className="info-row highlight">
                    <span className="label">{t('properties.remainingValue')}</span>
                    <span className="value">{formatCurrency(assetRemaining)}</span>
                  </div>
                  <div className="info-row highlight">
                    <span className="label">{t('properties.assetDetails.annualDepreciation', localizedText({ de: 'Jaehrliche Abschreibung', en: 'Annual depreciation', zh: '年度折旧' }))}</span>
                    <span className="value">{formatCurrency(assetAnnualDepreciation)}</span>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        {property.sale_date && (
          <div className="sale-notice">
            <FuturisticIcon icon={CalendarDays} tone="amber" size="xs" />
            <span>{t('properties.soldOn', { date: formatDate(property.sale_date) })}</span>
            {property.sale_price != null && (
              <span style={{ marginLeft: 8 }}>({t('properties.salePrice', 'Sale price')}: {formatCurrency(property.sale_price)})</span>
            )}
          </div>
        )}

        {property.disposal_reason && (
          <div className="sale-notice">
            <FuturisticIcon icon={Info} tone="slate" size="xs" />
            <span>{t(`properties.disposalReasons.${property.disposal_reason}`, property.disposal_reason)}</span>
          </div>
        )}
      </div>

      {/* Tax Warnings Section */}
      {isRealEstate && warnings.length > 0 && (
        <div className="warnings-section">
          <h2>{t('properties.warnings.title')}</h2>
          <div className="warnings-list">
            {warnings.map((warning, index) => {
              const warningIcon = getWarningIcon(warning.level);
              return (
                <div key={index} className={`warning-card warning-${warning.level}`}>
                  <div className="warning-header">
                    <span className="warning-icon">
                      <FuturisticIcon icon={warningIcon.icon} tone={warningIcon.tone} size="xs" />
                    </span>
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
              );
            })}
          </div>
        </div>
      )}

      {/* Rental Contracts Section */}
      {isRealEstate && (
      <div className="rental-contracts-section">
        <div className="section-header">
          <h2>{t('properties.rentalContracts.title')}</h2>
          <div style={{ display: 'flex', gap: '8px' }}>
            <Link
              to={`/documents?property_id=${property.id}&type=rental_contract`}
              className="btn btn-primary btn-sm btn-icon"
              style={{ textDecoration: 'none' }}
            >
              <FuturisticIcon icon={Plus} tone="violet" size="xs" />
              <span>{t('properties.rentalContracts.addContract')}</span>
            </Link>
          </div>
        </div>

        {isLoadingContracts ? (
          <div className="loading-state">
            <div className="loading-spinner"></div>
            <p>{t('common.loading')}</p>
          </div>
        ) : rentalContracts.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">
              <FuturisticIcon icon={ScrollText} tone="slate" size="lg" />
            </div>
            <p>{t('properties.rentalContracts.emptyUploadHint', localizedText({ de: 'Noch kein Mietvertrag vorhanden. Laden Sie den Vertrag hoch, damit Taxja ihn automatisch erkennt und anlegt.', en: 'No rental contract yet. Upload the contract and Taxja will detect and create it automatically.', zh: '暂时没有租赁合同。请上传租赁合同文件，系统会自动识别并创建。' }))}</p>
            <Link to={`/documents?property_id=${property.id}&type=rental_contract`} className="btn btn-primary btn-sm btn-icon" style={{ marginTop: '8px', textDecoration: 'none' }}>
              <FuturisticIcon icon={ReceiptText} tone="violet" size="xs" />
              <span>{t('properties.rentalContracts.uploadContract', localizedText({ de: 'Mietvertrag hochladen', en: 'Upload rental contract', zh: '上传租赁合同' }))}</span>
            </Link>
          </div>
        ) : (
          <>
            {rentalContracts.length > 0 && rentalContracts.every(
              (c) => !c.is_active || (c.end_date && new Date(c.end_date) < new Date())
            ) && (
              <div className="warning-banner" style={{ marginBottom: '12px', padding: '10px 14px', background: '#fef3c7', border: '1px solid #f59e0b', borderRadius: '8px', fontSize: '0.9rem', color: '#92400e' }}>
                <span className="warning-banner-icon">
                  <FuturisticIcon icon={AlertTriangle} tone="amber" size="xs" />
                </span>
                {t('properties.rentalContracts.allExpiredWarning', localizedText({ de: 'Alle Mietvertraege sind abgelaufen. Diese Immobilie wurde automatisch auf Eigennutzung umgestellt. Wenn Sie weiter vermieten, fuegen Sie bitte einen neuen Mietvertrag hinzu.', en: 'All rental contracts have expired. This property has been switched back to owner-occupied status automatically. Add a new rental contract if you want to keep renting it out.', zh: '所有租赁合同都已过期，该房产已自动切换为自住状态。如需继续出租，请添加新的租赁合同。' }))}
              </div>
            )}
            <div className="rental-contracts-list">
              {rentalContracts.map((contract) => {
                const isExpired = !contract.is_active || (contract.end_date && new Date(contract.end_date) < new Date());
                const isEditing = editingContractId === contract.id;
                return (
                  <div key={contract.id} className={`rental-contract-card ${isExpired ? 'expired' : 'active'}`}>
                    <div className="contract-header">
                      <span className="contract-description">{contract.description}</span>
                      <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                        <span className={`contract-status-badge ${isExpired ? 'expired' : 'active'}`}>
                          {isExpired ? t('properties.rentalContracts.expired') : t('properties.rentalContracts.active')}
                        </span>
                        {!isEditing && (
                          <>
                            {contract.source_document_id ? (
                              <Link
                                to={`/documents/${contract.source_document_id}`}
                                className="btn btn-secondary btn-sm btn-icon"
                                style={{ padding: '2px 8px', fontSize: '0.75rem', textDecoration: 'none' }}
                                title={t('properties.rentalContracts.viewLinkedDocument', localizedText({ de: 'Verknuepften Vertrag ansehen', en: 'View linked contract', zh: '查看关联合同' }))}
                              >
                                <FuturisticIcon icon={FileSearch} tone="cyan" size="xs" />
                              </Link>
                            ) : (
                              <button
                                className="btn btn-secondary btn-sm btn-icon"
                                style={{ padding: '2px 8px', fontSize: '0.75rem' }}
                                onClick={() => startEditContract(contract)}
                                title={t('common.edit')}
                                aria-label={t('common.edit')}
                              >
                                <FuturisticIcon icon={PencilLine} tone="slate" size="xs" />
                              </button>
                            )}
                            <button
                              className="btn btn-secondary btn-sm btn-icon"
                              style={{ padding: '2px 8px', fontSize: '0.75rem' }}
                              onClick={() => handleDeleteContract(contract.id)}
                              title={t('common.delete')}
                              aria-label={t('common.delete')}
                            >
                              <FuturisticIcon icon={Trash2} tone="rose" size="xs" />
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="contract-details">
                      {isEditing ? (
                        <>
                          <div className="contract-detail-row">
                            <span className="label">{t('properties.rentalContracts.rent')}</span>
                            <input
                              type="number"
                              min="0.01"
                              step="0.01"
                              className="unit-percentage-input"
                              style={{ width: '120px' }}
                              value={editingContractData.amount}
                              onChange={(e) => setEditingContractData((p) => ({ ...p, amount: e.target.value }))}
                            />
                          </div>
                          <div className="contract-detail-row">
                            <span className="label">{t('properties.rentalContracts.startDate')}</span>
                            <DateInput
                              className="unit-percentage-input"
                              value={editingContractData.start_date}
                              onChange={(val) => setEditingContractData((p) => ({ ...p, start_date: val }))}
                              locale={getLocaleForLanguage(i18n.language)}
                              todayLabel={String(t('common.today', 'Today'))}
                            />
                          </div>
                          <div className="contract-detail-row">
                            <span className="label">{t('properties.rentalContracts.endDate')}</span>
                            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                              <DateInput
                                className="unit-percentage-input"
                                value={editingContractData.end_date}
                                onChange={(val) => setEditingContractData((p) => ({ ...p, end_date: val }))}
                                locale={getLocaleForLanguage(i18n.language)}
                                todayLabel={String(t('common.today', 'Today'))}
                              />
                              {editingContractData.end_date && (
                                <button
                                  className="btn btn-secondary btn-sm"
                                  style={{ padding: '2px 8px', fontSize: '0.7rem' }}
                                  onClick={() => setEditingContractData((p) => ({ ...p, end_date: '' }))}
                                >
                                  {t('properties.rentalContracts.clearEndDate')}
                                </button>
                              )}
                            </div>
                          </div>
                          <div className="contract-detail-row">
                            <span className="label">{t('properties.rentalContracts.status')}</span>
                            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                              <input
                                type="checkbox"
                                checked={editingContractData.is_active}
                                onChange={(e) => setEditingContractData((p) => ({ ...p, is_active: e.target.checked }))}
                              />
                              {editingContractData.is_active ? t('properties.rentalContracts.active') : t('properties.rentalContracts.expired')}
                            </label>
                          </div>
                          <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                            <button
                              className="btn btn-primary btn-sm"
                              disabled={savingContractId === contract.id}
                              onClick={() => saveEditContract(contract.id)}
                            >
                              {savingContractId === contract.id ? '...' : t('properties.rentalContracts.save')}
                            </button>
                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={cancelEditContract}
                            >
                              {t('common.cancel')}
                            </button>
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="contract-detail-row">
                            <span className="label">{t('properties.rentalContracts.rent')}</span>
                            <span className="value">{formatCurrency(contract.amount)}</span>
                          </div>
                          <div className="contract-detail-row">
                            <span className="label">{t('properties.rentalContracts.period')}</span>
                            <span className="value">
                              {contract.start_date ? formatDate(contract.start_date) : '-'}
                              {' -> '}
                              {contract.end_date ? formatDate(contract.end_date) : openEndedLabel}
                            </span>
                          </div>
                          {contract.source_document_id && (
                            <div className="contract-detail-row" style={{ borderTop: '1px dashed #e5e7eb', paddingTop: '6px', marginTop: '4px' }}>
                              <span className="label" />
                              <Link
                                to={`/documents/${contract.source_document_id}`}
                                style={{ fontSize: '0.8rem', color: '#4f46e5', textDecoration: 'none' }}
                              >
                                <span className="inline-link-icon">
                                  <FuturisticIcon icon={FileText} tone="cyan" size="xs" />
                                </span>
                                {t('properties.rentalContracts.editFromDocument', localizedText({ de: 'Bei Aenderungen zum verknuepften Vertrag wechseln', en: 'Open the linked contract to make changes', zh: '如需修改，请前往关联合同' }))}
                              </Link>
                            </div>
                          )}
                          <div className="contract-detail-row unit-percentage-row">
                            <span className="label">{t('properties.rentalContracts.unitPercentage')}</span>
                            <div className="unit-percentage-input-group">
                              <input
                                type="number"
                                min="0.01"
                                max="100"
                                step="0.01"
                                className="unit-percentage-input"
                                placeholder={t('properties.rentalContracts.unitPercentagePlaceholder')}
                                value={editingPercentages[contract.id] ?? ''}
                                onChange={(e) =>
                                  setEditingPercentages((prev) => ({ ...prev, [contract.id]: e.target.value }))
                                }
                              />
                              <span className="unit-percentage-suffix">%</span>
                              <button
                                className="btn btn-primary btn-sm"
                                disabled={savingContractId === contract.id}
                                onClick={() => saveUnitPercentage(contract.id)}
                              >
                                {savingContractId === contract.id ? '...' : t('properties.rentalContracts.save')}
                              </button>
                            </div>
                            {contract.unit_percentage == null && (
                              <div className="percentage-hint">
                                <span className="inline-link-icon">
                                  <FuturisticIcon icon={AlertTriangle} tone="amber" size="xs" />
                                </span>
                                {t('properties.rentalContracts.setPercentageHint')}
                              </div>
                            )}
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="rental-total-summary">
              <span className="label">{t('properties.rentalContracts.totalRentalPercentage')}</span>
              <span className="value">{property.rental_percentage}%</span>
            </div>
          </>
        )}
      </div>
      )}

      {/* Linked Transactions Section */}
      <div className="transactions-section">
        <div className="section-header">
          <div className="section-header-copy">
            <h2>{sectionCopy.title}</h2>
            <p className="section-description">
              {sectionCopy.description}{' '}
              <Link to="/transactions">{sectionCopy.manageLinkLabel}</Link>
            </p>
          </div>
        </div>

        {isLoadingTransactions ? (
          <div className="loading-state">
            <div className="loading-spinner"></div>
            <p>{t('common.loading')}</p>
          </div>
        ) : transactions.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">
              <FuturisticIcon icon={Files} tone="slate" size="lg" />
            </div>
            <h3>{sectionCopy.emptyTitle}</h3>
            <p>{sectionCopy.emptyDescription}</p>
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
    </div>
  );
};

export default PropertyDetail;
