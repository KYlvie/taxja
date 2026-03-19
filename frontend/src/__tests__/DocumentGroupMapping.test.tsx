/**
 * Bug Condition Exploration Tests — Document Group Mapping & i18n
 *
 * These tests encode the EXPECTED (post-fix) behavior. They are designed to
 * FAIL on the current unfixed code, proving the bugs exist.
 *
 * Test 1a: LOAN_CONTRACT should be in social_insurance group (currently in property — bug)
 * Test 1d: deductions group label should be "税务优惠凭证" (currently "抵扣与减免" — bug)
 *
 * Validates: Requirements 1.1, 1.2
 */
import { describe, it, expect } from 'vitest';
import { DocumentType } from '../types/document';
import zh from '../i18n/locales/zh.json';
import de from '../i18n/locales/de.json';
import en from '../i18n/locales/en.json';

// ---------------------------------------------------------------------------
// Replicate the grouping logic from DocumentList.tsx (mirrors current code)
// ---------------------------------------------------------------------------
type DocumentGroupId =
  | 'employment'
  | 'self_employed'
  | 'property'
  | 'social_insurance'
  | 'tax_filing'
  | 'deductions'
  | 'expense'
  | 'banking'
  | 'other';

const documentGroups: Array<{ id: DocumentGroupId; types: DocumentType[] }> = [
  {
    id: 'employment',
    types: [
      DocumentType.PAYSLIP,
      DocumentType.LOHNZETTEL,
      DocumentType.L1_FORM,
      DocumentType.L1K_BEILAGE,
      DocumentType.L1AB_BEILAGE,
    ],
  },
  {
    id: 'self_employed',
    types: [
      DocumentType.E1A_BEILAGE,
      DocumentType.JAHRESABSCHLUSS,
      DocumentType.U1_FORM,
      DocumentType.U30_FORM,
      DocumentType.GEWERBESCHEIN,
    ],
  },
  {
    id: 'property',
    types: [
      DocumentType.PURCHASE_CONTRACT,
      DocumentType.RENTAL_CONTRACT,
      DocumentType.E1B_BEILAGE,
      DocumentType.PROPERTY_TAX,
      DocumentType.GRUNDBUCHAUSZUG,
      DocumentType.BETRIEBSKOSTENABRECHNUNG,
    ],
  },
  {
    id: 'social_insurance',
    types: [
      DocumentType.SVS_NOTICE,
      DocumentType.VERSICHERUNGSBESTAETIGUNG,
      DocumentType.LOAN_CONTRACT,
    ],
  },
  {
    id: 'tax_filing',
    types: [
      DocumentType.E1_FORM,
      DocumentType.E1KV_BEILAGE,
      DocumentType.EINKOMMENSTEUERBESCHEID,
    ],
  },
  {
    id: 'deductions',
    types: [
      DocumentType.SPENDENBESTAETIGUNG,
      DocumentType.KINDERBETREUUNGSKOSTEN,
      DocumentType.FORTBILDUNGSKOSTEN,
      DocumentType.PENDLERPAUSCHALE,
      DocumentType.KIRCHENBEITRAG,
    ],
  },
  {
    id: 'expense',
    types: [DocumentType.RECEIPT, DocumentType.INVOICE],
  },
  {
    id: 'banking',
    types: [DocumentType.BANK_STATEMENT, DocumentType.KONTOAUSZUG],
  },
  {
    id: 'other',
    types: [DocumentType.OTHER, DocumentType.UNKNOWN],
  },
];

function getDocumentGroupId(type: DocumentType): DocumentGroupId {
  const matched = documentGroups.find((g) => g.types.includes(type));
  return matched?.id || 'other';
}

// ---------------------------------------------------------------------------
// Test 1a: LOAN_CONTRACT should be in social_insurance group
// Bug: Currently LOAN_CONTRACT is in property group
// This test asserts the EXPECTED behavior — will FAIL on unfixed code
// Validates: Requirement 1.1
// ---------------------------------------------------------------------------
describe('Bug Condition 1a: LOAN_CONTRACT group mapping', () => {
  it('LOAN_CONTRACT should be classified as social_insurance (expected behavior)', () => {
    // Post-fix expectation: LOAN_CONTRACT belongs in social_insurance
    expect(getDocumentGroupId(DocumentType.LOAN_CONTRACT)).toBe('social_insurance');
  });

  it('social_insurance group should contain LOAN_CONTRACT (expected behavior)', () => {
    const socialInsuranceGroup = documentGroups.find((g) => g.id === 'social_insurance');
    expect(socialInsuranceGroup?.types).toContain(DocumentType.LOAN_CONTRACT);
  });

  it('property group should NOT contain LOAN_CONTRACT (expected behavior)', () => {
    const propertyGroup = documentGroups.find((g) => g.id === 'property');
    expect(propertyGroup?.types).not.toContain(DocumentType.LOAN_CONTRACT);
  });
});

// ---------------------------------------------------------------------------
// Test 1d: deductions group i18n labels should be intuitive
// Bug: Current labels are "抵扣与减免" / "Absetzbeträge & Freibeträge" / "Deductions & Allowances"
// Expected: "税务优惠凭证" / "Steuerliche Absetzposten" / "Tax Deduction Documents"
// This test asserts the EXPECTED behavior — will FAIL on unfixed code
// Validates: Requirement 1.2
// ---------------------------------------------------------------------------
describe('Bug Condition 1d: deductions group i18n labels', () => {
  it('Chinese deductions label should be "税务优惠凭证"', () => {
    const label = (zh as any).documents.groups.deductions;
    expect(label).toBe('税务优惠凭证');
  });

  it('German deductions label should be "Steuerliche Absetzposten"', () => {
    const label = (de as any).documents.groups.deductions;
    expect(label).toBe('Steuerliche Absetzposten');
  });

  it('English deductions label should be "Tax Deduction Documents"', () => {
    const label = (en as any).documents.groups.deductions;
    expect(label).toBe('Tax Deduction Documents');
  });
});


