import React from 'react';
import { SuggestionCardProps } from './suggestion-cards/SuggestionCardBase';
import PropertySuggestionCard from './suggestion-cards/PropertySuggestionCard';
import RecurringIncomeSuggestionCard from './suggestion-cards/RecurringIncomeSuggestionCard';
import RecurringExpenseSuggestionCard from './suggestion-cards/RecurringExpenseSuggestionCard';
import AssetSuggestionCard from './suggestion-cards/AssetSuggestionCard';
import LoanSuggestionCard from './suggestion-cards/LoanSuggestionCard';
import LohnzettelSuggestionCard from './suggestion-cards/LohnzettelSuggestionCard';
import L1SuggestionCard from './suggestion-cards/L1SuggestionCard';
import L1kSuggestionCard from './suggestion-cards/L1kSuggestionCard';
import L1abSuggestionCard from './suggestion-cards/L1abSuggestionCard';
import E1aSuggestionCard from './suggestion-cards/E1aSuggestionCard';
import E1bSuggestionCard from './suggestion-cards/E1bSuggestionCard';
import E1kvSuggestionCard from './suggestion-cards/E1kvSuggestionCard';
import U1SuggestionCard from './suggestion-cards/U1SuggestionCard';
import U30SuggestionCard from './suggestion-cards/U30SuggestionCard';
import JahresabschlussSuggestionCard from './suggestion-cards/JahresabschlussSuggestionCard';
import SvsSuggestionCard from './suggestion-cards/SvsSuggestionCard';
import GrundsteuerSuggestionCard from './suggestion-cards/GrundsteuerSuggestionCard';
import KontoauszugSuggestionCard from './suggestion-cards/KontoauszugSuggestionCard';
import GenericTaxFormCard from './suggestion-cards/GenericTaxFormCard';

export interface SuggestionCardFactoryProps extends SuggestionCardProps {
  /** Specific confirm handlers for non-tax-data types */
  onConfirmProperty?: () => void;
  onConfirmRecurring?: () => void;
  onConfirmRecurringExpense?: () => void;
  onConfirmAsset?: (payload?: any) => void;
  onConfirmLoan?: () => void;
  onConfirmTaxData?: () => void;
  onConfirmBankTransactions?: (indices: number[]) => void;
}

/** Map of suggestion type → card component for non-generic types */
const CARD_MAP: Record<string, React.FC<SuggestionCardProps>> = {
  import_lohnzettel: LohnzettelSuggestionCard,
  import_l1: L1SuggestionCard,
  import_l1k: L1kSuggestionCard,
  import_l1ab: L1abSuggestionCard,
  import_e1a: E1aSuggestionCard,
  import_e1b: E1bSuggestionCard,
  import_e1kv: E1kvSuggestionCard,
  import_u1: U1SuggestionCard,
  import_u30: U30SuggestionCard,
  import_jahresabschluss: JahresabschlussSuggestionCard,
  import_svs: SvsSuggestionCard,
  import_grundsteuer: GrundsteuerSuggestionCard,
};

const SuggestionCardFactory: React.FC<SuggestionCardFactoryProps> = (props) => {
  const { suggestion } = props;
  const type = suggestion.type;

  // Legacy entity-creation types
  if (type === 'create_property') {
    return <PropertySuggestionCard {...props}
      onConfirm={props.onConfirmProperty || props.onConfirm}
      confirmActionKey="property" />;
  }
  if (type === 'create_recurring_income') {
    return <RecurringIncomeSuggestionCard {...props}
      onConfirm={props.onConfirmRecurring || props.onConfirm}
      confirmActionKey="recurring" />;
  }
  if (type === 'create_recurring_expense') {
    return <RecurringExpenseSuggestionCard {...props}
      onConfirm={props.onConfirmRecurringExpense || props.onConfirm}
      confirmActionKey="recurring_expense" />;
  }
  if (type === 'create_asset') {
    return <AssetSuggestionCard {...props}
      onConfirm={props.onConfirmAsset || props.onConfirm}
      confirmActionKey="asset" />;
  }
  if (type === 'create_loan') {
    return <LoanSuggestionCard {...props}
      onConfirm={props.onConfirmLoan || props.onConfirm}
      confirmActionKey="loan" />;
  }

  // Bank statement — special card with transaction selection
  if (type === 'import_bank_statement') {
    return <KontoauszugSuggestionCard {...props}
      onConfirm={props.onConfirmTaxData || props.onConfirm}
      onConfirmBankTransactions={props.onConfirmBankTransactions}
      confirmActionKey="bank_import" />;
  }

  // Tax form types — specific cards
  const SpecificCard = CARD_MAP[type];
  if (SpecificCard) {
    return <SpecificCard {...props}
      onConfirm={props.onConfirmTaxData || props.onConfirm}
      confirmActionKey="tax_data" />;
  }

  // Fallback: any import_* type we don't have a specific card for
  if (type?.startsWith('import_')) {
    return <GenericTaxFormCard {...props}
      onConfirm={props.onConfirmTaxData || props.onConfirm}
      confirmActionKey="tax_data" />;
  }

  return null;
};

export default SuggestionCardFactory;
