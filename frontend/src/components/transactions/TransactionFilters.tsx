import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { TransactionFilters as Filters, TransactionType } from '../../types/transaction';
import './TransactionFilters.css';

interface TransactionFiltersProps {
  filters: Filters;
  onFilterChange: (filters: Filters) => void;
  onClear: () => void;
}

const TransactionFilters = ({
  filters,
  onFilterChange,
  onClear,
}: TransactionFiltersProps) => {
  const { t } = useTranslation();
  const [localFilters, setLocalFilters] = useState<Filters>(filters);
  const currentYear = new Date().getFullYear();
  const yearOptions = Array.from({ length: 6 }, (_, i) => currentYear - i);

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
      <div className="year-quick-filter">
        {yearOptions.map((year) => (
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

      <div className="filters-grid">
        <div className="filter-group">
          <label>{t('transactions.filters.startDate')}</label>
          <input
            type="date"
            value={localFilters.start_date || ''}
            onChange={(e) => handleChange('start_date', e.target.value)}
          />
        </div>

        <div className="filter-group">
          <label>{t('transactions.filters.endDate')}</label>
          <input
            type="date"
            value={localFilters.end_date || ''}
            onChange={(e) => handleChange('end_date', e.target.value)}
          />
        </div>

        <div className="filter-group">
          <label>{t('transactions.type')}</label>
          <select
            value={localFilters.type || ''}
            onChange={(e) => handleChange('type', e.target.value)}
          >
            <option value="">{t('transactions.filters.allTypes')}</option>
            <option value={TransactionType.INCOME}>
              {t('transactions.types.income')}
            </option>
            <option value={TransactionType.EXPENSE}>
              {t('transactions.types.expense')}
            </option>
          </select>
        </div>

        <div className="filter-group">
          <label>{t('transactions.filters.search')}</label>
          <input
            type="text"
            placeholder={t('transactions.filters.searchPlaceholder')}
            value={localFilters.search || ''}
            onChange={(e) => handleChange('search', e.target.value)}
          />
        </div>

        <div className="filter-group">
          <label>{t('transactions.deductible')}</label>
          <select
            value={
              localFilters.is_deductible === undefined
                ? ''
                : localFilters.is_deductible.toString()
            }
            onChange={(e) =>
              handleChange(
                'is_deductible',
                e.target.value === '' ? undefined : e.target.value === 'true'
              )
            }
          >
            <option value="">{t('transactions.filters.all')}</option>
            <option value="true">{t('transactions.filters.deductibleOnly')}</option>
            <option value="false">{t('transactions.filters.nonDeductible')}</option>
          </select>
        </div>

        <div className="filter-group">
          <label>{t('transactions.filters.recurring')}</label>
          <select
            value={
              localFilters.is_recurring === undefined
                ? ''
                : localFilters.is_recurring.toString()
            }
            onChange={(e) =>
              handleChange(
                'is_recurring',
                e.target.value === '' ? undefined : e.target.value === 'true'
              )
            }
          >
            <option value="">{t('transactions.filters.all')}</option>
            <option value="true">{t('transactions.filters.recurringOnly')}</option>
            <option value="false">{t('transactions.filters.oneTimeOnly')}</option>
          </select>
        </div>

        <div className="filter-group">
          <label>{t('transactions.needsReview')}</label>
          <select
            value={
              localFilters.needs_review === undefined
                ? ''
                : localFilters.needs_review.toString()
            }
            onChange={(e) =>
              handleChange(
                'needs_review',
                e.target.value === '' ? undefined : e.target.value === 'true'
              )
            }
          >
            <option value="">{t('transactions.filters.all')}</option>
            <option value="true">{t('transactions.filters.needsReviewOnly')}</option>
          </select>
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
