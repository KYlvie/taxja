/**
 * Tests for aiAdvisorStore — Unified AI Interaction System
 *
 * Covers:
 * - Existing behavior backward compatibility
 * - Idempotency deduplication (IDEM-1, IDEM-2, IDEM-3)
 * - Processing message lifecycle
 * - Suggestion message lifecycle
 * - Follow-up message lifecycle
 * - Ordered message retrieval
 */

import { useAIAdvisorStore } from '../stores/aiAdvisorStore';
import type {
  ProcessingUpdateMessage,
  SuggestionChatMessage,
  FollowUpChatMessage,
  FollowUpQuestion,
} from '../stores/aiAdvisorStore';

// Reset store before each test
beforeEach(() => {
  useAIAdvisorStore.setState({
    messages: [],
    unreadCount: 0,
    pendingConfirmation: null,
    structuredMessages: [],
    processingDocs: [],
    pendingSuggestionDocIds: [],
  });
});

// =============================================================================
// Backward Compatibility — Existing ProactiveMessage behavior
// =============================================================================

describe('Backward Compatibility', () => {
  test('pushMessage adds a proactive message with auto-generated id and timestamp', () => {
    const store = useAIAdvisorStore.getState();
    store.pushMessage({ type: 'tip', content: 'Tax tip here' });

    const state = useAIAdvisorStore.getState();
    expect(state.messages).toHaveLength(1);
    expect(state.messages[0].type).toBe('tip');
    expect(state.messages[0].content).toBe('Tax tip here');
    expect(state.messages[0].id).toBeTruthy();
    expect(state.messages[0].timestamp).toBeInstanceOf(Date);
    expect(state.messages[0].read).toBe(false);
    expect(state.unreadCount).toBe(1);
  });

  test('pushMessage keeps only last 20 messages', () => {
    const store = useAIAdvisorStore.getState();
    for (let i = 0; i < 25; i++) {
      store.pushMessage({ type: 'tip', content: `Tip ${i}` });
    }
    expect(useAIAdvisorStore.getState().messages).toHaveLength(20);
    // Should keep newest
    expect(useAIAdvisorStore.getState().messages[19].content).toBe('Tip 24');
  });

  test('markAllRead resets unread count', () => {
    const store = useAIAdvisorStore.getState();
    store.pushMessage({ type: 'tip', content: 'Tip 1' });
    store.pushMessage({ type: 'tip', content: 'Tip 2' });
    expect(useAIAdvisorStore.getState().unreadCount).toBe(2);

    store.markAllRead();
    expect(useAIAdvisorStore.getState().unreadCount).toBe(0);
    expect(useAIAdvisorStore.getState().messages.every((m) => m.read)).toBe(true);
  });

  test('updateMessageAction updates action status', () => {
    const store = useAIAdvisorStore.getState();
    store.pushMessage({ type: 'recurring_confirm', content: 'Confirm?', actionStatus: 'pending' });

    const msgId = useAIAdvisorStore.getState().messages[0].id;
    store.updateMessageAction(msgId, 'confirmed');

    expect(useAIAdvisorStore.getState().messages[0].actionStatus).toBe('confirmed');
  });

  test('dismissMessage marks as read and dismissed', () => {
    const store = useAIAdvisorStore.getState();
    store.pushMessage({ type: 'tip', content: 'Dismiss me' });

    const msgId = useAIAdvisorStore.getState().messages[0].id;
    store.dismissMessage(msgId);

    const msg = useAIAdvisorStore.getState().messages[0];
    expect(msg.read).toBe(true);
    expect(msg.dismissed).toBe(true);
    expect(useAIAdvisorStore.getState().unreadCount).toBe(0);
  });

  test('requestConfirmation and resolveConfirmation work as promise', async () => {
    const store = useAIAdvisorStore.getState();
    const promise = store.requestConfirmation('Delete this?');
    expect(useAIAdvisorStore.getState().pendingConfirmation).not.toBeNull();

    store.resolveConfirmation(true);
    const result = await promise;
    expect(result).toBe(true);
    expect(useAIAdvisorStore.getState().pendingConfirmation).toBeNull();
  });
});

// =============================================================================
// Idempotency Deduplication Tests (IDEM-1, IDEM-2, IDEM-3)
// =============================================================================

