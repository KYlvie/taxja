/* @vitest-environment jsdom */

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import InsuranceSuggestionCard from '../components/documents/suggestion-cards/InsuranceSuggestionCard';
import type { SuggestionCardProps } from '../components/documents/suggestion-cards/SuggestionCardBase';

vi.mock('react-i18next', () => ({
  initReactI18next: { type: '3rdParty', init: () => {} },
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback || key,
  }),
}));

const makeProps = (
  suggestionType: string,
  data: Record<string, unknown> = {},
  overrides: Partial<SuggestionCardProps> = {},
): SuggestionCardProps => ({
  suggestion: {
    type: suggestionType,
    status: 'pending',
    data,
  },
  confirmResult: null,
  confirmingAction: null,
  onConfirm: vi.fn(),
  onDismiss: vi.fn(),
  ...overrides,
});

describe('InsuranceSuggestionCard', () => {
  it('renders the core insurance facts for the happy path', () => {
    render(
      <InsuranceSuggestionCard
        {...makeProps('create_insurance_recurring', {
          insurer_name: 'UNIQA Sachversicherung AG',
          insurance_type: 'Berufshaftpflichtversicherung',
          payment_amount: 186.4,
          premium_annual_brutto: 372.8,
          payment_frequency: 'semi_annual',
          deductibility_hint: '100% Betriebsausgabe (E1a KZ 9230)',
          polizze_nr: 'PH-2023-445566',
          versicherungsnehmer: 'DI Maria Steiner',
          vertragsbeginn: '2024-01-01',
        })}
      />,
    );

    expect(screen.getByText('UNIQA Sachversicherung AG')).toBeInTheDocument();
    expect(screen.getByText('Berufshaftpflichtversicherung')).toBeInTheDocument();
    expect(screen.getByText(/EUR 186[,.]40/)).toBeInTheDocument();
    expect(screen.getByText(/EUR 372[,.]80/)).toBeInTheDocument();
    expect(screen.getAllByText('semi_annual').length).toBeGreaterThan(0);
    expect(screen.getByText('100% Betriebsausgabe (E1a KZ 9230)')).toBeInTheDocument();
    expect(screen.getByText('PH-2023-445566')).toBeInTheDocument();
    expect(screen.getByText('DI Maria Steiner')).toBeInTheDocument();
  });

  it('requires business-use input before confirming a KFZ insurance recurring', () => {
    const onConfirm = vi.fn();
    render(
      <InsuranceSuggestionCard
        {...makeProps(
          'create_insurance_recurring',
          {
            insurer_name: 'Generali Versicherung AG',
            insurance_type: 'KFZ-Haftpflicht + Kasko',
            payment_amount: 89.25,
            premium_annual_brutto: 1071,
            payment_frequency: 'monthly',
            input_fields: ['business_use_percentage'],
            deductibility_hint: 'Teilweise absetzbar',
          },
          { onConfirm },
        )}
      />,
    );

    const confirmButton = screen.getByRole('button', { name: 'Confirm' });
    expect(confirmButton).toBeDisabled();

    const numberInputs = screen.getAllByRole('spinbutton');
    fireEvent.change(numberInputs[1], { target: { value: '60' } });

    expect(confirmButton).not.toBeDisabled();
    fireEvent.click(confirmButton);

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        business_use_percentage: 60,
        dedup_resolution: 'ignore_existing',
        override_payment_amount: 89.25,
        override_payment_frequency: 'monthly',
      }),
    );
  });

  it('submits override amount, frequency, and beruflicher anteil for Rechtsschutz Kombi', () => {
    const onConfirm = vi.fn();
    render(
      <InsuranceSuggestionCard
        {...makeProps(
          'create_insurance_recurring',
          {
            insurer_name: 'Allianz',
            insurance_type: 'Rechtsschutz',
            payment_amount: 15.81,
            premium_annual_brutto: 363.12,
            payment_frequency: 'annually',
            input_fields: ['beruflicher_anteil_pct'],
          },
          { onConfirm },
        )}
      />,
    );

    const numberInputs = screen.getAllByRole('spinbutton');
    fireEvent.change(numberInputs[0], { target: { value: '90.78' } });
    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: 'quarterly' } });
    fireEvent.change(numberInputs[1], { target: { value: '40' } });

    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        beruflicher_anteil_pct: 40,
        override_payment_amount: 90.78,
        override_payment_frequency: 'quarterly',
      }),
    );
  });

  it('uses the auto-filled Arbeitszimmer percentage without showing a manual input', () => {
    const onConfirm = vi.fn();
    render(
      <InsuranceSuggestionCard
        {...makeProps(
          'create_insurance_recurring',
          {
            insurer_name: 'Zuerich',
            insurance_type: 'Haushaltsversicherung',
            payment_amount: 28.9,
            premium_annual_brutto: 346.8,
            payment_frequency: 'monthly',
            business_use_percentage: 23.08,
            deductibility_hint: 'Arbeitszimmer context applied',
            input_fields: [],
          },
          { onConfirm },
        )}
      />,
    );

    expect(screen.queryByText('Business-use %')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        business_use_percentage: 23.08,
        override_payment_amount: 28.9,
        override_payment_frequency: 'monthly',
      }),
    );
  });

  it('renders dedup conflicts and defaults conflict handling to link_existing', () => {
    const onConfirm = vi.fn();
    render(
      <InsuranceSuggestionCard
        {...makeProps(
          'create_insurance_recurring',
          {
            insurer_name: 'UNIQA',
            insurance_type: 'Berufshaftpflicht',
            payment_amount: 186.4,
            payment_frequency: 'semi_annual',
            dedup_conflicts: [
              {
                date: '2024-07-01',
                amount: 186.4,
                description: 'UNIQA SEPA-Lastschrift',
              },
            ],
          },
          { onConfirm },
        )}
      />,
    );

    expect(screen.getByText('Potential overlaps')).toBeInTheDocument();
    expect(screen.getByText(/2024-07-01/)).toBeInTheDocument();
    expect(screen.getAllByRole('combobox')[1]).toHaveValue('link_existing');

    fireEvent.change(screen.getAllByRole('combobox')[1], { target: { value: 'cancel' } });
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        dedup_resolution: 'cancel',
      }),
    );
  });

  it('supports selecting ignore_existing when dedup conflicts are present', () => {
    const onConfirm = vi.fn();
    render(
      <InsuranceSuggestionCard
        {...makeProps(
          'create_insurance_recurring',
          {
            insurer_name: 'UNIQA',
            insurance_type: 'Berufshaftpflicht',
            payment_amount: 186.4,
            payment_frequency: 'semi_annual',
            dedup_conflicts: [
              {
                date: '2024-07-01',
                amount: 186.4,
                description: 'UNIQA SEPA-Lastschrift',
              },
            ],
          },
          { onConfirm },
        )}
      />,
    );

    fireEvent.change(screen.getAllByRole('combobox')[1], { target: { value: 'ignore_existing' } });
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        dedup_resolution: 'ignore_existing',
      }),
    );
  });

  it('requires property rental status for Gebaeudeversicherung when context is missing', () => {
    const onConfirm = vi.fn();
    render(
      <InsuranceSuggestionCard
        {...makeProps(
          'create_insurance_recurring',
          {
            insurer_name: 'Wiener Staedtische',
            insurance_type: 'Gebaeudeversicherung',
            payment_amount: 140,
            premium_annual_brutto: 1680,
            payment_frequency: 'monthly',
            input_fields: ['property_rental_status'],
          },
          { onConfirm },
        )}
      />
    );

    const confirmButton = screen.getByRole('button', { name: 'Confirm' });
    expect(confirmButton).toBeDisabled();

    fireEvent.change(screen.getAllByRole('combobox')[1], { target: { value: 'rented' } });
    expect(confirmButton).not.toBeDisabled();

    fireEvent.click(confirmButton);
    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        property_rental_status: 'rented',
      }),
    );
  });

  it('allows confirming a not-deductible private insurance recurring for expense tracking', () => {
    const onConfirm = vi.fn();
    render(
      <InsuranceSuggestionCard
        {...makeProps(
          'create_insurance_recurring',
          {
            insurer_name: 'GRAWE',
            insurance_type: 'Private Krankenversicherung',
            payment_amount: 240,
            premium_annual_brutto: 2880,
            payment_frequency: 'monthly',
            deductibility_hint: 'Nicht absetzbar',
            deductibility_status: 'not_deductible',
          },
          { onConfirm },
        )}
      />
    );

    expect(screen.getByText('Nicht absetzbar')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        override_payment_amount: 240,
        override_payment_frequency: 'monthly',
        archive_reason_code: 'not_relevant',
      }),
    );
  });

  it('submits archive_only from a recurring suggestion with the inferred not_relevant reason', () => {
    const onConfirm = vi.fn();
    render(
      <InsuranceSuggestionCard
        {...makeProps(
          'create_insurance_recurring',
          {
            insurer_name: 'GRAWE',
            insurance_type: 'Private Krankenversicherung',
            payment_amount: 240,
            premium_annual_brutto: 2880,
            payment_frequency: 'monthly',
            deductibility_status: 'not_deductible',
          },
          { onConfirm },
        )}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Archive only' }));

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        archive_only: true,
        archive_reason_code: 'not_relevant',
      }),
    );
  });

  it('submits archive_only with the default reference_only reason for reference documents', () => {
    const onConfirm = vi.fn();
    render(
      <InsuranceSuggestionCard
        {...makeProps(
          'archive_insurance_document',
          {
            insurer_name: 'UNIQA',
            insurance_type: 'Versicherungsbedingungen',
            document_subtype: 'bedingungen',
          },
          { onConfirm },
        )}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Archive only' }));

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        archive_only: true,
        archive_reason_code: 'reference_only',
      }),
    );
  });

  it('requires an archive note when archive reason is other', () => {
    const onConfirm = vi.fn();
    render(
      <InsuranceSuggestionCard
        {...makeProps(
          'archive_insurance_document',
          {
            insurer_name: 'GRAWE',
            insurance_type: 'Private Krankenversicherung',
            document_subtype: 'other',
          },
          { onConfirm },
        )}
      />,
    );

    const confirmButton = screen.getByRole('button', { name: 'Archive only' });
    expect(confirmButton).toBeDisabled();

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'manual archive justification' } });

    expect(confirmButton).not.toBeDisabled();
    fireEvent.click(confirmButton);

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        archive_only: true,
        archive_reason_code: 'other',
        archive_reason_note: 'manual archive justification',
      }),
    );
  });

  it('shows a blank payment amount when a Jahresbestaetigung only has annual premium', () => {
    render(
      <InsuranceSuggestionCard
        {...makeProps('create_insurance_recurring', {
          insurer_name: 'GRAWE',
          insurance_type: 'Private Krankenversicherung',
          premium_annual_brutto: 2880,
          payment_frequency: '',
          payment_amount: null,
        })}
      />,
    );

    expect(screen.getByText(/EUR 2\s*880[,.]00/)).toBeInTheDocument();
    expect(screen.getAllByText('-').length).toBeGreaterThan(0);
  });
});
