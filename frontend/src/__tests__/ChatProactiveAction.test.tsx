/* @vitest-environment jsdom */

import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ChatProactiveAction from '../components/ai/ChatProactiveAction';
import type { ProactiveMessage } from '../stores/aiAdvisorStore';

const mockNavigate = vi.fn();
const mockAcknowledge = vi.fn();
const mockSnooze = vi.fn();

vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: any) => {
      if (typeof opts === 'string') return opts;
      if (opts?.defaultValue) return opts.defaultValue;
      const fallbacks: Record<string, string> = {
        'common.confirm': 'Confirm',
        'common.dismiss': 'Dismiss',
        'common.viewDetails': 'View details',
        'ai.proactive.expandDetails': 'Expand details',
        'ai.proactive.hideDetails': 'Hide details',
        'ai.proactive.viewDetails': 'View details',
        'ai.proactive.remindLater': 'Remind me later',
      };
      return fallbacks[key] || key;
    },
    i18n: { language: 'en', resolvedLanguage: 'en' },
  }),
}));

vi.mock('../services/documentService', () => ({
  documentService: {
    dismissSuggestion: vi.fn(),
    confirmRecurring: vi.fn(),
    confirmRecurringExpense: vi.fn(),
    confirmTaxData: vi.fn(),
    confirmAsset: vi.fn(),
    confirmProperty: vi.fn(),
    executeAction: vi.fn(),
  },
}));

vi.mock('../services/dashboardService', () => ({
  dashboardService: {
    acknowledgeProactiveReminder: mockAcknowledge,
    snoozeProactiveReminder: mockSnooze,
  },
}));

vi.mock('../stores/aiAdvisorStore', () => ({
  useAIAdvisorStore: (selector: any) =>
    selector({
      updateMessageAction: vi.fn(),
      dismissMessage: vi.fn(),
    }),
}));

vi.mock('../stores/refreshStore', () => ({
  useRefreshStore: (selector: any) =>
    selector({
      refreshAll: vi.fn(),
    }),
}));

describe('ChatProactiveAction', () => {
  beforeEach(() => {
    mockNavigate.mockReset();
    mockAcknowledge.mockReset();
    mockSnooze.mockReset();
  });

  it('expands multi-target reminders and navigates to a specific asset detail', () => {
    const message: ProactiveMessage = {
      id: 'server:test-multi',
      type: 'health_check',
      content: 'You have multiple assets missing setup.',
      timestamp: new Date(),
      read: false,
      bucket: 'snoozeable_condition',
      serverId: 'server:test-multi',
      actionData: {
        detail_items: [
          { kind: 'asset', href: '/properties/a-1', label: 'macbook' },
          { kind: 'asset', href: '/properties/a-2', label: 'Wiedner Hauptstr. 63/2/14, 1040 Wien' },
        ],
        potential_savings: 30,
      },
    };

    render(<ChatProactiveAction message={message} />);

    fireEvent.click(screen.getByRole('button', { name: 'Expand details' }));
    expect(screen.getByText('macbook')).toBeInTheDocument();

    const detailButtons = screen.getAllByRole('button', { name: 'View details' });
    fireEvent.click(detailButtons[0]);
    expect(mockNavigate).toHaveBeenCalledWith('/properties/a-1');
  });

  it('navigates directly for a single document target reminder', () => {
    const message: ProactiveMessage = {
      id: 'server:test-single',
      type: 'health_check',
      content: 'A document needs review.',
      timestamp: new Date(),
      read: false,
      bucket: 'snoozeable_condition',
      serverId: 'server:test-single',
      actionData: {
        detail_items: [
          { kind: 'document', href: '/documents/42', label: 'T-Mobile.pdf' },
        ],
      },
    };

    render(<ChatProactiveAction message={message} />);

    fireEvent.click(screen.getByRole('button', { name: 'View details' }));
    expect(mockNavigate).toHaveBeenCalledWith('/documents/42');
    expect(mockAcknowledge).not.toHaveBeenCalled();
  });
});
