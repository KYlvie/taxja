/* @vitest-environment jsdom */

import { fireEvent, render, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DocumentUpload from '../components/documents/DocumentUpload';
import { useAIAdvisorStore } from '../stores/aiAdvisorStore';
import { useAuthStore } from '../stores/authStore';
import { useDocumentStore } from '../stores/documentStore';

const uploadDocument = vi.fn();
const uploadImageGroup = vi.fn();
const getDocument = vi.fn();
const mockNavigate = vi.fn();

vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: any) => {
      if (typeof opts === 'string') return opts;
      if (opts?.defaultValue) {
        return opts.defaultValue.replace(/\{\{(\w+)\}\}/g, (_: string, token: string) => String(opts[token] ?? ''));
      }
      return key;
    },
    i18n: { language: 'en', resolvedLanguage: 'en' },
  }),
}));

vi.mock('../services/documentService', () => ({
  documentService: {
    uploadDocument: (...args: any[]) => uploadDocument(...args),
    uploadImageGroup: (...args: any[]) => uploadImageGroup(...args),
    getDocument: (...args: any[]) => getDocument(...args),
  },
}));

vi.mock('../services/employerService', () => ({
  employerService: {
    detectFromDocument: vi.fn(),
    detectAnnualArchiveFromDocument: vi.fn(),
  },
}));

vi.mock('../mobile/files', () => ({
  capturePhotoAsFile: vi.fn(),
  pickNativeFiles: vi.fn(),
  supportsNativeFileActions: () => false,
}));

describe('DocumentUpload landlord recurring notifications', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockNavigate.mockReset();

    useAuthStore.setState({
      user: null,
      token: null,
      isAuthenticated: false,
    });
    useDocumentStore.setState({
      documents: [],
      currentDocument: null,
      total: 0,
      loading: false,
      error: null,
      filters: {},
    });
    useAIAdvisorStore.getState().clearMessages();

    uploadDocument.mockResolvedValue({
      id: 611,
      user_id: 1,
      document_type: 'rental_contract',
      file_path: '/docs/vl_01.pdf',
      file_name: 'VL_01_Mietvertrag_Praterstrasse.pdf',
      file_size: 1024,
      mime_type: 'application/pdf',
      confidence_score: 0,
      needs_review: false,
      created_at: '2026-03-28T00:00:00Z',
      updated_at: '2026-03-28T00:00:00Z',
      uploaded_at: '2026-03-28T00:00:00Z',
    });
  });

  it('pushes a recurring confirmation notification for matched landlord rental contracts', async () => {
    getDocument.mockResolvedValueOnce({
      id: 611,
      user_id: 1,
      document_type: 'rental_contract',
      file_path: '/docs/vl_01.pdf',
      file_name: 'VL_01_Mietvertrag_Praterstrasse.pdf',
      file_size: 1024,
      mime_type: 'application/pdf',
      confidence_score: 0.97,
      needs_review: false,
      created_at: '2026-03-28T00:00:00Z',
      updated_at: '2026-03-28T00:00:00Z',
      processed_at: '2026-03-28T00:01:00Z',
      ocr_status: 'completed',
      ocr_result: {
        property_address: 'Praterstrasse 40/12, 1020 Wien',
        monthly_rent: 1035,
        import_suggestion: {
          type: 'create_recurring_income',
          status: 'pending',
          data: {
            monthly_rent: 1035,
            address: 'Praterstrasse 40/12, 1020 Wien',
            matched_property_id: 'prop-1020',
            matched_property_address: 'Praterstrasse 40/12, 1020 Wien',
          },
        },
        _pipeline: {
          current_state: 'completed',
        },
      },
    });

    const { container } = render(<DocumentUpload />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;

    fireEvent.change(input, {
      target: {
        files: [new File(['rental'], 'VL_01_Mietvertrag_Praterstrasse.pdf', { type: 'application/pdf' })],
      },
    });

    await waitFor(() => expect(uploadDocument).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(611), { timeout: 5000 });

    await waitFor(() => {
      expect(useAIAdvisorStore.getState().messages).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            type: 'recurring_confirm',
            content: 'ai.proactive.recurringFound',
            documentId: 611,
            actionStatus: 'pending',
            actionData: expect.objectContaining({
              suggestion_type: 'create_recurring_income',
              monthly_rent: 1035,
              matched_property_id: 'prop-1020',
            }),
          }),
        ]),
      );
    }, { timeout: 7000 });
  }, 15000);

  it('pushes the no-property-match notification when the landlord contract cannot be linked', async () => {
    getDocument.mockResolvedValueOnce({
      id: 611,
      user_id: 1,
      document_type: 'rental_contract',
      file_path: '/docs/vl_01.pdf',
      file_name: 'VL_01_Mietvertrag_Praterstrasse.pdf',
      file_size: 1024,
      mime_type: 'application/pdf',
      confidence_score: 0.97,
      needs_review: false,
      created_at: '2026-03-28T00:00:00Z',
      updated_at: '2026-03-28T00:00:00Z',
      processed_at: '2026-03-28T00:01:00Z',
      ocr_status: 'completed',
      ocr_result: {
        property_address: 'Praterstrasse 40/12, 1020 Wien',
        monthly_rent: 1035,
        import_suggestion: {
          type: 'create_recurring_income',
          status: 'pending',
          data: {
            monthly_rent: 1035,
            address: 'Praterstrasse 40/12, 1020 Wien',
            no_property_match: true,
          },
        },
        _pipeline: {
          current_state: 'completed',
        },
      },
    });

    const { container } = render(<DocumentUpload />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;

    fireEvent.change(input, {
      target: {
        files: [new File(['rental'], 'VL_01_Mietvertrag_Praterstrasse.pdf', { type: 'application/pdf' })],
      },
    });

    await waitFor(() => expect(uploadDocument).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(611), { timeout: 5000 });

    await waitFor(() => {
      expect(useAIAdvisorStore.getState().messages).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            type: 'recurring_confirm',
            content: 'ai.proactive.recurringNoProperty',
            documentId: 611,
            actionData: expect.objectContaining({
              suggestion_type: 'create_recurring_income',
              no_property_match: true,
            }),
          }),
        ]),
      );
    }, { timeout: 7000 });
  }, 15000);
});
