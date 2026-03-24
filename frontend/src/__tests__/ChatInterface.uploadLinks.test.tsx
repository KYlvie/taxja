/* @vitest-environment jsdom */

import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ChatInterface from '../components/ai/ChatInterface';
import { useAIAdvisorStore } from '../stores/aiAdvisorStore';

const mockNavigate = vi.fn();
const mockFetchCreditBalance = vi.fn();

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
      const fallbacks: Record<string, string> = {
        'ai.proactive.viewDocument': 'View document',
        'ai.proactive.viewDetails': 'View details',
        'common.close': 'Close',
        'ai.welcomeTitle': 'Welcome',
        'ai.greeting.general': 'General greeting',
        'ai.inputPlaceholder': 'Ask me anything...',
        'subscription.credits_title': 'Credits',
      };
      return fallbacks[key] || key;
    },
    i18n: { language: 'en', resolvedLanguage: 'en' },
  }),
}));

vi.mock('../hooks/useConfirm', () => ({
  useConfirm: () => ({ confirm: vi.fn().mockResolvedValue(true) }),
}));

vi.mock('../services/aiService', () => ({
  aiService: {
    getChatHistory: vi.fn().mockResolvedValue([]),
    sendMessage: vi.fn(),
    sendMessageWithFile: vi.fn(),
    clearChatHistory: vi.fn(),
  },
}));

vi.mock('../services/documentService', () => ({
  documentService: {
    dismissSuggestion: vi.fn(),
    confirmRecurring: vi.fn(),
    confirmRecurringExpense: vi.fn(),
    executeAction: vi.fn(),
    confirmTaxData: vi.fn(),
    confirmAsset: vi.fn(),
  },
}));

vi.mock('../services/employerService', () => ({
  employerService: {
    confirmNoPayroll: vi.fn(),
    confirmAnnualArchive: vi.fn(),
  },
}));

vi.mock('../services/recurringService', () => ({
  recurringService: {
    update: vi.fn(),
  },
}));

vi.mock('../services/propertyService', () => ({
  propertyService: {
    recalculateRental: vi.fn(),
  },
}));

vi.mock('../stores/subscriptionStore', () => ({
  useSubscriptionStore: (selector: any) =>
    selector({
      creditBalance: null,
      creditLoading: false,
      fetchCreditBalance: mockFetchCreditBalance,
    }),
}));

vi.mock('../components/ai/AIResponse', () => ({
  default: ({ content }: { content: string }) => <div>{content}</div>,
}));

vi.mock('../components/ai/SuggestedQuestions', () => ({
  default: () => null,
}));

vi.mock('../components/ai/ChatProcessingIndicator', () => ({
  default: () => null,
}));

vi.mock('../components/ai/ChatSuggestionCard', () => ({
  default: () => null,
}));

vi.mock('../components/ai/ChatFollowUpQuestion', () => ({
  default: () => null,
}));

vi.mock('../components/ai/ChatProactiveAction', () => ({
  __esModule: true,
  default: () => null,
  isActionableProactive: (message: { type: string; actionStatus?: string }) =>
    ['recurring_confirm', 'asset_confirm', 'tax_form_review', 'employer_month_confirm'].includes(message.type) &&
    message.actionStatus === 'pending',
}));

describe('ChatInterface upload navigation links', () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn();
    mockNavigate.mockReset();
    mockFetchCreditBalance.mockReset();
    useAIAdvisorStore.getState().clearMessages();
  });

  it('renders both destination and document links for upload success messages', async () => {
    useAIAdvisorStore.getState().pushMessage({
      type: 'upload_success',
      content: 'Transaction created.',
      link: '/transactions',
      secondaryLink: '/documents/5',
      secondaryLinkLabel: 'View document',
    });

    await act(async () => {
      render(<ChatInterface />);
    });

    fireEvent.click(screen.getByRole('button', { name: 'View details' }));
    expect(mockNavigate).toHaveBeenCalledWith('/transactions');

    fireEvent.click(screen.getByRole('button', { name: 'View document' }));
    expect(mockNavigate).toHaveBeenCalledWith('/documents/5');
  });

  it('shows a document link inside recurring confirmation cards', async () => {
    useAIAdvisorStore.getState().pushMessage({
      type: 'recurring_confirm',
      content: 'Recurring income found.',
      documentId: 7,
      link: '/documents/7',
      actionData: {
        monthly_rent: 2184,
        address: 'Thenneberg 12, 1010 Wien',
        suggestion_type: 'create_recurring_income',
      },
      actionStatus: 'pending',
    });

    await act(async () => {
      render(<ChatInterface />);
    });

    fireEvent.click(screen.getByRole('button', { name: 'View document' }));
    expect(mockNavigate).toHaveBeenCalledWith('/documents/7');
  });
});
