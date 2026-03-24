/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import LiabilitiesPage from '../pages/LiabilitiesPage';
import en from '../i18n/locales/en.json';

const list = vi.fn();
const get = vi.fn();
const getSummary = vi.fn();
const create = vi.fn();
const update = vi.fn();
const remove = vi.fn();
const getProperties = vi.fn();
const getDocuments = vi.fn();
const alert = vi.fn();
const confirm = vi.fn();

const translate = (
  key: string,
  fallbackOrOptions?: string | { defaultValue?: string } | Record<string, unknown>,
  params?: Record<string, unknown>,
) => {
  const fromLocale = key.split('.').reduce<unknown>((current, segment) => {
    if (current && typeof current === 'object' && segment in (current as Record<string, unknown>)) {
      return (current as Record<string, unknown>)[segment];
    }
    return undefined;
  }, en);

  const interpolationParams =
    fallbackOrOptions &&
    typeof fallbackOrOptions === 'object' &&
    !('defaultValue' in fallbackOrOptions)
      ? (fallbackOrOptions as Record<string, unknown>)
      : params;

  if (typeof fromLocale === 'string') {
    return fromLocale.replace(/\{\{(\w+)\}\}/g, (_, token) =>
      String(interpolationParams?.[token] ?? ''),
    );
  }

  if (typeof fallbackOrOptions === 'string') {
    return fallbackOrOptions;
  }

  if (
    fallbackOrOptions &&
    typeof fallbackOrOptions === 'object' &&
    'defaultValue' in fallbackOrOptions &&
    typeof fallbackOrOptions.defaultValue === 'string'
  ) {
    return fallbackOrOptions.defaultValue.replace(/\{\{(\w+)\}\}/g, (_, token) =>
      String(interpolationParams?.[token] ?? ''),
    );
  }

  return key;
};

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: translate,
    i18n: {
      language: 'en',
    },
  }),
}));

vi.mock('../services/liabilityService', () => ({
  liabilityService: {
    list: (...args: any[]) => list(...args),
    get: (...args: any[]) => get(...args),
    getSummary: (...args: any[]) => getSummary(...args),
    create: (...args: any[]) => create(...args),
    update: (...args: any[]) => update(...args),
    remove: (...args: any[]) => remove(...args),
  },
}));

vi.mock('../services/propertyService', () => ({
  propertyService: {
    getProperties: (...args: any[]) => getProperties(...args),
  },
}));

vi.mock('../services/documentService', () => ({
  documentService: {
    getDocuments: (...args: any[]) => getDocuments(...args),
  },
}));

vi.mock('../hooks/useConfirm', () => ({
  useConfirm: () => ({
    confirm: (...args: any[]) => confirm(...args),
    alert: (...args: any[]) => alert(...args),
  }),
}));

const baseListItems = [
  {
    id: 10,
    user_id: 1,
    liability_type: 'property_loan',
    source_type: 'document_confirmed',
    display_name: 'Sparkasse Mortgage',
    currency: 'EUR',
    lender_name: 'Sparkasse',
    principal_amount: 250000,
    outstanding_balance: 181000,
    interest_rate: 3.25,
    start_date: '2024-01-01',
    end_date: '2049-01-01',
    monthly_payment: 950,
    tax_relevant: true,
    tax_relevance_reason: 'Rental property financing',
    report_category: 'darlehen_und_kredite',
    linked_property_id: 'property-1',
    linked_loan_id: 7,
    source_document_id: 99,
    is_active: true,
    can_edit_directly: false,
    can_deactivate_directly: false,
    edit_via_document: true,
    requires_supporting_document: false,
    recommended_document_type: 'loan_contract',
    notes: null,
    created_at: '2026-03-22T00:00:00Z',
    updated_at: '2026-03-22T00:00:00Z',
  },
  {
    id: 11,
    user_id: 1,
    liability_type: 'family_loan',
    source_type: 'manual',
    display_name: 'Family bridge loan',
    currency: 'EUR',
    lender_name: 'Parents',
    principal_amount: 20000,
    outstanding_balance: 4000,
    interest_rate: null,
    start_date: '2025-01-01',
    end_date: null,
    monthly_payment: 375,
    tax_relevant: false,
    tax_relevance_reason: null,
    report_category: 'sonstige_verbindlichkeiten',
    linked_property_id: null,
    linked_loan_id: null,
    source_document_id: null,
    is_active: true,
    can_edit_directly: true,
    can_deactivate_directly: true,
    edit_via_document: false,
    requires_supporting_document: true,
    recommended_document_type: 'loan_contract',
    notes: 'Short bridge',
    created_at: '2026-03-22T00:00:00Z',
    updated_at: '2026-03-22T00:00:00Z',
  },
];

