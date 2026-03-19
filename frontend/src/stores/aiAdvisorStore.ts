import { create } from 'zustand';

const SESSION_KEY = 'taxja_ai_greeting_shown';

// =============================================================================
// Type Definitions — Unified AI Interaction System
// =============================================================================

/**
 * Frozen enum of action kinds.
 * New types must be explicitly added here — prevents free-form string drift.
 */
export type ActionKind =
  | 'confirm_property'
  | 'confirm_asset'
  | 'confirm_recurring'
  | 'confirm_recurring_expense'
  | 'confirm_tax_data'
  | 'confirm_loan'
  | 'confirm_bank_transactions'
  | 'dismiss_suggestion';

/**
 * Self-describing action contract from backend.
 * Frontend dispatches generically via endpoint + method — no per-type switch needed.
 */
export interface ActionDescriptor {
  kind: ActionKind;
  targetId: string;
  endpoint: string;
  method: 'POST' | 'PUT' | 'DELETE';
  payload?: Record<string, any>;
  /** Button labels — backend can control per action type. Falls back to generic i18n. */
  confirmLabel?: string;
  dismissLabel?: string;
  detailLabel?: string;
}

/**
 * Unified UI state enum.
 * Backend returns this single stable value — frontend doesn't derive from multiple fields.
 */
export type UIState =
  | 'processing'
  | 'needs_input'
  | 'ready_to_confirm'
  | 'confirmed'
  | 'dismissed'
  | 'error';

/**
 * Follow-up question from backend — rendered as inline form control in chat.
 */
export interface FollowUpQuestion {
  id: string;
  question: string;
  inputType: 'text' | 'number' | 'date' | 'select' | 'boolean';
  options?: { value: string; label: string }[];
  defaultValue?: any;
  required: boolean;
  fieldKey: string;
  /** Inline help text shown beneath input — saves user from asking AI or leaving flow */
  helpText?: string;
  validation?: {
    min?: number;
    max?: number;
    pattern?: string;
  };
}

// =============================================================================
// Existing ProactiveMessage — UNCHANGED for backward compatibility
// =============================================================================

export interface ProactiveMessage {
  id: string;
  type: 'login' | 'upload_success' | 'upload_review' | 'upload_error' | 'tip' | 'reminder' | 'recurring_confirm' | 'unit_percentage_prompt' | 'contract_expired' | 'health_check' | 'asset_confirm' | 'employer_month_confirm' | 'employer_annual_archive_confirm' | 'tax_form_review';
  content: string;
  timestamp: Date;
  read: boolean;
  /** Optional: navigate user to a page */
  link?: string;
  /** Document ID for actionable messages (e.g. recurring confirmation) */
  documentId?: number;
  /** Extra data for actionable messages */
  actionData?: Record<string, any>;
  /** Status of the action (confirm/dismiss) */
  actionStatus?: 'pending' | 'confirmed' | 'dismissed';
  /** Severity level for health check items */
  severity?: 'high' | 'medium' | 'low';
  /** Whether the notification was dismissed by user */
  dismissed?: boolean;
  /** Unified action descriptor — enables generic dispatch without per-type switch */
  action?: ActionDescriptor;
}

// =============================================================================
// NEW: Structured Chat Message Types
// =============================================================================

/**
 * Suggestion displayed as structured card inside the chat panel.
 * RULE: No embedded forms — complex suggestions show summary + buttons ONLY.
 * Multi-field input goes through FollowUpChatMessage as a separate message.
 */
export interface SuggestionChatMessage {
  id: string;
  /** ⚠️ Backend-generated. Frontend must use verbatim — never self-generate. */
  idempotencyKey: string;
  timestamp: Date;
  type: 'suggestion';
  suggestionType: string;
  documentId: number;
  extractedData: Record<string, any>;
  followUpQuestions?: FollowUpQuestion[];
  status: 'pending' | 'confirmed' | 'dismissed' | 'needs_input';
  action?: ActionDescriptor;
  /** Suggestion version for optimistic concurrency on follow-up answers */
  suggestionVersion?: number;
}

/**
 * Follow-up questions rendered with inline input controls in chat.
 * Separate from SuggestionChatMessage to keep chat conversational.
 */
