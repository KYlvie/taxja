# AI Tax Assistant Components

This directory contains the AI Tax Assistant interface components for Taxja.

## Components

### AIChatWidget
Floating chat button and expandable chat window that appears on all pages.

**Features:**
- Floating button in bottom-right corner
- Expandable chat window (400x600px on desktop, full-screen on mobile)
- Minimizable on desktop
- Context-aware based on current page

**Usage:**
```tsx
import AIChatWidget from './components/ai/AIChatWidget';

<AIChatWidget
  contextData={{
    page: 'dashboard',
    documentId: '123',
  }}
/>
```

### ChatInterface
Main chat interface with message history, input, and typing indicators.

**Features:**
- Message history with auto-scroll
- Typing indicator while AI responds
- Clear chat history button
- Suggested questions on first load
- Error handling

### AIResponse
Renders AI responses with markdown support and prominent disclaimer.

**Features:**
- Markdown rendering (bold, italic, lists, code blocks, links)
- Prominent disclaimer display (yellow warning box)
- Multi-language support
- Responsive design

### SuggestedQuestions
Context-aware suggested questions based on current page.

**Features:**
- Different questions for each page (dashboard, transactions, documents, reports)
- Quick-click buttons to populate input
- Icon-based visual design

## AI Service

The `aiService` handles all API communication with the backend AI endpoints.

**Methods:**
- `sendMessage(message, contextData)` - Send a message to AI
- `getChatHistory()` - Get chat history
- `clearChatHistory()` - Clear chat history
- `askAboutDocument(documentId, question)` - Ask about a specific document
- `askForSuggestions(taxData)` - Get tax optimization suggestions
- `explainOCRResult(documentId, ocrData)` - Get OCR explanation

## Integration Points

### OCR Review Page
- "Ask AI about this document" button
- AI explains OCR results and deductibility
- Context includes document ID and extracted data

### What-If Simulator
- "Ask AI for suggestions" button
- AI provides optimization recommendations
- Context includes simulation results

### All Pages
- Floating chat widget available everywhere
- Context-aware suggestions based on page

## Styling

All components use dedicated CSS files with:
- Gradient purple theme (#667eea to #764ba2)
- Responsive design (mobile-first)
- Smooth animations and transitions
- Accessibility support

## Translation Keys

Required translation keys in `i18n/locales/*.json`:

```json
{
  "ai": {
    "openChat": "Open chat",
    "askTaxjaAI": "Ask Taxja AI",
    "askAI": "Ask AI",
    "taxjaAssistant": "Taxja AI Assistant",
    "minimize": "Minimize",
    "close": "Close",
    "clickToExpand": "Click to expand",
    "welcomeTitle": "Welcome to Taxja AI Assistant",
    "welcomeMessage": "Ask me anything about Austrian taxes!",
    "thinking": "Thinking...",
    "inputPlaceholder": "Ask a tax question...",
    "send": "Send",
    "clearHistory": "Clear history",
    "confirmClearHistory": "Are you sure you want to clear chat history?",
    "errorSendingMessage": "Failed to send message",
    "disclaimer": "⚠️ This answer is for general reference only and does not constitute tax advice. Please refer to FinanzOnline for final results. For complex situations, consult a Steuerberater.",
    "suggestedQuestions": "Suggested questions",
    "askAboutDocument": "Ask AI about this document",
    "askForSuggestions": "Ask AI for suggestions",
    "explanation": "AI Explanation",
    "suggestions": "AI Suggestions",
    "loading": "Loading...",
    "questions": {
      "general": {
        "incomeTax": "How is income tax calculated in Austria?",
        "deductions": "What deductions can I claim?",
        "svs": "How does SVS social insurance work?",
        "commuting": "What is Pendlerpauschale?",
        "vat": "When do I need to pay VAT?",
        "flatRate": "Should I use flat-rate tax?"
      },
      "dashboard": {
        "taxSavings": "How can I save on taxes?",
        "estimatedTax": "What is my estimated tax?",
        "nextDeadline": "When is the next tax deadline?"
      },
      "transactions": {
        "deductible": "Is this expense deductible?",
        "categorize": "How should I categorize this?",
        "vat": "How do I handle VAT?"
      },
      "documents": {
        "receipt": "What can I deduct from this receipt?",
        "invoice": "How do I process this invoice?",
        "deductible": "Which items are deductible?"
      },
      "reports": {
        "generate": "How do I generate a tax report?",
        "finanzonline": "How do I submit to FinanzOnline?",
        "refund": "Will I get a tax refund?"
      }
    }
  }
}
```

## Requirements Validation

This implementation satisfies:
- **Requirement 38.1**: Chat widget on all pages with floating button
- **Requirement 38.2**: RAG-based AI responses (backend integration)
- **Requirement 38.3**: Multi-language support (German, English, Chinese)
- **Requirement 38.4**: Prominent disclaimer on every response
- **Requirement 38.5**: Chat history management
- **Requirement 38.6**: Clear history functionality
- **Requirement 38.7**: AI-powered OCR explanation
- **Requirement 38.8**: AI-powered what-if suggestions
