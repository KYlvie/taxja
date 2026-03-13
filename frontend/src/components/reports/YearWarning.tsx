import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import taxConfigService from '../../services/taxConfigService';

/** Fallback years used while API loads or if it fails */
const FALLBACK_YEARS = [2023, 2024, 2025, 2026];

/** Shared state so all YearWarning instances use the same data */
let sharedYears: number[] | null = null;

export const isYearSupported = (year: number) =>
  (sharedYears ?? FALLBACK_YEARS).includes(year);

interface YearWarningProps {
  taxYear: number;
}

const YearWarning = ({ taxYear }: YearWarningProps) => {
  const { t } = useTranslation();
  const [supportedYears, setSupportedYears] = useState<number[]>(
    sharedYears ?? FALLBACK_YEARS
  );

  useEffect(() => {
    taxConfigService.getSupportedYears().then((res) => {
      sharedYears = res.years;
      setSupportedYears(res.years);
    });
  }, []);

  if (supportedYears.includes(taxYear)) return null;

  return (
    <div className="year-warning" role="alert" style={{
      background: '#fff3cd',
      border: '1px solid #ffc107',
      borderRadius: '8px',
      padding: '12px 16px',
      marginBottom: '16px',
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      fontSize: '0.9rem',
      color: '#856404',
    }}>
      <span>⚠️</span>
      <span>
        {t('reports.unsupportedYear', {
          year: taxYear,
          supported: supportedYears.join(', '),
        })}
      </span>
    </div>
  );
};

export default YearWarning;