describe('Idempotency Deduplication', () => {
  test('IDEM-1: pushing same idempotencyKey 5 times results in 1 message', () => {
    const store = useAIAdvisorStore.getState();
    const key = '42:none:processing_phase_1';

    for (let i = 0; i < 5; i++) {
      store.pushProcessingMessage({
        idempotencyKey: key,
        type: 'processing_update',
        documentId: 42,
        phase: 'ocr',
        message: `Analyzing... attempt ${i}`,
        uiState: 'processing',
      });
    }

    const state = useAIAdvisorStore.getState();
    const processingMsgs = state.structuredMessages.filter((m) => m.type === 'processing_update');
    expect(processingMsgs).toHaveLength(1);
    // Should have the latest content
    expect((processingMsgs[0] as ProcessingUpdateMessage).message).toBe('Analyzing... attempt 4');
  });

  test('IDEM-2: pushing same suggestion key twice results in 1 message', () => {
    const store = useAIAdvisorStore.getState();
    const key = '42:create_asset:completed';

    store.pushSuggestionMessage({
      idempotencyKey: key,
      type: 'suggestion',
      suggestionType: 'create_asset',
      documentId: 42,
      extractedData: { amount: 35000 },
      status: 'pending',
    });

    store.pushSuggestionMessage({
      idempotencyKey: key,
      type: 'suggestion',
      suggestionType: 'create_asset',
      documentId: 42,
      extractedData: { amount: 35000, updated: true },
      status: 'needs_input',
    });

    const state = useAIAdvisorStore.getState();
    const suggestions = state.structuredMessages.filter((m) => m.type === 'suggestion');
    expect(suggestions).toHaveLength(1);
    expect((suggestions[0] as SuggestionChatMessage).status).toBe('needs_input');
    expect((suggestions[0] as SuggestionChatMessage).extractedData.updated).toBe(true);
  });

  test('IDEM-3: 3 different docs get 3 separate messages', () => {
    const store = useAIAdvisorStore.getState();

    store.pushProcessingMessage({
      idempotencyKey: '1:none:processing_phase_1',
      type: 'processing_update',
      documentId: 1,
      phase: 'ocr',
      message: 'Analyzing doc 1...',
      uiState: 'processing',
    });

    store.pushProcessingMessage({
      idempotencyKey: '2:none:processing_phase_1',
      type: 'processing_update',
      documentId: 2,
      phase: 'ocr',
      message: 'Analyzing doc 2...',
      uiState: 'processing',
    });

    store.pushProcessingMessage({
      idempotencyKey: '3:none:processing_phase_1',
      type: 'processing_update',
      documentId: 3,
      phase: 'ocr',
      message: 'Analyzing doc 3...',
      uiState: 'processing',
    });

    const state = useAIAdvisorStore.getState();
    expect(state.structuredMessages).toHaveLength(3);
    expect(state.processingDocs).toEqual([1, 2, 3]);
  });

  test('idempotency key update preserves original message id', () => {
    const store = useAIAdvisorStore.getState();
    const key = '42:none:processing_phase_1';

    store.pushProcessingMessage({
      idempotencyKey: key,
      type: 'processing_update',
      documentId: 42,
      phase: 'ocr',
      message: 'First',
      uiState: 'processing',
    });

    const firstId = useAIAdvisorStore.getState().structuredMessages[0].id;

    store.pushProcessingMessage({
      idempotencyKey: key,
      type: 'processing_update',
      documentId: 42,
      phase: 'classifying',
      message: 'Second',
      uiState: 'processing',
    });

    // ID should be preserved (same logical message)
    expect(useAIAdvisorStore.getState().structuredMessages[0].id).toBe(firstId);
  });
});

// =============================================================================
// Processing Message Lifecycle
// =============================================================================

