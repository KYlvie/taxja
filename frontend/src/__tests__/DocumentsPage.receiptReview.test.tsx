/* @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import DocumentsPage from '../pages/DocumentsPage';

const getDocument = vi.fn();
const downloadDocument = vi.fn();
const correctOCR = vi.fn();
const getById = vi.fn();
const updateTransaction = vi.fn();
const aiToast = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string | { defaultValue?: string }) => {
      const translations: Record<string, string> = {
        'documents.ocr.quantity': '数量',
        'documents.ocr.category': '类别',
        'transactions.categories.maintenance': '维修保养',
      };
      if (typeof fallback === 'string') return fallback;
      if (translations[key]) return translations[key];
      if (fallback && typeof fallback === 'object' && typeof fallback.defaultValue === 'string') {
        return fallback.defaultValue;
      }
      return key;
    },
  }),
}));

vi.mock('../components/documents/DocumentUpload', () => ({ default: () => <div data-testid="doc-upload" /> }));
vi.mock('../components/documents/DocumentList', () => ({ default: () => <div data-testid="doc-list" /> }));
vi.mock('../components/documents/OCRReview', () => ({ default: () => <div data-testid="ocr-review" /> }));
vi.mock('../components/documents/EmployerReviewPanel', () => ({ default: () => null }));
vi.mock('../components/documents/BescheidImport', () => ({ default: () => null }));
vi.mock('../components/documents/E1FormImport', () => ({ default: () => null }));
vi.mock('../components/documents/SuggestionCardFactory', () => ({ default: () => null }));

vi.mock('../services/documentService', () => ({
  documentService: {
    getDocument: (...args: any[]) => getDocument(...args),
    downloadDocument: (...args: any[]) => downloadDocument(...args),
    correctOCR: (...args: any[]) => correctOCR(...args),
  },
}));

vi.mock('../services/transactionService', () => ({
  transactionService: {
    getById: (...args: any[]) => getById(...args),
    update: (...args: any[]) => updateTransaction(...args),
  },
}));

vi.mock('../mobile/files', () => ({
  saveBlobWithNativeShare: vi.fn(),
}));

vi.mock('../stores/refreshStore', () => ({
  useRefreshStore: {
    getState: () => ({
      refreshTransactions: vi.fn(),
      refreshDashboard: vi.fn(),
      refreshProperties: vi.fn(),
      refreshRecurring: vi.fn(),
    }),
  },
}));

vi.mock('../stores/aiToastStore', () => ({
  aiToast: (...args: any[]) => aiToast(...args),
}));

describe('DocumentsPage receipt review flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.URL.createObjectURL = vi.fn(() => 'blob:test');
    global.URL.revokeObjectURL = vi.fn();

    const documentDetail = {
      id: 101,
      user_id: 1,
      document_type: 'receipt',
      file_path: '/tmp/receipt.pdf',
      file_name: 'receipt.pdf',
      file_size: 100,
      mime_type: 'application/pdf',
      confidence_score: 0.92,
      needs_review: false,
      created_at: '2026-03-17T00:00:00Z',
      updated_at: '2026-03-17T00:00:00Z',
      ocr_result: {
        merchant: 'Billa',
        amount: 4.99,
        line_items: [
          {
            description: 'Druckerpapier A4',
            amount: 4.99,
            quantity: 1,
            vat_rate: 20,
            category: 'maintenance',
            is_deductible: true,
            deduction_reason: 'Betriebsausgabe – Büromaterial',
          },
        ],
      },
    };

    getDocument
      .mockResolvedValueOnce(documentDetail)
      .mockResolvedValueOnce(documentDetail);
    downloadDocument.mockResolvedValue(new Blob(['pdf']));
    correctOCR.mockResolvedValue(documentDetail);
    getById.mockResolvedValue(null);
  });

  it('shows system judgment first and enters a real edit mode before saving', async () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/documents/101']}>
        <Routes>
          <Route path="/documents/:documentId" element={<DocumentsPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(getDocument).toHaveBeenCalledWith(101));
    await waitFor(() => expect(screen.getByText('税务判断')).toBeInTheDocument());

    expect(screen.queryByPlaceholderText('填写判断原因或备注')).not.toBeInTheDocument();
    expect(screen.getByText('系统会先给出预判，只有您觉得不对时再点编辑修改。')).toBeInTheDocument();

    expect(screen.getByText('商家')).toBeInTheDocument();
    expect(screen.getByText('数量 1 | 维修保养')).toBeInTheDocument();
    expect(screen.queryByText('Qty 1 | maintenance')).not.toBeInTheDocument();

    const editButton = container.querySelector('.receipt-review-edit-btn') as HTMLButtonElement;
    fireEvent.click(editButton);

    expect(screen.getByPlaceholderText('填写判断原因或备注')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '不可抵税' }));
    fireEvent.change(screen.getByPlaceholderText('填写判断原因或备注'), {
      target: { value: '改成人工复核结论' },
    });
    fireEvent.click(screen.getByRole('button', { name: '保存这张小票' }));

    await waitFor(() => expect(correctOCR).toHaveBeenCalledTimes(1));
    const correctedPayload = correctOCR.mock.calls[0][1];
    expect(correctedPayload.line_items[0].is_deductible).toBe(false);
    expect(correctedPayload.line_items[0].deduction_reason).toBe('改成人工复核结论');
  });
});