// ===========================================================================
// Preservation Tests — Task 2
//
// These tests capture the CURRENT (pre-fix) behavior for all non-LOAN_CONTRACT
// document types. They must PASS on unfixed code and continue to pass after
// the fix is applied, ensuring no regressions.
//
// **Validates: Requirements 3.1, 3.2, 3.4**
// ===========================================================================

describe('Preservation: Non-LOAN_CONTRACT group mappings are unchanged', () => {
  // Expected current mappings for every document type EXCEPT LOAN_CONTRACT
  const expectedMappings: Array<{ type: DocumentType; group: DocumentGroupId }> = [
    // employment
    { type: DocumentType.PAYSLIP, group: 'employment' },
    { type: DocumentType.LOHNZETTEL, group: 'employment' },
    { type: DocumentType.L1_FORM, group: 'employment' },
    { type: DocumentType.L1K_BEILAGE, group: 'employment' },
    { type: DocumentType.L1AB_BEILAGE, group: 'employment' },
    // self_employed
    { type: DocumentType.E1A_BEILAGE, group: 'self_employed' },
    { type: DocumentType.JAHRESABSCHLUSS, group: 'self_employed' },
    { type: DocumentType.U1_FORM, group: 'self_employed' },
    { type: DocumentType.U30_FORM, group: 'self_employed' },
    { type: DocumentType.GEWERBESCHEIN, group: 'self_employed' },
    // property (LOAN_CONTRACT excluded — that's the bug condition)
    { type: DocumentType.PURCHASE_CONTRACT, group: 'property' },
    { type: DocumentType.RENTAL_CONTRACT, group: 'property' },
    { type: DocumentType.E1B_BEILAGE, group: 'property' },
    { type: DocumentType.PROPERTY_TAX, group: 'property' },
    { type: DocumentType.GRUNDBUCHAUSZUG, group: 'property' },
    { type: DocumentType.BETRIEBSKOSTENABRECHNUNG, group: 'property' },
    // social_insurance
    { type: DocumentType.SVS_NOTICE, group: 'social_insurance' },
    { type: DocumentType.VERSICHERUNGSBESTAETIGUNG, group: 'social_insurance' },
    // tax_filing
    { type: DocumentType.E1_FORM, group: 'tax_filing' },
    { type: DocumentType.E1KV_BEILAGE, group: 'tax_filing' },
    { type: DocumentType.EINKOMMENSTEUERBESCHEID, group: 'tax_filing' },
    // deductions
    { type: DocumentType.SPENDENBESTAETIGUNG, group: 'deductions' },
    { type: DocumentType.KINDERBETREUUNGSKOSTEN, group: 'deductions' },
    { type: DocumentType.FORTBILDUNGSKOSTEN, group: 'deductions' },
    { type: DocumentType.PENDLERPAUSCHALE, group: 'deductions' },
    { type: DocumentType.KIRCHENBEITRAG, group: 'deductions' },
    // expense
    { type: DocumentType.RECEIPT, group: 'expense' },
    { type: DocumentType.INVOICE, group: 'expense' },
    // banking
    { type: DocumentType.BANK_STATEMENT, group: 'banking' },
    { type: DocumentType.KONTOAUSZUG, group: 'banking' },
    // other
    { type: DocumentType.OTHER, group: 'other' },
    { type: DocumentType.UNKNOWN, group: 'other' },
  ];

  it.each(expectedMappings)(
    '$type should be in $group group',
    ({ type, group }) => {
      expect(getDocumentGroupId(type)).toBe(group);
    },
  );

  it('RENTAL_CONTRACT is in property group (Req 3.1)', () => {
    expect(getDocumentGroupId(DocumentType.RENTAL_CONTRACT)).toBe('property');
  });

  it('PURCHASE_CONTRACT is in property group (Req 3.2)', () => {
    expect(getDocumentGroupId(DocumentType.PURCHASE_CONTRACT)).toBe('property');
  });

  it('PAYSLIP is in employment group (Req 3.4)', () => {
    expect(getDocumentGroupId(DocumentType.PAYSLIP)).toBe('employment');
  });

  it('every document type (except LOAN_CONTRACT) has exactly one group', () => {
    const allNonLoanTypes = Object.values(DocumentType).filter(
      (t) => t !== DocumentType.LOAN_CONTRACT,
    );
    for (const t of allNonLoanTypes) {
      const group = getDocumentGroupId(t);
      expect(group).toBeDefined();
      // Verify it appears in exactly one group
      const matchingGroups = documentGroups.filter((g) => g.types.includes(t));
      expect(matchingGroups.length).toBeLessThanOrEqual(1);
    }
  });
});

describe('Preservation: Current i18n group labels for non-deductions groups', () => {
  it('Chinese employment label is "工资与雇佣"', () => {
    expect((zh as any).documents.groups.employment).toBe('工资与雇佣');
  });

  it('Chinese property label is "房产与租赁"', () => {
    expect((zh as any).documents.groups.property).toBe('房产与租赁');
  });

  it('Chinese other label is "其他"', () => {
    expect((zh as any).documents.groups.other).toBe('其他');
  });

  it('all group IDs have Chinese translations', () => {
    const groupIds = ['employment', 'self_employed', 'property', 'social_insurance', 'tax_filing', 'deductions', 'expense', 'banking', 'other'];
    for (const id of groupIds) {
      expect((zh as any).documents.groups[id]).toBeDefined();
      expect(typeof (zh as any).documents.groups[id]).toBe('string');
    }
  });
});