describe('LiabilitiesPage', () => {
  beforeAll(() => {
    class ResizeObserverMock {
      observe() {}
      unobserve() {}
      disconnect() {}
    }

    vi.stubGlobal('ResizeObserver', ResizeObserverMock);
  });

  beforeEach(() => {
    vi.clearAllMocks();
    confirm.mockResolvedValue(true);
    alert.mockResolvedValue(true);

    list.mockResolvedValue({
      total: 2,
      active_count: 2,
      items: baseListItems,
    });

    getSummary.mockResolvedValue({
      total_assets: 250000,
      total_liabilities: 185000,
      net_worth: 65000,
      active_liability_count: 2,
      monthly_debt_service: 1325,
      annual_deductible_interest: 4800,
    });

    get.mockImplementation(async (id: number) => {
      if (id === 10) {
        return {
          ...baseListItems[0],
          related_transactions: [],
          related_recurring_transactions: [],
        };
      }
      return {
        ...baseListItems[1],
        related_transactions: [],
        related_recurring_transactions: [],
      };
    });

    getProperties.mockResolvedValue({
      total: 1,
      include_archived: true,
      properties: [
        {
          id: 'property-1',
          address: 'Main Street 1, Wien',
        },
      ],
    });

    getDocuments.mockResolvedValue({
      total: 1,
      documents: [
        {
          id: 301,
          user_id: 1,
          document_type: 'loan_contract',
          file_path: '/documents/301.pdf',
          file_name: '03_Kreditvertrag_Erste_Bank_5S.pdf',
          file_size: 1000,
          mime_type: 'application/pdf',
          ocr_result: {
            import_suggestion: {
              status: 'pending',
              data: {
                missing_fields: ['loan_amount', 'interest_rate'],
              },
            },
          },
          confidence_score: 0.6,
          needs_review: true,
          created_at: '2026-03-22T00:00:00Z',
          updated_at: '2026-03-22T00:00:00Z',
        },
      ],
    });
  });

  it('shows source-managed guidance for document-backed liabilities', async () => {
    render(
      <MemoryRouter initialEntries={['/liabilities/10']}>
        <Routes>
          <Route path="/liabilities" element={<LiabilitiesPage />} />
          <Route path="/liabilities/new" element={<LiabilitiesPage />} />
          <Route path="/liabilities/:id" element={<LiabilitiesPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: translate('liabilities.page.title') })).toBeInTheDocument(),
    );

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Sparkasse Mortgage' })).toBeInTheDocument(),
    );
    expect(screen.getByText(translate('liabilities.documents.sourceManagedTitle'))).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('liabilities.documents.openSourceDocument') })).toHaveAttribute(
      'href',
      '/documents/99',
    );
    expect(screen.queryByRole('button', { name: translate('common.edit') })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: translate('liabilities.actions.deactivate') })).not.toBeInTheDocument();
  });

  it('keeps manual liabilities directly editable and prompts for supporting documents', async () => {
    render(
      <MemoryRouter initialEntries={['/liabilities/11']}>
        <Routes>
          <Route path="/liabilities" element={<LiabilitiesPage />} />
          <Route path="/liabilities/new" element={<LiabilitiesPage />} />
          <Route path="/liabilities/:id" element={<LiabilitiesPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByRole('button', { name: translate('common.edit') })).toBeInTheDocument(),
    );
    expect(screen.getByRole('button', { name: translate('common.edit') })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: translate('liabilities.actions.deactivate') })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: translate('common.edit') }));

    await waitFor(() =>
      expect(screen.getByText(translate('liabilities.documents.manualUploadTitle'))).toBeInTheDocument(),
    );
    expect(screen.getByRole('link', { name: translate('liabilities.documents.uploadSupportingDocument') })).toHaveAttribute(
      'href',
      '/documents?type=loan_contract',
    );
  });

  it('shows pending loan contracts that have not become liabilities yet', async () => {
    render(
      <MemoryRouter initialEntries={['/liabilities']}>
        <Routes>
          <Route path="/liabilities" element={<LiabilitiesPage />} />
          <Route path="/liabilities/new" element={<LiabilitiesPage />} />
          <Route path="/liabilities/:id" element={<LiabilitiesPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: translate('liabilities.documents.pendingTitle') })).toBeInTheDocument(),
    );
    expect(screen.getByText('03_Kreditvertrag_Erste_Bank_5S.pdf')).toBeInTheDocument();
    expect(
      screen.getByText(
        translate('liabilities.documents.pendingMissingFields', {
          fields: 'Loan amount, Interest rate',
        }),
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: translate('liabilities.documents.openSourceDocument') })).toBeInTheDocument();
  });
});
