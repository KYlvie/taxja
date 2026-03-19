# Implementation Tasks: AI Assistant Unified Interaction System

## Recommended Execution Order (Adjusted Priority)

The recommended build order prioritizes the **"upload → chat → confirm" closed loop** — this delivers the most user-visible value first:

```
1. Task 3:  aiAdvisorStore extension (message types, idempotency, ui_state)     ⭐ FOUNDATION
2. Task 7:  Backend /process-status endpoint                                     ⭐ FOUNDATION
3. Task 8:  Backend /follow-up endpoint (partial answers, use_defaults)          ⭐ FOUNDATION
4. Task 4-6: Backend follow-up question generation (schema + asset + property)
5. Task 11: ChatProcessingIndicator component
6. Task 9:  ChatSuggestionCard component
7. Task 10: ChatFollowUpQuestion component
8. Task 14: Wire upload → chat processing messages  ← THIS IS THE KEY MILESTONE
9. Task 15: Frontend API methods
10. Task 12: ChatProactiveAction component
11. Task 13: ChatInterface render extension
12. Task 17: Proactive inline actions (via unified action contract)
13. Task 16: Chat context with suggestion_context
14. Tasks 1-2, 18-21: Visual unification (Phase 3 — do LAST)
```

**Key milestone**: After Task 14, the "upload → processing → suggestion → follow-up → confirm" loop is functional in chat. This is the most important deliverable.

---

## Phase 1: Foundation (No Breaking Changes)

### Task 1: Create AIAvatar Shared Component
- [ ] Create `frontend/src/components/ai/AIAvatar.tsx` with size variants (sm/md/lg) and status (online/thinking/idle)
- [ ] Create `frontend/src/components/ai/AIAvatar.css` with gradient animation and pulse effect
- [ ] Export from components/ai index

**Files**: `frontend/src/components/ai/AIAvatar.tsx`, `AIAvatar.css`
**Requirements**: FR-16

### Task 2: Create Shared Action Button Styles
- [ ] Create `frontend/src/components/ai/ai-action-buttons.css` with confirm/dismiss/loading variants
- [ ] Ensure consistent border-radius, padding, font-size across all AI surfaces

**Files**: `frontend/src/components/ai/ai-action-buttons.css`
**Requirements**: FR-18

### Task 3: Extend aiAdvisorStore with New Message Types ⭐ HIGHEST PRIORITY
- [ ] Add `BaseChatMessage` interface with `id`, `idempotencyKey`, `timestamp`
- [ ] Add `SuggestionChatMessage` interface (type='suggestion', extractedData, followUpQuestions, status, action)
- [ ] Add `FollowUpQuestion` interface (question, inputType, options, validation)
- [ ] Add `ProcessingUpdateMessage` interface (documentId, phase, message, uiState)
- [ ] Add `ActionDescriptor` interface (kind, targetId, endpoint, method, payload)
- [ ] Add `UIState` type enum ('processing' | 'needs_input' | 'ready_to_confirm' | 'confirmed' | 'dismissed' | 'error')
- [ ] Add `pendingSuggestions[]` state for tracking active suggestions
- [ ] Add `processingDocs[]` state for tracking upload progress
- [ ] Add `pushMessage()` with **idempotencyKey deduplication** — if key exists, update in-place instead of inserting
- [ ] Add `pushProcessingMessage()`, `updateProcessingMessage()`, `removeProcessingMessage()` actions
- [ ] Add `pushSuggestionMessage()`, `updateSuggestionStatus()` actions

**Files**: `frontend/src/stores/aiAdvisorStore.ts`
**Requirements**: FR-1, FR-13, NFR-6

### Task 4: Backend - Add Follow-Up Questions to Suggestion Schema
- [ ] Create `FollowUpQuestion` Pydantic schema in `backend/app/schemas/document.py`
- [ ] Add `follow_up_questions` field to suggestion response in document pipeline
- [ ] Ensure backward compatibility (field is optional, defaults to empty array)

