# Requirements: AI Assistant Unified Interaction System

## 1. Vision

Taxja's AI assistant should feel like a **real human tax advisor sitting next to you** - proactively helping, asking smart questions when it needs more info, and guiding users through complex tax decisions. All AI interactions (notifications, suggestions, confirmations, follow-up questions) should use a **single, consistent interaction paradigm**: the AI chat panel.

### 1.1 Hard Rule: Chat is Primary, Documents Page is Secondary

> **All new suggestion / follow-up / proactive confirm flows default to appearing in the Chat panel first.** The Documents page SuggestionCards are retained only as a secondary access path for users who prefer direct page interaction. No new feature should introduce a dual-primary entry point — chat is always the primary surface for AI-user interaction.

This rule prevents the system from drifting back into the current "5 separate interaction systems" fragmentation.

### 1.2 Implementation Constraint: Primary vs Secondary Surface

The following ordering must be enforced in implementation:

1. **Upload triggers suggestion → suggestion enters Chat first** (via `aiAdvisorStore.pushMessage`)
2. **Documents page SuggestionCard renders from the same backend data** (secondary access path)
3. **Both surfaces share the same backend state** — confirming in either surface updates the same `suggestion.status`
4. **It is NOT allowed to**: create the suggestion on the Documents page first, then "mirror" it to chat. The chat is the primary creation surface.
5. **Documents page must not interrupt the chat flow**: The secondary SuggestionCard may render the same suggestion state, but must NOT auto-open forms, modals, or grab focus when a suggestion is pending. It displays passively — the user must actively click to interact with it. This prevents the dual-surface experience from feeling like two systems competing for attention.

## 2. Current State Assessment

### 2.1 What Exists (5 separate interaction systems)

| System | Component | Pattern | Consistency |
|--------|-----------|---------|-------------|
| **Chat** | ChatInterface + FloatingAIChat | Conversational text Q&A | Good |
| **Confirm Dialog** | ConfirmDialog + GlobalConfirmDialog | Modal with typing animation | Good - feels like AI |
| **Toast** | AIToast | Auto-dismiss corner notification | OK - passive only |
| **Suggestion Cards** | SuggestionCardFactory + 20 card types | Inline form + buttons in document page | Inconsistent |
| **Proactive Messages** | aiAdvisorStore notifications | Badge + sidebar panel | Incomplete |

### 2.2 Problems Found in Current Code

#### P1 - CRITICAL: Asset Upload Follow-Up Questions Are NOT In-Chat

When a user uploads an asset invoice (e.g., a vehicle purchase contract), the system:
1. Runs OCR + asset recognition
2. Generates an `AssetSuggestionCard` with inline form fields
3. Displays it **on the Documents page** - NOT in the AI chat panel

**Problem**: The user must navigate to Documents page, find the card, fill in depreciation details (useful life, business use %, put-into-use date), then confirm. This is disconnected from the "AI advisor" experience. A real advisor would **ask you directly**: "I see you bought a vehicle for EUR 35,000. When did you start using it for business? What percentage is business use?"

**Files affected:**
- `frontend/src/components/documents/suggestion-cards/AssetSuggestionCard.tsx` - Complex inline form
- `frontend/src/pages/DocumentsPage.tsx` - Orchestrates suggestion rendering (lines ~2168-2187)
- `backend/app/services/asset_recognition_service.py` - Generates suggestion data

#### P2 - HIGH: Three Different Confirmation UX Patterns

| Action | Current Pattern | Feel |
|--------|----------------|------|
| Delete transaction | `ConfirmDialog` modal (typing animation) | Feels like AI |
| Confirm property from Kaufvertrag | `SuggestionCard` inline buttons | Feels like form |
| Confirm recurring from contract | `SuggestionCard` inline buttons | Feels like form |
| Confirm asset with depreciation | `AssetSuggestionCard` inline form + buttons | Feels like complex form |
| Confirm tax data import | `TaxFormCard` inline buttons | Feels like form |
| Dismiss bank statement entries | `KontoauszugSuggestionCard` checkbox list | Feels like spreadsheet |

