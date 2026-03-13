import api from './api';
import i18n from 'i18next';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export interface ChatResponse {
  content: string;
  timestamp: string;
}

export interface ContextData {
  page?: string;
  documentId?: string;
  transactionId?: string;
  [key: string]: any;
}

class AIService {
  private getLanguage(): string {
    return i18n.language?.substring(0, 2) || 'de';
  }

  async sendMessage(message: string, _contextData?: ContextData): Promise<ChatResponse> {
    const response = await api.post('/ai/chat', {
      message,
      language: this.getLanguage(),
    }, {
      timeout: 120000,  // 120s — Ollama on CPU can be slow
    });
    // Backend returns { message, message_id, timestamp }
    return {
      content: response.data.message,
      timestamp: response.data.timestamp,
    };
  }

  async getChatHistory(): Promise<ChatMessage[]> {
    const response = await api.get('/ai/history');
    // Backend returns { messages: [...], total_count, has_more }
    const data = response.data;
    const messages = data.messages || data;
    return messages.map((msg: any) => ({
      id: String(msg.id),
      role: msg.role,
      content: msg.content,
      timestamp: msg.created_at || msg.timestamp,
    }));
  }

  async clearChatHistory(): Promise<void> {
    await api.delete('/ai/history');
  }

  async askAboutDocument(_documentId: string, question?: string): Promise<ChatResponse> {
    return this.sendMessage(
      question || 'Explain this document and its deductibility'
    );
  }

  async askForSuggestions(currentTaxData: any): Promise<ChatResponse> {
    const lang = this.getLanguage();
    const parts: string[] = [];

    if (currentTaxData?.simulationResult) {
      const r = currentTaxData.simulationResult;
      parts.push(`Current tax: ${r.currentTax}, Simulated tax: ${r.simulatedTax}, Difference: ${r.taxDifference}`);
      parts.push(`Current net income: ${r.currentNetIncome}, Simulated net income: ${r.simulatedNetIncome}`);
    }

    const contextStr = parts.length > 0 ? ` My current situation: ${parts.join('. ')}.` : '';

    const prompts: Record<string, string> = {
      de: `Welche Steueroptimierungen kannst du mir vorschlagen?${contextStr}`,
      en: `What tax optimization suggestions do you have for my situation?${contextStr}`,
      zh: `\u4F60\u80FD\u7ED9\u6211\u4EC0\u4E48\u7A0E\u52A1\u4F18\u5316\u5EFA\u8BAE\uFF1F${contextStr}`,
    };

    return this.sendMessage(prompts[lang] || prompts.de);
  }

  async explainOCRResult(_documentId: string, _ocrData: any): Promise<ChatResponse> {
    return this.sendMessage(
      'Explain these OCR results and which items are deductible'
    );
  }
}

export const aiService = new AIService();
