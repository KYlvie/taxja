/**
 * Client-side category matcher — mirrors backend rule_based_classifier.py
 * Used to auto-suggest categories as the user types a description.
 */

import { IncomeCategory, ExpenseCategory } from '../types/transaction';

interface MatchResult {
  category: string;
  confidence: number;
}

// ── Income keywords (7 Einkunftsarten) ──────────────────────────────────

const INCOME_KEYWORDS: Record<string, IncomeCategory> = {
  // Nr.1 Land- und Forstwirtschaft
  holzverkauf: IncomeCategory.AGRICULTURE,
  ernte: IncomeCategory.AGRICULTURE,
  obstbau: IncomeCategory.AGRICULTURE,
  imkerei: IncomeCategory.AGRICULTURE,
  honig: IncomeCategory.AGRICULTURE,
  forstwirtschaft: IncomeCategory.AGRICULTURE,
  landwirtschaft: IncomeCategory.AGRICULTURE,
  gartenbau: IncomeCategory.AGRICULTURE,
  'waldgrundstück': IncomeCategory.AGRICULTURE,
  // Nr.2 Selbständige Arbeit
  honorar: IncomeCategory.SELF_EMPLOYMENT,
  freiberuf: IncomeCategory.SELF_EMPLOYMENT,
  gutachten: IncomeCategory.SELF_EMPLOYMENT,
  'sachverständig': IncomeCategory.SELF_EMPLOYMENT,
  ordination: IncomeCategory.SELF_EMPLOYMENT,
  // Nr.3 Gewerbebetrieb
  umsatz: IncomeCategory.BUSINESS,
  provision: IncomeCategory.BUSINESS,
  'erlös': IncomeCategory.BUSINESS,
  tischlerei: IncomeCategory.BUSINESS,
  warenverkauf: IncomeCategory.BUSINESS,
  vermittlung: IncomeCategory.BUSINESS,
  gewerbe: IncomeCategory.BUSINESS,
  einzelhandel: IncomeCategory.BUSINESS,
  gastronomie: IncomeCategory.BUSINESS,
  // Nr.4 Nichtselbständige Arbeit
  gehalt: IncomeCategory.EMPLOYMENT,
  lohn: IncomeCategory.EMPLOYMENT,
  salary: IncomeCategory.EMPLOYMENT,
  pension: IncomeCategory.EMPLOYMENT,
  weihnachtsgeld: IncomeCategory.EMPLOYMENT,
  urlaubsgeld: IncomeCategory.EMPLOYMENT,
  'überstunden': IncomeCategory.EMPLOYMENT,
  abfertigung: IncomeCategory.EMPLOYMENT,
  'prämie': IncomeCategory.EMPLOYMENT,
  // Nr.5 Kapitalvermögen
  dividende: IncomeCategory.CAPITAL_GAINS,
  kursgewinn: IncomeCategory.CAPITAL_GAINS,
  zinsen: IncomeCategory.CAPITAL_GAINS,
  bitcoin: IncomeCategory.CAPITAL_GAINS,
  krypto: IncomeCategory.CAPITAL_GAINS,
  aktien: IncomeCategory.CAPITAL_GAINS,
  'fondsausschüttung': IncomeCategory.CAPITAL_GAINS,
  fonds: IncomeCategory.CAPITAL_GAINS,
  kest: IncomeCategory.CAPITAL_GAINS,
  // Nr.6 Vermietung und Verpachtung
  miete: IncomeCategory.RENTAL,
  mieteinnahme: IncomeCategory.RENTAL,
  rent: IncomeCategory.RENTAL,
  pacht: IncomeCategory.RENTAL,
  airbnb: IncomeCategory.RENTAL,
  booking: IncomeCategory.RENTAL,
  ferienwohnung: IncomeCategory.RENTAL,
  homestay: IncomeCategory.RENTAL,
  vermietung: IncomeCategory.RENTAL,
  // Nr.7 Sonstige Einkünfte
  spekulationsgewinn: IncomeCategory.OTHER_INCOME,
  aufsichtsrat: IncomeCategory.OTHER_INCOME,
  'veräußerungsgewinn': IncomeCategory.OTHER_INCOME,
  immoest: IncomeCategory.OTHER_INCOME,
  'sonstige einkünfte': IncomeCategory.OTHER_INCOME,
};

// ── Expense: merchant names ─────────────────────────────────────────────

