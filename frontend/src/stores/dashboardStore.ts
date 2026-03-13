import { create } from 'zustand';

interface DashboardData {
  yearToDateIncome: number;
  yearToDateExpenses: number;
  estimatedTax: number;
  paidTax: number;
  remainingTax: number;
  netIncome: number;
  vatThresholdDistance?: number;
  estimatedRefund?: number;
  withheldTax?: number;
  calculatedTax?: number;
  hasLohnzettel?: boolean;
  isGmbH?: boolean;
  gmbhTax?: {
    koest: number;
    koestRate: number;
    mindestKoest: number;
    profitAfterKoest: number;
    kestOnDividend: number;
    netDividend: number;
    totalTaxBurden: number;
    effectiveTotalRate: number;
  };
  monthlyData?: any[];
  incomeCategoryData?: any[];
  expenseCategoryData?: any[];
  yearOverYearData?: any;
}

interface TaxDeadline {
  id: number;
  title: string;
  date: string;
  description: string;
  isOverdue: boolean;
}

interface SavingsSuggestion {
  id: number;
  title: string;
  description: string;
  potentialSavings: number;
  actionLink: string;
}

interface DashboardState {
  data: DashboardData | null;
  deadlines: TaxDeadline[];
  suggestions: SavingsSuggestion[];
  isLoading: boolean;
  setData: (data: DashboardData) => void;
  setDeadlines: (deadlines: TaxDeadline[]) => void;
  setSuggestions: (suggestions: SavingsSuggestion[]) => void;
  setLoading: (isLoading: boolean) => void;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  data: null,
  deadlines: [],
  suggestions: [],
  isLoading: false,
  setData: (data) => set({ data }),
  setDeadlines: (deadlines) => set({ deadlines }),
  setSuggestions: (suggestions) => set({ suggestions }),
  setLoading: (isLoading) => set({ isLoading }),
}));