describe('Processing Message Lifecycle', () => {
  test('pushProcessingMessage tracks documentId in processingDocs', () => {
    const store = useAIAdvisorStore.getState();
    store.pushProcessingMessage({
      idempotencyKey: '42:none:processing_phase_1',
      type: 'processing_update',
      documentId: 42,
      phase: 'ocr',
      message: 'Analyzing...',
      uiState: 'processing',
    });

    expect(useAIAdvisorStore.getState().processingDocs).toContain(42);
  });

  test('pushProcessingMessage does not duplicate documentId in processingDocs', () => {
    const store = useAIAdvisorStore.getState();

    store.pushProcessingMessage({
      idempotencyKey: '42:none:processing_phase_1',
      type: 'processing_update',
      documentId: 42,
      phase: 'ocr',
      message: 'Analyzing...',
      uiState: 'processing',
    });

    store.pushProcessingMessage({
      idempotencyKey: '42:none:processing_phase_1',
      type: 'processing_update',
      documentId: 42,
      phase: 'classifying',
      message: 'Classifying...',
      uiState: 'processing',
    });

    expect(useAIAdvisorStore.getState().processingDocs).toEqual([42]);
  });

  test('updateProcessingMessage updates fields in-place', () => {
    const store = useAIAdvisorStore.getState();
    store.pushProcessingMessage({
      idempotencyKey: '42:none:processing_phase_1',
      type: 'processing_update',
      documentId: 42,
      phase: 'ocr',
      message: 'Analyzing...',
      uiState: 'processing',
    });

    store.updateProcessingMessage(42, {
      phase: 'extracting',
      message: 'Extracting details...',
      documentType: 'kaufvertrag',
    });

    const msg = useAIAdvisorStore.getState().structuredMessages[0] as ProcessingUpdateMessage;
    expect(msg.phase).toBe('extracting');
    expect(msg.message).toBe('Extracting details...');
    expect(msg.documentType).toBe('kaufvertrag');
  });

  test('removeProcessingMessage removes message and cleans processingDocs', () => {
    const store = useAIAdvisorStore.getState();
    store.pushProcessingMessage({
      idempotencyKey: '42:none:processing_phase_1',
      type: 'processing_update',
      documentId: 42,
      phase: 'ocr',
      message: 'Analyzing...',
      uiState: 'processing',
    });

    store.removeProcessingMessage(42);

    const state = useAIAdvisorStore.getState();
    expect(state.structuredMessages).toHaveLength(0);
    expect(state.processingDocs).not.toContain(42);
  });
});

// =============================================================================
// Suggestion Message Lifecycle
// =============================================================================

describe('Suggestion Message Lifecycle', () => {
  test('pushSuggestionMessage adds suggestion and tracks documentId', () => {
    const store = useAIAdvisorStore.getState();
    store.pushSuggestionMessage({
      idempotencyKey: '42:create_asset:completed',
      type: 'suggestion',
      suggestionType: 'create_asset',
      documentId: 42,
      extractedData: { amount: 35000, vendor: 'AutoHaus Wien' },
      status: 'pending',
    });

    const state = useAIAdvisorStore.getState();
    expect(state.structuredMessages).toHaveLength(1);
    expect(state.pendingSuggestionDocIds).toContain(42);
    expect((state.structuredMessages[0] as SuggestionChatMessage).suggestionType).toBe('create_asset');
  });

  test('updateSuggestionStatus changes status and removes from pending on confirm', () => {
    const store = useAIAdvisorStore.getState();
    store.pushSuggestionMessage({
      idempotencyKey: '42:create_asset:completed',
      type: 'suggestion',
      suggestionType: 'create_asset',
      documentId: 42,
      extractedData: {},
      status: 'pending',
    });

    store.updateSuggestionStatus(42, 'confirmed');

    const state = useAIAdvisorStore.getState();
    expect((state.structuredMessages[0] as SuggestionChatMessage).status).toBe('confirmed');
    expect(state.pendingSuggestionDocIds).not.toContain(42);
  });

  test('updateSuggestionStatus removes from pending on dismiss', () => {
    const store = useAIAdvisorStore.getState();
    store.pushSuggestionMessage({
      idempotencyKey: '42:create_property:completed',
      type: 'suggestion',
      suggestionType: 'create_property',
      documentId: 42,
      extractedData: {},
      status: 'pending',
    });

    store.updateSuggestionStatus(42, 'dismissed');

    expect(useAIAdvisorStore.getState().pendingSuggestionDocIds).toEqual([]);
  });

  test('updateSuggestionStatus to needs_input keeps in pending', () => {
    const store = useAIAdvisorStore.getState();
    store.pushSuggestionMessage({
      idempotencyKey: '42:create_asset:completed',
      type: 'suggestion',
      suggestionType: 'create_asset',
      documentId: 42,
      extractedData: {},
      status: 'pending',
    });

    store.updateSuggestionStatus(42, 'needs_input');

    expect(useAIAdvisorStore.getState().pendingSuggestionDocIds).toContain(42);
  });
});

// =============================================================================
// Follow-Up Message Lifecycle
// =============================================================================

