import { describe, expect, it } from 'vitest';

import { canReprocessDocument } from '../utils/documentReprocessing';

describe('canReprocessDocument', () => {
  it('allows retry for OCR-capable unconfirmed documents', () => {
    expect(
      canReprocessDocument({
        id: 1,
        mime_type: 'application/pdf',
        transaction_id: undefined,
        ocr_status: 'completed',
        ocr_result: {
          merchant: 'Billa',
        },
      })
    ).toBe(true);
  });

  it('hides retry when a transaction has already been created', () => {
    expect(
      canReprocessDocument({
        id: 2,
        mime_type: 'application/pdf',
        transaction_id: 99,
        ocr_status: 'completed',
        ocr_result: {
          merchant: 'Billa',
        },
      })
    ).toBe(false);
  });

  it('hides retry when the document has already been confirmed', () => {
    expect(
      canReprocessDocument({
        id: 3,
        mime_type: 'application/pdf',
        transaction_id: undefined,
        ocr_status: 'completed',
        ocr_result: {
          confirmed: true,
        },
      })
    ).toBe(false);
  });

  it('hides retry when a contract suggestion has already been confirmed', () => {
    expect(
      canReprocessDocument({
        id: 4,
        mime_type: 'application/pdf',
        transaction_id: undefined,
        ocr_status: 'completed',
        ocr_result: {
          import_suggestion: {
            type: 'create_property',
            status: 'confirmed',
            property_id: 'prop-1',
          },
        },
      })
    ).toBe(false);
  });

  it('hides retry when an asset outcome has already been auto-created', () => {
    expect(
      canReprocessDocument({
        id: 5,
        mime_type: 'application/pdf',
        transaction_id: undefined,
        ocr_status: 'completed',
        ocr_result: {
          asset_outcome: {
            status: 'auto_created',
            asset_id: 'asset-1',
          },
        },
      })
    ).toBe(false);
  });

  it('hides retry when the document list reports linked transactions', () => {
    expect(
      canReprocessDocument({
        id: 6,
        mime_type: 'application/pdf',
        transaction_id: undefined,
        linked_transaction_count: 2,
        ocr_status: 'completed',
        ocr_result: {
          import_suggestion: {
            type: 'import_bank_statement',
            status: 'pending',
          },
        },
      })
    ).toBe(false);
  });

  it('hides retry when bank import progress already created transactions', () => {
    expect(
      canReprocessDocument({
        id: 7,
        mime_type: 'application/pdf',
        transaction_id: undefined,
        ocr_status: 'completed',
        ocr_result: {
          import_suggestion: {
            type: 'import_bank_statement',
            status: 'pending',
            imported_count: 1,
            created_transaction_ids: [901],
          },
        },
      })
    ).toBe(false);
  });
});
