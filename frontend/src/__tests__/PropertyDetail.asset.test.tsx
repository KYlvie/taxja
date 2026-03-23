/* @vitest-environment jsdom */

import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

import PropertyDetail from '../components/properties/PropertyDetail';
import { PropertyStatus, PropertyType } from '../types/property';

const getPropertyTransactions = vi.fn();
const getPropertyMetrics = vi.fn();
const getRentalContracts = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    i18n: { language: 'zh' },
    t: (key: string, fallback?: any) => {
      if (typeof fallback === 'string') return fallback;
      if (fallback && typeof fallback === 'object' && typeof fallback.defaultValue === 'string') {
        return fallback.defaultValue;
      }
      return key;
    },
  }),
}));

vi.mock('../hooks/useConfirm', () => ({
  useConfirm: () => ({
    confirm: vi.fn().mockResolvedValue(true),
  }),
}));

vi.mock('../services/propertyService', () => ({
  propertyService: {
    getPropertyTransactions: (...args: any[]) => getPropertyTransactions(...args),
    getPropertyMetrics: (...args: any[]) => getPropertyMetrics(...args),
    getRentalContracts: (...args: any[]) => getRentalContracts(...args),
  },
}));

vi.mock('../services/recurringService', () => ({
  recurringService: {
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

describe('PropertyDetail linked document actions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getPropertyTransactions.mockResolvedValue([]);
    getPropertyMetrics.mockResolvedValue({
      property_id: 'asset-1',
      accumulated_depreciation: 300,
      remaining_depreciable_value: 900,
      annual_depreciation: 300,
      total_rental_income: 0,
      total_expenses: 0,
      net_rental_income: 0,
      warnings: [],
    });
    getRentalContracts.mockResolvedValue([]);
  });

  it('shows top-level source document actions for depreciable assets', async () => {
    render(
      <MemoryRouter>
        <PropertyDetail
          property={{
            id: 'asset-1',
            user_id: 1,
            asset_type: 'computer',
            sub_category: 'computer',
            name: 'MacBook Pro',
            property_type: PropertyType.RENTAL,
            rental_percentage: 100,
            address: '',
            street: '',
            city: '',
            postal_code: '',
            purchase_date: '2026-03-10',
            purchase_price: 1499,
            building_value: 1200,
            depreciation_rate: 0.25,
            useful_life_years: 4,
            acquisition_kind: 'purchase',
            put_into_use_date: '2026-03-20',
            business_use_percentage: 80,
            comparison_basis: 'net',
            comparison_amount: 1249.17,
            depreciation_method: 'degressive',
            vat_recoverable_status: 'likely_yes',
            ifb_candidate: true,
            ifb_rate: 20,
            supplier: 'Apple',
            accumulated_depreciation: 300,
            annual_depreciation: 300,
            remaining_value: 900,
            kaufvertrag_document_id: 42,
            status: PropertyStatus.ACTIVE,
            created_at: '2026-03-18T00:00:00Z',
            updated_at: '2026-03-18T00:00:00Z',
          }}
          onEdit={vi.fn()}
          onArchive={vi.fn()}
          onBack={vi.fn()}
        />
      </MemoryRouter>
    );

    await waitFor(() => expect(getPropertyTransactions).toHaveBeenCalledWith('asset-1'));
    expect(getRentalContracts).not.toHaveBeenCalled();
    expect(getPropertyMetrics).not.toHaveBeenCalled();

    expect(screen.getByRole('heading', { name: 'MacBook Pro' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '\u67e5\u770b\u8d2d\u7f6e\u6587\u4ef6' })).toHaveAttribute('href', '/documents/42');
    expect(screen.getByRole('link', { name: '\u7ba1\u7406\u5173\u8054\u6587\u4ef6' })).toHaveAttribute('href', '/documents?property_id=asset-1');
    expect(screen.queryByText('properties.rentalContracts.title')).not.toBeInTheDocument();
  });

  it('shows top-level contract actions for real-estate properties', async () => {
    render(
      <MemoryRouter>
        <PropertyDetail
          property={{
            id: 'property-1',
            user_id: 1,
            asset_type: 'real_estate',
            property_type: PropertyType.RENTAL,
            rental_percentage: 100,
            address: 'Argentinierstraße 21, 1234 Wien',
            street: 'Argentinierstraße 21',
            city: 'Wien',
            postal_code: '1234',
            purchase_date: '2025-03-15',
            purchase_price: 385000,
            building_value: 308000,
            land_value: 77000,
            grunderwerbsteuer: 13475,
            notary_fees: 4500,
            registry_fees: 4235,
            construction_year: 1928,
            depreciation_rate: 0.015,
            kaufvertrag_document_id: 88,
            mietvertrag_document_id: 91,
            status: PropertyStatus.ACTIVE,
            created_at: '2026-03-18T00:00:00Z',
            updated_at: '2026-03-18T00:00:00Z',
          }}
          onEdit={vi.fn()}
          onArchive={vi.fn()}
          onBack={vi.fn()}
        />
      </MemoryRouter>
    );

    await waitFor(() => expect(getPropertyTransactions).toHaveBeenCalledWith('property-1'));
    expect(getRentalContracts).toHaveBeenCalledWith('property-1');

    expect(screen.getByRole('link', { name: '\u67e5\u770b\u8d2d\u623f\u5408\u540c' })).toHaveAttribute('href', '/documents/88');
    expect(screen.getByRole('link', { name: '\u67e5\u770b\u79df\u8d41\u5408\u540c' })).toHaveAttribute('href', '/documents/91');
  });
});
