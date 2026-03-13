# Dashboard Components

This directory contains all dashboard-related components for the Taxja frontend application.

## Components Overview

### 1. DashboardOverview
**File**: `DashboardOverview.tsx`

Displays key financial metrics in card format:
- Year-to-date income
- Year-to-date expenses
- Estimated tax (with paid/remaining breakdown)
- Net income (after tax and SVS)
- VAT threshold distance (for applicable users)

**Props**:
```typescript
interface DashboardOverviewProps {
  yearToDateIncome: number;
  yearToDateExpenses: number;
  estimatedTax: number;
  paidTax: number;
  remainingTax: number;
  netIncome: number;
  vatThresholdDistance?: number;
}
```

### 2. TrendCharts
**File**: `TrendCharts.tsx`

Visualizes financial data using Recharts library:
- Monthly income/expense bar chart
- Income category breakdown (pie chart)
- Expense category breakdown (pie chart)
- Year-over-year comparison

**Props**:
```typescript
interface TrendChartsProps {
  monthlyData: MonthlyData[];
  incomeCategoryData: CategoryData[];
  expenseCategoryData: CategoryData[];
  yearOverYearData?: YearOverYearData;
}
```

### 3. SavingsSuggestions
**File**: `SavingsSuggestions.tsx`

Displays top 3 tax-saving suggestions with:
- Suggestion title and description
- Potential savings amount
- Action button linking to relevant page

**Props**:
```typescript
interface SavingsSuggestionsProps {
  suggestions: Suggestion[];
}
```

### 4. TaxCalendar
**File**: `TaxCalendar.tsx`

Shows upcoming tax deadlines with:
- Date display
- Urgency indicators (overdue, urgent, soon, normal)
- Deadline descriptions
- Automatic filtering (next 90 days + overdue)

**Props**:
```typescript
interface TaxCalendarProps {
  deadlines: TaxDeadline[];
}
```

### 5. WhatIfSimulator
**File**: `WhatIfSimulator.tsx`

Interactive tax simulation tool:
- Add/remove income or expenses
- Real-time tax calculation
- Shows tax and net income impact
- Provides explanations

**Features**:
- Form validation with React Hook Form
- API integration with dashboard service
- Error handling
- Loading states

### 6. FlatRateComparison
**File**: `FlatRateComparison.tsx`

Compares flat-rate vs actual accounting:
- Eligibility check
- Side-by-side calculation breakdown
- Savings summary
- Recommendation badge
- Detailed explanation

**Features**:
- Automatic data fetching on mount
- Responsive grid layout
- Visual indicators for recommended method

### 7. RefundEstimate
**File**: `RefundEstimate.tsx`

Employee tax refund calculator widget:
- Displays estimated refund amount
- Shows withheld vs calculated tax
- Handles positive refunds, additional payments, and balanced scenarios
- Links to detailed refund calculator

**Props**:
```typescript
interface RefundEstimateProps {
  estimatedRefund?: number;
  withheldTax?: number;
  calculatedTax?: number;
  hasLohnzettel?: boolean;
}
```

## Usage Example

```typescript
import DashboardOverview from '../components/dashboard/DashboardOverview';
import TrendCharts from '../components/dashboard/TrendCharts';
import SavingsSuggestions from '../components/dashboard/SavingsSuggestions';
import TaxCalendar from '../components/dashboard/TaxCalendar';
import WhatIfSimulator from '../components/dashboard/WhatIfSimulator';
import FlatRateComparison from '../components/dashboard/FlatRateComparison';
import RefundEstimate from '../components/dashboard/RefundEstimate';

const DashboardPage = () => {
  const { data, deadlines, suggestions } = useDashboardStore();

  return (
    <div className="dashboard-page">
      <RefundEstimate
        estimatedRefund={data?.estimatedRefund}
        withheldTax={data?.withheldTax}
        calculatedTax={data?.calculatedTax}
      />
      
      <DashboardOverview
        yearToDateIncome={data.yearToDateIncome}
        yearToDateExpenses={data.yearToDateExpenses}
        estimatedTax={data.estimatedTax}
        paidTax={data.paidTax}
        remainingTax={data.remainingTax}
        netIncome={data.netIncome}
        vatThresholdDistance={data.vatThresholdDistance}
      />
      
      <SavingsSuggestions suggestions={suggestions} />
      <TaxCalendar deadlines={deadlines} />
      <TrendCharts {...chartData} />
      <WhatIfSimulator />
      <FlatRateComparison />
    </div>
  );
};
```

## Styling

Each component has its own CSS file following the naming convention:
- `ComponentName.tsx` → `ComponentName.css`

All components use:
- Consistent color scheme
- Responsive design (mobile-first)
- Hover effects and transitions
- Accessible color contrasts

## API Integration

Components integrate with the dashboard service (`services/dashboardService.ts`):

```typescript
// Dashboard data
dashboardService.getDashboardData(year?: number)

// Savings suggestions
dashboardService.getSuggestions()

// Tax calendar
dashboardService.getCalendar()

// What-if simulation
dashboardService.simulateTax(data)

// Flat-rate comparison
dashboardService.compareFlatRate(year?: number)
```

## Internationalization

All text is internationalized using i18next:
- Translation keys in `i18n/locales/en.json` under `dashboard.*`
- Supports German, English, and Chinese
- Currency formatting uses Austrian locale (`de-AT`)

## Requirements Mapping

- **29.1**: DashboardOverview - Requirements 34.1, 34.2, 34.3, 34.7
- **29.2**: TrendCharts - Requirement 34.1
- **29.3**: SavingsSuggestions - Requirement 34.5
- **29.4**: TaxCalendar - Requirements 8.7, 34.6
- **29.5**: WhatIfSimulator - Requirement 34.4
- **29.6**: FlatRateComparison - Requirements 31.1-31.6
- **29.7**: RefundEstimate - Requirements 37.6, 37.7

## Testing

To test these components:

```bash
cd frontend
npm run test
```

Component tests should verify:
- Correct rendering with various data states
- User interactions (button clicks, form submissions)
- API integration
- Error handling
- Responsive behavior

## Future Enhancements

Potential improvements:
- Add export functionality for charts
- Implement chart customization options
- Add more simulation scenarios
- Enhanced mobile gestures for charts
- Real-time data updates via WebSocket