describe('Follow-Up Message Lifecycle', () => {
  const mockQuestions: FollowUpQuestion[] = [
    {
      id: 'q1',
      question: 'When did you start using this for business?',
      inputType: 'date',
      required: true,
      fieldKey: 'put_into_use_date',
      helpText: 'The date you started using this for business, not the purchase date.',
    },
    {
      id: 'q2',
      question: 'What percentage is business use?',
      inputType: 'number',
      defaultValue: 100,
      required: true,
      fieldKey: 'business_use_percentage',
      validation: { min: 1, max: 100 },
    },
  ];

  test('pushFollowUpMessage adds follow-up with answered=false', () => {
    const store = useAIAdvisorStore.getState();
    store.pushFollowUpMessage({
      idempotencyKey: '42:create_asset:follow_up',
      type: 'follow_up',
      documentId: 42,
      questions: mockQuestions,
    });

    const state = useAIAdvisorStore.getState();
    expect(state.structuredMessages).toHaveLength(1);
    const msg = state.structuredMessages[0] as FollowUpChatMessage;
    expect(msg.type).toBe('follow_up');
    expect(msg.answered).toBe(false);
    expect(msg.questions).toHaveLength(2);
    expect(msg.questions[0].helpText).toBe('The date you started using this for business, not the purchase date.');
  });

  test('markFollowUpAnswered sets answered to true', () => {
    const store = useAIAdvisorStore.getState();
    store.pushFollowUpMessage({
      idempotencyKey: '42:create_asset:follow_up',
      type: 'follow_up',
      documentId: 42,
      questions: mockQuestions,
    });

    store.markFollowUpAnswered(42);

    const msg = useAIAdvisorStore.getState().structuredMessages[0] as FollowUpChatMessage;
    expect(msg.answered).toBe(true);
  });

  test('follow-up idempotency dedup works', () => {
    const store = useAIAdvisorStore.getState();
    const key = '42:create_asset:follow_up';

    store.pushFollowUpMessage({
      idempotencyKey: key,
      type: 'follow_up',
      documentId: 42,
      questions: mockQuestions,
    });

    // Push again with same key — should update, not duplicate
    store.pushFollowUpMessage({
      idempotencyKey: key,
      type: 'follow_up',
      documentId: 42,
      questions: [mockQuestions[1]], // Only 1 remaining question
    });

    const state = useAIAdvisorStore.getState();
    expect(state.structuredMessages).toHaveLength(1);
    expect((state.structuredMessages[0] as FollowUpChatMessage).questions).toHaveLength(1);
  });
});

// =============================================================================
// Ordered Messages
// =============================================================================

describe('getOrderedMessages', () => {
  test('returns proactive + structured messages sorted by timestamp', () => {
    const store = useAIAdvisorStore.getState();

    // Push a proactive message first
    store.pushMessage({ type: 'tip', content: 'Tax tip' });

    // Push a processing message slightly later
    store.pushProcessingMessage({
      idempotencyKey: '42:none:processing_phase_1',
      type: 'processing_update',
      documentId: 42,
      phase: 'ocr',
      message: 'Analyzing...',
      uiState: 'processing',
    });

    // Push a suggestion message
    store.pushSuggestionMessage({
      idempotencyKey: '42:create_asset:completed',
      type: 'suggestion',
      suggestionType: 'create_asset',
      documentId: 42,
      extractedData: {},
      status: 'pending',
    });

    const ordered = store.getOrderedMessages();
    expect(ordered.length).toBeGreaterThanOrEqual(3);

    // All should be sorted by timestamp (ascending)
    for (let i = 1; i < ordered.length; i++) {
      const prevTime = ordered[i - 1].timestamp instanceof Date
        ? ordered[i - 1].timestamp.getTime()
        : new Date(ordered[i - 1].timestamp).getTime();
      const currTime = ordered[i].timestamp instanceof Date
        ? ordered[i].timestamp.getTime()
        : new Date(ordered[i].timestamp).getTime();
      expect(currTime).toBeGreaterThanOrEqual(prevTime);
    }
  });

  test('dismissed proactive messages are excluded from ordered list', () => {
    const store = useAIAdvisorStore.getState();
    store.pushMessage({ type: 'tip', content: 'Keep me' });
    store.pushMessage({ type: 'tip', content: 'Dismiss me' });

    const dismissedId = useAIAdvisorStore.getState().messages[1].id;
    store.dismissMessage(dismissedId);

    const ordered = store.getOrderedMessages();
    const proactiveMessages = ordered.filter((m) => 'content' in m && m.content === 'Dismiss me');
    expect(proactiveMessages).toHaveLength(0);
  });
});

// =============================================================================
// Full Lifecycle: Upload → Processing → Suggestion → Follow-Up → Confirm
// =============================================================================

