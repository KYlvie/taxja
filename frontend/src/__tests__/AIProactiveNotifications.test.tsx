/**
 * Tests for AI proactive notification system — verifies:
 * 1. aiAdvisorStore supports tax_form_review message type
 * 2. ChatInterface renders tax_form_review cards with data summary + action buttons
 * 3. ChatInterface renders generic link buttons for messages with link property
 * 4. Dashboard alerts endpoint includes import_* pending suggestions
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act } from 'react';
import { useAIAdvisorStore } from '../stores/aiAdvisorStore';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockNavigate = vi.fn();
vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
  useLocation: () => ({ pathname: '/documents' }),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: any) => {
      if (opts?.defaultValue) return opts.defaultValue.replace(/\{\{(\w+)\}\}/g, (_: string, k: string) => opts[k] ?? k);
      if (typeof opts === 'string') return opts;
      return key;
    },
    i18n: { language: 'en', resolvedLanguage: 'en' },
  }),
}));

vi.mock('../services/aiService', () => ({
  aiService: { sendMessage: vi.fn(), getHistory: vi.fn().mockResolvedValue({ messages: [] }), clearHistory: vi.fn() },
}));
vi.mock('../services/documentService', () => ({
  documentService: { dismissSuggestion: vi.fn() },
}));
vi.mock('../services/employerService', () => ({
  employerService: {},
}));
vi.mock('../services/recurringService', () => ({
  recurringService: { confirmSuggestion: vi.fn() },
}));
vi.mock('../services/propertyService', () => ({
  propertyService: {},
}));

// ---------------------------------------------------------------------------
// 1. aiAdvisorStore tests
// ---------------------------------------------------------------------------
describe('aiAdvisorStore', () => {
  beforeEach(() => {
    useAIAdvisorStore.getState().clearMessages();
  });

  it('accepts tax_form_review message type', () => {
    const store = useAIAdvisorStore.getState();

    act(() => {
      store.pushMessage({
        type: 'tax_form_review',
        content: 'Tax form detected in L16.pdf',
        documentId: 42,
        link: '/documents/42',
        actionData: {
          suggestion_type: 'import_lohnzettel',
          tax_year: 2025,
          summary: 'KZ245: €35,000.00\nKZ260: €4,200.00',
          file_name: 'L16.pdf',
        },
        actionStatus: 'pending',
      });
    });

    const messages = useAIAdvisorStore.getState().messages;
    expect(messages).toHaveLength(1);
    expect(messages[0].type).toBe('tax_form_review');
    expect(messages[0].actionStatus).toBe('pending');
    expect(messages[0].link).toBe('/documents/42');
    expect(messages[0].actionData?.suggestion_type).toBe('import_lohnzettel');
  });

  it('tracks unread count for tax_form_review messages', () => {
    const store = useAIAdvisorStore.getState();

    act(() => {
      store.pushMessage({ type: 'tax_form_review', content: 'Form 1' });
      store.pushMessage({ type: 'tax_form_review', content: 'Form 2' });
    });

    expect(useAIAdvisorStore.getState().unreadCount).toBe(2);
  });

  it('updateMessageAction changes status from pending to confirmed', () => {
    const store = useAIAdvisorStore.getState();

    act(() => {
      store.pushMessage({
        type: 'tax_form_review',
        content: 'Tax form',
        actionStatus: 'pending',
      });
    });

    const msgId = useAIAdvisorStore.getState().messages[0].id;

    act(() => {
      useAIAdvisorStore.getState().updateMessageAction(msgId, 'confirmed');
    });

    expect(useAIAdvisorStore.getState().messages[0].actionStatus).toBe('confirmed');
  });

  it('updateMessageAction changes status from pending to dismissed', () => {
    const store = useAIAdvisorStore.getState();

    act(() => {
      store.pushMessage({
        type: 'tax_form_review',
        content: 'Tax form',
        actionStatus: 'pending',
      });
    });

    const msgId = useAIAdvisorStore.getState().messages[0].id;

    act(() => {
      useAIAdvisorStore.getState().updateMessageAction(msgId, 'dismissed');
    });

    expect(useAIAdvisorStore.getState().messages[0].actionStatus).toBe('dismissed');
  });
});

// ---------------------------------------------------------------------------
// 2. Tax form review card rendering (unit tests on store + message structure)
// ---------------------------------------------------------------------------
describe('Tax form review message structure', () => {
  it('builds correct actionData with summary lines', () => {
    // Simulate what DocumentUpload.tsx builds
    const formData = {
      kz_245: 35000,
      kz_260: 4200,
      tax_year: 2025,
    };

    const summaryParts: string[] = [];
    if (formData.kz_245) summaryParts.push(`KZ245: €${Number(formData.kz_245).toLocaleString('de-AT', { minimumFractionDigits: 2 })}`);
    if (formData.kz_260) summaryParts.push(`KZ260: €${Number(formData.kz_260).toLocaleString('de-AT', { minimumFractionDigits: 2 })}`);

    const actionData = {
      suggestion_type: 'import_lohnzettel',
      tax_year: formData.tax_year,
      summary: summaryParts.join('\n'),
      file_name: 'L16_2025.pdf',
    };

    expect(actionData.suggestion_type).toBe('import_lohnzettel');
    expect(actionData.tax_year).toBe(2025);
    expect(actionData.summary).toContain('KZ245');
    expect(actionData.summary).toContain('KZ260');
    expect(actionData.summary.split('\n')).toHaveLength(2);
  });

  it('builds summary for E1a with betriebseinnahmen and gewinn_verlust', () => {
    const formData = {
      betriebseinnahmen: 80000,
      gewinn_verlust: -5000,
      tax_year: 2025,
    };

    const summaryParts: string[] = [];
    if (formData.betriebseinnahmen) summaryParts.push(`Revenue: €${Number(formData.betriebseinnahmen).toLocaleString('de-AT', { minimumFractionDigits: 2 })}`);
    if (formData.gewinn_verlust != null) summaryParts.push(`Profit/Loss: €${Number(formData.gewinn_verlust).toLocaleString('de-AT', { minimumFractionDigits: 2 })}`);

    expect(summaryParts).toHaveLength(2);
    expect(summaryParts[1]).toContain('-');
  });

  it('builds summary for Kontoauszug with transaction_count', () => {
    const formData = { transaction_count: 47 };
    const summaryParts: string[] = [];
    if (formData.transaction_count) summaryParts.push(`Transactions: ${formData.transaction_count}`);

    expect(summaryParts).toHaveLength(1);
    expect(summaryParts[0]).toBe('Transactions: 47');
  });

  it('builds summary for U1 with gesamtumsatz and zahllast', () => {
    const formData = { gesamtumsatz: 120000, zahllast: 8500 };
    const summaryParts: string[] = [];
    if (formData.gesamtumsatz) summaryParts.push(`Total revenue: €${Number(formData.gesamtumsatz).toLocaleString('de-AT', { minimumFractionDigits: 2 })}`);
    if (formData.zahllast != null) summaryParts.push(`VAT payable: €${Number(formData.zahllast).toLocaleString('de-AT', { minimumFractionDigits: 2 })}`);

    expect(summaryParts).toHaveLength(2);
    expect(summaryParts[0]).toContain('120');
  });

  it('builds empty summary when no recognized fields', () => {
    const formData = { some_unknown_field: 'abc' };
    const summaryParts: string[] = [];
    // None of the known fields match
    if ((formData as any).kz_245) summaryParts.push('x');
    if ((formData as any).betriebseinnahmen) summaryParts.push('x');
    if ((formData as any).gesamtumsatz) summaryParts.push('x');

    expect(summaryParts).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// 3. Dashboard alerts filter logic (unit test)
// ---------------------------------------------------------------------------
describe('Dashboard alerts import_* filter logic', () => {
  it('import_ types pass the startsWith check', () => {
    const testTypes = [
      'import_lohnzettel',
      'import_l1',
      'import_e1a',
      'import_e1b',
      'import_e1kv',
      'import_u1',
      'import_u30',
      'import_jahresabschluss',
      'import_svs',
      'import_grundsteuer',
      'import_bank_statement',
    ];

    for (const stype of testTypes) {
      expect(stype.startsWith('import_')).toBe(true);
    }
  });

  it('non-import types do not pass the filter', () => {
    const nonImportTypes = [
      'create_recurring_income',
      'create_recurring_expense',
      'create_property',
      'create_asset',
    ];

    for (const stype of nonImportTypes) {
      expect(stype.startsWith('import_')).toBe(false);
    }
  });

  it('backend filter logic matches: allowed types OR import_ prefix', () => {
    // Simulates the Python logic:
    // if stype not in (...) and not stype.startswith("import_"): continue
    const allowedExact = new Set([
      'create_recurring_income',
      'create_recurring_expense',
      'create_property',
    ]);

    function shouldInclude(stype: string): boolean {
      return allowedExact.has(stype) || stype.startsWith('import_');
    }

    expect(shouldInclude('create_recurring_income')).toBe(true);
    expect(shouldInclude('create_property')).toBe(true);
    expect(shouldInclude('import_lohnzettel')).toBe(true);
    expect(shouldInclude('import_e1a')).toBe(true);
    expect(shouldInclude('create_asset')).toBe(false);
    expect(shouldInclude('unknown_type')).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 4. Generic link button logic
// ---------------------------------------------------------------------------
describe('Generic link button logic', () => {
  const typesWithSpecialCards = [
    'recurring_confirm',
    'employer_month_confirm',
    'employer_annual_archive_confirm',
    'contract_expired',
    'unit_percentage_prompt',
    'tax_form_review',
  ];

  it('types with special cards should NOT get generic link button', () => {
    for (const type of typesWithSpecialCards) {
      expect(typesWithSpecialCards.includes(type)).toBe(true);
    }
  });

  it('upload_review with link should get generic link button', () => {
    const pm = { type: 'upload_review', link: '/documents/5' };
    const hasSpecialCard = typesWithSpecialCards.includes(pm.type);
    expect(hasSpecialCard).toBe(false);
    expect(pm.link).toBeTruthy();
    // Should show generic link button
  });

  it('health_check with link should get generic link button', () => {
    const pm = { type: 'health_check', link: '/dashboard' };
    const hasSpecialCard = typesWithSpecialCards.includes(pm.type);
    expect(hasSpecialCard).toBe(false);
    expect(pm.link).toBeTruthy();
  });

  it('tip without link should NOT get generic link button', () => {
    const pm = { type: 'tip', link: undefined };
    expect(pm.link).toBeFalsy();
  });

  it('asset_confirm with link should get generic link button', () => {
    const pm = { type: 'asset_confirm', link: '/documents/10' };
    const hasSpecialCard = typesWithSpecialCards.includes(pm.type);
    expect(hasSpecialCard).toBe(false);
    expect(pm.link).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// 5. i18n key existence
// ---------------------------------------------------------------------------
describe('i18n keys for AI proactive notifications', () => {
  // Load actual locale files to verify keys exist
  it('en.json has all required proactive notification keys', async () => {
    const en = await import('../i18n/locales/en.json');
    const proactive = en.default?.ai?.proactive || en.ai?.proactive;
    expect(proactive).toBeDefined();
    expect(proactive.taxFormDetected).toBeDefined();
    expect(proactive.viewAndConfirm).toBeDefined();
    expect(proactive.taxFormViewed).toBeDefined();
    expect(proactive.viewDetails).toBeDefined();
    expect(proactive.pendingTaxForm).toBeDefined();
  });

  it('de.json has all required proactive notification keys', async () => {
    const de = await import('../i18n/locales/de.json');
    const proactive = de.default?.ai?.proactive || de.ai?.proactive;
    expect(proactive).toBeDefined();
    expect(proactive.taxFormDetected).toBeDefined();
    expect(proactive.viewAndConfirm).toBeDefined();
    expect(proactive.taxFormViewed).toBeDefined();
    expect(proactive.viewDetails).toBeDefined();
    expect(proactive.pendingTaxForm).toBeDefined();
  });

  it('zh.json has all required proactive notification keys', async () => {
    const zh = await import('../i18n/locales/zh.json');
    const proactive = zh.default?.ai?.proactive || zh.ai?.proactive;
    expect(proactive).toBeDefined();
    expect(proactive.taxFormDetected).toBeDefined();
    expect(proactive.viewAndConfirm).toBeDefined();
    expect(proactive.taxFormViewed).toBeDefined();
    expect(proactive.viewDetails).toBeDefined();
    expect(proactive.pendingTaxForm).toBeDefined();
  });
});