const EXPENSE_MERCHANTS: Record<string, ExpenseCategory> = {
  billa: ExpenseCategory.GROCERIES,
  spar: ExpenseCategory.GROCERIES,
  hofer: ExpenseCategory.GROCERIES,
  lidl: ExpenseCategory.GROCERIES,
  merkur: ExpenseCategory.GROCERIES,
  penny: ExpenseCategory.GROCERIES,
  interspar: ExpenseCategory.GROCERIES,
  obi: ExpenseCategory.MAINTENANCE,
  baumax: ExpenseCategory.MAINTENANCE,
  bauhaus: ExpenseCategory.MAINTENANCE,
  hornbach: ExpenseCategory.MAINTENANCE,
  libro: ExpenseCategory.OFFICE_SUPPLIES,
  pagro: ExpenseCategory.OFFICE_SUPPLIES,
  staples: ExpenseCategory.OFFICE_SUPPLIES,
  mediamarkt: ExpenseCategory.EQUIPMENT,
  saturn: ExpenseCategory.EQUIPMENT,
  conrad: ExpenseCategory.EQUIPMENT,
  uniqa: ExpenseCategory.INSURANCE,
  generali: ExpenseCategory.INSURANCE,
  allianz: ExpenseCategory.INSURANCE,
  'wien energie': ExpenseCategory.UTILITIES,
  evn: ExpenseCategory.UTILITIES,
  verbund: ExpenseCategory.UTILITIES,
  'booking.com': ExpenseCategory.TRAVEL,
  expedia: ExpenseCategory.TRAVEL,
  flixbus: ExpenseCategory.TRAVEL,
  ryanair: ExpenseCategory.TRAVEL,
  omv: ExpenseCategory.OTHER,
  shell: ExpenseCategory.OTHER,
};

// ── Expense: product keywords ───────────────────────────────────────────

const EXPENSE_KEYWORDS: Record<string, ExpenseCategory> = {
  reparatur: ExpenseCategory.MAINTENANCE,
  wartung: ExpenseCategory.MAINTENANCE,
  reinig: ExpenseCategory.MAINTENANCE,
  heizung: ExpenseCategory.EQUIPMENT,
  staubsauger: ExpenseCategory.EQUIPMENT,
  waschmaschine: ExpenseCategory.EQUIPMENT,
  drucker: ExpenseCategory.EQUIPMENT,
  laptop: ExpenseCategory.EQUIPMENT,
  computer: ExpenseCategory.EQUIPMENT,
  monitor: ExpenseCategory.EQUIPMENT,
  papier: ExpenseCategory.OFFICE_SUPPLIES,
  toner: ExpenseCategory.OFFICE_SUPPLIES,
  'büro': ExpenseCategory.OFFICE_SUPPLIES,
  porto: ExpenseCategory.OFFICE_SUPPLIES,
  reise: ExpenseCategory.TRAVEL,
  hotel: ExpenseCategory.TRAVEL,
  flug: ExpenseCategory.TRAVEL,
  marketing: ExpenseCategory.MARKETING,
  werbung: ExpenseCategory.MARKETING,
  steuerberater: ExpenseCategory.PROFESSIONAL_SERVICES,
  rechtsanwalt: ExpenseCategory.PROFESSIONAL_SERVICES,
  notar: ExpenseCategory.PROFESSIONAL_SERVICES,
  beratung: ExpenseCategory.PROFESSIONAL_SERVICES,
  versicherung: ExpenseCategory.INSURANCE,
  grundsteuer: ExpenseCategory.PROPERTY_TAX,
  kredit: ExpenseCategory.LOAN_INTEREST,
  darlehen: ExpenseCategory.LOAN_INTEREST,
  strom: ExpenseCategory.UTILITIES,
  kfz: ExpenseCategory.OTHER,
  autowerkstatt: ExpenseCategory.OTHER,
  internet: ExpenseCategory.OTHER,
  telefon: ExpenseCategory.OTHER,
  handy: ExpenseCategory.OTHER,
  'büromiete': ExpenseCategory.OTHER,
  svs: ExpenseCategory.OTHER,
  sozialversicherung: ExpenseCategory.OTHER,
  pendlerpauschale: ExpenseCategory.COMMUTING,
  fahrtkosten: ExpenseCategory.COMMUTING,
  vignette: ExpenseCategory.COMMUTING,
  homeoffice: ExpenseCategory.HOME_OFFICE,
  'home office': ExpenseCategory.HOME_OFFICE,
  schreibtisch: ExpenseCategory.HOME_OFFICE,
};

// Online retailers — skip merchant matching for these
const ONLINE_RETAILERS = new Set(['amazon', 'gls', 'dhl', 'dpd', 'post.at']);

/**
 * Match an income description to a category.
 */
function matchIncome(desc: string): MatchResult | null {
  for (const [kw, cat] of Object.entries(INCOME_KEYWORDS)) {
    if (desc.includes(kw)) {
      return { category: cat, confidence: 0.85 };
    }
  }
  return null;
}

/**
 * Match an expense description to a category.
 */
function matchExpense(desc: string): MatchResult | null {
  const isOnline = [...ONLINE_RETAILERS].some((r) => desc.includes(r));

  if (!isOnline) {
    for (const [merchant, cat] of Object.entries(EXPENSE_MERCHANTS)) {
      if (desc.includes(merchant)) {
        return { category: cat, confidence: 0.9 };
      }
    }
  }

  for (const [kw, cat] of Object.entries(EXPENSE_KEYWORDS)) {
    if (desc.includes(kw)) {
      return { category: cat, confidence: 0.8 };
    }
  }

  return null;
}

/**
 * Auto-suggest a category based on description text.
 * Returns null if no match found — user picks manually.
 */
export function suggestCategory(
  description: string,
  type: 'income' | 'expense'
): MatchResult | null {
  const desc = description.toLowerCase().trim();
  if (desc.length < 2) return null;

  if (type === 'income') {
    return matchIncome(desc);
  }
  return matchExpense(desc);
}