export interface FollowUpChatMessage {
  id: string;
  idempotencyKey: string;
  timestamp: Date;
  type: 'follow_up';
  documentId: number;
  questions: FollowUpQuestion[];
  /** Tracks whether user has submitted answers */
  answered: boolean;
  suggestionVersion?: number;
}

/**
 * Document processing progress shown in chat during OCR/analysis.
 */
export interface ProcessingUpdateMessage {
  id: string;
  idempotencyKey: string;
  timestamp: Date;
  type: 'processing_update';
  documentId: number;
  phase: 'uploading' | 'ocr' | 'classifying' | 'extracting' | 'analyzing' | 'complete';
  documentType?: string;
  message: string;
  uiState: UIState;
  phaseStartedAt?: string;
  phaseUpdatedAt?: string;
  currentPhaseAttempt?: number;
}

/**
 * Union of all new structured chat message types.
 */
export type StructuredChatMessage =
  | SuggestionChatMessage
  | FollowUpChatMessage
  | ProcessingUpdateMessage;

// =============================================================================
// Existing PendingConfirmation — UNCHANGED
// =============================================================================

export interface PendingConfirmation {
  id: string;
  message: string;
  resolve: (confirmed: boolean) => void;
}

// =============================================================================
// Store Interface
// =============================================================================

interface AIAdvisorState {
  // --- Existing state (unchanged) ---
  messages: ProactiveMessage[];
  unreadCount: number;
  loginGreetingShown: boolean;
  pendingConfirmation: PendingConfirmation | null;

  // --- NEW: Structured chat messages (suggestion, follow-up, processing) ---
  structuredMessages: StructuredChatMessage[];
  /** Documents currently being processed (for tracking active uploads) */
  processingDocs: number[];
  /** Document IDs with pending suggestions awaiting user action */
  pendingSuggestionDocIds: number[];

  // --- Existing actions (unchanged signatures) ---
  pushMessage: (msg: Omit<ProactiveMessage, 'id' | 'timestamp' | 'read'>) => void;
  markAllRead: () => void;
  clearMessages: () => void;
  setLoginGreetingShown: () => void;
  updateMessageAction: (messageId: string, status: 'confirmed' | 'dismissed') => void;
  dismissMessage: (messageId: string) => void;
  requestConfirmation: (message: string) => Promise<boolean>;
  resolveConfirmation: (confirmed: boolean) => void;

  // --- NEW: Structured message actions ---
  /**
   * Push a structured message with idempotency deduplication.
   * If a message with the same idempotencyKey exists, update in-place instead of inserting.
   * ⚠️ idempotencyKey MUST be backend-generated — frontend must NOT self-generate.
   */
  pushStructuredMessage: (msg: StructuredChatMessage) => void;

  /** Push or update a processing progress message */
  pushProcessingMessage: (msg: Omit<ProcessingUpdateMessage, 'id' | 'timestamp'> & { idempotencyKey: string }) => void;
  /** Update an existing processing message by documentId */
  updateProcessingMessage: (documentId: number, updates: Partial<ProcessingUpdateMessage>) => void;
  /** Remove processing message when document processing completes */
  removeProcessingMessage: (documentId: number) => void;

  /** Push a suggestion message into the chat */
  pushSuggestionMessage: (msg: Omit<SuggestionChatMessage, 'id' | 'timestamp'>) => void;
  /** Update suggestion status (e.g., pending → confirmed) */
  updateSuggestionStatus: (documentId: number, status: SuggestionChatMessage['status']) => void;

  /** Push a follow-up question message */
  pushFollowUpMessage: (msg: Omit<FollowUpChatMessage, 'id' | 'timestamp' | 'answered'>) => void;
  /** Mark follow-up as answered */
  markFollowUpAnswered: (documentId: number) => void;

  /** Get all structured messages sorted by timestamp */
  getOrderedMessages: () => (ProactiveMessage | StructuredChatMessage)[];

  /** Task 23: Get batch processing summary for collective indicator */
  getBatchProcessingSummary: () => { count: number; documentIds: number[] } | null;
}

// =============================================================================
// Helper: Generate unique message ID
// =============================================================================

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

// =============================================================================
// Store Implementation
// =============================================================================

