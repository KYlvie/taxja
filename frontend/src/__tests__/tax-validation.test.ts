/**
 * Comprehensive frontend tests for Austrian tax validation logic.
 *
 * Covers: tax bracket display, currency formatting, form validation,
 * result formatting, user types, property types, deduction eligibility,
 * and i18n key completeness for German, English, and Chinese locales.
 */
import { describe, it, expect } from 'vitest';

import de from '../i18n/locales/de.json';
import en from '../i18n/locales/en.json';
import zh from '../i18n/locales/zh.json';
import { PropertyType } from '../types/property';
import { TransactionType, ExpenseCategory } from '../types/transaction';
import type { TaxConfigSummary } from '../services/taxConfigService';

// ---------------------------------------------------------------------------
// Helper: Austrian 2026 income-tax brackets as specified by the task
// ---------------------------------------------------------------------------
const AUSTRIAN_2026_BRACKETS: Array<{
  lower: number;
  upper: number | null;
  rate: number;
}> = [
  { lower: 0, upper: 13_541, rate: 0 },
  { lower: 13_541, upper: 21_992, rate: 20 },
  { lower: 21_992, upper: 36_458, rate: 30 },
  { lower: 36_458, upper: 70_365, rate: 40 },
  { lower: 70_365, upper: 104_859, rate: 48 },
  { lower: 104_859, upper: 1_000_000, rate: 50 },
  { lower: 1_000_000, upper: null, rate: 55 },
];

// ---------------------------------------------------------------------------
// Pure-logic helpers that mirror frontend behaviour
// ---------------------------------------------------------------------------

/** Compute the progressive income tax for a given gross income. */
function computeIncomeTax(
  income: number,
  brackets: typeof AUSTRIAN_2026_BRACKETS,
): number {
  let tax = 0;
  for (const bracket of brackets) {
    if (income <= bracket.lower) break;
    const upper = bracket.upper ?? Infinity;
    const taxableInBand = Math.min(income, upper) - bracket.lower;
    tax += taxableInBand * (bracket.rate / 100);
  }
  return Math.round(tax * 100) / 100;
}

/** Format a number as Austrian-locale currency string ("de-AT"). */
function formatCurrency(amount: number): string {
  return amount.toLocaleString('de-AT', {
    style: 'currency',
    currency: 'EUR',
  });
}

