import { describe, expect, it } from 'vitest';

import bs from '../i18n/locales/bs.json';
import de from '../i18n/locales/de.json';
import en from '../i18n/locales/en.json';
import fr from '../i18n/locales/fr.json';
import hu from '../i18n/locales/hu.json';
import pl from '../i18n/locales/pl.json';
import ru from '../i18n/locales/ru.json';
import tr from '../i18n/locales/tr.json';
import zh from '../i18n/locales/zh.json';

const locales = {
  de,
  en,
  zh,
  fr,
  ru,
  hu,
  pl,
  tr,
  bs,
} as const;

const requiredDocumentFieldKeys = [
  'tax_year',
  'employer_name',
  'employee_name',
  'sv_nummer',
  'kz_210',
  'loan_amount',
  'interest_rate',
  'social_insurance',
  'document_transaction_direction',
  'document_transaction_direction_source',
  'document_transaction_direction_confidence',
  'commercial_document_semantics',
  'is_reversal',
  'extraction_method',
  'utilities_included',
  'llm_fallback',
  'employer',
  'employee',
  'familienbonus',
  'telearbeitspauschale',
] as const;

const requiredSuggestionFieldAliases = [
  'employer_name',
  'employee_name',
  'sv_nummer',
  'kz_210',
  'social_insurance',
  'utilities_included',
  'document_transaction_direction',
  'commercial_document_semantics',
  'is_reversal',
] as const;

const requiredPendingLoanKeys = [
  'linkedDocumentId',
  'manualUploadHint',
  'manualUploadTitle',
  'missingHint',
  'missingTitle',
  'openLinkedLoanFlow',
  'openSourceDocument',
  'pendingHint',
  'pendingMissingFields',
  'pendingNeedsInput',
  'pendingReview',
  'pendingTitle',
  'sourceManagedMessage',
  'sourceManagedPropertyLoanMessage',
  'sourceManagedTitle',
  'uploadSupportingDocument',
] as const;

const requiredLiabilityFormAndDetailKeys = [
  'liabilities.form.editTitle',
  'liabilities.form.createTitle',
  'liabilities.fields.liabilityType',
  'liabilities.fields.reportCategory',
  'liabilities.fields.displayName',
  'liabilities.fields.lenderName',
  'liabilities.fields.currency',
  'liabilities.fields.principalAmount',
  'liabilities.fields.outstandingBalance',
  'liabilities.fields.interestRate',
  'liabilities.fields.monthlyPayment',
  'liabilities.fields.startDate',
  'liabilities.fields.endDate',
  'liabilities.fields.linkedProperty',
  'liabilities.fields.taxRelevant',
  'liabilities.fields.taxRelevanceReason',
  'liabilities.fields.createRecurringPlan',
  'liabilities.fields.createRecurringPlanHint',
  'liabilities.fields.recurringDay',
  'liabilities.fields.notes',
  'liabilities.detail.title',
  'liabilities.detail.empty',
  'liabilities.detail.noTransactions',
  'liabilities.detail.noRecurring',
  'liabilities.detail.relatedTransactions',
  'liabilities.detail.relatedRecurring',
  'liabilities.progress.title',
  'liabilities.progress.repaid',
  'liabilities.progress.ofTotal',
  'liabilities.progress.remaining',
  'liabilities.schedule.title',
  'liabilities.schedule.noData',
  'liabilities.schedule.month',
  'liabilities.schedule.payment',
  'liabilities.schedule.principal',
  'liabilities.schedule.interest',
  'liabilities.schedule.remaining',
  'liabilities.schedule.showLess',
  'liabilities.schedule.showAll',
  'liabilities.schedule.totalPayments',
  'liabilities.schedule.totalInterest',
  'liabilities.schedule.payoffDate',
  'liabilities.interestTrend.title',
  'liabilities.interestTrend.projected',
  'liabilities.interestTrend.monthly',
  'documents.linkedEntity.transaction',
  'documents.linkedEntity.recurring',
  'documents.linkedEntity.property',
  'documents.linkedEntity.asset',
  'documents.linkedEntity.open',
  'common.today',
  'common.save',
  'common.saving',
] as const;

const requiredTaxImportKeys = [
  'documents.preview',
  'documents.previewNotAvailable',
  'documents.taxData.savedTitle',
  'documents.taxData.savedDescription',
  'documents.taxData.recordId',
  'documents.taxData.dataType',
  'documents.bescheid.title',
  'documents.bescheid.description',
  'documents.bescheid.parsePreview',
  'documents.bescheid.confidence',
  'documents.e1.title',
  'documents.e1.description',
  'documents.e1.parsePreview',
  'documents.e1.confidence',
] as const;