export const useAIAdvisorStore = create<AIAdvisorState>((set, get) => ({
  // --- Existing state ---
  messages: [],
  unreadCount: 0,
  loginGreetingShown: sessionStorage.getItem(SESSION_KEY) === '1',
  pendingConfirmation: null,

  // --- NEW state ---
  structuredMessages: [],
  processingDocs: [],
  pendingSuggestionDocIds: [],

  // =========================================================================
  // Existing actions — UNCHANGED
  // =========================================================================

  pushMessage: (msg) =>
    set((state) => {
      const newMsg: ProactiveMessage = {
        ...msg,
        id: generateId(),
        timestamp: new Date(),
        read: false,
      };
      const messages = [...state.messages, newMsg].slice(-20);
      return { messages, unreadCount: state.unreadCount + 1 };
    }),

  markAllRead: () =>
    set((state) => ({
      messages: state.messages.map((m) => ({ ...m, read: true })),
      unreadCount: 0,
    })),

  clearMessages: () => set({
    messages: [],
    unreadCount: 0,
    structuredMessages: [],
    processingDocs: [],
    pendingSuggestionDocIds: [],
  }),

  setLoginGreetingShown: () => {
    sessionStorage.setItem(SESSION_KEY, '1');
    set({ loginGreetingShown: true });
  },

  updateMessageAction: (messageId, status) =>
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === messageId ? { ...m, actionStatus: status } : m
      ),
    })),

  dismissMessage: (messageId) =>
    set((state) => {
      const msg = state.messages.find((m) => m.id === messageId);
      const wasUnread = msg && !msg.read;
      return {
        messages: state.messages.map((m) =>
          m.id === messageId ? { ...m, read: true, dismissed: true } : m
        ),
        unreadCount: wasUnread ? Math.max(0, state.unreadCount - 1) : state.unreadCount,
      };
    }),

  requestConfirmation: (message: string) => {
    return new Promise<boolean>((resolve) => {
      set({
        pendingConfirmation: {
          id: `confirm-${Date.now()}`,
          message,
          resolve,
        },
      });
    });
  },

  resolveConfirmation: (confirmed: boolean) => {
    const pending = get().pendingConfirmation;
    if (pending) {
      pending.resolve(confirmed);
      set({ pendingConfirmation: null });
    }
  },

  // =========================================================================
  // NEW: Structured message actions with idempotency deduplication
  // =========================================================================

  pushStructuredMessage: (msg) =>
    set((state) => {
      // Defensive: skip dedup if idempotencyKey is missing (prevents all-undefined match)
      if (!msg.idempotencyKey) {
        console.warn('[aiAdvisorStore] pushStructuredMessage called without idempotencyKey');
        return { structuredMessages: [...state.structuredMessages, msg].slice(-50) };
      }

      const existingIdx = state.structuredMessages.findIndex(
        (m) => m.idempotencyKey === msg.idempotencyKey
      );

      if (existingIdx >= 0) {
        // Update in-place — same idempotency key means same logical message
        const updated = [...state.structuredMessages];
        updated[existingIdx] = { ...msg, id: updated[existingIdx].id };
        return { structuredMessages: updated };
      }

      // New message — append and keep max 50
      const structuredMessages = [...state.structuredMessages, msg].slice(-50);
      return { structuredMessages };
    }),

  pushProcessingMessage: (msg) =>
    set((state) => {
      const fullMsg: ProcessingUpdateMessage = {
        ...msg,
        id: generateId(),
        timestamp: new Date(),
      };

      // Dedup by idempotencyKey
      const existingIdx = state.structuredMessages.findIndex(
        (m) => m.idempotencyKey === msg.idempotencyKey
      );

      let structuredMessages: StructuredChatMessage[];
      if (existingIdx >= 0) {
        structuredMessages = [...state.structuredMessages];
        structuredMessages[existingIdx] = { ...fullMsg, id: structuredMessages[existingIdx].id };
      } else {
        structuredMessages = [...state.structuredMessages, fullMsg].slice(-50);
      }

      // Track processing doc
      const processingDocs = state.processingDocs.includes(msg.documentId)
        ? state.processingDocs
        : [...state.processingDocs, msg.documentId];

      return { structuredMessages, processingDocs };
    }),

  updateProcessingMessage: (documentId, updates) =>
    set((state) => ({
      structuredMessages: state.structuredMessages.map((m) =>
        m.type === 'processing_update' && (m as ProcessingUpdateMessage).documentId === documentId
          ? { ...m, ...updates }
          : m
      ),
    })),

  removeProcessingMessage: (documentId) =>
    set((state) => ({
      structuredMessages: state.structuredMessages.filter(
        (m) => !(m.type === 'processing_update' && (m as ProcessingUpdateMessage).documentId === documentId)
      ),
      processingDocs: state.processingDocs.filter((id) => id !== documentId),
    })),

  pushSuggestionMessage: (msg) =>
    set((state) => {
      const fullMsg: SuggestionChatMessage = {
        ...msg,
        id: generateId(),
        timestamp: new Date(),
      };

      // Dedup by idempotencyKey
      const existingIdx = state.structuredMessages.findIndex(
        (m) => m.idempotencyKey === msg.idempotencyKey
      );

      let structuredMessages: StructuredChatMessage[];
      if (existingIdx >= 0) {
        structuredMessages = [...state.structuredMessages];
        structuredMessages[existingIdx] = { ...fullMsg, id: structuredMessages[existingIdx].id };
      } else {
        structuredMessages = [...state.structuredMessages, fullMsg].slice(-50);
      }

      // Track pending suggestion
      const pendingSuggestionDocIds = state.pendingSuggestionDocIds.includes(msg.documentId)
        ? state.pendingSuggestionDocIds
        : [...state.pendingSuggestionDocIds, msg.documentId];

      return { structuredMessages, pendingSuggestionDocIds };
    }),

  updateSuggestionStatus: (documentId, status) =>
    set((state) => {
      const structuredMessages = state.structuredMessages.map((m) =>
        m.type === 'suggestion' && (m as SuggestionChatMessage).documentId === documentId
          ? { ...m, status }
          : m
      );

      // Remove from pending if confirmed or dismissed
      const pendingSuggestionDocIds =
        status === 'confirmed' || status === 'dismissed'
          ? state.pendingSuggestionDocIds.filter((id) => id !== documentId)
          : state.pendingSuggestionDocIds;

      return { structuredMessages, pendingSuggestionDocIds };
    }),

  pushFollowUpMessage: (msg) =>
    set((state) => {
      const fullMsg: FollowUpChatMessage = {
        ...msg,
        id: generateId(),
        timestamp: new Date(),
        answered: false,
      };

      // Dedup by idempotencyKey
      const existingIdx = state.structuredMessages.findIndex(
        (m) => m.idempotencyKey === msg.idempotencyKey
      );

      let structuredMessages: StructuredChatMessage[];
      if (existingIdx >= 0) {
        structuredMessages = [...state.structuredMessages];
        structuredMessages[existingIdx] = { ...fullMsg, id: structuredMessages[existingIdx].id };
      } else {
        structuredMessages = [...state.structuredMessages, fullMsg].slice(-50);
      }

      return { structuredMessages };
    }),

  markFollowUpAnswered: (documentId) =>
    set((state) => ({
      structuredMessages: state.structuredMessages.map((m) =>
        m.type === 'follow_up' && (m as FollowUpChatMessage).documentId === documentId
          ? { ...m, answered: true }
          : m
      ),
    })),

  // =========================================================================
  // Computed: Get all messages ordered by timestamp
  // =========================================================================

  getOrderedMessages: () => {
    const state = get();
    const allMessages: (ProactiveMessage | StructuredChatMessage)[] = [
      ...state.messages.filter((m) => !m.dismissed),
      ...state.structuredMessages,
    ];
    const getTime = (ts: any): number => {
      if (ts instanceof Date) return ts.getTime();
      if (typeof ts === 'number') return ts;
      const d = new Date(ts);
      return isNaN(d.getTime()) ? 0 : d.getTime();
    };
    return allMessages.sort((a, b) => getTime(a.timestamp) - getTime(b.timestamp));
  },

  // =========================================================================
  // Task 23: Batch processing summary
  // =========================================================================

  getBatchProcessingSummary: () => {
    const state = get();
    if (state.processingDocs.length <= 1) return null;
    return {
      count: state.processingDocs.length,
      documentIds: [...state.processingDocs],
    };
  },
}));