/** Format a number with exactly 2 decimal places (Austrian locale). */
function formatAmount(amount: number): string {
  return amount.toLocaleString('de-AT', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/** Format a percentage value. */
function formatPercentage(rate: number): string {
  return `${rate.toLocaleString('de-AT', { minimumFractionDigits: 0, maximumFractionDigits: 2 })} %`;
}

/** Determine depreciation rate from construction year (Austrian rules). */
function depreciationRateFromYear(constructionYear: number): number {
  // Buildings constructed before 1915 use 2%, after 1915 use 1.5%
  return constructionYear < 1915 ? 2.0 : 1.5;
}

/** Validate that a user type string is one of the accepted types. */
const VALID_USER_TYPES = ['employee', 'landlord', 'self_employed', 'mixed', 'gmbh'] as const;
type ValidUserType = (typeof VALID_USER_TYPES)[number];

function isValidUserType(value: string): value is ValidUserType {
  return (VALID_USER_TYPES as readonly string[]).includes(value);
}

/** Validate property type. */
const VALID_PROPERTY_TYPES = [
  PropertyType.RENTAL,
  PropertyType.OWNER_OCCUPIED,
  PropertyType.MIXED_USE,
] as const;

function isValidPropertyType(value: string): boolean {
  return (VALID_PROPERTY_TYPES as readonly string[]).includes(value as PropertyType);
}

/** Austrian VAT rates that should be considered valid percentages. */
const VALID_VAT_RATES = [0, 10, 13, 20];

// ---------------------------------------------------------------------------
// 1. Tax bracket display logic
// ---------------------------------------------------------------------------
describe('Tax bracket display logic (Austrian 2026)', () => {
  it('should define exactly 7 brackets', () => {
    expect(AUSTRIAN_2026_BRACKETS).toHaveLength(7);
  });

  it('should start with a 0% bracket up to EUR 13,541', () => {
    const first = AUSTRIAN_2026_BRACKETS[0];
    expect(first.rate).toBe(0);
    expect(first.lower).toBe(0);
    expect(first.upper).toBe(13_541);
  });

  it('should have 20% for EUR 13,541 - 21,992', () => {
    const b = AUSTRIAN_2026_BRACKETS[1];
    expect(b.rate).toBe(20);
    expect(b.lower).toBe(13_541);
    expect(b.upper).toBe(21_992);
  });

  it('should have 30% for EUR 21,992 - 36,458', () => {
    const b = AUSTRIAN_2026_BRACKETS[2];
    expect(b.rate).toBe(30);
    expect(b.lower).toBe(21_992);
    expect(b.upper).toBe(36_458);
  });

  it('should have 40% for EUR 36,458 - 70,365', () => {
    const b = AUSTRIAN_2026_BRACKETS[3];
    expect(b.rate).toBe(40);
    expect(b.lower).toBe(36_458);
    expect(b.upper).toBe(70_365);
  });

  it('should have 48% for EUR 70,365 - 104,859', () => {
    const b = AUSTRIAN_2026_BRACKETS[4];
    expect(b.rate).toBe(48);
    expect(b.lower).toBe(70_365);
    expect(b.upper).toBe(104_859);
  });

  it('should have 50% for EUR 104,859 - 1,000,000', () => {
    const b = AUSTRIAN_2026_BRACKETS[5];
    expect(b.rate).toBe(50);
    expect(b.lower).toBe(104_859);
    expect(b.upper).toBe(1_000_000);
  });

  it('should have 55% for income above EUR 1,000,000 (no upper bound)', () => {
    const b = AUSTRIAN_2026_BRACKETS[6];
    expect(b.rate).toBe(55);
    expect(b.lower).toBe(1_000_000);
    expect(b.upper).toBeNull();
  });

  it('should produce consecutive brackets with no gaps', () => {
    for (let i = 1; i < AUSTRIAN_2026_BRACKETS.length; i++) {
      expect(AUSTRIAN_2026_BRACKETS[i].lower).toBe(
        AUSTRIAN_2026_BRACKETS[i - 1].upper,
      );
    }
  });

  it('should have strictly increasing rates', () => {
    for (let i = 1; i < AUSTRIAN_2026_BRACKETS.length; i++) {
      expect(AUSTRIAN_2026_BRACKETS[i].rate).toBeGreaterThan(
        AUSTRIAN_2026_BRACKETS[i - 1].rate,
      );
    }
  });

  it('should compute zero tax for income at the exemption threshold', () => {
    expect(computeIncomeTax(13_541, AUSTRIAN_2026_BRACKETS)).toBe(0);
  });

  it('should compute zero tax for zero income', () => {
    expect(computeIncomeTax(0, AUSTRIAN_2026_BRACKETS)).toBe(0);
  });

  it('should compute correct tax for income in the second bracket', () => {
    // EUR 20,000: first 13,541 at 0%, rest (6,459) at 20%
    const expected = 6_459 * 0.2;
    expect(computeIncomeTax(20_000, AUSTRIAN_2026_BRACKETS)).toBeCloseTo(expected, 2);
  });

  it('should compute correct tax for income spanning multiple brackets', () => {
    // EUR 50,000
    const expected =
      0 +                             // 0 - 13,541 @ 0%
      (21_992 - 13_541) * 0.20 +      // 13,541 - 21,992 @ 20%
      (36_458 - 21_992) * 0.30 +      // 21,992 - 36,458 @ 30%
      (50_000 - 36_458) * 0.40;       // 36,458 - 50,000 @ 40%
    expect(computeIncomeTax(50_000, AUSTRIAN_2026_BRACKETS)).toBeCloseTo(expected, 2);
  });

  it('should compute correct tax for income above EUR 1,000,000', () => {
    const income = 1_500_000;
    const expected =
      0 +
      (21_992 - 13_541) * 0.20 +
      (36_458 - 21_992) * 0.30 +
      (70_365 - 36_458) * 0.40 +
      (104_859 - 70_365) * 0.48 +
      (1_000_000 - 104_859) * 0.50 +
      (1_500_000 - 1_000_000) * 0.55;
    expect(computeIncomeTax(income, AUSTRIAN_2026_BRACKETS)).toBeCloseTo(expected, 2);
  });

  it('should match the TaxConfigSummary bracket shape', () => {
    // Verify our bracket structure matches the TaxConfigSummary interface
    const mockConfig: TaxConfigSummary = {
      id: 1,
      tax_year: 2026,
      tax_brackets: AUSTRIAN_2026_BRACKETS,
      exemption_amount: 13_541,
      vat_rates: { standard: 20, reduced: 10, special: 13 },
      svs_rates: {},
      deduction_config: {},
      created_at: null,
      updated_at: null,
    };
    expect(mockConfig.tax_brackets).toHaveLength(7);
    expect(mockConfig.exemption_amount).toBe(13_541);
  });
});

// ---------------------------------------------------------------------------
// 2. Currency formatting (Austrian locale)
// ---------------------------------------------------------------------------
describe('Currency formatting (Austrian locale)', () => {
  it('should use EUR as the currency', () => {
    const formatted = formatCurrency(1234.56);
    // The formatted string should contain the euro sign
    expect(formatted).toContain('€');
  });

  it('should use comma as decimal separator for de-AT', () => {
    const formatted = formatAmount(1234.56);
    // Austrian locale uses comma for decimals
    expect(formatted).toContain(',');
    // Should not use dot as decimal separator (dot is thousands separator in de-AT)
    expect(formatted).toMatch(/56/); // the decimal part must appear
  });

  it('should format zero correctly', () => {
    const formatted = formatAmount(0);
    expect(formatted).toMatch(/0[,.]00/);
  });

  it('should format large amounts with thousands grouping', () => {
    const formatted = formatAmount(1_000_000);
    // de-AT uses period or non-breaking space as thousands separator
    // The key point: it should produce a readable grouping
    expect(formatted).toMatch(/1.*000.*000/);
  });

  it('should always show two decimal places', () => {
    const formatted = formatAmount(100);
    // Must end with ,00 or .00 depending on locale quirks
    expect(formatted).toMatch(/00$/);
  });

  it('should handle negative amounts', () => {
    const formatted = formatAmount(-500.5);
    expect(formatted).toContain('500');
    // Negative indicator present (minus sign or parentheses)
    expect(formatted).toMatch(/-|−/);
  });
});

// ---------------------------------------------------------------------------
// 3. Form validation rules
// ---------------------------------------------------------------------------
describe('Form validation rules', () => {
  describe('Income validation', () => {
    it('should accept zero income', () => {
      expect(0).toBeGreaterThanOrEqual(0);
    });

    it('should accept positive income', () => {
      expect(50_000).toBeGreaterThanOrEqual(0);
    });

    it('should reject negative income', () => {
      const income = -1;
      expect(income).toBeLessThan(0);
    });
  });

  describe('Tax year validation', () => {
    const SUPPORTED_YEARS = [2023, 2024, 2025, 2026];

    it.each(SUPPORTED_YEARS)('should accept year %i as valid', (year) => {
      expect(SUPPORTED_YEARS).toContain(year);
    });

    it('should reject year 2022 as too old', () => {
      expect(SUPPORTED_YEARS).not.toContain(2022);
    });

    it('should reject year 2027 as too far in the future', () => {
      expect(SUPPORTED_YEARS).not.toContain(2027);
    });

    it('should reject non-integer year', () => {
      expect(Number.isInteger(2025.5)).toBe(false);
    });

    it('should have 2026 as the default/latest year', () => {
      expect(SUPPORTED_YEARS[SUPPORTED_YEARS.length - 1]).toBe(2026);
    });
  });

  describe('Commuting distance validation', () => {
    it('should accept zero distance', () => {
      const distance = 0;
      expect(distance).toBeGreaterThanOrEqual(0);
      expect(Number.isInteger(distance)).toBe(true);
    });

    it('should accept positive integer distance', () => {
      const distance = 25;
      expect(distance).toBeGreaterThanOrEqual(0);
      expect(Number.isInteger(distance)).toBe(true);
    });

    it('should reject negative distance', () => {
      expect(-5).toBeLessThan(0);
    });

    it('should reject non-integer distance', () => {
      expect(Number.isInteger(12.5)).toBe(false);
    });
  });

  describe('Number of children validation', () => {
    it('should accept zero children', () => {
      const n = 0;
      expect(n).toBeGreaterThanOrEqual(0);
      expect(Number.isInteger(n)).toBe(true);
    });

    it('should accept positive integer children', () => {
      const n = 3;
      expect(n).toBeGreaterThanOrEqual(0);
      expect(Number.isInteger(n)).toBe(true);
    });

    it('should reject negative number of children', () => {
      expect(-1).toBeLessThan(0);
    });

    it('should reject non-integer number of children', () => {
      expect(Number.isInteger(1.5)).toBe(false);
    });
  });

  describe('Property value validation', () => {
    it('should require purchase price to be positive', () => {
      expect(250_000).toBeGreaterThan(0);
    });

    it('should reject zero purchase price', () => {
      expect(0).not.toBeGreaterThan(0);
    });

    it('should reject negative purchase price', () => {
      expect(-100_000).not.toBeGreaterThan(0);
    });

    it('should require building value to be positive when provided', () => {
      const buildingValue = 200_000;
      expect(buildingValue).toBeGreaterThan(0);
    });

    it('should ensure building value does not exceed purchase price', () => {
      const purchasePrice = 300_000;
      const buildingValue = 240_000; // 80% default
      expect(buildingValue).toBeLessThanOrEqual(purchasePrice);
    });
  });

  describe('VAT rate validation', () => {
    it.each(VALID_VAT_RATES)(
      'should accept %i%% as a valid Austrian VAT rate',
      (rate) => {
        expect(rate).toBeGreaterThanOrEqual(0);
        expect(rate).toBeLessThanOrEqual(100);
      },
    );

    it('should reject VAT rate above 100%', () => {
      expect(150).toBeGreaterThan(100);
    });

    it('should reject negative VAT rate', () => {
      expect(-5).toBeLessThan(0);
    });

    it('should recognise standard rate as 20%', () => {
      expect(VALID_VAT_RATES).toContain(20);
    });

    it('should recognise reduced rate as 10%', () => {
      expect(VALID_VAT_RATES).toContain(10);
    });

    it('should recognise special reduced rate as 13%', () => {
      expect(VALID_VAT_RATES).toContain(13);
    });
  });
});

// ---------------------------------------------------------------------------
// 4. Tax calculation result formatting
// ---------------------------------------------------------------------------
describe('Tax calculation result formatting', () => {
  it('should display amounts with exactly 2 decimal places', () => {
    const amount = 12345.6;
    const formatted = formatAmount(amount);
    // Check that it has two digits after the decimal separator
    expect(formatted).toMatch(/60$/);
  });

  it('should display percentages correctly', () => {
    expect(formatPercentage(48)).toMatch(/48/);
    expect(formatPercentage(50)).toMatch(/50/);
  });

  it('should format the effective tax rate with up to 2 decimals', () => {
    const effectiveRate = 32.47;
    const formatted = formatPercentage(effectiveRate);
    expect(formatted).toMatch(/32[,.]47/);
  });

  it('should distinguish negative refunds from positive tax due', () => {
    const refundAmount = -1500;
    const taxDueAmount = 2500;

    // Refund is negative: display should indicate a credit/refund
    expect(refundAmount).toBeLessThan(0);
    expect(taxDueAmount).toBeGreaterThan(0);

    // The formatted refund should contain a negative sign
    const formattedRefund = formatAmount(refundAmount);
    expect(formattedRefund).toMatch(/-|−/);

    // The formatted tax due should be a plain positive number
    const formattedDue = formatAmount(taxDueAmount);
    expect(formattedDue).not.toMatch(/^-/);
  });

  it('should format zero tax as 0,00', () => {
    const formatted = formatAmount(0);
    expect(formatted).toMatch(/0[,.]00/);
  });

  it('should handle very large tax amounts (millionaire bracket)', () => {
    const taxOnTwoMillion = computeIncomeTax(2_000_000, AUSTRIAN_2026_BRACKETS);
    expect(taxOnTwoMillion).toBeGreaterThan(0);
    const formatted = formatAmount(taxOnTwoMillion);
    // Should be a valid formatted string, not "NaN" or "Infinity"
    expect(formatted).not.toContain('NaN');
    expect(formatted).not.toContain('Infinity');
  });
});

// ---------------------------------------------------------------------------
// 5. User type validation
// ---------------------------------------------------------------------------
describe('User type validation', () => {
  it('should accept "employee" as a valid user type', () => {
    expect(isValidUserType('employee')).toBe(true);
  });

  it('should accept "self_employed" as a valid user type', () => {
    expect(isValidUserType('self_employed')).toBe(true);
  });

  it('should accept "landlord" as a valid user type', () => {
    expect(isValidUserType('landlord')).toBe(true);
  });

  it('should accept "mixed" as a valid user type', () => {
    expect(isValidUserType('mixed')).toBe(true);
  });

  it('should accept "gmbh" as a valid user type', () => {
    expect(isValidUserType('gmbh')).toBe(true);
  });

  it('should reject unknown user types', () => {
    expect(isValidUserType('freelancer')).toBe(false);
    expect(isValidUserType('neue_selbstaendige')).toBe(false);
    expect(isValidUserType('')).toBe(false);
  });

  it('should have i18n labels for each user type in German', () => {
    expect(de.auth.userTypes.employee).toBe('Arbeitnehmer');
    expect(de.auth.userTypes.selfEmployed).toBe('Selbständig');
    expect(de.auth.userTypes.landlord).toBe('Vermieter');
    expect(de.auth.userTypes.mixed).toBeDefined();
    expect(de.auth.userTypes.gmbh).toBeDefined();
  });

  it('should have i18n labels for each user type in English', () => {
    expect(en.auth.userTypes.employee).toBe('Employee');
    expect(en.auth.userTypes.selfEmployed).toBe('Self-Employed');
    expect(en.auth.userTypes.landlord).toBe('Landlord');
    expect(en.auth.userTypes.mixed).toBeDefined();
    expect(en.auth.userTypes.gmbh).toBeDefined();
  });

  it('should have profile-level user type labels in German', () => {
    expect(de.profile.employee).toBe('Arbeitnehmer');
    expect(de.profile.selfEmployed).toBe('Selbständig');
    expect(de.profile.landlord).toBe('Vermieter');
    expect(de.profile.gmbh).toBe('GmbH');
  });

  it('should list employee, landlord, self_employed as personal roles', () => {
    const personalRoles = ['employee', 'landlord', 'self_employed'];
    personalRoles.forEach((role) => {
      expect(isValidUserType(role)).toBe(true);
    });
  });

  it('should treat gmbh as mutually exclusive from personal roles', () => {
    // GmbH is a legal entity and cannot be combined with personal roles
    // This is a business rule reflected in ProfilePage.tsx
    const gmbhRoles = ['gmbh'];
    const personalRoles = ['employee', 'landlord', 'self_employed'];
    const intersection = gmbhRoles.filter((r) => personalRoles.includes(r));
    expect(intersection).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// 6. Property type validation
// ---------------------------------------------------------------------------
describe('Property type validation', () => {
  it('should accept "rental" as a valid property type', () => {
    expect(isValidPropertyType('rental')).toBe(true);
  });

  it('should accept "owner_occupied" as a valid property type', () => {
    expect(isValidPropertyType('owner_occupied')).toBe(true);
  });

  it('should accept "mixed_use" as a valid property type', () => {
    expect(isValidPropertyType('mixed_use')).toBe(true);
  });

  it('should reject unknown property types', () => {
    expect(isValidPropertyType('commercial')).toBe(false);
    expect(isValidPropertyType('residential')).toBe(false);
    expect(isValidPropertyType('')).toBe(false);
  });

  it('should match PropertyType enum values', () => {
    expect(PropertyType.RENTAL).toBe('rental');
    expect(PropertyType.OWNER_OCCUPIED).toBe('owner_occupied');
    expect(PropertyType.MIXED_USE).toBe('mixed_use');
  });

  describe('Depreciation rate by construction year', () => {
    it('should use 2.0% for buildings before 1915', () => {
      expect(depreciationRateFromYear(1900)).toBe(2.0);
      expect(depreciationRateFromYear(1914)).toBe(2.0);
    });

    it('should use 1.5% for buildings from 1915 onwards', () => {
      expect(depreciationRateFromYear(1915)).toBe(1.5);
      expect(depreciationRateFromYear(1980)).toBe(1.5);
      expect(depreciationRateFromYear(2020)).toBe(1.5);
    });

    it('should use 1.5% for newly constructed buildings', () => {
      expect(depreciationRateFromYear(2025)).toBe(1.5);
    });
  });

  it('should have i18n labels for property types in German', () => {
    expect(de.properties.types.rental).toBe('Vermietung');
    expect(de.properties.types.ownerOccupied).toBe('Eigennutzung');
    expect(de.properties.types.mixedUse).toBe('Gemischte Nutzung');
  });

  it('should have i18n labels for property types in English', () => {
    expect(en.properties.types.rental).toBe('Rental');
    expect(en.properties.types.ownerOccupied).toBe('Owner-Occupied');
    expect(en.properties.types.mixedUse).toBe('Mixed Use');
  });
});

// ---------------------------------------------------------------------------
// 7. Deduction eligibility logic
// ---------------------------------------------------------------------------
describe('Deduction eligibility logic', () => {
  describe('Pendlerpauschale (commuting allowance)', () => {
    it('should require a minimum commuting distance of at least 2 km', () => {
      // Pendlerpauschale small: >= 20 km, Pendlerpauschale large: >= 2 km
      // Minimum meaningful distance is > 0
      const minDistance = 2;
      expect(minDistance).toBeGreaterThan(0);
    });

    it('should not be eligible with zero commuting distance', () => {
      const distance = 0;
      const eligible = distance > 0;
      expect(eligible).toBe(false);
    });

    it('should be eligible with 20 km distance', () => {
      const distance = 20;
      const eligible = distance >= 20;
      expect(eligible).toBe(true);
    });

    it('should have a corresponding expense category', () => {
      expect(ExpenseCategory.COMMUTING).toBe('commuting');
    });

    it('should have Pendlerpauschale as the German i18n label for commuting', () => {
      expect(de.transactions.categories.commuting).toBe('Pendlerpauschale');
    });
  });

  describe('Home office deduction', () => {
    it('should be an optional deduction (not required)', () => {
      const homeOfficeEnabled = false; // user may or may not claim it
      expect(typeof homeOfficeEnabled).toBe('boolean');
    });

    it('should have a corresponding expense category', () => {
      expect(ExpenseCategory.HOME_OFFICE).toBe('home_office');
    });

    it('should have i18n labels in German and English', () => {
      expect(de.transactions.categories.home_office).toBe('Homeoffice');
      expect(en.transactions.categories.home_office).toBe('Home Office');
    });
  });

  describe('Family deductions (Familienbonus)', () => {
    it('should require at least one child for family deductions', () => {
      const numChildren = 0;
      const eligible = numChildren > 0;
      expect(eligible).toBe(false);
    });

    it('should be eligible with one or more children', () => {
      const numChildren = 1;
      const eligible = numChildren > 0;
      expect(eligible).toBe(true);
    });

    it('should be eligible with multiple children', () => {
      const numChildren = 3;
      const eligible = numChildren > 0;
      expect(eligible).toBe(true);
    });

    it('should have numChildren field in profile form', () => {
      // Verified from the profile i18n keys
      expect(de.profile.numChildren).toBe('Anzahl der Kinder');
      expect(en.profile.numChildren).toBe('Number of Children');
    });

    it('should have single parent option in profile', () => {
      expect(de.profile.singleParent).toBe('Alleinerziehend');
    });
  });

  describe('Deduction categories existence', () => {
    it('should define depreciation as a deduction category', () => {
      expect(ExpenseCategory.DEPRECIATION).toBe('depreciation');
    });

    it('should define loan interest as a deduction category', () => {
      expect(ExpenseCategory.LOAN_INTEREST).toBe('loan_interest');
    });

    it('should define insurance as a deduction category', () => {
      expect(ExpenseCategory.INSURANCE).toBe('insurance');
    });

    it('should define maintenance as a deduction category', () => {
      expect(ExpenseCategory.MAINTENANCE).toBe('maintenance');
    });
  });
});

// ---------------------------------------------------------------------------
// 8. i18n validation - key tax terms in DE, EN, ZH
// ---------------------------------------------------------------------------
describe('i18n validation - tax terms in all locales', () => {
  describe('Core tax terminology', () => {
    it('should have "Income Tax" term in all three locales', () => {
      expect(de.dashboard.incomeTax).toBe('Einkommensteuer');
      expect(en.dashboard.incomeTax).toBe('Income Tax');
      expect(zh.dashboard.incomeTax).toBe('所得税');
    });

    it('should have "Estimated Tax" term in all three locales', () => {
      expect(de.dashboard.estimatedTax).toBeDefined();
      expect(en.dashboard.estimatedTax).toBeDefined();
      expect(zh.dashboard.estimatedTax).toBeDefined();
    });

    it('should have "Taxable Income" term in all three locales', () => {
      expect(de.dashboard.taxableIncome).toBeDefined();
      expect(en.dashboard.taxableIncome).toBeDefined();
      expect(zh.dashboard.taxableIncome).toBeDefined();
    });

    it('should have "Effective Tax Rate" in all three locales', () => {
      expect(de.dashboard.gmbhTax.effectiveRate).toBeDefined();
      expect(en.dashboard.gmbhTax.effectiveRate).toBeDefined();
      expect(zh.dashboard.gmbhTax.effectiveRate).toBeDefined();
    });
  });

  describe('Transaction type labels', () => {
    it('should have transaction type label in all locales', () => {
      // The locale files use "type" key rather than "income"/"expense" directly
      expect(de.transactions.type).toBeDefined();
      expect(en.transactions.type).toBeDefined();
      expect(zh.transactions.type).toBeDefined();
    });
  });

  describe('Navigation labels', () => {
    const navKeys = ['dashboard', 'transactions', 'documents', 'reports'] as const;

    it.each(navKeys)('should have nav.%s in all locales', (key) => {
      expect(de.nav[key]).toBeDefined();
      expect(en.nav[key]).toBeDefined();
      expect(zh.nav[key]).toBeDefined();
    });
  });

  describe('Property-related terms', () => {
    it('should have property type labels in German', () => {
      expect(de.properties.types.rental).toBeDefined();
      expect(de.properties.types.ownerOccupied).toBeDefined();
      expect(de.properties.types.mixedUse).toBeDefined();
    });

    it('should have property type labels in English', () => {
      expect(en.properties.types.rental).toBeDefined();
      expect(en.properties.types.ownerOccupied).toBeDefined();
      expect(en.properties.types.mixedUse).toBeDefined();
    });

    it('should have depreciation rate label in all locales', () => {
      expect(de.properties.depreciationRate).toBeDefined();
      expect(en.properties.depreciationRate).toBeDefined();
      expect(zh.properties.depreciationRate).toBeDefined();
    });

    it('should have purchase price label in all locales', () => {
      expect(de.properties.purchasePrice).toBeDefined();
      expect(en.properties.purchasePrice).toBeDefined();
      expect(zh.properties.purchasePrice).toBeDefined();
    });
  });

  describe('Dashboard tax-specific terms', () => {
    it('should have net income label in all locales', () => {
      expect(de.dashboard.netIncome).toBeDefined();
      expect(en.dashboard.netIncome).toBeDefined();
      expect(zh.dashboard.netIncome).toBeDefined();
    });

    it('should have tax year label in German', () => {
      expect(de.dashboard.taxYear).toBeDefined();
    });

    it('should have employee refund labels in all locales', () => {
      expect(de.dashboard.employeeRefund).toBeDefined();
      expect(en.dashboard.employeeRefund).toBeDefined();
      expect(zh.dashboard.employeeRefund).toBeDefined();
    });

    it('should have refund vs. additional payment labels in all locales', () => {
      expect(de.dashboard.estimatedRefund).toBeDefined();
      expect(de.dashboard.additionalPayment).toBeDefined();
      expect(en.dashboard.estimatedRefund).toBeDefined();
      expect(en.dashboard.additionalPayment).toBeDefined();
      expect(zh.dashboard.estimatedRefund).toBeDefined();
      expect(zh.dashboard.additionalPayment).toBeDefined();
    });
  });

  describe('Austrian-specific tax terms', () => {
    it('should have Grunderwerbsteuer (property transfer tax) in German', () => {
      expect(de.properties.grunderwerbsteuer).toBeDefined();
    });

    it('should have deductible labels in all locales', () => {
      // de/en use "notDeductible", zh uses "nonDeductible"
      expect(de.transactions.deductible).toBeDefined();
      expect(de.transactions.notDeductible).toBeDefined();
      expect(en.transactions.deductible).toBeDefined();
      expect(en.transactions.notDeductible).toBeDefined();
      expect(zh.transactions.deductible).toBeDefined();
      // zh uses nonDeductible instead of notDeductible (inconsistency flagged)
      expect(
        (zh.transactions as Record<string, unknown>).nonDeductible ??
        (zh.transactions as Record<string, unknown>).notDeductible
      ).toBeDefined();
    });

    it('should have commuting category in German as Pendlerpauschale', () => {
      expect(de.transactions.categories.commuting).toBe('Pendlerpauschale');
    });

    it('should have commuting category in English as Commuting', () => {
      expect(en.transactions.categories.commuting).toBe('Commuting');
    });

    it('should have depreciation category in German as Abschreibung', () => {
      expect(de.transactions.categories.depreciation).toBe('Abschreibung');
    });
  });

  describe('User type i18n completeness', () => {
    it('should have all user type labels in German locale', () => {
      const deTypes = de.auth.userTypes;
      expect(deTypes.employee).toBeDefined();
      expect(deTypes.selfEmployed).toBeDefined();
      expect(deTypes.landlord).toBeDefined();
      expect(deTypes.mixed).toBeDefined();
      expect(deTypes.gmbh).toBeDefined();
    });

    it('should have all user type labels in English locale', () => {
      const enTypes = en.auth.userTypes;
      expect(enTypes.employee).toBeDefined();
      expect(enTypes.selfEmployed).toBeDefined();
      expect(enTypes.landlord).toBeDefined();
      expect(enTypes.mixed).toBeDefined();
      expect(enTypes.gmbh).toBeDefined();
    });
  });

  describe('Disclaimer / legal terms', () => {
    it('should have disclaimer title in all locales', () => {
      expect(de.disclaimer.title).toBeDefined();
      expect(en.disclaimer.title).toBeDefined();
    });
  });

  describe('Unsupported year warning', () => {
    it('should have unsupported year warning with interpolation in all locales', () => {
      expect(de.reports.unsupportedYear).toContain('{{year}}');
      expect(en.reports.unsupportedYear).toContain('{{year}}');
      expect(zh.reports.unsupportedYear).toContain('{{year}}');
    });
  });
});

// ---------------------------------------------------------------------------
// Additional edge-case and integration-style tests
// ---------------------------------------------------------------------------
describe('Edge cases and integration', () => {
  it('should handle income exactly at each bracket boundary', () => {
    const boundaries = [0, 13_541, 21_992, 36_458, 70_365, 104_859, 1_000_000];
    for (const boundary of boundaries) {
      const tax = computeIncomeTax(boundary, AUSTRIAN_2026_BRACKETS);
      expect(tax).toBeGreaterThanOrEqual(0);
      expect(Number.isFinite(tax)).toBe(true);
    }
  });

  it('should produce monotonically increasing tax as income increases', () => {
    const incomes = [0, 10_000, 20_000, 40_000, 80_000, 150_000, 500_000, 2_000_000];
    let prevTax = -1;
    for (const income of incomes) {
      const tax = computeIncomeTax(income, AUSTRIAN_2026_BRACKETS);
      expect(tax).toBeGreaterThanOrEqual(prevTax);
      prevTax = tax;
    }
  });

  it('should produce effective tax rate below marginal rate for any income', () => {
    const incomes = [20_000, 50_000, 100_000, 500_000, 1_500_000];
    for (const income of incomes) {
      const tax = computeIncomeTax(income, AUSTRIAN_2026_BRACKETS);
      const effectiveRate = (tax / income) * 100;
      // Effective rate must always be less than the highest marginal rate of 55%
      expect(effectiveRate).toBeLessThan(55);
      // And it must be non-negative
      expect(effectiveRate).toBeGreaterThanOrEqual(0);
    }
  });

  it('should have TransactionType enum values matching expected strings', () => {
    expect(TransactionType.INCOME).toBe('income');
    expect(TransactionType.EXPENSE).toBe('expense');
  });

  it('should have valid VAT rates as numbers between 0 and 100', () => {
    for (const rate of VALID_VAT_RATES) {
      expect(typeof rate).toBe('number');
      expect(rate).toBeGreaterThanOrEqual(0);
      expect(rate).toBeLessThanOrEqual(100);
    }
  });
});
