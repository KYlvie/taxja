import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { TransactionFilters as Filters, TransactionType } from '../../types/transaction';
import Select from '../common/Select';
import DateInput from '../common/DateInput';
import { getLocaleForLanguage } from '../../utils/locale';
import './TransactionFilters.css';

interface TransactionFiltersProps {
  filters: Filters;
  availableYears?: number[];
  onFilterChange: (filters: Filters) => void;
  onClear: () => void;
}

const TransactionFilters = ({
  filters,
  availableYears = [],
  onFilterChange,
  onClear,
}: TransactionFiltersProps) => {
  const { t, i18n } = useTranslation();
  const [localFilters, setLocalFilters] = useState<Filters>(filters);

  useEffect(() => {
    setLocalFilters(filters);
  }, [filters]);

  // Derive active year from date filters
  const activeYear = (() => {
    if (localFilters.start_date && localFilters.end_date) {
      const sy = localFilters.start_date.slice(0, 4);
      const ey = localFilters.end_date.slice(0, 4);
      if (sy === ey && localFilters.start_date === `${sy}-01-01` && localFilters.end_date === `${sy}-12-31`) {
        return Number(sy);
      }
    }
    return null;
  })();

  const handleYearClick = (year: number) => {
    if (activeYear === year) {
      // Toggle off — clear date filters
      const next = { ...localFilters, start_date: undefined, end_date: undefined };
      setLocalFilters(next);
      onFilterChange(next);
    } else {
      const next = { ...localFilters, start_date: `${year}-01-01`, end_date: `${year}-12-31` };
      setLocalFilters(next);
      onFilterChange(next);
    }
  };

  const handleChange = (key: keyof Filters, value: any) => {
    const newFilters = { ...localFilters, [key]: value || undefined };
    setLocalFilters(newFilters);
  };

  const handleApply = () => {
    onFilterChange(localFilters);
  };

  const handleClear = () => {
    setLocalFilters({});
    onClear();
  };

  return (
    <div className="transaction-filters">
      {availableYears.length > 0 ? (
        <div className="year-quick-filter">
          {availableYears.map((year) => (
            <button
              key={year}
              type="button"
              className={`year-pill ${activeYear === year ? 'active' : ''}`}
              onClick={() => handleYearClick(year)}
            >
              {year}
            </button>
          ))}
        </div>
      ) : null}

      <div className="filters-grid">
        <div className="filter-group">
          <label>{t('transactions.filters.startDate')}</label>
          <DateInput
            value={localFilters.start_date || ''}
            onChange={(val) => handleChange('start_date', val)}
            locale={getLocaleForLanguage(i18n.language)}
            todayLabel={String(t('common.today', 'Today'))}
          />
        </div>

        <div className="filter-group">
          <label>{t('transactions.filters.endDate')}</label>
          <DateInput
            value={localFilters.end_date || ''}
            onChange={(val) => handleChange('end_date', val)}
            locale={getLocaleForLanguage(i18n.language)}
            todayLabel={String(t('common.today', 'Today'))}
          />
        </div>

        <div className="filter-group">
          <label>{t('transactions.type')}</label>
          <Select value={localFilters.type || ''} onChange={v => handleChange('type', v)}
            placeholder={t('transactions.filters.allTypes')} size="sm"
            options={[
              { value: TransactionType.INCOME, label: t('transactions.types.income') },
              { value: TransactionType.EXPENSE, label: t('transactions.types.expense') },
              { value: TransactionType.ASSET_ACQUISITION, label: t('transactions.types.asset_acquisition') },
              { value: TransactionType.LIABILITY_DRAWDOWN, label: t('transactions.types.liability_drawdown') },
              { value: TransactionType.LIABILITY_REPAYMENT, label: t('transactions.types.liability_repayment') },
              { value: TransactionType.TAX_PAYMENT, label: t('transactions.types.tax_payment') },
              { value: TransactionType.TRANSFER, label: t('transactions.types.transfer') },
            ]} />
        </div>

        <div className="filter-group">
          <label>{t('transactions.needsReview')}</label>
          <Select
            value={localFilters.needs_review === undefined ? '' : localFilters.needs_review.toString()}
            onChange={v => handleChange('needs_review', v === '' ? undefined : v === 'true')}
            placeholder={t('transactions.filters.all')} size="sm"
            options={[
              { value: 'true', label: t('transactions.filters.needsReviewOnly') },
            ]} />
        </div>

        <div className="filter-group">
          <label>{t('transactions.deductible')}</label>
          <Select
            value={localFilters.is_deductible === undefined ? '' : localFilters.is_deductible.toString()}
            onChange={v => handleChange('is_deductible', v === '' ? undefined : v === 'true')}
            placeholder={t('transactions.filters.all')} size="sm"
            options={[
              { value: 'true', label: t('transactions.filters.deductibleOnly') },
              { value: 'false', label: t('transactions.filters.nonDeductible') },
            ]} />
        </div>

        <div className="filter-group">
          <label>{t('transactions.filters.recurring')}</label>
          <Select
            value={localFilters.is_recurring === undefined ? '' : localFilters.is_recurring.toString()}
            onChange={v => handleChange('is_recurring', v === '' ? undefined : v === 'true')}
            placeholder={t('transactions.filters.all')} size="sm"
            options={[
              { value: 'true', label: t('transactions.filters.recurringOnly') },
              { value: 'false', label: t('transactions.filters.oneTimeOnly') },
            ]} />
        </div>

        <div className="filter-group filter-group--full-row">
          <label>{t('transactions.filters.search')}</label>
          <input
            type="text"
            placeholder={t('transactions.filters.searchPlaceholder')}
            value={localFilters.search || ''}
            onChange={(e) => handleChange('search', e.target.value)}
          />
        </div>
      </div>

      <div className="filter-actions">
        <button className="btn btn-secondary" onClick={handleClear}>
          {t('transactions.filters.clear')}
        </button>
        <button className="btn btn-primary" onClick={handleApply}>
          {t('transactions.filters.apply')}
        </button>
      </div>
    </div>
  );
};

export default TransactionFilters;
