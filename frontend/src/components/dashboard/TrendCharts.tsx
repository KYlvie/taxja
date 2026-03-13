import { useTranslation } from 'react-i18next';
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import './TrendCharts.css';

interface MonthlyData {
  month: string;
  income: number;
  expenses: number;
}

interface CategoryData {
  name: string;
  value: number;
  color: string;
}

interface TrendChartsProps {
  monthlyData: MonthlyData[];
  incomeCategoryData: CategoryData[];
  expenseCategoryData: CategoryData[];
  yearOverYearData?: {
    currentYear: number;
    previousYear: number;
    currentYearIncome: number;
    previousYearIncome: number;
    currentYearExpenses: number;
    previousYearExpenses: number;
  };
}

const TrendCharts = ({
  monthlyData,
  incomeCategoryData,
  expenseCategoryData,
  yearOverYearData,
}: TrendChartsProps) => {
  const { t } = useTranslation();

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('de-AT', {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="custom-tooltip">
          <p className="label">{label}</p>
          {payload.map((entry: any, index: number) => (
            <p key={index} style={{ color: entry.color }}>
              {entry.name}: {formatCurrency(entry.value)}
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  const renderCustomLabel = (entry: any) => {
    return `${entry.name}: ${formatCurrency(entry.value)}`;
  };

  return (
    <div className="trend-charts">
      {/* Monthly Income/Expense Bar Chart */}
      <div className="chart-container">
        <h3>{t('dashboard.monthlyTrend')}</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={monthlyData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="month" />
            <YAxis tickFormatter={formatCurrency} />
            <Tooltip content={<CustomTooltip />} />
            <Legend />
            <Bar
              dataKey="income"
              fill="#10b981"
              name={t('dashboard.income')}
            />
            <Bar
              dataKey="expenses"
              fill="#ef4444"
              name={t('dashboard.expenses')}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Category Breakdown Pie Charts */}
      <div className="pie-charts-row">
        <div className="chart-container">
          <h3>{t('dashboard.incomeByCategory')}</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={incomeCategoryData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={renderCustomLabel}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {incomeCategoryData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip formatter={(value: number) => formatCurrency(value)} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-container">
          <h3>{t('dashboard.expensesByCategory')}</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={expenseCategoryData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={renderCustomLabel}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {expenseCategoryData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip formatter={(value: number) => formatCurrency(value)} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Year-over-Year Comparison */}
      {yearOverYearData && (
        <div className="chart-container">
          <h3>{t('dashboard.yearOverYearComparison')}</h3>
          <div className="yoy-comparison">
            <div className="yoy-card">
              <h4>
                {t('dashboard.income')} {yearOverYearData.currentYear}
              </h4>
              <p className="yoy-amount">
                {formatCurrency(yearOverYearData.currentYearIncome)}
              </p>
              <p className="yoy-change">
                {yearOverYearData.previousYearIncome > 0 && (
                  <>
                    {((yearOverYearData.currentYearIncome -
                      yearOverYearData.previousYearIncome) /
                      yearOverYearData.previousYearIncome) *
                      100 >
                    0
                      ? '↑'
                      : '↓'}{' '}
                    {Math.abs(
                      ((yearOverYearData.currentYearIncome -
                        yearOverYearData.previousYearIncome) /
                        yearOverYearData.previousYearIncome) *
                        100
                    ).toFixed(1)}
                    % {t('dashboard.vsLastYear')}
                  </>
                )}
              </p>
            </div>

            <div className="yoy-card">
              <h4>
                {t('dashboard.expenses')} {yearOverYearData.currentYear}
              </h4>
              <p className="yoy-amount">
                {formatCurrency(yearOverYearData.currentYearExpenses)}
              </p>
              <p className="yoy-change">
                {yearOverYearData.previousYearExpenses > 0 && (
                  <>
                    {((yearOverYearData.currentYearExpenses -
                      yearOverYearData.previousYearExpenses) /
                      yearOverYearData.previousYearExpenses) *
                      100 >
                    0
                      ? '↑'
                      : '↓'}{' '}
                    {Math.abs(
                      ((yearOverYearData.currentYearExpenses -
                        yearOverYearData.previousYearExpenses) /
                        yearOverYearData.previousYearExpenses) *
                        100
                    ).toFixed(1)}
                    % {t('dashboard.vsLastYear')}
                  </>
                )}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TrendCharts;