**Problem**: Only delete operations feel like talking to an AI. Everything else feels like filling forms.

#### P3 - HIGH: Proactive Messages Lack Actionable In-Chat Response

The `FloatingAIChat` generates proactive messages (tips, reminders, recurring confirmations), but:
- `recurring_confirm` type → just shows text + optional link to navigate away
- `asset_confirm` type → just shows text + optional link to navigate away
- `tax_form_review` type → just shows text + optional link to navigate away

**Problem**: None of these allow inline action. The user must leave the chat, navigate to another page, find the relevant item, and take action there. A real advisor would let you respond **right there in the conversation**.

**Files affected:**
- `frontend/src/components/ai/FloatingAIChat.tsx` - Renders proactive messages (lines ~450-580)
- `frontend/src/stores/aiAdvisorStore.ts` - Message types have `actionData` but no inline action UI

#### P4 - MEDIUM: No Conversational Follow-Up for Missing Data

The backend's `_ask_for_params()` in `ai_orchestrator.py` asks for missing parameters via text:
```
"Please provide your gross income, e.g. 'Calculate tax for EUR 50,000'."
```

But for **document processing**, when data is missing (e.g., building value ratio in a Kaufvertrag), the system:
- Silently falls back to defaults (70% building value assumption)
- OR shows a suggestion card with pre-filled guesses

**Problem**: The AI should ask the user directly: "I extracted a purchase price of EUR 350,000 from your Kaufvertrag. I need the building-to-land ratio - do you have a Liegenschaftsbewertung? Or should I use the standard 70/30 split?"

**Files affected:**
- `backend/app/services/document_pipeline_orchestrator.py` - Phase 2 processing
- `backend/app/services/asset_recognition_service.py` - Silent defaults
- `backend/app/services/kaufvertrag_extractor.py` - Extraction without follow-up

#### P5 - MEDIUM: Chat and Suggestion Systems Are Disconnected

The chat (`ChatInterface`) and the suggestion system (`SuggestionCardFactory`) share no state:
- Chat doesn't know about pending suggestions
- Suggestions don't appear in chat history
- Users can't ask questions about a pending suggestion in chat context

**Files affected:**
- `frontend/src/services/aiService.ts` - No suggestion context in chat API
- `frontend/src/components/ai/ChatInterface.tsx` - No suggestion awareness
- `backend/app/api/v1/endpoints/ai_assistant.py` - Chat endpoint has no document suggestion context

#### P6 - LOW: Inconsistent Visual Design Across AI Surfaces

| Surface | Avatar | Animation | Color Scheme |
|---------|--------|-----------|-------------- |
| Chat messages | 26px gradient circle | msgIn 0.25s | Theme primary |
| ConfirmDialog | Robot emoji | Character typing 8-25ms | Variant-based |
| AIToast | 26px gradient circle | Slide + scale | Variant border |
| SuggestionCards | Icon per type | None | Blue gradient (recurring), bordered (others) |
| Proactive panel | Emoji per type | None | Subtle gradient |

**Problem**: Five different visual languages for what should be one AI persona.

#### P7 - LOW: No "Thinking" State for Document Processing

When a document is uploaded and being processed (3-30 seconds), the AI chat panel shows nothing. The processing state only appears on the Documents page as a status badge.

**Problem**: A real advisor would say "Let me look at this document..." and then come back with findings.

## 3. User Stories

### US-1: Unified AI Follow-Up Questions
As a user who uploaded an asset invoice, I want the AI to ask me follow-up questions **in the chat panel** (e.g., "When did you start using this for business?") so I can answer naturally without navigating to another page.

### US-2: In-Chat Confirmation with Context
As a user, when the AI detects a recurring transaction pattern from my uploaded contract, I want to see the suggestion **in the chat** with confirm/dismiss options, so the interaction feels like a conversation, not a form.

