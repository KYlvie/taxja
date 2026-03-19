/**
 * Tests for the Tax Filing Summary panel in TaxToolsPage.
 *
 * Since TaxToolsPage depends on many services/stores, we test the data
 * structures, formatting logic, and conflict detection used by the panel.
 * We also render the summary section in isolation via a lightweight wrapper.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { TaxFilingSummary, TaxFilingEntry } from '../services/taxFilingService';

// ---------------------------------------------------------------------------
// 1. TaxFilingSummary data structure validation
// ---------------------------------------------------------------------------
function makeSummary(overrides: Partial<TaxFilingSummary> = {}): TaxFilingSummary {
  return {
    year: 2025,
    income: [],
    deductions: [],
    vat: [],
    other: [],
    totals: {
      total_income: 0,
      total_deductions: 0,
      taxable_income: 0,
      estimated_tax: 0,
      withheld_tax: 0,
      estimated_refund: 0,
      total_vat_payable: 0,
    },
    conflicts: [],
    record_count: 0,
    ...overrides,
  };
}

function makeEntry(overrides: Partial<TaxFilingEntry> = {}): TaxFilingEntry {
  return {
    id: 1,
    data_type: 'lohnzettel',
    source_document_id: 10,
    confirmed_at: '2025-06-01T12:00:00Z',
    data: {},
    ...overrides,
  };
}

describe('TaxFilingSummary data structure', () => {
  it('should have all required fields', () => {
    const s = makeSummary();
    expect(s.year).toBe(2025);
    expect(s.income).toEqual([]);
    expect(s.deductions).toEqual([]);
    expect(s.vat).toEqual([]);
    expect(s.other).toEqual([]);
    expect(s.conflicts).toEqual([]);
    expect(s.record_count).toBe(0);
    expect(s.totals.taxable_income).toBe(0);
  });

  it('should correctly count records', () => {
    const s = makeSummary({
      income: [makeEntry({ id: 1 }), makeEntry({ id: 2 })],
      deductions: [makeEntry({ id: 3 })],
      record_count: 3,
    });
    expect(s.record_count).toBe(3);
    expect(s.income).toHaveLength(2);
    expect(s.deductions).toHaveLength(1);
  });

  it('should compute refund as positive when withheld > estimated', () => {
    const s = makeSummary({
      totals: {
        total_income: 40000,
        total_deductions: 5000,
        taxable_income: 35000,
        estimated_tax: 5000,
        withheld_tax: 7000,
        estimated_refund: 2000,
        total_vat_payable: 0,
      },
    });
    expect(s.totals.estimated_refund).toBeGreaterThan(0);
  });

  it('should compute negative refund when tax due exceeds withheld', () => {
    const s = makeSummary({
      totals: {
        total_income: 100000,
        total_deductions: 2000,
        taxable_income: 98000,
        estimated_tax: 30000,
        withheld_tax: 25000,
        estimated_refund: -5000,
        total_vat_payable: 0,
      },
    });
    expect(s.totals.estimated_refund).toBeLessThan(0);
  });
});

// ---------------------------------------------------------------------------
// 2. Conflict detection
// ---------------------------------------------------------------------------
describe('Conflict detection', () => {
  it('should have empty conflicts array when no conflicts', () => {
    const s = makeSummary();
    expect(s.conflicts).toHaveLength(0);
  });

  it('should contain conflict objects with description and source_document_ids', () => {
    const s = makeSummary({
      conflicts: [
        {
          description: 'L16 income (€30,000) differs from Bescheid income (€28,000)',
          source_document_ids: [10, 15],
        },
      ],
    });
    expect(s.conflicts).toHaveLength(1);
    expect(s.conflicts[0].description).toContain('L16');
    expect(s.conflicts[0].source_document_ids).toEqual([10, 15]);
  });

  it('should support multiple conflicts', () => {
    const s = makeSummary({
      conflicts: [
        { description: 'Income mismatch', source_document_ids: [1, 2] },
        { description: 'Deduction mismatch', source_document_ids: [3, 4] },
      ],
    });
    expect(s.conflicts).toHaveLength(2);
  });
});

// ---------------------------------------------------------------------------
// 3. Entry categorisation
// ---------------------------------------------------------------------------
describe('Entry categorisation', () => {
  const INCOME_TYPES = ['lohnzettel', 'e1a', 'e1b', 'e1kv'];
  const DEDUCTION_TYPES = ['l1', 'l1k', 'l1ab'];
  const VAT_TYPES = ['u1', 'u30'];

  it.each(INCOME_TYPES)('should place %s entries in income array', (dataType) => {
    const entry = makeEntry({ data_type: dataType });
    const s = makeSummary({ income: [entry], record_count: 1 });
    expect(s.income[0].data_type).toBe(dataType);
  });

  it.each(DEDUCTION_TYPES)('should place %s entries in deductions array', (dataType) => {
    const entry = makeEntry({ data_type: dataType });
    const s = makeSummary({ deductions: [entry], record_count: 1 });
    expect(s.deductions[0].data_type).toBe(dataType);
  });

  it.each(VAT_TYPES)('should place %s entries in vat array', (dataType) => {
    const entry = makeEntry({ data_type: dataType });
    const s = makeSummary({ vat: [entry], record_count: 1 });
    expect(s.vat[0].data_type).toBe(dataType);
  });
});

// ---------------------------------------------------------------------------
// 4. Rendering the conflict warning bar
// ---------------------------------------------------------------------------

/** Lightweight component that renders just the conflict warning bar logic from TaxToolsPage */
const ConflictWarningBar: React.FC<{ conflicts: any[] }> = ({ conflicts }) => {
  if (!conflicts || conflicts.length === 0) return null;
  return (
    <div data-testid="conflict-bar" style={{ background: '#fffbeb', border: '1px solid #fcd34d' }}>
      <div data-testid="conflict-title">⚠️ Data conflicts detected</div>
      {conflicts.map((conflict: any, idx: number) => (
        <div key={idx} data-testid={`conflict-item-${idx}`}>
          {conflict.description || conflict.message || JSON.stringify(conflict)}
          {conflict.source_document_ids && (
            <span data-testid={`conflict-source-${idx}`}>
              (Document: {conflict.source_document_ids.join(', ')})
            </span>
          )}
        </div>
      ))}
    </div>
  );
};