describe('Full Lifecycle', () => {
  test('complete upload-to-confirm flow', () => {
    const store = useAIAdvisorStore.getState();

    // 1. Upload starts → processing message
    store.pushProcessingMessage({
      idempotencyKey: '42:none:processing_phase_1',
      type: 'processing_update',
      documentId: 42,
      phase: 'ocr',
      message: 'Analyzing your document...',
      uiState: 'processing',
    });
    expect(useAIAdvisorStore.getState().processingDocs).toContain(42);

    // 2. Processing updates (polls with same key — dedup)
    store.pushProcessingMessage({
      idempotencyKey: '42:none:processing_phase_1',
      type: 'processing_update',
      documentId: 42,
      phase: 'classifying',
      message: 'Identified as Kaufvertrag...',
      uiState: 'processing',
    });
    expect(useAIAdvisorStore.getState().structuredMessages).toHaveLength(1);

    // 3. Processing completes → remove processing, push suggestion
    store.removeProcessingMessage(42);
    expect(useAIAdvisorStore.getState().processingDocs).not.toContain(42);

    store.pushSuggestionMessage({
      idempotencyKey: '42:create_asset:completed',
      type: 'suggestion',
      suggestionType: 'create_asset',
      documentId: 42,
      extractedData: { amount: 35000, vendor: 'AutoHaus Wien' },
      status: 'needs_input',
      action: {
        kind: 'confirm_asset',
        targetId: '42',
        endpoint: '/documents/42/confirm-asset',
        method: 'POST',
        confirmLabel: 'Create Asset',
        dismissLabel: 'Not an Asset',
      },
    });
    expect(useAIAdvisorStore.getState().pendingSuggestionDocIds).toContain(42);

    // 4. Push follow-up questions
    store.pushFollowUpMessage({
      idempotencyKey: '42:create_asset:follow_up',
      type: 'follow_up',
      documentId: 42,
      questions: [
        {
          id: 'q1',
          question: 'When did you start using this?',
          inputType: 'date',
          required: true,
          fieldKey: 'put_into_use_date',
        },
      ],
    });

    // 5. User answers follow-up
    store.markFollowUpAnswered(42);
    const followUp = useAIAdvisorStore.getState().structuredMessages.find(
      (m) => m.type === 'follow_up'
    ) as FollowUpChatMessage;
    expect(followUp.answered).toBe(true);

    // 6. Suggestion becomes ready → user confirms
    store.updateSuggestionStatus(42, 'confirmed');
    const suggestion = useAIAdvisorStore.getState().structuredMessages.find(
      (m) => m.type === 'suggestion'
    ) as SuggestionChatMessage;
    expect(suggestion.status).toBe('confirmed');
    expect(useAIAdvisorStore.getState().pendingSuggestionDocIds).not.toContain(42);

    // 7. All messages should be in ordered list
    const ordered = store.getOrderedMessages();
    expect(ordered.length).toBeGreaterThanOrEqual(2); // suggestion + follow-up (processing was removed)
  });
});

// =============================================================================
// Edge Cases
// =============================================================================

describe('Edge Cases', () => {
  test('structuredMessages capped at 50', () => {
    const store = useAIAdvisorStore.getState();
    for (let i = 0; i < 55; i++) {
      store.pushProcessingMessage({
        idempotencyKey: `${i}:none:processing_phase_1`,
        type: 'processing_update',
        documentId: i,
        phase: 'ocr',
        message: `Doc ${i}`,
        uiState: 'processing',
      });
    }
    expect(useAIAdvisorStore.getState().structuredMessages).toHaveLength(50);
  });

  test('clearMessages clears both proactive and structured', () => {
    const store = useAIAdvisorStore.getState();
    store.pushMessage({ type: 'tip', content: 'Tip' });
    store.pushSuggestionMessage({
      idempotencyKey: '1:create_property:completed',
      type: 'suggestion',
      suggestionType: 'create_property',
      documentId: 1,
      extractedData: {},
      status: 'pending',
    });

    store.clearMessages();

    const state = useAIAdvisorStore.getState();
    expect(state.messages).toHaveLength(0);
    expect(state.structuredMessages).toHaveLength(0);
  });

  test('removeProcessingMessage for non-existent doc is safe', () => {
    const store = useAIAdvisorStore.getState();
    // Should not throw
    store.removeProcessingMessage(999);
    expect(useAIAdvisorStore.getState().structuredMessages).toHaveLength(0);
  });

  test('updateSuggestionStatus for non-existent doc is safe', () => {
    const store = useAIAdvisorStore.getState();
    store.updateSuggestionStatus(999, 'confirmed');
    expect(useAIAdvisorStore.getState().structuredMessages).toHaveLength(0);
  });
});
