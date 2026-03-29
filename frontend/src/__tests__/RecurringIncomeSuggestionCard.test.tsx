/* @vitest-environment jsdom */

import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import RecurringIncomeSuggestionCard from '../components/documents/suggestion-cards/RecurringIncomeSuggestionCard';
import type { SuggestionCardProps } from '../components/documents/suggestion-cards/SuggestionCardBase';

vi.mock('react-i18next', () => ({
  initReactI18next: { type: '3rdParty', init: () => {} },
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback || key,
  }),
}));

const makeProps = (
  data: Record<string, unknown>,
  overrides: Partial<SuggestionCardProps> = {},
): SuggestionCardProps => ({
  suggestion: {
    type: 'create_recurring_income',
    status: 'pending',
    data,
  },
  confirmResult: null,
  confirmingAction: null,
  onConfirm: vi.fn(),
  onDismiss: vi.fn(),
  ...overrides,
});

describe('RecurringIncomeSuggestionCard', () => {
  it('renders the landlord rental recurring facts for a matched property', () => {
    render(
      <RecurringIncomeSuggestionCard
        {...makeProps({
          monthly_rent: 1035,
          start_date: '2024-01-01',
          end_date: '2026-12-31',
          address: 'Praterstrasse 40/12, 1020 Wien',
          matched_property_id: 'prop-1020',
          matched_property_address: 'Praterstrasse 40/12, 1020 Wien',
        })}
      />,
    );

    expect(screen.getByText(/EUR 1\s*035[,.]00/)).toBeInTheDocument();
    expect(screen.getAllByText('Praterstrasse 40/12, 1020 Wien').length).toBeGreaterThan(0);
    expect(screen.getByText(/2024/)).toBeInTheDocument();
    expect(screen.getByText(/2026/)).toBeInTheDocument();
    expect(screen.queryByText('documents.suggestion.noPropertyMatch')).not.toBeInTheDocument();
    expect(screen.queryByText('documents.suggestion.addressMismatchWarning')).not.toBeInTheDocument();
  });

  it('shows a no-property-match warning when the rental contract cannot be linked', () => {
    render(
      <RecurringIncomeSuggestionCard
        {...makeProps({
          monthly_rent: 1035,
          start_date: '2024-01-01',
          address: 'Praterstrasse 40/12, 1020 Wien',
        })}
      />,
    );

    expect(screen.getByText('documents.suggestion.noPropertyMatch')).toBeInTheDocument();
  });

  it('shows the address mismatch warning for partial matches', () => {
    render(
      <RecurringIncomeSuggestionCard
        {...makeProps({
          monthly_rent: 1035,
          start_date: '2024-01-01',
          address: 'Praterstrasse 40/12, 1020 Wien',
          matched_property_id: 'prop-1020',
          matched_property_address: 'Praterstr. 40 Top 12, Wien',
          address_mismatch_warning: true,
        })}
      />,
    );

    expect(screen.getByText('documents.suggestion.addressMismatchWarning')).toBeInTheDocument();
    expect(screen.getByText('Praterstr. 40 Top 12, Wien')).toBeInTheDocument();
  });
});