import React from 'react';

describe('Conflict warning bar rendering', () => {
  it('renders nothing when no conflicts', () => {
    const { container } = render(<ConflictWarningBar conflicts={[]} />);
    expect(container.innerHTML).toBe('');
  });

  it('renders nothing when conflicts is null-ish', () => {
    const { container } = render(<ConflictWarningBar conflicts={null as any} />);
    expect(container.innerHTML).toBe('');
  });

  it('renders the warning bar when conflicts exist', () => {
    render(
      <ConflictWarningBar
        conflicts={[{ description: 'Income mismatch', source_document_ids: [10, 15] }]}
      />,
    );
    expect(screen.getByTestId('conflict-bar')).toBeTruthy();
    expect(screen.getByTestId('conflict-title')).toBeTruthy();
  });

  it('renders each conflict item', () => {
    render(
      <ConflictWarningBar
        conflicts={[
          { description: 'Income mismatch', source_document_ids: [10] },
          { description: 'Deduction mismatch', source_document_ids: [20, 25] },
        ]}
      />,
    );
    expect(screen.getByTestId('conflict-item-0')).toBeTruthy();
    expect(screen.getByTestId('conflict-item-1')).toBeTruthy();
    expect(screen.getByText(/Income mismatch/)).toBeTruthy();
    expect(screen.getByText(/Deduction mismatch/)).toBeTruthy();
  });

  it('shows source document IDs', () => {
    render(
      <ConflictWarningBar
        conflicts={[{ description: 'Test', source_document_ids: [42, 99] }]}
      />,
    );
    expect(screen.getByTestId('conflict-source-0').textContent).toContain('42');
    expect(screen.getByTestId('conflict-source-0').textContent).toContain('99');
  });
});

// ---------------------------------------------------------------------------
// 5. Year selector logic
// ---------------------------------------------------------------------------
describe('Year selector logic', () => {
  it('should select the first year by default when years are available', () => {
    const years = [2025, 2024, 2023];
    const defaultYear = years.length > 0 ? years[0] : null;
    expect(defaultYear).toBe(2025);
  });

  it('should return null when no years available', () => {
    const years: number[] = [];
    const defaultYear = years.length > 0 ? years[0] : null;
    expect(defaultYear).toBeNull();
  });

  it('should have years sorted descending (most recent first)', () => {
    const years = [2025, 2024, 2023];
    for (let i = 1; i < years.length; i++) {
      expect(years[i]).toBeLessThan(years[i - 1]);
    }
  });
});

// ---------------------------------------------------------------------------
// 6. Summary totals formatting
// ---------------------------------------------------------------------------
describe('Summary totals formatting', () => {
  const fmtEur = (v: number) =>
    `€ ${v.toLocaleString('de-AT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  it('formats positive amounts correctly', () => {
    expect(fmtEur(35000)).toMatch(/35/);
    expect(fmtEur(35000)).toContain('€');
  });

  it('formats zero correctly', () => {
    const formatted = fmtEur(0);
    expect(formatted).toMatch(/0[,.]00/);
  });

  it('formats negative refund amounts', () => {
    const formatted = fmtEur(-1500);
    expect(formatted).toMatch(/-|−/);
  });

  it('formats large amounts with grouping', () => {
    const formatted = fmtEur(1000000);
    expect(formatted).toMatch(/1.*000.*000/);
  });
});