**Files**: `backend/app/schemas/document.py`
**Requirements**: FR-6, FR-7

### Task 5: Backend - Generate Follow-Up Questions for Assets
- [ ] In `document_pipeline_orchestrator.py`, build follow-up questions when asset suggestion has missing required fields
- [ ] Required questions for assets: put_into_use_date, business_use_percentage
- [ ] Conditional questions: is_used_asset, first_registration_date (for vehicles), prior_owner_usage_years
- [ ] Optional questions: depreciation_method, useful_life_years (with smart defaults)
- [ ] All questions trilingual (de/en/zh)
- [ ] Include `helpText` for non-obvious fields (e.g., put_into_use_date: "The date you started using this for business, not the purchase date"; building_value_ratio: "Standard is 70/30. Use your Liegenschaftsgutachten if available.")

**Files**: `backend/app/services/document_pipeline_orchestrator.py`, `backend/app/services/asset_recognition_service.py`
**Requirements**: FR-6, FR-7

### Task 6: Backend - Generate Follow-Up Questions for Properties
- [ ] Add follow-up questions for properties when missing: building_value_ratio, building_year, intended_use
- [ ] Provide select options for building_value_ratio (70/30, 60/40, 80/20, custom)
- [ ] All questions trilingual

**Files**: `backend/app/services/document_pipeline_orchestrator.py`
**Requirements**: FR-6, FR-7

### Task 7: Backend - Add Document Process Status Endpoint ⭐ HIGH PRIORITY
- [ ] Create `GET /documents/{id}/process-status` endpoint
- [ ] Return: phase, document_type, human-readable message, suggestion (if complete)
- [ ] Return `ui_state` enum derived from `_derive_ui_state()` — single stable state for frontend
- [ ] Return `idempotency_key` (backend-generated, source of truth — frontend must use verbatim)
- [ ] Return `phase_started_at` and `phase_updated_at` ISO timestamps — enables frontend to show elapsed time, detect stalls, trigger retry UI
- [ ] Return `current_phase_attempt` (int, default 1) — tracks retry count for Phase 2 retries
- [ ] Return `suggestion_version` for optimistic concurrency on follow-up answers
- [ ] Return `action` descriptor on suggestions (see design Section 3.5), including `confirmLabel`/`dismissLabel`/`detailLabel`
- [ ] Phase messages trilingual

**Files**: `backend/app/api/v1/endpoints/documents.py`
**Requirements**: FR-13, FR-14, FR-15, NFR-6, NFR-7

### Task 8: Backend - Add Follow-Up Answer Endpoint
- [ ] Create `POST /documents/{id}/follow-up` endpoint
- [ ] Accept `FollowUpAnswerRequest` with `answers: Dict[str, Any]`, `use_defaults: bool = False`, and `suggestion_version: int`
- [ ] **Optimistic concurrency**: Validate `suggestion_version` matches current version; return HTTP 409 Conflict if mismatch
- [ ] **Partial answers**: Merge only provided answers; preserve order of remaining questions
- [ ] **Use defaults mode**: When `use_defaults=True`, apply `default_value` for all unanswered questions; track which defaults were applied
- [ ] Clear answered questions from `follow_up_questions` array (preserve order of remaining)
- [ ] When all questions answered, set suggestion status to `ready_to_confirm`
- [ ] **Bump suggestion version** on every successful write
- [ ] Return: `ui_state`, `suggestion_version`, `remaining_questions` count, `remaining_question_list`, `applied_defaults` dict
- [ ] `applied_defaults` must include both the value and the original question text (so chat can display "I used standard 70/30 ratio")

**Files**: `backend/app/api/v1/endpoints/documents.py`
**Requirements**: FR-9, FR-19, FR-20, FR-21, NFR-9

---

## Phase 2: Integration (Parallel Systems)

