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
});
