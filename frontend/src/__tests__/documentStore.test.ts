import { describe, expect, it } from 'vitest';

import { useDocumentStore } from '../stores/documentStore';

describe('documentStore addDocument', () => {
  it('does not append a duplicate document with the same id', () => {
    useDocumentStore.setState({
      documents: [
        {
          id: 101,
          user_id: 1,
          document_type: 'receipt' as any,
          file_path: '/docs/receipt.pdf',
          file_name: 'receipt.pdf',
          file_size: 128,
          mime_type: 'application/pdf',
          confidence_score: 0.8,
          needs_review: false,
          created_at: '2026-03-18T00:00:00Z',
          updated_at: '2026-03-18T00:00:00Z',
        },
      ],
      total: 1,
    });

    useDocumentStore.getState().addDocument({
      id: 101,
      user_id: 1,
      document_type: 'receipt' as any,
      file_path: '/docs/receipt.pdf',
      file_name: 'receipt.pdf',
      file_size: 128,
      mime_type: 'application/pdf',
      confidence_score: 0.95,
      needs_review: false,
      created_at: '2026-03-18T00:00:00Z',
      updated_at: '2026-03-18T01:00:00Z',
      deduplicated: true,
      message: 'Duplicate document detected. Existing document reused.',
    });

    const state = useDocumentStore.getState();
    expect(state.documents).toHaveLength(1);
    expect(state.total).toBe(1);
    expect(state.documents[0].deduplicated).toBe(true);
    expect(state.documents[0].confidence_score).toBe(0.95);
  });
});
