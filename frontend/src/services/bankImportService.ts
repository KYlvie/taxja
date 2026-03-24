import api from './api';
import type {
  BankStatementImportSummary,
  BankStatementLine,
  BankStatementTransactionSummary,
} from '../types/bankImport';

type ImportEnvelope = {
  success: boolean;
  import: BankStatementImportSummary;
};

type LinesEnvelope = {
  success: boolean;
  lines: BankStatementLine[];
};

type LineActionEnvelope = {
  success: boolean;
  line: BankStatementLine;
  transaction?: BankStatementTransactionSummary;
};

export const bankImportService = {
  initializeFromDocument: async (documentId: number): Promise<BankStatementImportSummary> => {
    const response = await api.post<ImportEnvelope>(`/bank-import/document/${documentId}/initialize`);
    return response.data.import;
  },

  getImport: async (importId: number): Promise<BankStatementImportSummary> => {
    const response = await api.get<ImportEnvelope>(`/bank-import/imports/${importId}`);
    return response.data.import;
  },

  getLines: async (importId: number): Promise<BankStatementLine[]> => {
    const response = await api.get<LinesEnvelope>(`/bank-import/imports/${importId}/lines`);
    return response.data.lines;
  },

  confirmCreateLine: async (lineId: number): Promise<LineActionEnvelope> => {
    const response = await api.post<LineActionEnvelope>(`/bank-import/lines/${lineId}/confirm-create`);
    return response.data;
  },

  matchExistingLine: async (lineId: number, transactionId?: number): Promise<LineActionEnvelope> => {
    const response = await api.post<LineActionEnvelope>(
      `/bank-import/lines/${lineId}/match-existing`,
      transactionId ? { transaction_id: transactionId } : {}
    );
    return response.data;
  },

  ignoreLine: async (lineId: number): Promise<LineActionEnvelope> => {
    const response = await api.post<LineActionEnvelope>(`/bank-import/lines/${lineId}/ignore`);
    return response.data;
  },
};

export default bankImportService;