const requiredBankWorkbenchKeys = [
  'documents.bankWorkbench.title',
  'documents.bankWorkbench.initializing',
  'documents.bankWorkbench.loadingLines',
  'documents.bankWorkbench.loadFailed',
  'documents.bankWorkbench.actionFailed',
  'documents.bankWorkbench.summaryTitle',
  'documents.bankWorkbench.importedAt',
  'documents.bankWorkbench.totalCount',
  'documents.bankWorkbench.autoProcessed',
  'documents.bankWorkbench.pendingReview',
  'documents.bankWorkbench.ignoredCount',
  'documents.bankWorkbench.confidence',
  'documents.bankWorkbench.linkedTransaction',
  'documents.bankWorkbench.noCounterparty',
  'documents.bankWorkbench.noPurpose',
  'documents.bankWorkbench.status.autoCreated',
  'documents.bankWorkbench.status.matchedExisting',
  'documents.bankWorkbench.status.ignoredDuplicate',
  'documents.bankWorkbench.status.pendingReview',
  'documents.bankWorkbench.actions.create',
  'documents.bankWorkbench.actions.match',
  'documents.bankWorkbench.actions.ignore',
  'documents.bankWorkbench.emptyPending',
  'documents.bankWorkbench.emptyResolved',
  'documents.bankWorkbench.emptyIgnored',
  'documents.bankWorkbench.groups.pending.title',
  'documents.bankWorkbench.groups.pending.description',
  'documents.bankWorkbench.groups.resolved.title',
  'documents.bankWorkbench.groups.resolved.description',
  'documents.bankWorkbench.groups.ignored.title',
  'documents.bankWorkbench.groups.ignored.description',
  'documents.suggestion.importBankStatement',
  'documents.suggestion.openBankWorkbench',
  'documents.suggestion.bankWorkbenchHint',
] as const;

const getNestedValue = (source: unknown, path: string): string | undefined =>
  path.split('.').reduce<unknown>((current, segment) => {
    if (current && typeof current === 'object' && segment in (current as Record<string, unknown>)) {
      return (current as Record<string, unknown>)[segment];
    }
    return undefined;
  }, source) as string | undefined;

describe('locale coverage for liabilities and document field labels', () => {
  it('keeps the supported locale set at nine languages', () => {
    expect(Object.keys(locales)).toHaveLength(9);
  });

  it('includes translated document field labels for every supported locale', () => {
    for (const [language, locale] of Object.entries(locales)) {
      const labels = locale.documents.review.taxFieldLabels as Record<string, string>;

      for (const key of requiredDocumentFieldKeys) {
        expect(labels[key], `${language}:${key}`).toBeTruthy();
        expect(labels[key], `${language}:${key}`).not.toContain('?');
      }
    }
  });

  it('includes translated suggestion-field aliases for every supported locale', () => {
    for (const [language, locale] of Object.entries(locales)) {
      const labels = locale.documents.suggestion.fields as Record<string, string>;

      for (const key of requiredSuggestionFieldAliases) {
        expect(labels[key], `${language}:${key}`).toBeTruthy();
        expect(labels[key], `${language}:${key}`).not.toContain('?');
      }
    }
  });

  it('includes translated pending loan document strings for every supported locale', () => {
    for (const [language, locale] of Object.entries(locales)) {
      const labels = locale.liabilities.documents as Record<string, string>;

      for (const key of requiredPendingLoanKeys) {
        expect(labels[key], `${language}:${key}`).toBeTruthy();
        expect(labels[key], `${language}:${key}`).not.toContain('?');
      }
    }
  });

  it('includes translated tax-import strings for every supported locale', () => {
    for (const [language, locale] of Object.entries(locales)) {
      for (const key of requiredTaxImportKeys) {
        const value = getNestedValue(locale, key);
        expect(value, `${language}:${key}`).toBeTruthy();
        expect(value, `${language}:${key}`).not.toContain('?');
      }
    }
  });

  it('includes translated bank statement workbench strings for every supported locale', () => {
    for (const [language, locale] of Object.entries(locales)) {
      for (const key of requiredBankWorkbenchKeys) {
        const value = getNestedValue(locale, key);
        expect(value, `${language}:${key}`).toBeTruthy();
        expect(value, `${language}:${key}`).not.toContain('?');
      }
    }
  });

  it('includes liability form/detail and linked-entity strings for every supported locale', () => {
    for (const [language, locale] of Object.entries(locales)) {
      for (const key of requiredLiabilityFormAndDetailKeys) {
        const value = getNestedValue(locale, key);
        expect(value, `${language}:${key}`).toBeTruthy();
        expect(value, `${language}:${key}`).not.toContain('?');
      }
    }
  });
});