### Task 9: Create ChatSuggestionCard Component
- [ ] Create `frontend/src/components/ai/ChatSuggestionCard.tsx`
- [ ] Render suggestion data as structured card inside chat (AIAvatar + header + key/value rows + buttons)
- [ ] Support all suggestion types: create_property, create_asset, create_recurring_income, create_recurring_expense, create_loan, import_* (tax forms), import_bank_statement
- [ ] **Use ActionDescriptor for confirm** — call `handleActionConfirm(suggestion.action)` generically, NOT per-type switch
- [ ] Use `action.confirmLabel` / `action.dismissLabel` for button text (fallback to generic i18n)
- [ ] Dismiss button → call documentService.dismissSuggestion()
- [ ] Show loading spinner during confirmation
- [ ] Show success/error result message after action
- [ ] Use shared ai-action-buttons.css
- [ ] **RULE: No embedded forms.** Complex suggestions (asset, property with missing data) show summary + buttons ONLY. All multi-field input goes through `ChatFollowUpQuestion` as a separate message.

**Files**: `frontend/src/components/ai/ChatSuggestionCard.tsx`
**Requirements**: FR-1, FR-2, FR-3, FR-4, FR-22

### Task 10: Create ChatFollowUpQuestion Component
- [ ] Create `frontend/src/components/ai/ChatFollowUpQuestion.tsx`
- [ ] Render questions with appropriate input controls (date picker, number input, select, boolean toggle)
- [ ] Validate inputs according to question.validation rules
- [ ] "Submit answers" button → call documentService.submitFollowUp()
- [ ] "Use defaults" button → proceed without answers
- [ ] After submit, update suggestion message status to 'pending' (ready for confirm)

**Files**: `frontend/src/components/ai/ChatFollowUpQuestion.tsx`
**Requirements**: FR-8, FR-9

### Task 11: Create ChatProcessingIndicator Component
- [ ] Create `frontend/src/components/ai/ChatProcessingIndicator.tsx`
- [ ] Show phase-appropriate message with animated dots
- [ ] Progress through phases: "Analyzing..." → "Identified as [type]..." → "Extracting details..."
- [ ] Use AIAvatar with status='thinking'

**Files**: `frontend/src/components/ai/ChatProcessingIndicator.tsx`
**Requirements**: FR-13, FR-14

### Task 12: Create ChatProactiveAction Component
- [ ] Create `frontend/src/components/ai/ChatProactiveAction.tsx`
- [ ] Render proactive messages with inline Confirm/Dismiss/View Details buttons
- [ ] Confirm → direct API call (no navigation away)
- [ ] View Details → expand message to show full data
- [ ] Support types: recurring_confirm, asset_confirm, tax_form_review, employer_month_confirm

**Files**: `frontend/src/components/ai/ChatProactiveAction.tsx`
**Requirements**: FR-10, FR-11, FR-12

### Task 13: Extend ChatInterface to Render New Message Types
- [ ] Import and render ChatSuggestionCard for type='suggestion'
- [ ] Import and render ChatFollowUpQuestion for type='follow_up'
- [ ] Import and render ChatProcessingIndicator for type='processing_update'
- [ ] Import and render ChatProactiveAction for proactive types with actionData
- [ ] Ensure scroll-to-bottom works for new message types
- [ ] Ensure mobile layout works for new message types

**Files**: `frontend/src/components/ai/ChatInterface.tsx`
**Requirements**: FR-1, FR-8, FR-10, NFR-5

### Task 14: Wire Document Upload → Chat Processing Messages ⭐ KEY MILESTONE
- [ ] In DocumentsPage.tsx (or DocumentUpload.tsx), after upload success:
  - Push 'processing_update' message to aiAdvisorStore using **backend-provided idempotency_key** (NOT self-generated)
  - Start polling /documents/{id}/process-status every 2 seconds
  - Update processing message on each poll (dedup by idempotency_key)
  - When complete, remove processing message and push suggestion message
  - If follow-up questions exist, push follow_up message as **separate** chat message (NOT embedded in suggestion card)