### US-3: Proactive Document Processing Feedback
As a user, after I upload a document, I want the AI to show me its analysis progress in the chat panel ("Analyzing your Kaufvertrag...", "I found a property at Hauptstrasse 12..."), so I know what's happening without checking the Documents page.

### US-4: Conversational Data Collection
As a user, when the AI needs additional information to complete a tax calculation or document processing (e.g., building value ratio, business use percentage), I want to provide it via chat responses, not by filling form fields.

### US-5: Connected Suggestion Context
As a user, I want to ask questions about a pending suggestion in the chat (e.g., "What depreciation method do you recommend for my vehicle?") and get context-aware answers.

### US-6: Consistent AI Persona
As a user, I want all AI interactions (notifications, suggestions, confirmations, chat) to look and feel the same - same avatar, same animation style, same visual language.

## 4. Functional Requirements

### 4.1 In-Chat Suggestion Rendering (FR-1 to FR-5)

- **FR-1**: When a document is processed and generates a suggestion (property, asset, recurring, tax form), the suggestion must appear as a **structured chat message** in the FloatingAIChat panel, not only as a SuggestionCard on the Documents page.
- **FR-2**: The in-chat suggestion message must include:
  - AI avatar + "I found something in your document" header
  - Key extracted data (amount, vendor, date, type) in a card-like format
  - Confirm + Dismiss action buttons
  - For complex suggestions (assets): expandable "I need more details" section with form fields
- **FR-3**: Clicking Confirm in chat must trigger the same backend confirmation API as the current SuggestionCard system.
- **FR-4**: After confirmation, the chat must show a result message ("Property created successfully at Hauptstrasse 12").
- **FR-5**: The SuggestionCards on the Documents page must remain as a secondary access path for users who prefer it.

### 4.2 Conversational Follow-Up Questions (FR-6 to FR-9)

- **FR-6**: When document processing identifies missing required data, the backend must return a `follow_up_questions` array in the suggestion response.
- **FR-7**: Each follow-up question must include: question text, input type (text/number/select/date), options (for select), default value, and validation rules.
- **FR-8**: The frontend must render follow-up questions as structured chat messages with inline input controls.
- **FR-9**: User responses to follow-up questions must be collected and sent back to the backend to update the suggestion before confirmation.

### 4.3 Proactive Message Actions (FR-10 to FR-12)

- **FR-10**: Proactive messages of type `recurring_confirm`, `asset_confirm`, `tax_form_review`, and `employer_month_confirm` must include inline action buttons (Confirm/Dismiss/View Details).
- **FR-11**: Clicking Confirm on a proactive message must directly execute the confirmation API, not navigate away.
- **FR-12**: Clicking "View Details" must expand the message to show full extracted data, similar to a SuggestionCard.

### 4.4 Document Processing Progress in Chat (FR-13 to FR-15)

- **FR-13**: When a document upload starts, push a "thinking" message to the chat: "Analyzing your document...".
- **FR-14**: When Phase 1 (OCR + classification) completes, update the message: "I identified this as a [type]. Extracting details...".
- **FR-15**: When Phase 2 completes, replace with the final suggestion message (per FR-1).

### 4.5 Unified Visual Design (FR-16 to FR-18)

- **FR-16**: All AI-originated content (chat, toast, suggestion, confirmation, proactive) must use the same avatar (gradient circle, not emoji).
- **FR-17**: All AI messages must use the same slide-in animation (standardize on `msgIn 0.25s`).
- **FR-18**: Action buttons across all AI surfaces must use the same style (primary for confirm, ghost for dismiss).

### 4.6 Follow-Up Endpoint Behavior (FR-19 to FR-21)

- **FR-19**: The `/documents/{id}/follow-up` endpoint must accept **partial answers** — users may answer some questions and skip others. Remaining questions must be preserved in original order and re-presented to the user.
- **FR-20**: When the user clicks "Use defaults", the backend must explicitly write the default values into the suggestion data (not leave them as `null`). The response must include which defaults were applied, so the chat can display: "I used the standard 70/30 building ratio and 100% business use."
- **FR-21**: The follow-up question order must be stable — re-requesting unanswered questions must not shuffle their sequence.

