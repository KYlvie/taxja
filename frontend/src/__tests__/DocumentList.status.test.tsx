/* @vitest-environment jsdom */

import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DocumentList from '../components/documents/DocumentList';
import { useDocumentStore } from '../stores/documentStore';
import { DocumentType } from '../types/document';

const { getDocuments } = vi.hoisted(() => ({
  getDocuments: vi.fn(),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: string | { defaultValue?: string }) =>
      (typeof options === 'string' ? options : options?.defaultValue) ??
      (
        {
          'documents.status.transactionCreated': '已生成交易',
          'documents.status.recognized': '已识别',
          'documents.groups.all': '全部文档',
          'documents.groups.expense': '票据发票',
          'documents.groups.employment': '工资与雇佣',
          'documents.groups.self_employed': '自营/企业',
          'documents.groups.property': '房产与租赁',
          'documents.groups.social_insurance': '社保与保险',
          'documents.groups.tax_filing': '税务申报与通知',
          'documents.groups.deductions': '抵扣与减免',
          'documents.groups.banking': '银行资料',
          'documents.groups.other': '其他',
          'documents.list.name': '文件',
          'documents.list.type': '分类',
          'documents.list.uploadDate': '日期',
          'documents.list.size': '大小',
          'documents.list.confidence': '识别可信度',
          'documents.list.status': '状态',
          'documents.search.placeholder': '搜索',
          'documents.viewGrid': '网格视图',
          'documents.viewList': '列表视图',
          'documents.filters.clear': '清空筛选',
          'documents.emptyGroup': '空',
          'documents.types.receipt': '收据',
          'documents.download': '下载',
          'common.delete': '删除',
        } as Record<string, string>
      )[key] ?? key,
    i18n: { language: 'zh', resolvedLanguage: 'zh' },
  }),
}));

vi.mock('../services/documentService', () => ({
  documentService: {
    getDocuments,
    deleteDocument: vi.fn(),
    downloadDocument: vi.fn(),
  },
}));

vi.mock('../stores/aiAdvisorStore', () => ({
  useAIAdvisorStore: (
    selector: (state: { pushMessage: ReturnType<typeof vi.fn> }) => unknown
  ) => selector({ pushMessage: vi.fn() }),
}));

vi.mock('../mobile/files', () => ({
  saveBlobWithNativeShare: vi.fn(),
}));

describe('DocumentList status', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useDocumentStore.setState({
      documents: [],
      currentDocument: null,
      total: 0,
      loading: false,
      error: null,
      filters: {},
    });
  });

  it('shows transaction-created status when a document is already linked to a transaction', async () => {
    getDocuments.mockResolvedValue({
      documents: [
        {
          id: 118,
          user_id: 5,
          document_type: DocumentType.RECEIPT,
          file_path: 'users/5/documents/receipt.png',
          file_name: 'receipt.png',
          file_size: 1024,
          mime_type: 'image/png',
          confidence_score: 1,
          needs_review: false,
          transaction_id: 1151,
          ocr_result: { confirmed: true },
          ocr_status: 'completed',
          created_at: '2026-03-18T02:09:54.000Z',
          updated_at: '2026-03-18T02:09:54.000Z',
          processed_at: '2026-03-18T02:09:54.000Z',
        },
      ],
      total: 1,
    });

    render(
      <MemoryRouter>
        <DocumentList />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Transaction created')).toBeInTheDocument();
    });

    expect(screen.queryByText('Recognized')).not.toBeInTheDocument();
  });
});