- [ ] Auto-open FloatingAIChat panel when processing starts (desktop: expand, mobile: show badge pulse)
- [ ] **HARD CONSTRAINT**: Suggestion must enter Chat first → Documents page SuggestionCard renders from same backend data as secondary path. It is NOT allowed to create suggestion on Documents page first, then mirror to chat.

**Files**: `frontend/src/pages/DocumentsPage.tsx`, `frontend/src/services/documentService.ts`
**Requirements**: FR-13, FR-14, FR-15, Section 1.2 Implementation Constraint

### Task 15: Add Frontend API Methods
- [ ] `documentService.getProcessStatus(docId)` → GET /documents/{id}/process-status
- [ ] `documentService.submitFollowUp(docId, answers)` → POST /documents/{id}/follow-up
- [ ] `aiService.sendMessageWithSuggestionContext(msg, suggestionCtx)` → POST /ai/chat with suggestion_context

**Files**: `frontend/src/services/documentService.ts`, `frontend/src/services/aiService.ts`
**Requirements**: FR-3, FR-9

### Task 16: Backend - Extend Chat API with Suggestion Context
- [ ] Accept optional `suggestion_context: SuggestionContext` in POST /ai/chat request body
- [ ] **Minimal fields only**: SuggestionContext contains `document_id`, `suggestion_type`, `summary` (key extracted fields), `pending_questions` — NOT full `ocr_result` or document blob
- [ ] In ai_orchestrator.py, inject suggestion summary into RAG context when present
- [ ] Enable users to ask questions like "What depreciation method should I use?" and get suggestion-aware answers

**Files**: `backend/app/api/v1/endpoints/ai_assistant.py`, `backend/app/services/ai_orchestrator.py`, `backend/app/schemas/ai_assistant.py`
**Requirements**: FR-2, NFR-8

### Task 17: Wire Proactive Message Inline Actions (via Unified Action Contract)
- [ ] In FloatingAIChat.tsx, add a **generic** `handleActionConfirm(action: ActionDescriptor, payload?)` handler
- [ ] Handler dispatches based on `action.endpoint` + `action.method` — NO per-type switch needed
- [ ] `handleProactiveDismiss(msg)` → update message status
- [ ] `handleProactiveExpand(msg)` → toggle detail view
- [ ] Refresh relevant stores after confirmation
- [ ] Fallback: if `action` descriptor is missing (legacy messages), use existing per-type switch

**Files**: `frontend/src/components/ai/FloatingAIChat.tsx`
**Requirements**: FR-10, FR-11, FR-12, FR-22

---

## Phase 3: Polish (Visual Unification)

### Task 18: Replace All Avatar Implementations with AIAvatar
- [ ] ChatInterface.tsx: Replace `.chat-avatar.assistant` div with `<AIAvatar />`
- [ ] ConfirmDialog.tsx: Replace robot emoji with `<AIAvatar status="thinking" />`
- [ ] AIToast.tsx: Replace `.ai-toast-avatar` span with `<AIAvatar size="sm" />`
- [ ] FloatingAIChat.tsx proactive messages: Replace emoji icons with `<AIAvatar size="sm" />`
- [ ] Update CSS to remove old avatar styles

**Files**: Multiple frontend components
**Requirements**: FR-16

### Task 19: Standardize Action Button Styles
- [ ] Import ai-action-buttons.css in all AI components
- [ ] Replace suggestion card confirm/dismiss buttons with `.ai-action-btn` classes
- [ ] Replace ConfirmDialog buttons with `.ai-action-btn` classes
- [ ] Replace proactive message action buttons with `.ai-action-btn` classes
- [ ] Ensure consistent hover/focus/disabled states

**Files**: Multiple frontend components + CSS files
**Requirements**: FR-18