### 4.7 Unified Action Contract for Proactive Messages (FR-22)

- **FR-22**: All proactive messages with inline actions must carry a standardized `action` descriptor from the backend:
  ```
  action: {
    kind: "confirm_recurring" | "confirm_asset" | "confirm_tax_data" | ...,
    targetId: string,     // document ID or entity ID
    endpoint: string,     // e.g., "/documents/123/confirm-asset"
    payload?: object      // optional pre-filled data
  }
  ```
  This prevents the frontend from growing an unbounded `switch` statement — the action contract is self-describing and the handler can dispatch generically.

## 5. Non-Functional Requirements

- **NFR-1**: In-chat suggestion rendering must not degrade chat scroll performance (virtualize if > 50 messages).
- **NFR-2**: Follow-up question round-trip (user answers → backend processes → updated suggestion) must complete within 3 seconds.
- **NFR-3**: All existing SuggestionCard functionality must remain working (backward compatibility).
- **NFR-4**: Chat panel must handle concurrent suggestions from multiple document uploads without UI conflicts.
- **NFR-5**: Mobile (FAB mode) must support all in-chat suggestion interactions.
- **NFR-6**: All chat messages must carry an `idempotencyKey` (composed of `documentId + suggestionType + phase`) to prevent duplicate insertions when polling or retrying. The store's `pushMessage()` must deduplicate by this key.
- **NFR-7**: The `idempotencyKey` is **generated by the backend** and returned in API responses. The frontend must use the backend-provided key verbatim — it must NOT self-generate or infer keys by string concatenation. This prevents key drift when phase names or suggestion types change.
- **NFR-8**: The `suggestion_context` passed to the chat API must only carry **minimal necessary fields** (document_id, suggestion_type, key summary fields, pending question keys) — NOT the full `ocr_result` or document payload. This keeps LLM prompts predictable and prevents context bloat.
- **NFR-9**: The follow-up endpoint must enforce **optimistic concurrency** via `suggestion_version`. If a concurrent write from another tab/session has incremented the version, the endpoint returns HTTP 409 Conflict with the current version, and the frontend prompts the user to refresh.

## 6. Acceptance Criteria — "No Navigation Away" Regression Tests

The core value proposition of this feature is: **users can complete all AI-initiated interactions without leaving the chat panel**. The following must be verified as acceptance criteria:

- **AC-1**: Upload asset invoice → follow-up questions appear in chat → user answers in chat → confirms in chat → asset created. User never navigates to Documents page.
- **AC-2**: Upload Kaufvertrag → property suggestion appears in chat → user confirms building ratio in chat → property created. User never navigates to Documents page.
- **AC-3**: Proactive recurring_confirm message → user clicks Confirm in chat → recurring transaction created. User never navigates to Transactions page.
- **AC-4**: Proactive tax_form_review message → user clicks Confirm in chat → tax data imported. User never navigates to Documents page.
- **AC-5**: User asks "What depreciation method should I use?" while a pending asset suggestion is in chat → AI responds with suggestion-aware context.

These are **blocking acceptance criteria** — the feature is not complete until all 5 pass.

## 7. Out of Scope

- Real-time WebSocket push for processing status (polling is acceptable for v1)
- Voice input for follow-up question responses
- AI-initiated document upload requests ("Can you upload your Lohnzettel?")
- Removing SuggestionCards from Documents page (they remain as secondary access)

## 8. Key Risk: Dual-System Long-Term Drift

The biggest architectural risk is not technical — it's **organizational**. With both chat suggestions and Documents page suggestion cards coexisting, the team may inadvertently add new capabilities to both surfaces, recreating the fragmentation this spec aims to fix.

**Mitigation**: The Hard Rule in Section 1.1 must be enforced in code review. Any new suggestion or confirmation flow that does NOT appear in the chat panel first must be explicitly justified and approved.
