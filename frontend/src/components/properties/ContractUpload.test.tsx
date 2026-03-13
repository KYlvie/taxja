import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import i18n from '../../i18n';
import ContractUpload from './ContractUpload';
import { documentService } from '../../services/documentService';

// Mock document service
vi.mock('../../services/documentService', () => ({
  documentService: {
    uploadDocument: vi.fn(),
    getDocumentForReview: vi.fn(),
  },
}));

const renderWithI18n = (component: React.ReactElement) => {
  return render(
    <I18nextProvider i18n={i18n}>
      {component}
    </I18nextProvider>
  );
};

describe('ContractUpload', () => {
  const mockOnExtracted = vi.fn();
  const mockOnCancel = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders upload zone initially', () => {
    renderWithI18n(
      <ContractUpload onExtracted={mockOnExtracted} onCancel={mockOnCancel} />
    );

    expect(screen.getByText(/upload contract/i)).toBeInTheDocument();
    expect(screen.getAllByText(/kaufvertrag/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/mietvertrag/i).length).toBeGreaterThanOrEqual(1);
  });

  it('shows contract type cards', () => {
    renderWithI18n(
      <ContractUpload onExtracted={mockOnExtracted} onCancel={mockOnCancel} />
    );

    expect(screen.getByText(/Kaufvertrag \(Purchase Contract\)/)).toBeInTheDocument();
    expect(screen.getByText(/Mietvertrag \(Rental Contract\)/)).toBeInTheDocument();
  });

  it('calls onCancel when cancel button is clicked', () => {
    renderWithI18n(
      <ContractUpload onExtracted={mockOnExtracted} onCancel={mockOnCancel} />
    );

    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    fireEvent.click(cancelButton);

    expect(mockOnCancel).toHaveBeenCalledTimes(1);
  });

  it('validates file type', async () => {
    renderWithI18n(
      <ContractUpload onExtracted={mockOnExtracted} onCancel={mockOnCancel} />
    );

    const file = new File(['test'], 'test.txt', { type: 'text/plain' });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    Object.defineProperty(input, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(input);

    await waitFor(() => {
      expect(screen.getByText(/invalid file type/i)).toBeInTheDocument();
    });
  });

  it('validates file size', async () => {
    renderWithI18n(
      <ContractUpload onExtracted={mockOnExtracted} onCancel={mockOnCancel} />
    );

    // Create a file larger than 10MB
    const largeFile = new File(['x'.repeat(11 * 1024 * 1024)], 'large.pdf', {
      type: 'application/pdf',
    });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    Object.defineProperty(input, 'files', {
      value: [largeFile],
      writable: false,
    });

    fireEvent.change(input);

    await waitFor(() => {
      expect(screen.getByText(/file too large/i)).toBeInTheDocument();
    });
  });

  it('uploads and processes Kaufvertrag successfully', async () => {
    const mockDocument = {
      id: 1,
      user_id: 1,
      document_type: 'kaufvertrag',
      file_name: 'kaufvertrag.pdf',
      file_path: '/path/to/file',
      file_size: 1024,
      mime_type: 'application/pdf',
      confidence_score: 0.85,
      needs_review: false,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    };

    const mockReviewData = {
      document: mockDocument,
      extracted_data: {
        document_type: 'kaufvertrag',
        street: 'Hauptstraße 123',
        city: 'Wien',
        postal_code: '1010',
        purchase_date: '2020-06-15',
        purchase_price: 350000,
        building_value: 280000,
        notary_fees: 5000,
        grunderwerbsteuer: 12000,
        confidence: 0.85,
      },
      suggestions: [],
    };

    vi.mocked(documentService.uploadDocument).mockResolvedValue(mockDocument);
    vi.mocked(documentService.getDocumentForReview).mockResolvedValue(mockReviewData);

    renderWithI18n(
      <ContractUpload onExtracted={mockOnExtracted} onCancel={mockOnCancel} />
    );

    const file = new File(['test'], 'kaufvertrag.pdf', {
      type: 'application/pdf',
    });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    Object.defineProperty(input, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(input);

    // Wait for upload
    await waitFor(() => {
      expect(screen.getByText(/uploading/i)).toBeInTheDocument();
    });

    // Wait for processing
    await waitFor(() => {
      expect(screen.getByText(/processing/i)).toBeInTheDocument();
    });

    // Wait for extraction results
    await waitFor(() => {
      expect(screen.getByText(/extracted data/i)).toBeInTheDocument();
    }, { timeout: 3000 });

    // Check extracted fields are displayed
    expect(screen.getByDisplayValue('Hauptstraße 123')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Wien')).toBeInTheDocument();
    expect(screen.getByDisplayValue('1010')).toBeInTheDocument();
  });

  it('allows editing extracted data', async () => {
    const mockDocument = {
      id: 1,
      user_id: 1,
      document_type: 'kaufvertrag',
      file_name: 'kaufvertrag.pdf',
      file_path: '/path/to/file',
      file_size: 1024,
      mime_type: 'application/pdf',
      confidence_score: 0.85,
      needs_review: false,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    };

    const mockReviewData = {
      document: mockDocument,
      extracted_data: {
        document_type: 'kaufvertrag',
        street: 'Hauptstraße 123',
        city: 'Wien',
        postal_code: '1010',
        confidence: 0.85,
      },
      suggestions: [],
    };

    vi.mocked(documentService.uploadDocument).mockResolvedValue(mockDocument);
    vi.mocked(documentService.getDocumentForReview).mockResolvedValue(mockReviewData);

    renderWithI18n(
      <ContractUpload onExtracted={mockOnExtracted} onCancel={mockOnCancel} />
    );

    const file = new File(['test'], 'kaufvertrag.pdf', {
      type: 'application/pdf',
    });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    Object.defineProperty(input, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(input);

    await waitFor(() => {
      expect(screen.getByText(/extracted data/i)).toBeInTheDocument();
    }, { timeout: 3000 });

    // Edit street field
    const streetInput = screen.getByDisplayValue('Hauptstraße 123');
    fireEvent.change(streetInput, { target: { value: 'Nebenstraße 456' } });

    expect(screen.getByDisplayValue('Nebenstraße 456')).toBeInTheDocument();
  });

  it('calls onExtracted with edited data when confirmed', async () => {
    const mockDocument = {
      id: 1,
      user_id: 1,
      document_type: 'kaufvertrag',
      file_name: 'kaufvertrag.pdf',
      file_path: '/path/to/file',
      file_size: 1024,
      mime_type: 'application/pdf',
      confidence_score: 0.85,
      needs_review: false,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    };

    const mockReviewData = {
      document: mockDocument,
      extracted_data: {
        document_type: 'kaufvertrag',
        street: 'Hauptstraße 123',
        city: 'Wien',
        postal_code: '1010',
        purchase_price: 350000,
        confidence: 0.85,
      },
      suggestions: [],
    };

    vi.mocked(documentService.uploadDocument).mockResolvedValue(mockDocument);
    vi.mocked(documentService.getDocumentForReview).mockResolvedValue(mockReviewData);

    renderWithI18n(
      <ContractUpload onExtracted={mockOnExtracted} onCancel={mockOnCancel} />
    );

    const file = new File(['test'], 'kaufvertrag.pdf', {
      type: 'application/pdf',
    });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    Object.defineProperty(input, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(input);

    await waitFor(() => {
      expect(screen.getByText(/extracted data/i)).toBeInTheDocument();
    }, { timeout: 3000 });

    // Click use data button
    const useDataButton = screen.getByRole('button', { name: /use this data/i });
    fireEvent.click(useDataButton);

    expect(mockOnExtracted).toHaveBeenCalledWith(
      expect.objectContaining({
        street: 'Hauptstraße 123',
        city: 'Wien',
        postal_code: '1010',
        purchase_price: '350000',
      }),
      expect.objectContaining({
        document_type: 'kaufvertrag',
        confidence: 0.85,
      })
    );
  });

  it('shows low confidence warning', async () => {
    const mockDocument = {
      id: 1,
      user_id: 1,
      document_type: 'kaufvertrag',
      file_name: 'kaufvertrag.pdf',
      file_path: '/path/to/file',
      file_size: 1024,
      mime_type: 'application/pdf',
      confidence_score: 0.65,
      needs_review: true,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    };

    const mockReviewData = {
      document: mockDocument,
      extracted_data: {
        document_type: 'kaufvertrag',
        street: 'Hauptstraße 123',
        confidence: 0.65,
      },
      suggestions: [],
    };

    vi.mocked(documentService.uploadDocument).mockResolvedValue(mockDocument);
    vi.mocked(documentService.getDocumentForReview).mockResolvedValue(mockReviewData);

    renderWithI18n(
      <ContractUpload onExtracted={mockOnExtracted} onCancel={mockOnCancel} />
    );

    const file = new File(['test'], 'kaufvertrag.pdf', {
      type: 'application/pdf',
    });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    Object.defineProperty(input, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(input);

    await waitFor(() => {
      expect(screen.getByText(/confidence is low/i)).toBeInTheDocument();
    }, { timeout: 3000 });

    expect(screen.getByText(/carefully review/i)).toBeInTheDocument();
  });

  it('handles upload error', async () => {
    vi.mocked(documentService.uploadDocument).mockRejectedValue(
      new Error('Upload failed')
    );

    renderWithI18n(
      <ContractUpload onExtracted={mockOnExtracted} onCancel={mockOnCancel} />
    );

    const file = new File(['test'], 'kaufvertrag.pdf', {
      type: 'application/pdf',
    });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    Object.defineProperty(input, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(input);

    await waitFor(() => {
      expect(screen.getByText(/upload failed/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/error uploading contract/i)).toBeInTheDocument();
  });

  it('allows retry after error', async () => {
    vi.mocked(documentService.uploadDocument).mockRejectedValue(
      new Error('Upload failed')
    );

    renderWithI18n(
      <ContractUpload onExtracted={mockOnExtracted} onCancel={mockOnCancel} />
    );

    const file = new File(['test'], 'kaufvertrag.pdf', {
      type: 'application/pdf',
    });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    Object.defineProperty(input, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(input);

    await waitFor(() => {
      expect(screen.getByText(/upload failed/i)).toBeInTheDocument();
    });

    // Click retry button
    const retryButton = screen.getByRole('button', { name: /retry/i });
    fireEvent.click(retryButton);

    // Should return to initial state
    expect(screen.getByText(/upload contract/i)).toBeInTheDocument();
  });
});
