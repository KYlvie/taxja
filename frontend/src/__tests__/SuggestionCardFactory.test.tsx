/**
 * Tests for SuggestionCardFactory — verifies correct card routing for all
 * suggestion types, fallback behaviour, and action button wiring.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import SuggestionCardFactory from '../components/documents/SuggestionCardFactory';
import type { SuggestionCardFactoryProps } from '../components/documents/SuggestionCardFactory';

// Mock react-i18next
vi.mock('react-i18next', () => ({
  initReactI18next: { type: '3rdParty', init: () => {} },
  useTranslation: () => ({
    t: (key: string, fallback?: any) => (typeof fallback === 'string' ? fallback : key),
    i18n: { language: 'en', resolvedLanguage: 'en' },
  }),
}));

/** Build minimal props for a given suggestion type */
function makeProps(
  type: string,
  data: Record<string, any> = {},
  overrides: Partial<SuggestionCardFactoryProps> = {},
): SuggestionCardFactoryProps {
  return {
    suggestion: { type, data, status: 'pending' },
    confirmResult: null,
    confirmingAction: null,
    onConfirm: vi.fn(),
    onDismiss: vi.fn(),
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// 1. Legacy entity-creation types
// ---------------------------------------------------------------------------
describe('Legacy entity-creation types', () => {
  it('renders PropertySuggestionCard for create_property', () => {
    const props = makeProps('create_property', { address: 'Wien 1010', purchase_price: 300000 });
    const { container } = render(<SuggestionCardFactory {...props} />);
    expect(container.querySelector('.import-suggestion-card')).toBeTruthy();
    expect(screen.getByText(/Wien 1010/)).toBeTruthy();
  });

  it('renders RecurringIncomeSuggestionCard for create_recurring_income', () => {
    const { container } = render(
      <SuggestionCardFactory {...makeProps('create_recurring_income', { description: 'Miete' })} />,
    );
    expect(container.querySelector('.import-suggestion-card')).toBeTruthy();
  });

  it('renders RecurringExpenseSuggestionCard for create_recurring_expense', () => {
    const { container } = render(
      <SuggestionCardFactory {...makeProps('create_recurring_expense', { description: 'Versicherung' })} />,
    );
    expect(container.querySelector('.import-suggestion-card')).toBeTruthy();
  });

  it('renders InsuranceSuggestionCard for create_insurance_recurring', () => {
    const { container } = render(
      <SuggestionCardFactory
        {...makeProps('create_insurance_recurring', {
          insurer_name: 'Allianz',
          insurance_type: 'Rechtsschutz',
          payment_amount: 89.4,
          payment_frequency: 'quarterly',
        })}
      />,
    );
    expect(container.querySelector('.import-suggestion-card')).toBeTruthy();
    expect(screen.getByText(/Allianz/)).toBeTruthy();
  });

  it('submits archive_only for archive_insurance_document', () => {
    const onConfirmInsuranceRecurring = vi.fn();
    render(
      <SuggestionCardFactory
        {...makeProps('archive_insurance_document', {
          insurer_name: 'UNIQA',
          insurance_type: 'Versicherungsbedingungen',
          document_subtype: 'bedingungen',
        })}
        onConfirmInsuranceRecurring={onConfirmInsuranceRecurring}
      />,
    );
    fireEvent.click(screen.getAllByRole('button')[0]);
    expect(onConfirmInsuranceRecurring).toHaveBeenCalledWith(
      expect.objectContaining({
        archive_only: true,
        archive_reason_code: 'reference_only',
      }),
    );
  });

  it('renders AssetSuggestionCard for create_asset', () => {
    const { container } = render(
      <SuggestionCardFactory {...makeProps('create_asset', { name: 'Laptop' })} />,
    );
    expect(container.querySelector('.import-suggestion-card')).toBeTruthy();
  });

  it('renders LoanSuggestionCard for create_loan', () => {
    const { container } = render(
      <SuggestionCardFactory {...makeProps('create_loan', { bank: 'Erste Bank' })} />,
    );
    expect(container.querySelector('.import-suggestion-card')).toBeTruthy();
  });

  it('renders LoanSuggestionCard for create_loan_repayment', () => {
    const { container } = render(
      <SuggestionCardFactory {...makeProps('create_loan_repayment', { bank: 'Erste Bank' })} />,
    );
    expect(container.querySelector('.import-suggestion-card')).toBeTruthy();
  });

  it('uses onConfirmLoanRepayment when provided for create_loan_repayment', () => {
    const onConfirmLoanRepayment = vi.fn();
    const onConfirm = vi.fn();
    render(
      <SuggestionCardFactory
        {...makeProps('create_loan_repayment', { lender_name: 'Erste Bank' })}
        onConfirmLoanRepayment={onConfirmLoanRepayment}
        onConfirm={onConfirm}
      />,
    );
    const confirmBtn = screen.getAllByRole('button')[0];
    fireEvent.click(confirmBtn);
    expect(onConfirmLoanRepayment).toHaveBeenCalled();
    expect(onConfirm).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// 2. Tax form import types — each should render its specific card
// ---------------------------------------------------------------------------
describe('Tax form import types', () => {
  const TAX_TYPES: Array<{ type: string; icon: string; dataKey?: string }> = [
    { type: 'import_lohnzettel', icon: '📋', dataKey: 'kz_245' },
    { type: 'import_l1', icon: '📝', dataKey: 'kz_717' },
    { type: 'import_l1k', icon: '👨‍👩‍👧', dataKey: 'familienbonus_total' },
    { type: 'import_l1ab', icon: '📑', dataKey: 'alleinverdiener' },
    { type: 'import_e1a', icon: '💼', dataKey: 'betriebseinnahmen' },
    { type: 'import_e1b', icon: '🏘️', dataKey: 'properties' },
    { type: 'import_e1kv', icon: '📈', dataKey: 'kapitalertraege' },
    { type: 'import_u1', icon: '🧾', dataKey: 'gesamtumsatz' },
    { type: 'import_u30', icon: '📅', dataKey: 'meldezeitraum' },
    { type: 'import_jahresabschluss', icon: '📊', dataKey: 'einnahmen' },
    { type: 'import_svs', icon: '🏥', dataKey: 'total_amount' },
    { type: 'import_grundsteuer', icon: '🏛️', dataKey: 'annual_tax' },
  ];

  it.each(TAX_TYPES)(
    'renders a card for $type',
    ({ type, dataKey }) => {
      const data: Record<string, any> = { tax_year: 2025, confidence: 0.95 };
      if (dataKey) data[dataKey] = 1000;
      const { container } = render(<SuggestionCardFactory {...makeProps(type, data)} />);
      expect(container.querySelector('.import-suggestion-card')).toBeTruthy();
    },
  );

  it('uses onConfirmTaxData when provided for tax form types', () => {
    const onConfirmTaxData = vi.fn();
    const onConfirm = vi.fn();
    render(
      <SuggestionCardFactory
        {...makeProps('import_lohnzettel', { tax_year: 2025, kz_245: 30000 })}
        onConfirmTaxData={onConfirmTaxData}
        onConfirm={onConfirm}
      />,
    );
    const confirmBtn = screen.getAllByRole('button')[0];
    fireEvent.click(confirmBtn);
    expect(onConfirmTaxData).toHaveBeenCalled();
    expect(onConfirm).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// 3. Bank statement — special card with transaction selection
// ---------------------------------------------------------------------------
describe('Bank statement card (import_bank_statement)', () => {
  const bankData = {
    bank_name: 'Erste Bank',
    iban: 'AT12 3456 7890 1234',
    transactions: [
      { date: '2025-01-15', amount: -50, counterparty: 'REWE', purpose: 'Einkauf', is_duplicate: false },
      { date: '2025-01-16', amount: 1200, counterparty: 'Arbeitgeber', purpose: 'Gehalt', is_duplicate: false },
      { date: '2025-01-17', amount: -30, counterparty: 'REWE', purpose: 'Einkauf', is_duplicate: true },
    ],
  };

  it('renders the bank statement card', () => {
    const { container } = render(
      <SuggestionCardFactory {...makeProps('import_bank_statement', bankData)} />,
    );
    expect(container.querySelector('.import-suggestion-card')).toBeTruthy();
  });

  it('shows bank name and IBAN', () => {
    render(<SuggestionCardFactory {...makeProps('import_bank_statement', bankData)} />);
    expect(screen.getByText('Erste Bank')).toBeTruthy();
    expect(screen.getByText('AT12 3456 7890 1234')).toBeTruthy();
  });

  it('shows aggregate transaction counts instead of inline selection', () => {
    render(<SuggestionCardFactory {...makeProps('import_bank_statement', bankData)} />);
    expect(screen.getByText('3')).toBeTruthy();
    expect(screen.getByText('2')).toBeTruthy();
    expect(screen.getByText('1')).toBeTruthy();
  });

  it('shows the workbench call-to-action for duplicate handling', () => {
    render(<SuggestionCardFactory {...makeProps('import_bank_statement', bankData)} />);
    expect(screen.getByText(/Open bank statement workbench/i)).toBeTruthy();
  });

  it('calls onOpenBankWorkbench when the user confirms', () => {
    const onOpenBankWorkbench = vi.fn();
    render(
      <SuggestionCardFactory
        {...makeProps('import_bank_statement', bankData)}
        onOpenBankWorkbench={onOpenBankWorkbench}
      />,
    );
    const buttons = screen.getAllByRole('button');
    const importBtn = buttons[0];
    fireEvent.click(importBtn);
    expect(onOpenBankWorkbench).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// 4. Fallback behaviour
// ---------------------------------------------------------------------------
describe('Fallback behaviour', () => {
  it('renders GenericTaxFormCard for unknown import_* types', () => {
    const { container } = render(
      <SuggestionCardFactory {...makeProps('import_unknown_form', { tax_year: 2025, some_field: 42 })} />,
    );
    expect(container.querySelector('.import-suggestion-card')).toBeTruthy();
  });

  it('renders null for completely unknown types', () => {
    const { container } = render(
      <SuggestionCardFactory {...makeProps('something_random', {})} />,
    );
    expect(container.innerHTML).toBe('');
  });
});

// ---------------------------------------------------------------------------
// 5. Confirm / Dismiss button wiring
// ---------------------------------------------------------------------------
describe('Confirm and dismiss buttons', () => {
  it('calls onConfirmProperty for create_property', () => {
    const onConfirmProperty = vi.fn();
    render(
      <SuggestionCardFactory
        {...makeProps('create_property', { address: 'Test' })}
        onConfirmProperty={onConfirmProperty}
      />,
    );
    fireEvent.click(screen.getAllByRole('button')[0]);
    expect(onConfirmProperty).toHaveBeenCalled();
  });

  it('calls onDismiss when dismiss button is clicked', () => {
    const onDismiss = vi.fn();
    render(
      <SuggestionCardFactory
        {...makeProps('import_lohnzettel', { tax_year: 2025 })}
        onDismiss={onDismiss}
      />,
    );
    const buttons = screen.getAllByRole('button');
    const dismissBtn = buttons[buttons.length - 1];
    fireEvent.click(dismissBtn);
    expect(onDismiss).toHaveBeenCalled();
  });

  it('disables buttons when confirmingAction is set', () => {
    render(
      <SuggestionCardFactory
        {...makeProps('import_l1', { tax_year: 2025 })}
        confirmingAction="tax_data"
        confirmResult={null}
        onConfirm={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );
    const buttons = screen.getAllByRole('button');
    buttons.forEach((btn) => expect(btn).toBeDisabled());
  });

  it('shows confirmResult message when present', () => {
    render(
      <SuggestionCardFactory
        {...makeProps('import_svs', { tax_year: 2025 })}
        confirmResult={{ type: 'success', message: 'Data imported successfully' }}
        confirmingAction={null}
        onConfirm={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );
    expect(screen.getByText('Data imported successfully')).toBeTruthy();
  });
});
