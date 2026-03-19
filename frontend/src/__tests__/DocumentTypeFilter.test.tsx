/**
 * Tests for document type grouping logic used in DocumentList.
 *
 * The grouping is defined in DocumentList.tsx via `documentGroups` and
 * `getDocumentGroupId`. We replicate the logic here to validate correctness
 * without needing to render the full component (which depends on stores/API).
 */
import { describe, it, expect } from 'vitest';
import { DocumentType } from '../types/document';

// ---------------------------------------------------------------------------
// Replicate the grouping logic from DocumentList.tsx
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
// Tests
// ---------------------------------------------------------------------------
describe('Document type grouping', () => {
  it('should define exactly 9 groups', () => {
    expect(documentGroups).toHaveLength(9);
  });

  it('should cover all DocumentType enum values', () => {
    const allGroupedTypes = documentGroups.flatMap((g) => g.types);
    const enumValues = Object.values(DocumentType);
    for (const val of enumValues) {
      expect(allGroupedTypes).toContain(val);
    }
  });

  it('should not have any type in multiple groups', () => {
    const allGroupedTypes = documentGroups.flatMap((g) => g.types);
    const unique = new Set(allGroupedTypes);
    expect(unique.size).toBe(allGroupedTypes.length);
  });
});

describe('Employment group', () => {
  const types = [
    DocumentType.PAYSLIP,
    DocumentType.LOHNZETTEL,
    DocumentType.L1_FORM,
    DocumentType.L1K_BEILAGE,
    DocumentType.L1AB_BEILAGE,
  ];
  it.each(types)('classifies %s as employment', (type) => {
    expect(getDocumentGroupId(type)).toBe('employment');
  });
  it('contains 5 types', () => {
    expect(documentGroups.find((g) => g.id === 'employment')?.types).toHaveLength(5);
  });
});

describe('Self-employed group', () => {
  const types = [
    DocumentType.E1A_BEILAGE,
    DocumentType.JAHRESABSCHLUSS,
    DocumentType.U1_FORM,
    DocumentType.U30_FORM,
    DocumentType.GEWERBESCHEIN,
  ];
  it.each(types)('classifies %s as self_employed', (type) => {
    expect(getDocumentGroupId(type)).toBe('self_employed');
  });
});

describe('Property group', () => {
  const types = [
    DocumentType.PURCHASE_CONTRACT,
    DocumentType.RENTAL_CONTRACT,
    DocumentType.E1B_BEILAGE,
    DocumentType.PROPERTY_TAX,
    DocumentType.GRUNDBUCHAUSZUG,
    DocumentType.BETRIEBSKOSTENABRECHNUNG,
  ];
  it.each(types)('classifies %s as property', (type) => {
    expect(getDocumentGroupId(type)).toBe('property');
  });
});

describe('Social insurance group', () => {
  it('classifies SVS_NOTICE as social_insurance', () => {
    expect(getDocumentGroupId(DocumentType.SVS_NOTICE)).toBe('social_insurance');
  });
  it('classifies VERSICHERUNGSBESTAETIGUNG as social_insurance', () => {
    expect(getDocumentGroupId(DocumentType.VERSICHERUNGSBESTAETIGUNG)).toBe('social_insurance');
  });
  it('classifies LOAN_CONTRACT as social_insurance', () => {
    expect(getDocumentGroupId(DocumentType.LOAN_CONTRACT)).toBe('social_insurance');
  });
});

describe('Tax filing group', () => {
  const types = [DocumentType.E1_FORM, DocumentType.E1KV_BEILAGE, DocumentType.EINKOMMENSTEUERBESCHEID];
  it.each(types)('classifies %s as tax_filing', (type) => {
    expect(getDocumentGroupId(type)).toBe('tax_filing');
  });
});

describe('Deductions group', () => {
  const types = [
    DocumentType.SPENDENBESTAETIGUNG,
    DocumentType.KINDERBETREUUNGSKOSTEN,
    DocumentType.FORTBILDUNGSKOSTEN,
    DocumentType.PENDLERPAUSCHALE,
    DocumentType.KIRCHENBEITRAG,
  ];
  it.each(types)('classifies %s as deductions', (type) => {
    expect(getDocumentGroupId(type)).toBe('deductions');
  });
});

describe('Expense group', () => {
  it('classifies RECEIPT as expense', () => {
    expect(getDocumentGroupId(DocumentType.RECEIPT)).toBe('expense');
  });
  it('classifies INVOICE as expense', () => {
    expect(getDocumentGroupId(DocumentType.INVOICE)).toBe('expense');
  });
});

describe('Banking group', () => {
  it('classifies BANK_STATEMENT as banking', () => {
    expect(getDocumentGroupId(DocumentType.BANK_STATEMENT)).toBe('banking');
  });
  it('classifies KONTOAUSZUG as banking', () => {
    expect(getDocumentGroupId(DocumentType.KONTOAUSZUG)).toBe('banking');
  });
});

describe('Other / fallback group', () => {
  it('classifies OTHER as other', () => {
    expect(getDocumentGroupId(DocumentType.OTHER)).toBe('other');
  });
  it('classifies UNKNOWN as other', () => {
    expect(getDocumentGroupId(DocumentType.UNKNOWN)).toBe('other');
  });
  it('falls back to other for unrecognised types', () => {
    expect(getDocumentGroupId('nonexistent_type' as DocumentType)).toBe('other');
  });
});
