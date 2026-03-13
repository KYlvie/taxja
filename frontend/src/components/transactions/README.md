# Transaction Components

This directory contains all React components for transaction management in the Taxja application.

## Components

### TransactionList
Displays transactions in a responsive table format with sorting, filtering, and actions.

**Props:**
- `transactions: Transaction[]` - Array of transactions to display
- `onEdit: (transaction: Transaction) => void` - Callback when edit button is clicked
- `onDelete: (id: number) => void` - Callback when delete button is clicked
- `onView: (transaction: Transaction) => void` - Callback when row is clicked

**Features:**
- Color-coded income/expense rows
- Inline edit/delete actions
- Document attachment indicators
- Deductibility badges
- Empty state handling

### TransactionFilters
Provides filtering controls for transactions.

**Props:**
- `filters: TransactionFilters` - Current filter values
- `onFilterChange: (filters: TransactionFilters) => void` - Callback when filters are applied
- `onClear: () => void` - Callback when filters are cleared

**Features:**
- Date range selection
- Type filtering (income/expense)
- Search by description
- Deductibility filtering
- Responsive grid layout

### TransactionForm
Form for creating and editing transactions with validation.

**Props:**
- `transaction?: Transaction` - Optional transaction for edit mode
- `onSubmit: (data: TransactionFormData) => void` - Callback when form is submitted
- `onCancel: () => void` - Callback when cancel button is clicked

**Features:**
- React Hook Form integration
- Zod schema validation
- Dynamic category selection
- Real-time validation errors
- Deductibility status display
- Document link display

### TransactionDetail
Modal view showing complete transaction details.

**Props:**
- `transaction: Transaction` - Transaction to display
- `onEdit: () => void` - Callback when edit button is clicked
- `onDelete: () => void` - Callback when delete button is clicked
- `onClose: () => void` - Callback when modal is closed

**Features:**
- Modal overlay
- Tax information section
- Classification confidence bar
- Linked document access
- Metadata display
- Edit/delete actions

### TransactionImport
CSV import workflow with preview and validation.

**Props:**
- `onImport: (file: File) => Promise<ImportResult>` - Callback to handle file import
- `onConfirm: (transactions: Transaction[]) => void` - Callback when import is confirmed
- `onCancel: () => void` - Callback when import is cancelled

**Features:**
- File upload with validation
- Import instructions
- Preview of imported data
- Summary statistics
- Error reporting
- Confirm/cancel workflow

## Usage Example

```tsx
import {
  TransactionList,
  TransactionFilters,
  TransactionForm,
  TransactionDetail,
  TransactionImport,
} from '../components/transactions';

function TransactionsPage() {
  const [viewMode, setViewMode] = useState<'list' | 'create' | 'edit' | 'detail' | 'import'>('list');
  const [selectedTransaction, setSelectedTransaction] = useState<Transaction | null>(null);

  return (
    <div>
      {viewMode === 'list' && (
        <>
          <TransactionFilters
            filters={filters}
            onFilterChange={setFilters}
            onClear={clearFilters}
          />
          <TransactionList
            transactions={transactions}
            onEdit={(txn) => {
              setSelectedTransaction(txn);
              setViewMode('edit');
            }}
            onDelete={handleDelete}
            onView={(txn) => {
              setSelectedTransaction(txn);
              setViewMode('detail');
            }}
          />
        </>
      )}

      {viewMode === 'create' && (
        <TransactionForm
          onSubmit={handleCreate}
          onCancel={() => setViewMode('list')}
        />
      )}

      {viewMode === 'edit' && selectedTransaction && (
        <TransactionForm
          transaction={selectedTransaction}
          onSubmit={handleUpdate}
          onCancel={() => setViewMode('list')}
        />
      )}

      {viewMode === 'detail' && selectedTransaction && (
        <TransactionDetail
          transaction={selectedTransaction}
          onEdit={() => setViewMode('edit')}
          onDelete={handleDelete}
          onClose={() => setViewMode('list')}
        />
      )}

      {viewMode === 'import' && (
        <TransactionImport
          onImport={handleImport}
          onConfirm={handleConfirmImport}
          onCancel={() => setViewMode('list')}
        />
      )}
    </div>
  );
}
```

## Styling

Each component has its own CSS file with:
- Responsive design (mobile-first)
- Consistent color scheme
- Smooth transitions
- Accessibility considerations

## Type Definitions

All components use types from `../../types/transaction.ts`:
- `Transaction`
- `TransactionType`
- `TransactionFilters`
- `TransactionFormData`
- `ImportResult`
- `IncomeCategory`
- `ExpenseCategory`

## Internationalization

All text is internationalized using `react-i18next`. Translation keys are in `i18n/locales/*.json` under the `transactions` namespace.

## State Management

Components integrate with the Zustand store (`stores/transactionStore.ts`) for global state management.

## API Integration

Components use the transaction service (`services/transactionService.ts`) for API calls.