### Task 20: Standardize Animation Timings
- [ ] Use `msgIn 0.25s` for all new chat message entries
- [ ] Use consistent typing indicator (reuse from ChatInterface)
- [ ] Add subtle slide-in for suggestion cards and follow-up questions
- [ ] Ensure no jarring transitions between message types

**Files**: Multiple CSS files
**Requirements**: FR-17

### Task 21: i18n for All New Components
- [ ] Add keys in en.json, de.json, zh.json for:
  - Processing phase messages ("Analyzing...", "Extracting...")
  - Suggestion headers ("I found a property in your document")
  - Follow-up question prompts
  - Action button labels ("Confirm", "Dismiss", "Use defaults", "Submit answers")
  - Success/error messages

**Files**: `frontend/src/i18n/locales/en.json`, `de.json`, `zh.json`
**Requirements**: FR-9

---

## Phase 4: Enhancement (Optional, Post-MVP)

### Task 22: Smart Suggestion Priority Ordering
- [ ] Sort pending suggestions by: severity (high→low), then confidence (high→low), then timestamp (newest→oldest)
- [ ] Show count badge on FloatingAIChat for pending suggestions

### Task 23: Multi-Suggestion Batch Handling
- [ ] When multiple documents uploaded simultaneously, queue processing messages
- [ ] Show "Processing 3 documents..." collective indicator
- [ ] Present suggestions one at a time as they complete

### Task 24: Undo for Confirmed Suggestions
- [ ] After confirmation, show "Undo" button for 10 seconds
- [ ] Undo calls DELETE endpoint to reverse the creation
- [ ] Only for entity creation (property, recurring, asset), not for tax data import

### Task 25: "Ask About This" Link on Document Page SuggestionCards
- [ ] Add small "Ask AI about this" link on each SuggestionCard
- [ ] Clicking opens FloatingAIChat with suggestion context pre-loaded
- [ ] Bridges the Documents page experience with the chat experience

---

## Dependency Graph

```
Task 1 (AIAvatar) ─────────────────────────────────────────┐
Task 2 (Action buttons) ───────────────────────────────────┤
Task 3 (Store extension) ──┬── Task 9 (ChatSuggestionCard) ┤
                           ├── Task 10 (ChatFollowUp)      ├── Task 18 (Replace avatars)
                           ├── Task 11 (Processing)        ├── Task 19 (Button styles)
                           └── Task 12 (ProactiveAction)   ├── Task 20 (Animations)
                                                           └── Task 21 (i18n)
Task 4 (Schema) ──┬── Task 5 (Asset follow-ups) ──┐
                   └── Task 6 (Property follow-ups)│
Task 7 (Status endpoint) ─────────────────────────┤
Task 8 (Follow-up endpoint) ──────────────────────┤
                                                   │
Task 13 (ChatInterface render) ◄──── Tasks 9-12   │
Task 14 (Upload → Chat wire) ◄──── Tasks 7, 3     │
Task 15 (API methods) ◄──── Tasks 7, 8            │
Task 16 (Chat context) ────────────────────────────┘
Task 17 (Proactive wire) ◄──── Task 12
```

## Estimated Effort

| Phase | Tasks | Estimated Effort |
|-------|-------|------------------|
| Phase 1: Foundation | Tasks 1-8 | Medium |
| Phase 2: Integration | Tasks 9-17 | Large |
| Phase 3: Polish | Tasks 18-21 | Small |
| Phase 4: Enhancement | Tasks 22-25 | Medium (optional) |

## Testing Strategy

### Unit Tests
Each new component (ChatSuggestionCard, ChatFollowUpQuestion, etc.) needs render + interaction tests.

### Integration Tests
Upload document → processing → suggestion → follow-up → confirm end-to-end flow.

### Backend Tests
New endpoints (process-status, follow-up) with various document types.
- Follow-up endpoint: test partial answers, full answers, use_defaults, order preservation
- Process-status endpoint: test ui_state derivation for all pipeline states

### Visual Regression
Screenshot tests for new chat message types at desktop + mobile sizes.

### Backward Compatibility
Verify existing SuggestionCards on Documents page still work unchanged.

### "No Navigation Away" Regression Tests (BLOCKING ACCEPTANCE CRITERIA)

These tests verify the core value proposition — users can complete all AI interactions without leaving the chat panel:

| Test ID | Scenario | Steps | Pass Criteria |
|---------|----------|-------|---------------|
| AC-1 | Asset invoice upload | Upload vehicle Kaufvertrag → answer follow-up in chat → confirm in chat | Asset created; user never navigated to Documents page |
| AC-2 | Property upload | Upload Kaufvertrag → confirm building ratio in chat → confirm | Property created; no Documents page navigation |
| AC-3 | Recurring confirm | Receive recurring_confirm proactive → click Confirm in chat | Recurring transaction created; no Transactions page navigation |
| AC-4 | Tax form review | Receive tax_form_review proactive → click Confirm in chat | Tax data imported; no Documents page navigation |
| AC-5 | Suggestion context Q&A | While pending asset suggestion → ask "What depreciation method?" in chat | AI response includes suggestion-aware context (mentions the specific asset) |

**These are blocking — the feature is not shippable until all 5 pass.**

### Idempotency Deduplication Tests

| Test ID | Scenario | Pass Criteria |
|---------|----------|---------------|
| IDEM-1 | Poll process-status 5 times for same doc | Only 1 processing_update message in chat, not 5 |
| IDEM-2 | Upload completes, suggestion pushed twice due to race | Only 1 suggestion message in chat |
| IDEM-3 | Upload 3 docs simultaneously | 3 separate processing messages, each with unique key |

### Dual-Surface State Sync Tests (Chat + Documents Page)

| Test ID | Scenario | Pass Criteria |
|---------|----------|---------------|
| SYNC-1 | Confirm suggestion in Chat panel | Documents page SuggestionCard also shows confirmed state |
| SYNC-2 | Confirm suggestion via Documents page SuggestionCard | Chat panel suggestion message also shows confirmed state |
| SYNC-3 | Dismiss in Chat → check Documents page | SuggestionCard shows dismissed; no "double confirm" possible |
| SYNC-4 | Attempt confirm in both surfaces simultaneously | Only one succeeds; the other detects version mismatch gracefully |
| SYNC-5 | Chat shows follow-up; Documents page secondary card also open; one side submits answers → other side submits stale version | HTTP 409 returned on stale side; user prompted to refresh; no silent data overwrite |

### Retry & Failure Recovery Tests

| Test ID | Scenario | Pass Criteria |
|---------|----------|---------------|
| RETRY-1 | Follow-up submit fails (network error) → retry | Second submit succeeds; no duplicate data written |
| RETRY-2 | Confirm succeeds but frontend request times out → user refreshes | Chat shows confirmed state (no orphaned "pending" message) |
| RETRY-3 | Document processing hits `phase_2_failed` | Chat shows error message; user can retry or dismiss |
| RETRY-4 | Follow-up submit with stale `suggestion_version` | HTTP 409 returned; frontend shows "Please refresh" message |

### Normal Chat Regression Tests

These verify that adding new message types doesn't break existing chat behavior:

| Test ID | Scenario | Pass Criteria |
|---------|----------|---------------|
| CHAT-1 | Send normal Q&A message while processing_update is visible | Response appears correctly; processing indicator stays |
| CHAT-2 | Scroll through mixed messages (Q&A + suggestion + follow-up + proactive) | No layout breaks; scroll position stable |
| CHAT-3 | Chat history restore after page reload | All message types (including suggestions) restore correctly |
| CHAT-4 | Mobile FAB mode with suggestion + follow-up visible | All interactive elements reachable; no overflow |
