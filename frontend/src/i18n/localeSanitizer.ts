import type { SupportedLanguage } from '../utils/locale';

type LocalePrimitive = string | number | boolean | null;
interface LocaleObject {
  [key: string]: LocaleNode;
}
// eslint-disable-next-line @typescript-eslint/no-empty-object-type
interface LocaleArray extends Array<LocaleNode> {}
// Use interface-based recursion to avoid circular type alias error
type LocaleNode = LocalePrimitive | LocaleObject | LocaleArray;

const CP1252_BYTE_BY_CODE_POINT = new Map<number, number>([
  [0x20ac, 0x80],
  [0x201a, 0x82],
  [0x0192, 0x83],
  [0x201e, 0x84],
  [0x2026, 0x85],
  [0x2020, 0x86],
  [0x2021, 0x87],
  [0x02c6, 0x88],
  [0x2030, 0x89],
  [0x0160, 0x8a],
  [0x2039, 0x8b],
  [0x0152, 0x8c],
  [0x017d, 0x8e],
  [0x2018, 0x91],
  [0x2019, 0x92],
  [0x201c, 0x93],
  [0x201d, 0x94],
  [0x2022, 0x95],
  [0x2013, 0x96],
  [0x2014, 0x97],
  [0x02dc, 0x98],
  [0x2122, 0x99],
  [0x0161, 0x9a],
  [0x203a, 0x9b],
  [0x0153, 0x9c],
  [0x017e, 0x9e],
  [0x0178, 0x9f],
]);

const CP1252_CONTROL_REPLACEMENTS = new Map<number, string>([
  [0x80, '\u20ac'],
  [0x82, '\u201a'],
  [0x83, '\u0192'],
  [0x84, '\u201e'],
  [0x85, '\u2026'],
  [0x86, '\u2020'],
  [0x87, '\u2021'],
  [0x88, '\u02c6'],
  [0x89, '\u2030'],
  [0x8a, '\u0160'],
  [0x8b, '\u2039'],
  [0x8c, '\u0152'],
  [0x8e, '\u017d'],
  [0x91, '\u2018'],
  [0x92, '\u2019'],
  [0x93, '\u201c'],
  [0x94, '\u201d'],
  [0x95, '\u2022'],
  [0x96, '\u2013'],
  [0x97, '\u2014'],
  [0x98, '\u02dc'],
  [0x99, '\u2122'],
  [0x9a, '\u0161'],
  [0x9b, '\u203a'],
  [0x9c, '\u0153'],
  [0x9e, '\u017e'],
  [0x9f, '\u0178'],
]);

const MOJIBAKE_HINTS = [
  '\u00c3',
  '\u00c2',
  '\u00e2',
  '\u00d0',
  '\u00d1',
  '\u00c5',
  '\u00c4',
  '\u00e6',
  '\u00e7',
  '\u00e9\u203a',
  '\u00ef\u00bc',
  '\u00e5',
];

const buildExportAndSearchHotfix = (
  exportCsv: string,
  exportPdf: string,
  searchPlaceholder: string,
  searchDeductPlaceholder: string
): LocaleObject => ({
  actions: {
    exportCsv,
    exportPdf,
  },
  classificationRules: {
    searchPlaceholder,
    searchDeductPlaceholder,
  },
  dashboard: {
    quickStart: {
      exportCsv,
      exportPdf,
    },
  },
  healthCheck: {
    gettingStarted: {
      exportCsv,
      exportPdf,
    },
  },
  quickActions: {
    exportCsv,
    exportPdf,
  },
  transactions: {
    exportCsv,
    exportPdf,
  },
});

const buildBankWorkbenchHotfix = (config: {
  title: string;
  modeImport: string;
  modeExtracted: string;
  initializing: string;
  loadingLines: string;
  loadFailed: string;
  actionFailed: string;
  summaryTitle: string;
  fallbackSummaryTitle: string;
  localFallbackNotice: string;
  fallbackTransactionsTitle: string;
  fallbackTransactionsDescription: string;
  noExtractedTransactions: string;
  importedAt: string;
  accountHolder: string;
  taxYear: string;
  openingBalance: string;
  closingBalance: string;
  totalCount: string;
  creditCount: string;
  debitCount: string;
  autoProcessed: string;
  pendingReview: string;
  ignoredCount: string;
  confidence: string;
  linkedTransaction: string;
  noLinkedTransaction: string;
  directionLabel: string;
  directionCredit: string;
  directionDebit: string;
  directionUnknown: string;
  noCounterparty: string;
  noPurpose: string;
  statusAutoCreated: string;
  statusMatchedExisting: string;
  statusIgnoredDuplicate: string;
  statusPendingReview: string;
  suggestedCreate: string;
  suggestedMatch: string;
  suggestedIgnore: string;
  actionCreate: string;
  actionMatch: string;
  actionIgnore: string;
  actionRestore: string;
  actionUndoCreate: string;
  actionUnmatch: string;
  actionViewUnavailable: string;
  fallbackCreatedOne: string;
  fallbackCreatedMany: string;
  fallbackAlreadyImportedOne: string;
  fallbackAlreadyImportedMany: string;
  fallbackNoTransactionsCreated: string;
  emptyPending: string;
  emptyResolved: string;
  emptyIgnored: string;
  pendingTitle: string;
  pendingDescription: string;
  resolvedTitle: string;
  resolvedDescription: string;
  ignoredTitle: string;
  ignoredDescription: string;
  importBankStatement: string;
  openBankWorkbench: string;
  bankWorkbenchHint: string;
}): LocaleObject => ({
  documents: {
    suggestion: {
      importBankStatement: config.importBankStatement,
      openBankWorkbench: config.openBankWorkbench,
      bankWorkbenchHint: config.bankWorkbenchHint,
    },
    bankWorkbench: {
      title: config.title,
      mode: {
        import: config.modeImport,
        extracted: config.modeExtracted,
      },
      initializing: config.initializing,
      loadingLines: config.loadingLines,
      loadFailed: config.loadFailed,
      actionFailed: config.actionFailed,
      summaryTitle: config.summaryTitle,
      fallbackSummaryTitle: config.fallbackSummaryTitle,
      localFallbackNotice: config.localFallbackNotice,
      fallbackTransactionsTitle: config.fallbackTransactionsTitle,
      fallbackTransactionsDescription: config.fallbackTransactionsDescription,
      noExtractedTransactions: config.noExtractedTransactions,
      importedAt: config.importedAt,
      accountHolder: config.accountHolder,
      taxYear: config.taxYear,
      openingBalance: config.openingBalance,
      closingBalance: config.closingBalance,
      totalCount: config.totalCount,
      creditCount: config.creditCount,
      debitCount: config.debitCount,
      autoProcessed: config.autoProcessed,
      pendingReview: config.pendingReview,
      ignoredCount: config.ignoredCount,
      confidence: config.confidence,
      linkedTransaction: config.linkedTransaction,
      noLinkedTransaction: config.noLinkedTransaction,
      direction: {
        label: config.directionLabel,
        credit: config.directionCredit,
        debit: config.directionDebit,
        unknown: config.directionUnknown,
      },
      noCounterparty: config.noCounterparty,
      noPurpose: config.noPurpose,
      status: {
        autoCreated: config.statusAutoCreated,
        matchedExisting: config.statusMatchedExisting,
        ignoredDuplicate: config.statusIgnoredDuplicate,
        pendingReview: config.statusPendingReview,
      },
      suggested: {
        create: config.suggestedCreate,
        match: config.suggestedMatch,
        ignore: config.suggestedIgnore,
      },
      actions: {
        create: config.actionCreate,
        match: config.actionMatch,
        ignore: config.actionIgnore,
        restore: config.actionRestore,
        undoCreate: config.actionUndoCreate,
        unmatch: config.actionUnmatch,
        viewUnavailable: config.actionViewUnavailable,
      },
      fallback: {
        createdOne: config.fallbackCreatedOne,
        createdMany: config.fallbackCreatedMany,
        alreadyImportedOne: config.fallbackAlreadyImportedOne,
        alreadyImportedMany: config.fallbackAlreadyImportedMany,
        noTransactionsCreated: config.fallbackNoTransactionsCreated,
      },
      emptyPending: config.emptyPending,
      emptyResolved: config.emptyResolved,
      emptyIgnored: config.emptyIgnored,
      groups: {
        pending: {
          title: config.pendingTitle,
          description: config.pendingDescription,
        },
        resolved: {
          title: config.resolvedTitle,
          description: config.resolvedDescription,
        },
        ignored: {
          title: config.ignoredTitle,
          description: config.ignoredDescription,
        },
      },
    },
  },
});

const buildClassificationMemoryHotfix = (config: {
  pageTitle: string;
  pageSubtitle: string;
  title: string;
  subtitle: string;
  empty: string;
  categorySectionDescription: string;
  automationSectionTitle: string;
  automationSectionDescription: string;
  searchAutomationPlaceholder: string;
  automationEmpty: string;
  selectAllAutomation: string;
  automationActionAutoCreate: string;
  reasonAutomation: string;
  reasonAutomationFrozen: string;
  reasonAutomationConflict: string;
  deductibilitySectionDescription: string;
  action: string;
}): LocaleObject => ({
  classificationRules: {
    pageTitle: config.pageTitle,
    pageSubtitle: config.pageSubtitle,
    title: config.title,
    subtitle: config.subtitle,
    empty: config.empty,
    categorySectionDescription: config.categorySectionDescription,
    automationSectionTitle: config.automationSectionTitle,
    automationSectionDescription: config.automationSectionDescription,
    searchAutomationPlaceholder: config.searchAutomationPlaceholder,
    automationEmpty: config.automationEmpty,
    selectAllAutomation: config.selectAllAutomation,
    automationActionAutoCreate: config.automationActionAutoCreate,
    reasonAutomation: config.reasonAutomation,
    reasonAutomationFrozen: config.reasonAutomationFrozen,
    reasonAutomationConflict: config.reasonAutomationConflict,
    deductibilitySectionDescription: config.deductibilitySectionDescription,
    action: config.action,
  },
});

const buildBankWorkbenchResolutionHotfix = (config: {
  statusRevokedCreate: string;
  statusRevokedMatch: string;
  reasonOrphanRepaired: string;
}): LocaleObject => ({
  documents: {
    bankWorkbench: {
      status: {
        revokedCreate: config.statusRevokedCreate,
        revokedMatch: config.statusRevokedMatch,
      },
      reason: {
        orphanRepaired: config.reasonOrphanRepaired,
      },
    },
  },
});

const buildProactiveReminderHotfix = (healthSummaryReminder: string): LocaleObject => ({
  ai: {
    proactive: {
      healthSummaryReminder,
    },
  },
});

const buildDocumentReviewHotfix = (config: {
  confirmed: string;
  confirmedSuccess: string;
  saveChanges: string;
  reviewAction: string;
  reviewActionHint: string;
  confirmReview: string;
  receiptEditing: string;
  receiptExpandDetails: string;
  receiptHideDetails: string;
  receiptLinkedTransactionShort: string;
}): LocaleObject => ({
  documents: {
    reviewAction: config.reviewAction,
    reviewActionHint: config.reviewActionHint,
    confirmReview: config.confirmReview,
    receiptReview: {
      editing: config.receiptEditing,
      expandDetails: config.receiptExpandDetails,
      hideDetails: config.receiptHideDetails,
      linkedTransactionShort: config.receiptLinkedTransactionShort,
    },
    review: {
      confirmed: config.confirmed,
      confirmedSuccess: config.confirmedSuccess,
      saveChanges: config.saveChanges,
    },
  },
});

const buildDocumentFiltersHotfix = (apply: string): LocaleObject => ({
  documents: {
    filters: {
      apply,
    },
  },
});

const buildReviewWorkflowHotfix = (config: {
  oneClickConfirm: string;
  bulkConfirmSuccess: string;
  pendingReview: string;
  pendingReviewOnly: string;
}): LocaleObject => ({
  common: {
    oneClickConfirm: config.oneClickConfirm,
    bulkConfirmSuccess: config.bulkConfirmSuccess,
  },
  documents: {
    needsReview: config.pendingReview,
    filters: {
      needsReview: config.pendingReview,
    },
    taxReview: {
      needsReview: config.pendingReview,
    },
  },
  transactions: {
    needsReview: config.pendingReview,
    filters: {
      needsReviewOnly: config.pendingReviewOnly,
    },
  },
});

const buildTransactionSemanticsHotfix = (config: {
  systemGenerated: string;
  bankReconcileHint: string;
  ignored: string;
  suggestedIgnore: string;
  ignore: string;
}): LocaleObject => ({
  transactions: {
    systemGenerated: config.systemGenerated,
    bankReconcileHint: config.bankReconcileHint,
  },
  documents: {
    bankWorkbench: {
      status: {
        ignoredDuplicate: config.ignored,
      },
      suggested: {
        ignore: config.suggestedIgnore,
      },
      actions: {
        ignore: config.ignore,
      },
    },
  },
});

const buildTaxPackageHotfix = (config: {
  exportPackage: string;
  exportPackageLoading: string;
  exportPackageFailed: string;
  exportPackagePanelTitle: string;
  exportPackagePanelDescription: string;
  includeFoundationMaterials: string;
  includeFoundationMaterialsHint: string;
  packageScopeTransactionsCsv: string;
  packageScopeTransactionsPdf: string;
  packageScopeSummaryPdf: string;
  packageScopeDocuments: string;
  packageScopeFoundationOptional: string;
  preparePackage: string;
  packageStatusPending: string;
  packageStatusProcessing: string;
  packageStatusReady: string;
  packageDownloadSingle: string;
  packageDownloadPart: string;
  packageFailureTitle: string;
  packageFailureDocumentCount: string;
  packageFailureEstimatedSize: string;
  packageFailureLargestFamily: string;
  exportPackagePreviewLoading: string;
  exportPackagePreviewFailed: string;
  exportPackageWarningTitle: string;
  exportPackageWarningDescription: string;
  exportPackageWarningPendingTransactions: string;
  exportPackageWarningPendingDocuments: string;
  exportPackageWarningFallbackYears: string;
  exportPackageWarningSkippedFiles: string;
  reviewTransactionsBeforeExport: string;
  reviewDocumentsBeforeExport: string;
  reviewDocumentsByYear?: string;
  continueExportPackage: string;
  reviewWarningsFirst: string;
}): LocaleObject => ({
  reports: {
    taxForm: {
      exportPackage: config.exportPackage,
      exportPackageLoading: config.exportPackageLoading,
      exportPackageFailed: config.exportPackageFailed,
      exportPackagePanelTitle: config.exportPackagePanelTitle,
      exportPackagePanelDescription: config.exportPackagePanelDescription,
      includeFoundationMaterials: config.includeFoundationMaterials,
      includeFoundationMaterialsHint: config.includeFoundationMaterialsHint,
      packageScopeTransactionsCsv: config.packageScopeTransactionsCsv,
      packageScopeTransactionsPdf: config.packageScopeTransactionsPdf,
      packageScopeSummaryPdf: config.packageScopeSummaryPdf,
      packageScopeDocuments: config.packageScopeDocuments,
      packageScopeFoundationOptional: config.packageScopeFoundationOptional,
      preparePackage: config.preparePackage,
      packageStatusPending: config.packageStatusPending,
      packageStatusProcessing: config.packageStatusProcessing,
      packageStatusReady: config.packageStatusReady,
      packageDownloadSingle: config.packageDownloadSingle,
      packageDownloadPart: config.packageDownloadPart,
      packageFailureTitle: config.packageFailureTitle,
      packageFailureDocumentCount: config.packageFailureDocumentCount,
      packageFailureEstimatedSize: config.packageFailureEstimatedSize,
      packageFailureLargestFamily: config.packageFailureLargestFamily,
      exportPackagePreviewLoading: config.exportPackagePreviewLoading,
      exportPackagePreviewFailed: config.exportPackagePreviewFailed,
      exportPackageWarningTitle: config.exportPackageWarningTitle,
      exportPackageWarningDescription: config.exportPackageWarningDescription,
      exportPackageWarningPendingTransactions: config.exportPackageWarningPendingTransactions,
      exportPackageWarningPendingDocuments: config.exportPackageWarningPendingDocuments,
      exportPackageWarningFallbackYears: config.exportPackageWarningFallbackYears,
      exportPackageWarningSkippedFiles: config.exportPackageWarningSkippedFiles,
      reviewTransactionsBeforeExport: config.reviewTransactionsBeforeExport,
      reviewDocumentsBeforeExport: config.reviewDocumentsBeforeExport,
      reviewDocumentsByYear: config.reviewDocumentsByYear || config.reviewDocumentsBeforeExport,
      continueExportPackage: config.continueExportPackage,
      reviewWarningsFirst: config.reviewWarningsFirst,
    },
  },
});

const buildDocumentExportZipHotfix = (config: {
  exportZipYearHint: string;
  exportZipNoYears: string;
  fileYearLabel: string;
  filesLabel: string;
  estimatedSizeLabel: string;
  exportZipLargeHint: string;
  exportZipDirectDownloadHint: string;
}): LocaleObject => ({
  documents: {
    exportZipYearHint: config.exportZipYearHint,
    exportZipNoYears: config.exportZipNoYears,
    fileYearLabel: config.fileYearLabel,
    filesLabel: config.filesLabel,
    estimatedSizeLabel: config.estimatedSizeLabel,
    exportZipLargeHint: config.exportZipLargeHint,
    exportZipDirectDownloadHint: config.exportZipDirectDownloadHint,
  },
});

const buildTaxFieldLabelHotfix = (config: {
  issuer: string;
  recipient: string;
  documentDate: string;
  documentYear: string;
  yearBasis: string;
  yearConfidence: string;
  bescheidDate?: string;
  referenceNumber?: string;
  dueDate?: string;
}): LocaleObject => ({
  documents: {
    review: {
      taxFieldLabels: {
        issuer: config.issuer,
        recipient: config.recipient,
        document_date: config.documentDate,
        document_year: config.documentYear,
        year_basis: config.yearBasis,
        year_confidence: config.yearConfidence,
        ...(config.bescheidDate ? { bescheid_datum: config.bescheidDate } : {}),
        ...(config.referenceNumber ? { aktenzahl: config.referenceNumber } : {}),
        ...(config.dueDate ? { faellig_am: config.dueDate } : {}),
      },
    },
  },
});

const mergeLocaleHotfixes = (...parts: LocaleObject[]): LocaleObject => {
  const merged: LocaleObject = {};

  parts.forEach((part) => {
    Object.entries(part).forEach(([key, value]) => {
      const existing = merged[key];

      if (
        existing &&
        value &&
        typeof existing === 'object' &&
        typeof value === 'object' &&
        !Array.isArray(existing) &&
        !Array.isArray(value)
      ) {
        merged[key] = mergeLocaleHotfixes(existing as LocaleObject, value as LocaleObject);
        return;
      }

      merged[key] = value;
    });
  });

  return merged;
};

const LOCALE_HOTFIXES: Partial<Record<SupportedLanguage, LocaleObject>> = {
  de: {
    ...mergeLocaleHotfixes(
      buildExportAndSearchHotfix(
        'CSV exportieren',
        'PDF exportieren',
        'Nach Beschreibung oder Kategorie suchen...',
        'Nach Beschreibung suchen...'
      ),
      buildReviewWorkflowHotfix({
        oneClickConfirm: 'Alles bestaetigen',
        bulkConfirmSuccess: '{{count}} Eintraege bestaetigt.',
        pendingReview: 'Zur Pruefung',
        pendingReviewOnly: 'Nur zur Pruefung',
      }),
      buildTransactionSemanticsHotfix({
        systemGenerated: 'Systemgeneriert',
        bankReconcileHint: 'Bitte laden Sie Bankauszuege unter Dokumente hoch, um abzugleichen.',
        ignored: 'Ignoriert',
        suggestedIgnore: 'Vorgeschlagenes Ignorieren',
        ignore: 'Ignorieren',
      }),
      buildBankWorkbenchHotfix({
      title: 'Kontoauszugs-Arbeitsbereich',
      modeImport: 'Import-Arbeitsbereich',
      modeExtracted: 'Extrahierte Zeilen',
      initializing: 'Kontoauszugs-Arbeitsbereich wird vorbereitet...',
      loadingLines: 'Kontoauszugszeilen werden geladen...',
      loadFailed: 'Der Kontoauszugs-Arbeitsbereich konnte nicht geladen werden.',
      actionFailed: 'Die Aktion fuer den Kontoauszug konnte nicht abgeschlossen werden.',
      summaryTitle: 'Importzusammenfassung',
      fallbackSummaryTitle: 'Extrahierte Auszugsdetails',
      localFallbackNotice: 'Dieser Kontoauszug wird als extrahierte Buchungszeilen angezeigt, weil der Import-Arbeitsbereich in dieser Umgebung nicht verfuegbar ist.',
      fallbackTransactionsTitle: 'Extrahierte Buchungszeilen',
      fallbackTransactionsDescription: 'Diese Zeilen wurden direkt aus dem Dokument extrahiert. Sie koennen einzelne Zeilen bestaetigen und als Transaktionen importieren.',
      noExtractedTransactions: 'Aus diesem Kontoauszug wurden noch keine Buchungszeilen extrahiert.',
      importedAt: 'Importiert am',
      accountHolder: 'Kontoinhaber',
      taxYear: 'Steuerjahr',
      openingBalance: 'Anfangssaldo',
      closingBalance: 'Endsaldo',
      totalCount: 'Gesamtzeilen',
      creditCount: 'Gutschriften',
      debitCount: 'Belastungen',
      autoProcessed: 'Automatisch verarbeitet',
      pendingReview: 'Zur Bestaetigung',
      ignoredCount: 'Ignoriert',
      confidence: 'Konfidenz',
      linkedTransaction: 'Transaktion',
      noLinkedTransaction: 'Keine verknuepfte Transaktion',
      directionLabel: 'Richtung',
      directionCredit: 'Gutschrift',
      directionDebit: 'Belastung',
      directionUnknown: 'Erkannt',
      noCounterparty: 'Unbekannte Gegenpartei',
      noPurpose: 'Kein Verwendungszweck verfuegbar.',
      statusAutoCreated: 'Automatisch erstellt',
      statusMatchedExisting: 'Bestehende Transaktion zugeordnet',
      statusIgnoredDuplicate: 'Ignoriert',
      statusPendingReview: 'Zur Bestaetigung',
      suggestedCreate: 'Vorgeschlagene Neuanlage',
      suggestedMatch: 'Vorgeschlagene Zuordnung',
      suggestedIgnore: 'Vorgeschlagenes Ignorieren',
      actionCreate: 'Transaktion erstellen',
      actionMatch: 'Bestehende zuordnen',
      actionIgnore: 'Ignorieren',
      actionRestore: 'Erneut pruefen',
      actionUndoCreate: 'Erstellung rueckgaengig machen',
      actionUnmatch: 'Zuordnung aufheben',
      actionViewUnavailable: 'Keine Transaktion zur Vorschau',
      fallbackCreatedOne: '1 Transaktion erstellt.',
      fallbackCreatedMany: '{{count}} Transaktionen erstellt.',
      fallbackAlreadyImportedOne: 'Diese Auszugszeile wurde bereits importiert.',
      fallbackAlreadyImportedMany: 'Diese Auszugszeilen wurden bereits importiert.',
      fallbackNoTransactionsCreated: 'Es wurden keine neuen Transaktionen erstellt.',
      emptyPending: 'Derzeit muessen keine Kontoauszugszeilen bestaetigt werden.',
      emptyResolved: 'Es gibt noch keine automatisch verarbeiteten Kontoauszugszeilen.',
      emptyIgnored: 'Es gibt noch keine ignorierten Duplikate.',
      pendingTitle: 'Zur Bestaetigung',
      pendingDescription: 'Positionen mit niedriger Konfidenz bleiben hier, bis Sie die passende Verarbeitung bestaetigen.',
      resolvedTitle: 'Automatisch verarbeitet',
      resolvedDescription: 'Diese Zeilen wurden automatisch erstellt oder einer bestehenden Transaktion zugeordnet.',
      ignoredTitle: 'Ignoriert',
      ignoredDescription: 'Diese Zeilen wurden ignoriert und erzeugen keine neuen Transaktionen.',
      importBankStatement: 'Kontoauszug importieren',
      openBankWorkbench: 'Kontoauszugs-Arbeitsbereich oeffnen',
      bankWorkbenchHint: 'Oeffnen Sie den Kontoauszugs-Arbeitsbereich, um Eintraege mit niedriger Konfidenz zu pruefen, bestehende Transaktionen zuzuordnen und neue Transaktionen zu bestaetigen.',
    }),
      buildBankWorkbenchResolutionHotfix({
        statusRevokedCreate: 'Erstellung rueckgaengig',
        statusRevokedMatch: 'Zuordnung aufgehoben',
        reasonOrphanRepaired: 'Die verknuepfte Transaktion ist nicht mehr verfuegbar. Bitte pruefen Sie diese Zeile erneut.',
      }),
      buildDocumentReviewHotfix({
        confirmed: 'Bestaetigt',
        confirmedSuccess: 'Dokument bestaetigt',
        saveChanges: 'Aenderungen speichern',
        reviewAction: 'Weiter pruefen',
        reviewActionHint: 'Klicken, um die Bestaetigung abzuschliessen',
        confirmReview: 'Pruefung abschliessen?',
        receiptEditing: 'Bearbeitung',
        receiptExpandDetails: 'Details einblenden',
        receiptHideDetails: 'Details ausblenden',
        receiptLinkedTransactionShort: 'Verknuepfte Transaktion',
      })
    ),
    ...buildProactiveReminderHotfix(
      'Sie haben {{count}} Punkte in Ihrem Steuer-Check zu pruefen. Ihr aktueller Wert liegt bei {{score}}.'
    ),
    tour: {
      taxTools: {
        employer: {
          title: 'Arbeitgeberdaten',
          message:
            'Erfassen Sie Daten aus Ihrem Lohnzettel (L16), damit Eink\u00fcnfte aus nichtselbst\u00e4ndiger Arbeit in die Steuerberechnung einfliessen.',
        },
      },
    },
  },
  en: {
    ...mergeLocaleHotfixes(
      buildReviewWorkflowHotfix({
        oneClickConfirm: 'One-click confirm',
        bulkConfirmSuccess: 'Confirmed {{count}} items.',
        pendingReview: 'Pending review',
        pendingReviewOnly: 'Only pending review',
      }),
      buildTransactionSemanticsHotfix({
        systemGenerated: 'System-generated',
        bankReconcileHint: 'Upload bank statements in Documents to reconcile.',
        ignored: 'Ignored',
        suggestedIgnore: 'Suggested ignore',
        ignore: 'Ignore',
      }),
      buildBankWorkbenchHotfix({
      title: 'Bank statement workbench',
      modeImport: 'Import workbench',
      modeExtracted: 'Extracted rows',
      initializing: 'Preparing the bank statement workbench...',
      loadingLines: 'Loading statement lines...',
      loadFailed: 'Failed to load the bank statement workbench.',
      actionFailed: 'The bank statement action could not be completed.',
      summaryTitle: 'Import summary',
      fallbackSummaryTitle: 'Extracted statement details',
      localFallbackNotice: 'This bank statement is shown as extracted transaction lines because the bank import workbench is unavailable in this environment.',
      fallbackTransactionsTitle: 'Extracted transaction lines',
      fallbackTransactionsDescription: 'These lines were extracted directly from the document. You can confirm them one by one and import them as transactions.',
      noExtractedTransactions: 'No transaction lines were extracted from this bank statement yet.',
      importedAt: 'Imported',
      accountHolder: 'Account holder',
      taxYear: 'Tax year',
      openingBalance: 'Opening balance',
      closingBalance: 'Closing balance',
      totalCount: 'Total lines',
      creditCount: 'Credits',
      debitCount: 'Debits',
      autoProcessed: 'Auto processed',
      pendingReview: 'Pending review',
      ignoredCount: 'Ignored',
      confidence: 'Confidence',
      linkedTransaction: 'Transaction',
      noLinkedTransaction: 'No linked transaction',
      directionLabel: 'Direction',
      directionCredit: 'Credit',
      directionDebit: 'Debit',
      directionUnknown: 'Detected',
      noCounterparty: 'Unknown counterparty',
      noPurpose: 'No payment purpose available.',
      statusAutoCreated: 'Auto-created',
      statusMatchedExisting: 'Matched existing',
      statusIgnoredDuplicate: 'Ignored',
      statusPendingReview: 'Pending review',
      suggestedCreate: 'Suggested create',
      suggestedMatch: 'Suggested match',
      suggestedIgnore: 'Suggested ignore',
      actionCreate: 'Create transaction',
      actionMatch: 'Match existing',
      actionIgnore: 'Ignore',
      actionRestore: 'Review again',
      actionUndoCreate: 'Undo create',
      actionUnmatch: 'Unmatch',
      actionViewUnavailable: 'No transaction to preview',
      fallbackCreatedOne: 'Created 1 transaction.',
      fallbackCreatedMany: 'Created {{count}} transactions.',
      fallbackAlreadyImportedOne: 'This statement line was already imported.',
      fallbackAlreadyImportedMany: 'These statement lines were already imported.',
      fallbackNoTransactionsCreated: 'No new transactions were created.',
      emptyPending: 'No bank statement lines need confirmation right now.',
      emptyResolved: 'No automatically processed statement lines yet.',
      emptyIgnored: 'No ignored duplicate lines yet.',
      pendingTitle: 'Pending review',
      pendingDescription: 'Low-confidence items stay here until you confirm how they should be handled.',
      resolvedTitle: 'Automatically processed',
      resolvedDescription: 'These lines were auto-created or matched to an existing transaction.',
      ignoredTitle: 'Ignored',
      ignoredDescription: 'These lines were ignored and will not create transactions.',
      importBankStatement: 'Import bank statement',
      openBankWorkbench: 'Open bank statement workbench',
      bankWorkbenchHint: 'Open the bank statement workbench to review low-confidence items, match existing transactions, and confirm new transactions.',
    }),
      buildBankWorkbenchResolutionHotfix({
        statusRevokedCreate: 'Create undone',
        statusRevokedMatch: 'Match removed',
        reasonOrphanRepaired: 'The linked transaction is no longer available. Review this line again.',
      }),
      buildDocumentReviewHotfix({
        confirmed: 'Confirmed',
        confirmedSuccess: 'Document confirmed',
        saveChanges: 'Save changes',
        reviewAction: 'Continue review',
        reviewActionHint: 'Click to complete confirmation',
        confirmReview: 'Complete review?',
        receiptEditing: 'Editing',
        receiptExpandDetails: 'Expand details',
        receiptHideDetails: 'Hide details',
        receiptLinkedTransactionShort: 'Linked transaction',
      })
    ),
    ...buildProactiveReminderHotfix(
      'You have {{count}} tax health items to review. Your current health score is {{score}}.'
    ),
    tour: {
      taxTools: {
        assetReport: {
          title: 'Asset Report',
          message:
            'Select any tracked property or asset to generate detailed income statements and depreciation schedules.',
        },
      },
    },
  },
  zh: {
    ...mergeLocaleHotfixes(
      buildExportAndSearchHotfix(
        '\u5bfc\u51fa CSV',
        '\u5bfc\u51fa PDF',
        '\u6309\u63cf\u8ff0\u6216\u7c7b\u522b\u641c\u7d22...',
        '\u6309\u63cf\u8ff0\u641c\u7d22...'
      ),
      buildReviewWorkflowHotfix({
        oneClickConfirm: '\u4e00\u952e\u786e\u8ba4',
        bulkConfirmSuccess: '\u5df2\u786e\u8ba4 {{count}} \u9879\u3002',
        pendingReview: '\u5f85\u5ba1\u6838',
        pendingReviewOnly: '\u4ec5\u770b\u5f85\u5ba1\u6838',
      }),
      buildTransactionSemanticsHotfix({
        systemGenerated: '\u7cfb\u7edf\u751f\u6210',
        bankReconcileHint: '\u8bf7\u5230\u6587\u6863\u4e0a\u4f20\u94f6\u884c\u6d41\u6c34\u5b8c\u6210\u5bf9\u8d26',
        ignored: '\u5df2\u5ffd\u7565',
        suggestedIgnore: '\u5efa\u8bae\u5ffd\u7565',
        ignore: '\u5ffd\u7565',
      }),
      buildBankWorkbenchHotfix({
      title: '\u94f6\u884c\u6d41\u6c34\u5de5\u4f5c\u53f0',
      modeImport: '\u5bfc\u5165\u5de5\u4f5c\u53f0',
      modeExtracted: '\u63d0\u53d6\u7ed3\u679c',
      initializing: '\u6b63\u5728\u51c6\u5907\u94f6\u884c\u6d41\u6c34\u5de5\u4f5c\u53f0...',
      loadingLines: '\u6b63\u5728\u52a0\u8f7d\u94f6\u884c\u660e\u7ec6...',
      loadFailed: '\u52a0\u8f7d\u94f6\u884c\u6d41\u6c34\u5de5\u4f5c\u53f0\u5931\u8d25\u3002',
      actionFailed: '\u94f6\u884c\u6d41\u6c34\u64cd\u4f5c\u672a\u80fd\u5b8c\u6210\u3002',
      summaryTitle: '\u5bfc\u5165\u6458\u8981',
      fallbackSummaryTitle: '\u63d0\u53d6\u7684\u6d41\u6c34\u8be6\u60c5',
      localFallbackNotice: '\u7531\u4e8e\u5f53\u524d\u73af\u5883\u4e0d\u63d0\u4f9b\u94f6\u884c\u6d41\u6c34\u5bfc\u5165\u5de5\u4f5c\u53f0\uff0c\u6b64\u94f6\u884c\u6d41\u6c34\u5c06\u4ee5\u63d0\u53d6\u51fa\u7684\u4ea4\u6613\u884c\u5f62\u5f0f\u5c55\u793a\u3002',
      fallbackTransactionsTitle: '\u63d0\u53d6\u7684\u6d41\u6c34\u660e\u7ec6',
      fallbackTransactionsDescription: '\u4ee5\u4e0b\u660e\u7ec6\u76f4\u63a5\u4ece\u6587\u6863\u4e2d\u63d0\u53d6\u3002\u60a8\u53ef\u4ee5\u9010\u6761\u786e\u8ba4\u5e76\u5bfc\u5165\u4e3a\u4ea4\u6613\u3002',
      noExtractedTransactions: '\u8fd9\u4efd\u94f6\u884c\u6d41\u6c34\u6682\u65f6\u8fd8\u6ca1\u6709\u63d0\u53d6\u51fa\u4efb\u4f55\u4ea4\u6613\u660e\u7ec6\u3002',
      importedAt: '\u5bfc\u5165\u65f6\u95f4',
      accountHolder: '\u8d26\u6237\u6301\u6709\u4eba',
      taxYear: '\u7a0e\u52a1\u5e74\u5ea6',
      openingBalance: '\u671f\u521d\u4f59\u989d',
      closingBalance: '\u671f\u672b\u4f59\u989d',
      totalCount: '\u603b\u6761\u6570',
      creditCount: '\u6536\u5165\u7b14\u6570',
      debitCount: '\u652f\u51fa\u7b14\u6570',
      autoProcessed: '\u5df2\u81ea\u52a8\u5904\u7406',
      pendingReview: '\u5f85\u786e\u8ba4',
      ignoredCount: '\u5df2\u5ffd\u7565',
      confidence: '\u7f6e\u4fe1\u5ea6',
      linkedTransaction: '\u5173\u8054\u4ea4\u6613',
      noLinkedTransaction: '\u65e0\u5173\u8054\u4ea4\u6613',
      directionLabel: '\u65b9\u5411',
      directionCredit: '\u6536\u5165',
      directionDebit: '\u652f\u51fa',
      directionUnknown: '\u8bc6\u522b\u7ed3\u679c',
      noCounterparty: '\u672a\u77e5\u5bf9\u624b\u65b9',
      noPurpose: '\u6682\u65e0\u4ed8\u6b3e\u8bf4\u660e\u3002',
      statusAutoCreated: '\u5df2\u81ea\u52a8\u65b0\u589e',
      statusMatchedExisting: '\u5df2\u5339\u914d\u73b0\u6709\u4ea4\u6613',
      statusIgnoredDuplicate: '\u5df2\u5ffd\u7565',
      statusPendingReview: '\u5f85\u786e\u8ba4',
      suggestedCreate: '建议新建',
      suggestedMatch: '建议匹配',
      suggestedIgnore: '建议忽略',
      actionCreate: '\u65b0\u589e\u4ea4\u6613',
      actionMatch: '\u5339\u914d\u5df2\u6709\u4ea4\u6613',
      actionIgnore: '\u5ffd\u7565',
      actionRestore: '\u91cd\u65b0\u5ba1\u6838',
      actionUndoCreate: '\u64a4\u9500\u521b\u5efa',
      actionUnmatch: '\u53d6\u6d88\u5339\u914d',
      actionViewUnavailable: '\u6682\u65e0\u53ef\u9884\u89c8\u4ea4\u6613',
      fallbackCreatedOne: '\u5df2\u521b\u5efa 1 \u7b14\u4ea4\u6613\u3002',
      fallbackCreatedMany: '\u5df2\u521b\u5efa {{count}} \u7b14\u4ea4\u6613\u3002',
      fallbackAlreadyImportedOne: '\u8fd9\u6761\u6d41\u6c34\u660e\u7ec6\u5df2\u5bfc\u5165\u3002',
      fallbackAlreadyImportedMany: '\u8fd9\u4e9b\u6d41\u6c34\u660e\u7ec6\u5df2\u5bfc\u5165\u3002',
      fallbackNoTransactionsCreated: '\u6ca1\u6709\u521b\u5efa\u65b0\u7684\u4ea4\u6613\u3002',
      emptyPending: '\u76ee\u524d\u6ca1\u6709\u9700\u8981\u60a8\u786e\u8ba4\u7684\u94f6\u884c\u660e\u7ec6\u3002',
      emptyResolved: '\u6682\u65e0\u5df2\u81ea\u52a8\u5904\u7406\u7684\u94f6\u884c\u660e\u7ec6\u3002',
      emptyIgnored: '\u6682\u65e0\u5df2\u5ffd\u7565\u7684\u91cd\u590d\u660e\u7ec6\u3002',
      pendingTitle: '\u5f85\u786e\u8ba4',
      pendingDescription: '\u4f4e\u7f6e\u4fe1\u5ea6\u9879\u76ee\u4f1a\u6682\u65f6\u4fdd\u7559\u5728\u8fd9\u91cc\uff0c\u7b49\u60a8\u786e\u8ba4\u5e94\u5982\u4f55\u5904\u7406\u3002',
      resolvedTitle: '\u5df2\u81ea\u52a8\u5904\u7406',
      resolvedDescription: '\u8fd9\u4e9b\u660e\u7ec6\u5df2\u81ea\u52a8\u65b0\u589e\u4ea4\u6613\uff0c\u6216\u5df2\u5339\u914d\u5230\u73b0\u6709\u4ea4\u6613\u3002',
      ignoredTitle: '\u5df2\u5ffd\u7565',
      ignoredDescription: '\u8fd9\u4e9b\u660e\u7ec6\u5df2\u88ab\u5ffd\u7565\uff0c\u4e0d\u4f1a\u518d\u751f\u6210\u4ea4\u6613\u3002',
      importBankStatement: '\u5bfc\u5165\u94f6\u884c\u6d41\u6c34',
      openBankWorkbench: '\u6253\u5f00\u94f6\u884c\u6d41\u6c34\u5de5\u4f5c\u53f0',
      bankWorkbenchHint: '\u6253\u5f00\u94f6\u884c\u6d41\u6c34\u5de5\u4f5c\u53f0\uff0c\u590d\u6838\u4f4e\u7f6e\u4fe1\u5ea6\u9879\u76ee\uff0c\u5339\u914d\u5df2\u6709\u4ea4\u6613\uff0c\u5e76\u786e\u8ba4\u9700\u8981\u65b0\u589e\u7684\u4ea4\u6613\u3002',
    }),
      buildBankWorkbenchResolutionHotfix({
        statusRevokedCreate: '\u5df2\u64a4\u9500\u521b\u5efa',
        statusRevokedMatch: '\u5df2\u53d6\u6d88\u5339\u914d',
        reasonOrphanRepaired: '\u5173\u8054\u4ea4\u6613\u5df2\u5931\u6548\uff0c\u8bf7\u91cd\u65b0\u68c0\u67e5\u8fd9\u6761\u6d41\u6c34\u3002',
      }),
      buildDocumentReviewHotfix({
        confirmed: '\u5df2\u786e\u8ba4',
        confirmedSuccess: '\u6587\u6863\u5df2\u786e\u8ba4',
        saveChanges: '\u4fdd\u5b58\u66f4\u6539',
        reviewAction: '\u7ee7\u7eed\u5ba1\u6838',
        reviewActionHint: '\u70b9\u51fb\u5b8c\u6210\u786e\u8ba4',
        confirmReview: '\u786e\u8ba4\u5b8c\u6210\u5ba1\u6838\uff1f',
        receiptEditing: '\u7f16\u8f91\u4e2d',
        receiptExpandDetails: '\u5c55\u5f00\u8be6\u60c5',
        receiptHideDetails: '\u6536\u8d77\u8be6\u60c5',
        receiptLinkedTransactionShort: '\u5df2\u5173\u8054\u4ea4\u6613',
      })
    ),
    ...buildProactiveReminderHotfix(
      '\u60a8\u6709 {{count}} \u9879\u7a0e\u52a1\u5065\u5eb7\u63d0\u9192\u5f85\u5904\u7406\uff0c\u5f53\u524d\u5065\u5eb7\u5206\u4e3a {{score}} \u5206\u3002'
    ),
    tour: {
      taxTools: {
        employer: {
          title: '\u96c7\u4e3b\u7a0e\u52a1\u8bc1\u660e',
          message: '\u5f55\u5165\u60a8\u7684\u5de5\u8d44\u5355\uff08L16\uff09\u6570\u636e\uff0c\u4ee5\u4fbf\u5c06\u96c7\u4f63\u6536\u5165\u7eb3\u5165\u7a0e\u52a1\u8ba1\u7b97\u3002',
        },
      },
    },
  },
  fr: {
    ...mergeLocaleHotfixes(
      buildExportAndSearchHotfix(
        'Exporter en CSV',
        'Exporter en PDF',
        'Rechercher par description ou cat\u00e9gorie...',
        'Rechercher par description...'
      ),
      buildReviewWorkflowHotfix({
        oneClickConfirm: 'Confirmer en un clic',
        bulkConfirmSuccess: '{{count}} elements confirmes.',
        pendingReview: 'A verifier',
        pendingReviewOnly: 'Seulement a verifier',
      }),
      buildTransactionSemanticsHotfix({
        systemGenerated: 'Genere par le systeme',
        bankReconcileHint: 'Importez vos releves bancaires dans Documents pour effectuer le rapprochement.',
        ignored: 'Ignore',
        suggestedIgnore: 'Suggestion d ignorer',
        ignore: 'Ignorer',
      }),
      buildBankWorkbenchHotfix({
      title: 'Espace de traitement du releve bancaire',
      modeImport: 'Espace d import',
      modeExtracted: 'Lignes extraites',
      initializing: 'Preparation de l espace de traitement du releve bancaire...',
      loadingLines: 'Chargement des lignes du releve...',
      loadFailed: 'Impossible de charger l espace de traitement du releve bancaire.',
      actionFailed: 'L action sur le releve bancaire n a pas pu etre effectuee.',
      summaryTitle: 'Resume de l import',
      fallbackSummaryTitle: 'Details extraits du releve',
      localFallbackNotice: 'Ce releve bancaire est affiche sous forme de lignes extraites car l espace de traitement du releve bancaire n est pas disponible dans cet environnement.',
      fallbackTransactionsTitle: 'Lignes extraites',
      fallbackTransactionsDescription: 'Ces lignes ont ete extraites directement du document. Vous pouvez les confirmer une par une et les importer comme transactions.',
      noExtractedTransactions: 'Aucune ligne de transaction n a encore ete extraite de ce releve bancaire.',
      importedAt: 'Importe le',
      accountHolder: 'Titulaire du compte',
      taxYear: 'Annee fiscale',
      openingBalance: 'Solde d ouverture',
      closingBalance: 'Solde de cloture',
      totalCount: 'Nombre total de lignes',
      creditCount: 'Credits',
      debitCount: 'Debits',
      autoProcessed: 'Traite automatiquement',
      pendingReview: 'A confirmer',
      ignoredCount: 'Ignore',
      confidence: 'Confiance',
      linkedTransaction: 'Transaction',
      noLinkedTransaction: 'Aucune transaction liee',
      directionLabel: 'Sens',
      directionCredit: 'Credit',
      directionDebit: 'Debit',
      directionUnknown: 'Detecte',
      noCounterparty: 'Contrepartie inconnue',
      noPurpose: 'Aucun motif de paiement disponible.',
      statusAutoCreated: 'Cree automatiquement',
      statusMatchedExisting: 'Associe a une transaction existante',
      statusIgnoredDuplicate: 'Ignore',
      statusPendingReview: 'A confirmer',
      suggestedCreate: 'Creation suggeree',
      suggestedMatch: 'Rapprochement suggere',
      suggestedIgnore: 'Ignorer suggere',
      actionCreate: 'Creer la transaction',
      actionMatch: 'Associer a l existant',
      actionIgnore: 'Ignorer',
      actionRestore: 'Revoir',
      actionUndoCreate: 'Annuler la creation',
      actionUnmatch: 'Annuler le rapprochement',
      actionViewUnavailable: 'Aucune transaction a afficher',
      fallbackCreatedOne: '1 transaction creee.',
      fallbackCreatedMany: '{{count}} transactions creees.',
      fallbackAlreadyImportedOne: 'Cette ligne de releve a deja ete importee.',
      fallbackAlreadyImportedMany: 'Ces lignes de releve ont deja ete importees.',
      fallbackNoTransactionsCreated: 'Aucune nouvelle transaction n a ete creee.',
      emptyPending: 'Aucune ligne de releve ne necessite de confirmation pour le moment.',
      emptyResolved: 'Aucune ligne de releve traitee automatiquement pour le moment.',
      emptyIgnored: 'Aucun doublon ignore pour le moment.',
      pendingTitle: 'A confirmer',
      pendingDescription: 'Les elements a faible confiance restent ici jusqu a ce que vous confirmiez le traitement approprie.',
      resolvedTitle: 'Traitement automatique',
      resolvedDescription: 'Ces lignes ont ete creees automatiquement ou rapprochees d une transaction existante.',
      ignoredTitle: 'Ignore',
      ignoredDescription: 'Ces lignes ont ete ignorees et ne creeront pas de transactions.',
      importBankStatement: 'Importer le releve bancaire',
      openBankWorkbench: 'Ouvrir l espace de traitement',
      bankWorkbenchHint: 'Ouvrez l espace de traitement du releve bancaire pour verifier les elements a faible confiance, rapprocher les transactions existantes et confirmer les nouvelles transactions.',
    }),
      buildBankWorkbenchResolutionHotfix({
        statusRevokedCreate: 'Creation annulee',
        statusRevokedMatch: 'Correspondance retiree',
        reasonOrphanRepaired: 'La transaction liee n est plus disponible. Verifiez de nouveau cette ligne.',
      }),
      buildDocumentReviewHotfix({
        confirmed: 'Confirme',
        confirmedSuccess: 'Document confirme',
        saveChanges: 'Enregistrer les modifications',
        reviewAction: 'Poursuivre la verification',
        reviewActionHint: 'Cliquer pour terminer la confirmation',
        confirmReview: 'Terminer la verification ?',
        receiptEditing: 'Modification',
        receiptExpandDetails: 'Afficher les details',
        receiptHideDetails: 'Masquer les details',
        receiptLinkedTransactionShort: 'Transaction liee',
      }),
      buildDocumentFiltersHotfix('Appliquer')
    ),
    ...buildProactiveReminderHotfix(
      'Vous avez {{count}} points de sante fiscale a verifier. Votre score actuel est de {{score}}.'
    ),
    properties: {
      pendingDocuments: {
        title: 'Documents d\u2019actifs en attente',
        hint:
          'Les actifs d\u00e9tect\u00e9s \u00e0 partir de contrats d\u2019achat, de factures ou de re\u00e7us apparaissent ici. Une fois confirm\u00e9s, ils deviennent automatiquement des enregistrements d\u2019actifs. Les documents incomplets doivent \u00eatre compl\u00e9t\u00e9s dans la page Documents.',
        needsInput: 'Informations requises',
        missingFields: 'Champs manquants : {{fields}}',
        awaitingConfirmation: 'En attente de confirmation',
        openSourceDocument: 'Ouvrir le document source',
      },
    },
    liabilities: {
      overview: {
        pageTitle: 'Aper\u00e7u des dettes',
      },
    },
    taxTools: {
      page: {
        transactionsSummary: 'Transactions',
        txnIncome: 'Revenus',
        txnExpense: 'D\u00e9penses',
        txnDeductible: 'D\u00e9ductible',
      },
    },
    tour: {
      taxTools: {
        employer: {
          title: 'Attestation fiscale de l\u2019employeur',
          message:
            'Saisissez les donn\u00e9es de votre Lohnzettel (L16) afin d\u2019inclure les revenus salari\u00e9s dans votre calcul fiscal.',
        },
        audit: {
          title: 'Liste de contr\u00f4le d\u2019audit',
          message:
            'V\u00e9rifiez que vos dossiers sont complets et conformes avant de d\u00e9poser votre d\u00e9claration fiscale.',
        },
      },
    },
  },
  ru: {
    ...mergeLocaleHotfixes(
      buildReviewWorkflowHotfix({
        oneClickConfirm: '\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044c \u0432 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u043a',
        bulkConfirmSuccess: '\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u043e {{count}} \u043f\u043e\u0437\u0438\u0446\u0438\u0439.',
        pendingReview: '\u041d\u0430 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0435',
        pendingReviewOnly: '\u0422\u043e\u043b\u044c\u043a\u043e \u043d\u0430 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0435',
      }),
      buildTransactionSemanticsHotfix({
        systemGenerated: '\u0421\u043e\u0437\u0434\u0430\u043d\u043e \u0441\u0438\u0441\u0442\u0435\u043c\u043e\u0439',
        bankReconcileHint: '\u0427\u0442\u043e\u0431\u044b \u0432\u044b\u043f\u043e\u043b\u043d\u0438\u0442\u044c \u0441\u0432\u0435\u0440\u043a\u0443, \u0437\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u0435 \u0431\u0430\u043d\u043a\u043e\u0432\u0441\u043a\u0443\u044e \u0432\u044b\u043f\u0438\u0441\u043a\u0443 \u0432 \u0414\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u044b.',
        ignored: '\u0418\u0433\u043d\u043e\u0440\u0438\u0440\u043e\u0432\u0430\u043d\u043e',
        suggestedIgnore: '\u0420\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u0443\u0435\u0442\u0441\u044f \u0438\u0433\u043d\u043e\u0440\u0438\u0440\u043e\u0432\u0430\u0442\u044c',
        ignore: '\u0418\u0433\u043d\u043e\u0440\u0438\u0440\u043e\u0432\u0430\u0442\u044c',
      }),
      buildBankWorkbenchHotfix({
      title: '\u0420\u0430\u0431\u043e\u0447\u0430\u044f \u043e\u0431\u043b\u0430\u0441\u0442\u044c \u0431\u0430\u043d\u043a\u043e\u0432\u0441\u043a\u043e\u0439 \u0432\u044b\u043f\u0438\u0441\u043a\u0438',
      modeImport: '\u0420\u0430\u0431\u043e\u0447\u0430\u044f \u043e\u0431\u043b\u0430\u0441\u0442\u044c \u0438\u043c\u043f\u043e\u0440\u0442\u0430',
      modeExtracted: '\u0418\u0437\u0432\u043b\u0435\u0447\u0451\u043d\u043d\u044b\u0435 \u0441\u0442\u0440\u043e\u043a\u0438',
      initializing: '\u041f\u043e\u0434\u0433\u043e\u0442\u0430\u0432\u043b\u0438\u0432\u0430\u0435\u043c \u0440\u0430\u0431\u043e\u0447\u0443\u044e \u043e\u0431\u043b\u0430\u0441\u0442\u044c \u0431\u0430\u043d\u043a\u043e\u0432\u0441\u043a\u043e\u0439 \u0432\u044b\u043f\u0438\u0441\u043a\u0438...',
      loadingLines: '\u0417\u0430\u0433\u0440\u0443\u0436\u0430\u0435\u043c \u0441\u0442\u0440\u043e\u043a\u0438 \u0432\u044b\u043f\u0438\u0441\u043a\u0438...',
      loadFailed: '\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0437\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u0440\u0430\u0431\u043e\u0447\u0443\u044e \u043e\u0431\u043b\u0430\u0441\u0442\u044c \u0431\u0430\u043d\u043a\u043e\u0432\u0441\u043a\u043e\u0439 \u0432\u044b\u043f\u0438\u0441\u043a\u0438.',
      actionFailed: '\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0432\u044b\u043f\u043e\u043b\u043d\u0438\u0442\u044c \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0435 \u0434\u043b\u044f \u0431\u0430\u043d\u043a\u043e\u0432\u0441\u043a\u043e\u0439 \u0432\u044b\u043f\u0438\u0441\u043a\u0438.',
      summaryTitle: '\u0421\u0432\u043e\u0434\u043a\u0430 \u0438\u043c\u043f\u043e\u0440\u0442\u0430',
      fallbackSummaryTitle: '\u0418\u0437\u0432\u043b\u0435\u0447\u0451\u043d\u043d\u044b\u0435 \u0434\u0430\u043d\u043d\u044b\u0435 \u0432\u044b\u043f\u0438\u0441\u043a\u0438',
      localFallbackNotice: '\u042d\u0442\u0430 \u0431\u0430\u043d\u043a\u043e\u0432\u0441\u043a\u0430\u044f \u0432\u044b\u043f\u0438\u0441\u043a\u0430 \u043f\u043e\u043a\u0430\u0437\u0430\u043d\u0430 \u043a\u0430\u043a \u0438\u0437\u0432\u043b\u0435\u0447\u0451\u043d\u043d\u044b\u0435 \u0441\u0442\u0440\u043e\u043a\u0438, \u043f\u043e\u0442\u043e\u043c\u0443 \u0447\u0442\u043e \u0440\u0430\u0431\u043e\u0447\u0430\u044f \u043e\u0431\u043b\u0430\u0441\u0442\u044c \u0438\u043c\u043f\u043e\u0440\u0442\u0430 \u0431\u0430\u043d\u043a\u043e\u0432\u0441\u043a\u043e\u0439 \u0432\u044b\u043f\u0438\u0441\u043a\u0438 \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0430 \u0432 \u044d\u0442\u043e\u0439 \u0441\u0440\u0435\u0434\u0435.',
      fallbackTransactionsTitle: '\u0418\u0437\u0432\u043b\u0435\u0447\u0451\u043d\u043d\u044b\u0435 \u0441\u0442\u0440\u043e\u043a\u0438 \u0432\u044b\u043f\u0438\u0441\u043a\u0438',
      fallbackTransactionsDescription: '\u042d\u0442\u0438 \u0441\u0442\u0440\u043e\u043a\u0438 \u0438\u0437\u0432\u043b\u0435\u0447\u0435\u043d\u044b \u043d\u0430\u043f\u0440\u044f\u043c\u0443\u044e \u0438\u0437 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430. \u0412\u044b \u043c\u043e\u0436\u0435\u0442\u0435 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0430\u0442\u044c \u0438\u0445 \u043f\u043e \u043e\u0434\u043d\u043e\u0439 \u0438 \u0438\u043c\u043f\u043e\u0440\u0442\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u043a\u0430\u043a \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0438.',
      noExtractedTransactions: '\u0418\u0437 \u044d\u0442\u043e\u0439 \u0431\u0430\u043d\u043a\u043e\u0432\u0441\u043a\u043e\u0439 \u0432\u044b\u043f\u0438\u0441\u043a\u0438 \u043f\u043e\u043a\u0430 \u043d\u0435 \u0438\u0437\u0432\u043b\u0435\u0447\u0435\u043d\u043e \u043d\u0438 \u043e\u0434\u043d\u043e\u0439 \u0441\u0442\u0440\u043e\u043a\u0438 \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0438.',
      importedAt: '\u0418\u043c\u043f\u043e\u0440\u0442\u0438\u0440\u043e\u0432\u0430\u043d\u043e',
      accountHolder: '\u0412\u043b\u0430\u0434\u0435\u043b\u0435\u0446 \u0441\u0447\u0451\u0442\u0430',
      taxYear: '\u041d\u0430\u043b\u043e\u0433\u043e\u0432\u044b\u0439 \u0433\u043e\u0434',
      openingBalance: '\u041d\u0430\u0447\u0430\u043b\u044c\u043d\u044b\u0439 \u0431\u0430\u043b\u0430\u043d\u0441',
      closingBalance: '\u041a\u043e\u043d\u0435\u0447\u043d\u044b\u0439 \u0431\u0430\u043b\u0430\u043d\u0441',
      totalCount: '\u0412\u0441\u0435\u0433\u043e \u0441\u0442\u0440\u043e\u043a',
      creditCount: '\u041f\u043e\u0441\u0442\u0443\u043f\u043b\u0435\u043d\u0438\u044f',
      debitCount: '\u0421\u043f\u0438\u0441\u0430\u043d\u0438\u044f',
      autoProcessed: '\u041e\u0431\u0440\u0430\u0431\u043e\u0442\u0430\u043d\u043e \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438',
      pendingReview: '\u041e\u0436\u0438\u0434\u0430\u0435\u0442 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f',
      ignoredCount: '\u0418\u0433\u043d\u043e\u0440\u0438\u0440\u043e\u0432\u0430\u043d\u043e',
      confidence: '\u0423\u0432\u0435\u0440\u0435\u043d\u043d\u043e\u0441\u0442\u044c',
      linkedTransaction: '\u0422\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u044f',
      noLinkedTransaction: '\u041d\u0435\u0442 \u0441\u0432\u044f\u0437\u0430\u043d\u043d\u043e\u0439 \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0438',
      directionLabel: '\u041d\u0430\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435',
      directionCredit: '\u041f\u043e\u0441\u0442\u0443\u043f\u043b\u0435\u043d\u0438\u0435',
      directionDebit: '\u0421\u043f\u0438\u0441\u0430\u043d\u0438\u0435',
      directionUnknown: '\u041e\u043f\u0440\u0435\u0434\u0435\u043b\u0435\u043d\u043e',
      noCounterparty: '\u041a\u043e\u043d\u0442\u0440\u0430\u0433\u0435\u043d\u0442 \u043d\u0435 \u0443\u043a\u0430\u0437\u0430\u043d',
      noPurpose: '\u041d\u0435\u0442 \u043e\u043f\u0438\u0441\u0430\u043d\u0438\u044f \u043f\u043b\u0430\u0442\u0435\u0436\u0430.',
      statusAutoCreated: '\u0421\u043e\u0437\u0434\u0430\u043d\u043e \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438',
      statusMatchedExisting: '\u0421\u043e\u043f\u043e\u0441\u0442\u0430\u0432\u043b\u0435\u043d\u043e \u0441 \u0441\u0443\u0449\u0435\u0441\u0442\u0432\u0443\u044e\u0449\u0435\u0439 \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0435\u0439',
      statusIgnoredDuplicate: '\u0418\u0433\u043d\u043e\u0440\u0438\u0440\u043e\u0432\u0430\u043d\u043e',
      statusPendingReview: '\u041e\u0436\u0438\u0434\u0430\u0435\u0442 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f',
      suggestedCreate: 'Рекомендовано создать',
      suggestedMatch: 'Рекомендовано сопоставить',
      suggestedIgnore: 'Рекомендовано игнорировать',
      actionCreate: '\u0421\u043e\u0437\u0434\u0430\u0442\u044c \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u044e',
      actionMatch: '\u0421\u043e\u043f\u043e\u0441\u0442\u0430\u0432\u0438\u0442\u044c \u0441 \u0441\u0443\u0449\u0435\u0441\u0442\u0432\u0443\u044e\u0449\u0435\u0439',
      actionIgnore: '\u0418\u0433\u043d\u043e\u0440\u0438\u0440\u043e\u0432\u0430\u0442\u044c',
      actionRestore: '\u041f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c \u0441\u043d\u043e\u0432\u0430',
      actionUndoCreate: '\u041e\u0442\u043c\u0435\u043d\u0438\u0442\u044c \u0441\u043e\u0437\u0434\u0430\u043d\u0438\u0435',
      actionUnmatch: '\u041e\u0442\u043c\u0435\u043d\u0438\u0442\u044c \u0441\u043e\u043f\u043e\u0441\u0442\u0430\u0432\u043b\u0435\u043d\u0438\u0435',
      actionViewUnavailable: '\u041d\u0435\u0442 \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0438 \u0434\u043b\u044f \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0430',
      fallbackCreatedOne: '\u0421\u043e\u0437\u0434\u0430\u043d\u0430 1 \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u044f.',
      fallbackCreatedMany: '\u0421\u043e\u0437\u0434\u0430\u043d\u043e {{count}} \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0439.',
      fallbackAlreadyImportedOne: '\u042d\u0442\u0430 \u0441\u0442\u0440\u043e\u043a\u0430 \u0432\u044b\u043f\u0438\u0441\u043a\u0438 \u0443\u0436\u0435 \u0438\u043c\u043f\u043e\u0440\u0442\u0438\u0440\u043e\u0432\u0430\u043d\u0430.',
      fallbackAlreadyImportedMany: '\u042d\u0442\u0438 \u0441\u0442\u0440\u043e\u043a\u0438 \u0432\u044b\u043f\u0438\u0441\u043a\u0438 \u0443\u0436\u0435 \u0438\u043c\u043f\u043e\u0440\u0442\u0438\u0440\u043e\u0432\u0430\u043d\u044b.',
      fallbackNoTransactionsCreated: '\u041d\u043e\u0432\u044b\u0435 \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0438 \u043d\u0435 \u0431\u044b\u043b\u0438 \u0441\u043e\u0437\u0434\u0430\u043d\u044b.',
      emptyPending: '\u0421\u0435\u0439\u0447\u0430\u0441 \u043d\u0435\u0442 \u0441\u0442\u0440\u043e\u043a \u0432\u044b\u043f\u0438\u0441\u043a\u0438, \u043a\u043e\u0442\u043e\u0440\u044b\u0435 \u043d\u0443\u0436\u043d\u043e \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044c.',
      emptyResolved: '\u0415\u0449\u0435 \u043d\u0435\u0442 \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438 \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u0430\u043d\u043d\u044b\u0445 \u0441\u0442\u0440\u043e\u043a \u0432\u044b\u043f\u0438\u0441\u043a\u0438.',
      emptyIgnored: '\u0415\u0449\u0435 \u043d\u0435\u0442 \u0438\u0433\u043d\u043e\u0440\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u044b\u0445 \u0434\u0443\u0431\u043b\u0438\u043a\u0430\u0442\u043e\u0432.',
      pendingTitle: '\u041e\u0436\u0438\u0434\u0430\u0435\u0442 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f',
      pendingDescription: '\u042d\u043b\u0435\u043c\u0435\u043d\u0442\u044b \u0441 \u043d\u0438\u0437\u043a\u043e\u0439 \u0443\u0432\u0435\u0440\u0435\u043d\u043d\u043e\u0441\u0442\u044c\u044e \u043e\u0441\u0442\u0430\u044e\u0442\u0441\u044f \u0437\u0434\u0435\u0441\u044c, \u043f\u043e\u043a\u0430 \u0432\u044b \u043d\u0435 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u0435, \u043a\u0430\u043a \u0438\u0445 \u043d\u0443\u0436\u043d\u043e \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u0430\u0442\u044c.',
      resolvedTitle: '\u041e\u0431\u0440\u0430\u0431\u043e\u0442\u0430\u043d\u043e \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438',
      resolvedDescription: '\u042d\u0442\u0438 \u0441\u0442\u0440\u043e\u043a\u0438 \u0431\u044b\u043b\u0438 \u0441\u043e\u0437\u0434\u0430\u043d\u044b \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438 \u0438\u043b\u0438 \u0441\u043e\u043f\u043e\u0441\u0442\u0430\u0432\u043b\u0435\u043d\u044b \u0441 \u0443\u0436\u0435 \u0441\u0443\u0449\u0435\u0441\u0442\u0432\u0443\u044e\u0449\u0435\u0439 \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0435\u0439.',
      ignoredTitle: '\u0418\u0433\u043d\u043e\u0440\u0438\u0440\u043e\u0432\u0430\u043d\u043e',
      ignoredDescription: '\u042d\u0442\u0438 \u0441\u0442\u0440\u043e\u043a\u0438 \u0431\u044b\u043b\u0438 \u0438\u0433\u043d\u043e\u0440\u0438\u0440\u043e\u0432\u0430\u043d\u044b \u0438 \u043d\u0435 \u0441\u043e\u0437\u0434\u0430\u0434\u0443\u0442 \u043d\u043e\u0432\u044b\u0445 \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0439.',
      importBankStatement: '\u0418\u043c\u043f\u043e\u0440\u0442 \u0431\u0430\u043d\u043a\u043e\u0432\u0441\u043a\u043e\u0439 \u0432\u044b\u043f\u0438\u0441\u043a\u0438',
      openBankWorkbench: '\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u0440\u0430\u0431\u043e\u0447\u0443\u044e \u043e\u0431\u043b\u0430\u0441\u0442\u044c',
      bankWorkbenchHint: '\u041e\u0442\u043a\u0440\u043e\u0439\u0442\u0435 \u0440\u0430\u0431\u043e\u0447\u0443\u044e \u043e\u0431\u043b\u0430\u0441\u0442\u044c \u0431\u0430\u043d\u043a\u043e\u0432\u0441\u043a\u043e\u0439 \u0432\u044b\u043f\u0438\u0441\u043a\u0438, \u0447\u0442\u043e\u0431\u044b \u043f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c \u044d\u043b\u0435\u043c\u0435\u043d\u0442\u044b \u0441 \u043d\u0438\u0437\u043a\u043e\u0439 \u0443\u0432\u0435\u0440\u0435\u043d\u043d\u043e\u0441\u0442\u044c\u044e, \u0441\u043e\u043f\u043e\u0441\u0442\u0430\u0432\u0438\u0442\u044c \u0441\u0443\u0449\u0435\u0441\u0442\u0432\u0443\u044e\u0449\u0438\u0435 \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0438 \u0438 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044c \u043d\u043e\u0432\u044b\u0435 \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0438.',
    }),
      buildBankWorkbenchResolutionHotfix({
        statusRevokedCreate: '\u0421\u043e\u0437\u0434\u0430\u043d\u0438\u0435 \u043e\u0442\u043c\u0435\u043d\u0435\u043d\u043e',
        statusRevokedMatch: '\u0421\u0432\u044f\u0437\u044c \u0441\u043d\u044f\u0442\u0430',
        reasonOrphanRepaired: '\u0421\u0432\u044f\u0437\u0430\u043d\u043d\u0430\u044f \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u044f \u0431\u043e\u043b\u044c\u0448\u0435 \u043d\u0435 \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0430. \u041f\u0440\u043e\u0432\u0435\u0440\u044c\u0442\u0435 \u044d\u0442\u0443 \u0441\u0442\u0440\u043e\u043a\u0443 \u0435\u0449\u0435 \u0440\u0430\u0437.',
      }),
      buildDocumentReviewHotfix({
        confirmed: '\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u043e',
        confirmedSuccess: '\u0414\u043e\u043a\u0443\u043c\u0435\u043d\u0442 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0451\u043d',
        saveChanges: '\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c \u0438\u0437\u043c\u0435\u043d\u0435\u043d\u0438\u044f',
        reviewAction: '\u041f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0443',
        reviewActionHint: '\u041d\u0430\u0436\u043c\u0438\u0442\u0435, \u0447\u0442\u043e\u0431\u044b \u0437\u0430\u0432\u0435\u0440\u0448\u0438\u0442\u044c \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u0435',
        confirmReview: '\u0417\u0430\u0432\u0435\u0440\u0448\u0438\u0442\u044c \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0443?',
        receiptEditing: '\u0420\u0435\u0434\u0430\u043a\u0442\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u0435',
        receiptExpandDetails: '\u041f\u043e\u043a\u0430\u0437\u0430\u0442\u044c \u0434\u0435\u0442\u0430\u043b\u0438',
        receiptHideDetails: '\u0421\u043a\u0440\u044b\u0442\u044c \u0434\u0435\u0442\u0430\u043b\u0438',
        receiptLinkedTransactionShort: '\u0421\u0432\u044f\u0437\u0430\u043d\u043d\u0430\u044f \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u044f',
      }),
      buildDocumentFiltersHotfix('\u041f\u0440\u0438\u043c\u0435\u043d\u0438\u0442\u044c')
    ),
    ...buildProactiveReminderHotfix(
      '\u0423 \u0432\u0430\u0441 {{count}} \u043f\u0443\u043d\u043a\u0442\u043e\u0432 \u043d\u0430\u043b\u043e\u0433\u043e\u0432\u043e\u0439 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438 \u0434\u043b\u044f \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0430. \u0422\u0435\u043a\u0443\u0449\u0438\u0439 \u0431\u0430\u043b\u043b: {{score}}.'
    ),
    properties: {
      pendingDocuments: {
        title: '\u041e\u0436\u0438\u0434\u0430\u044e\u0449\u0438\u0435 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u044b \u043f\u043e \u0430\u043a\u0442\u0438\u0432\u0430\u043c',
        hint:
          '\u0410\u043a\u0442\u0438\u0432\u044b, \u043e\u0431\u043d\u0430\u0440\u0443\u0436\u0435\u043d\u043d\u044b\u0435 \u0432 \u0434\u043e\u0433\u043e\u0432\u043e\u0440\u0430\u0445 \u043a\u0443\u043f\u043b\u0438-\u043f\u0440\u043e\u0434\u0430\u0436\u0438, \u0441\u0447\u0435\u0442\u0430\u0445 \u0438\u043b\u0438 \u0447\u0435\u043a\u0430\u0445, \u043e\u0442\u043e\u0431\u0440\u0430\u0436\u0430\u044e\u0442\u0441\u044f \u0437\u0434\u0435\u0441\u044c. \u041f\u043e\u0441\u043b\u0435 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f \u043e\u043d\u0438 \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438 \u0441\u0442\u0430\u043d\u043e\u0432\u044f\u0442\u0441\u044f \u0437\u0430\u043f\u0438\u0441\u044f\u043c\u0438 \u043e\u0431 \u0430\u043a\u0442\u0438\u0432\u0430\u0445. \u0414\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u044b \u0441 \u043d\u0435\u0434\u043e\u0441\u0442\u0430\u044e\u0449\u0438\u043c\u0438 \u043f\u043e\u043b\u044f\u043c\u0438 \u043d\u0443\u0436\u043d\u043e \u0434\u043e\u043f\u043e\u043b\u043d\u0438\u0442\u044c \u043d\u0430 \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0435 \u00ab\u0414\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u044b\u00bb.',
        needsInput: '\u0422\u0440\u0435\u0431\u0443\u044e\u0442\u0441\u044f \u0434\u0430\u043d\u043d\u044b\u0435',
        missingFields: '\u041e\u0442\u0441\u0443\u0442\u0441\u0442\u0432\u0443\u044e\u0442: {{fields}}',
        awaitingConfirmation: '\u041e\u0436\u0438\u0434\u0430\u0435\u0442 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f',
        openSourceDocument: '\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u0438\u0441\u0445\u043e\u0434\u043d\u044b\u0439 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442',
      },
    },
    liabilities: {
      overview: {
        pageTitle: '\u041e\u0431\u0437\u043e\u0440 \u043e\u0431\u044f\u0437\u0430\u0442\u0435\u043b\u044c\u0441\u0442\u0432',
      },
    },
    taxTools: {
      page: {
        transactionsSummary: '\u0422\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0438',
        txnIncome: '\u0414\u043e\u0445\u043e\u0434\u044b',
        txnExpense: '\u0420\u0430\u0441\u0445\u043e\u0434\u044b',
        txnDeductible: '\u041a \u0432\u044b\u0447\u0435\u0442\u0443',
      },
    },
    tour: {
      taxTools: {
        assetReport: {
          title: '\u041e\u0442\u0447\u0451\u0442 \u043f\u043e \u0430\u043a\u0442\u0438\u0432\u0430\u043c',
          message:
            '\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043b\u044e\u0431\u0443\u044e \u043e\u0442\u0441\u043b\u0435\u0436\u0438\u0432\u0430\u0435\u043c\u0443\u044e \u043d\u0435\u0434\u0432\u0438\u0436\u0438\u043c\u043e\u0441\u0442\u044c \u0438\u043b\u0438 \u0430\u043a\u0442\u0438\u0432, \u0447\u0442\u043e\u0431\u044b \u0441\u0444\u043e\u0440\u043c\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u043f\u043e\u0434\u0440\u043e\u0431\u043d\u044b\u0435 \u043e\u0442\u0447\u0451\u0442\u044b \u043e \u0434\u043e\u0445\u043e\u0434\u0430\u0445 \u0438 \u0433\u0440\u0430\u0444\u0438\u043a\u0438 \u0430\u043c\u043e\u0440\u0442\u0438\u0437\u0430\u0446\u0438\u0438.',
        },
      },
    },
  },
  hu: {
    ...mergeLocaleHotfixes(
      buildReviewWorkflowHotfix({
        oneClickConfirm: 'Jovahagyas egy kattintassal',
        bulkConfirmSuccess: '{{count}} tetel jovahagyva.',
        pendingReview: 'Ellenorzesre var',
        pendingReviewOnly: 'Csak ellenorzesre varo',
      }),
      buildTransactionSemanticsHotfix({
        systemGenerated: 'Rendszer altal generalt',
        bankReconcileHint: 'Az egyezteteshez toltse fel a bankszamlakivonatot a Dokumentumokhoz.',
        ignored: 'Figyelmen kivul hagyva',
        suggestedIgnore: 'Javasolt figyelmen kivul hagyas',
        ignore: 'Figyelmen kivul hagy',
      }),
      buildBankWorkbenchHotfix({
      title: 'Bankszamlakivonat munkafelulet',
      modeImport: 'Import munkafelulet',
      modeExtracted: 'Kinyert sorok',
      initializing: 'A bankszamlakivonat munkafelulet elokeszitese...',
      loadingLines: 'A kivonatsorok betoltese...',
      loadFailed: 'Nem sikerult betolteni a bankszamlakivonat munkafeluletet.',
      actionFailed: 'A bankszamlakivonat muveletet nem sikerult befejezni.',
      summaryTitle: 'Import osszegzes',
      fallbackSummaryTitle: 'Kinyert kivonatreszletek',
      localFallbackNotice: 'Ez a bankszamlakivonat kinyert tranzakciosorokent jelenik meg, mert a bankszamlakivonat munkafelulet ebben a kornyezetben nem erheto el.',
      fallbackTransactionsTitle: 'Kinyert tranzakciosorok',
      fallbackTransactionsDescription: 'Ezeket a sorokat kozvetlenul a dokumentumbol nyertuk ki. Soronkent megerositheti es tranzakciokent importalhatja oket.',
      noExtractedTransactions: 'Ebbol a bankszamlakivonatbol meg nem sikerult tranzakciosorokat kinyerni.',
      importedAt: 'Importalva',
      accountHolder: 'Szamlatulajdonos',
      taxYear: 'Adoev',
      openingBalance: 'Nyito egyenleg',
      closingBalance: 'Zaro egyenleg',
      totalCount: 'Sorok osszesen',
      creditCount: 'Jovairasok',
      debitCount: 'Terhelesek',
      autoProcessed: 'Automatikusan feldolgozva',
      pendingReview: 'Megerositesre var',
      ignoredCount: 'Figyelmen kivul hagyva',
      confidence: 'Megbizhatosag',
      linkedTransaction: 'Tranzakcio',
      noLinkedTransaction: 'Nincs kapcsolt tranzakcio',
      directionLabel: 'Irany',
      directionCredit: 'Jovairas',
      directionDebit: 'Terheles',
      directionUnknown: 'Felismerve',
      noCounterparty: 'Ismeretlen partner',
      noPurpose: 'Nincs elerheto kozlemeny.',
      statusAutoCreated: 'Automatikusan letrehozva',
      statusMatchedExisting: 'Meglevo tranzakciohoz kapcsolva',
      statusIgnoredDuplicate: 'Figyelmen kivul hagyva',
      statusPendingReview: 'Megerositesre var',
      suggestedCreate: 'Javasolt letrehozas',
      suggestedMatch: 'Javasolt parositas',
      suggestedIgnore: 'Javasolt figyelmen kivul hagyas',
      actionCreate: 'Tranzakcio letrehozasa',
      actionMatch: 'Meglevo parositasa',
      actionIgnore: 'Figyelmen kivul hagy',
      actionRestore: 'Ujra ellenoriz',
      actionUndoCreate: 'Letrehozas visszavonasa',
      actionUnmatch: 'Parositas megszuntetese',
      actionViewUnavailable: 'Nincs megjelenitheto tranzakcio',
      fallbackCreatedOne: '1 tranzakcio letrehozva.',
      fallbackCreatedMany: '{{count}} tranzakcio letrehozva.',
      fallbackAlreadyImportedOne: 'Ez a kivonatsor mar importalva lett.',
      fallbackAlreadyImportedMany: 'Ezek a kivonatsorok mar importalva lettek.',
      fallbackNoTransactionsCreated: 'Nem jott letre uj tranzakcio.',
      emptyPending: 'Jelenleg nincs megerositesre varo kivonatsor.',
      emptyResolved: 'Meg nincs automatikusan feldolgozott kivonatsor.',
      emptyIgnored: 'Meg nincs figyelmen kivul hagyott duplikatum.',
      pendingTitle: 'Megerositesre var',
      pendingDescription: 'Az alacsony megbizhatosagu elemek itt maradnak, amig meg nem erositi a megfelelo kezelest.',
      resolvedTitle: 'Automatikusan feldolgozva',
      resolvedDescription: 'Ezek a sorok automatikusan letrejottek vagy egy meglevo tranzakciohoz lettek kapcsolva.',
      ignoredTitle: 'Figyelmen kivul hagyva',
      ignoredDescription: 'Ezeket a sorokat figyelmen kivul hagytuk, es nem hoznak letre uj tranzakciot.',
      importBankStatement: 'Bankszamlakivonat importalasa',
      openBankWorkbench: 'Munkafelulet megnyitasa',
      bankWorkbenchHint: 'Nyissa meg a bankszamlakivonat munkafeluletet az alacsony megbizhatosagu elemek ellenorzesehez, a meglevo tranzakciok parositasahoz es az uj tranzakciok megerositesehez.',
    }),
      buildBankWorkbenchResolutionHotfix({
        statusRevokedCreate: 'Letrehozas visszavonva',
        statusRevokedMatch: 'Parositas torolve',
        reasonOrphanRepaired: 'A kapcsolt tranzakcio mar nem erheto el. Ellenorizze ujra ezt a sort.',
      }),
      buildDocumentReviewHotfix({
        confirmed: 'Megerositve',
        confirmedSuccess: 'Dokumentum megerositve',
        saveChanges: 'Valtoztatasok mentese',
        reviewAction: 'Ellenorzes folytatasa',
        reviewActionHint: 'Kattintson a jovahagyas befejezesehez',
        confirmReview: 'Ellenorzes befejezese?',
        receiptEditing: 'Szerkesztes',
        receiptExpandDetails: 'Reszletek megjelenitese',
        receiptHideDetails: 'Reszletek elrejtese',
        receiptLinkedTransactionShort: 'Kapcsolt tranzakcio',
      }),
      buildDocumentFiltersHotfix('Alkalmaz')
    ),
    ...buildProactiveReminderHotfix(
      'Onnek {{count}} adoegeszsegi tetelt kell atneznie. A jelenlegi pontszam {{score}}.'
    ),
    properties: {
      pendingDocuments: {
        title: 'F\u00fcgg\u0151 eszk\u00f6zdokumentumok',
        hint:
          'Az ad\u00e1sv\u00e9teli szerz\u0151d\u00e9sekb\u0151l, sz\u00e1ml\u00e1kb\u00f3l vagy nyugt\u00e1kb\u00f3l felismert eszk\u00f6z\u00f6k itt jelennek meg. J\u00f3v\u00e1hagy\u00e1s ut\u00e1n automatikusan eszk\u00f6znyilv\u00e1ntart\u00e1sba ker\u00fclnek. A hi\u00e1nyos dokumentumokat a Dokumentumok oldalon kell kieg\u00e9sz\u00edteni.',
        needsInput: 'Adatok sz\u00fcks\u00e9gesek',
        missingFields: 'Hi\u00e1nyzik: {{fields}}',
        awaitingConfirmation: 'J\u00f3v\u00e1hagy\u00e1sra v\u00e1r',
        openSourceDocument: 'Forr\u00e1sdokumentum megnyit\u00e1sa',
      },
    },
    liabilities: {
      overview: {
        pageTitle: 'K\u00f6telezetts\u00e9gek \u00e1ttekint\u00e9se',
      },
    },
    taxTools: {
      page: {
        transactionsSummary: 'Tranzakci\u00f3k',
        txnIncome: 'Bev\u00e9telek',
        txnExpense: 'Kiad\u00e1sok',
        txnDeductible: 'Levonhat\u00f3',
      },
    },
    tour: {
      taxTools: {
        assetReport: {
          title: 'Eszk\u00f6zjelent\u00e9s',
          message:
            'V\u00e1lasszon b\u00e1rmely nyomon k\u00f6vetett ingatlant vagy eszk\u00f6zt a r\u00e9szletes eredm\u00e9nykimutat\u00e1sok \u00e9s \u00e9rt\u00e9kcs\u00f6kken\u00e9si tervek elk\u00e9sz\u00edt\u00e9s\u00e9hez.',
        },
      },
    },
  },
  pl: {
    ...mergeLocaleHotfixes(
      buildExportAndSearchHotfix(
        'Eksportuj CSV',
        'Eksportuj PDF',
        'Szukaj po opisie lub kategorii...',
        'Szukaj po opisie...'
      ),
      buildReviewWorkflowHotfix({
        oneClickConfirm: 'Potwierdz jednym kliknieciem',
        bulkConfirmSuccess: 'Potwierdzono {{count}} pozycji.',
        pendingReview: 'Do sprawdzenia',
        pendingReviewOnly: 'Tylko do sprawdzenia',
      }),
      buildTransactionSemanticsHotfix({
        systemGenerated: 'Wygenerowane przez system',
        bankReconcileHint: 'Aby uzgodnic, przeslij wyciag bankowy w Dokumentach.',
        ignored: 'Pominiete',
        suggestedIgnore: 'Zalecane pominiecie',
        ignore: 'Pomin',
      }),
      buildBankWorkbenchHotfix({
      title: 'Panel wyciagu bankowego',
      modeImport: 'Panel importu',
      modeExtracted: 'Wyodrebnione pozycje',
      initializing: 'Przygotowywanie panelu wyciagu bankowego...',
      loadingLines: 'Ladowanie pozycji wyciagu...',
      loadFailed: 'Nie udalo sie zaladowac panelu wyciagu bankowego.',
      actionFailed: 'Nie udalo sie wykonac operacji dla wyciagu bankowego.',
      summaryTitle: 'Podsumowanie importu',
      fallbackSummaryTitle: 'Wyodrebnione szczegoly wyciagu',
      localFallbackNotice: 'Ten wyciag bankowy jest pokazywany jako wyodrebnione wiersze transakcji, poniewaz panel wyciagu bankowego nie jest dostepny w tym srodowisku.',
      fallbackTransactionsTitle: 'Wyodrebnione wiersze transakcji',
      fallbackTransactionsDescription: 'Te wiersze zostaly wyodrebnione bezposrednio z dokumentu. Mozesz potwierdzac je pojedynczo i importowac jako transakcje.',
      noExtractedTransactions: 'Z tego wyciagu bankowego nie wyodrebniono jeszcze zadnych wierszy transakcji.',
      importedAt: 'Zaimportowano',
      accountHolder: 'Wlasciciel rachunku',
      taxYear: 'Rok podatkowy',
      openingBalance: 'Saldo poczatkowe',
      closingBalance: 'Saldo koncowe',
      totalCount: 'Laczna liczba pozycji',
      creditCount: 'Uznania',
      debitCount: 'Obciazenia',
      autoProcessed: 'Przetworzono automatycznie',
      pendingReview: 'Do potwierdzenia',
      ignoredCount: 'Pominiete',
      confidence: 'Pewnosc',
      linkedTransaction: 'Transakcja',
      noLinkedTransaction: 'Brak powiazanej transakcji',
      directionLabel: 'Kierunek',
      directionCredit: 'Uznanie',
      directionDebit: 'Obciazenie',
      directionUnknown: 'Wykryto',
      noCounterparty: 'Nieznana strona transakcji',
      noPurpose: 'Brak opisu platnosci.',
      statusAutoCreated: 'Utworzono automatycznie',
      statusMatchedExisting: 'Dopasowano do istniejacej transakcji',
      statusIgnoredDuplicate: 'Pominiete',
      statusPendingReview: 'Do potwierdzenia',
      suggestedCreate: 'Zalecane utworzenie',
      suggestedMatch: 'Zalecane dopasowanie',
      suggestedIgnore: 'Zalecane pominiecie',
      actionCreate: 'Utworz transakcje',
      actionMatch: 'Dopasuj istniejaca',
      actionIgnore: 'Ignoruj',
      actionRestore: 'Sprawdz ponownie',
      actionUndoCreate: 'Cofnij utworzenie',
      actionUnmatch: 'Anuluj dopasowanie',
      actionViewUnavailable: 'Brak transakcji do podgladu',
      fallbackCreatedOne: 'Utworzono 1 transakcje.',
      fallbackCreatedMany: 'Utworzono {{count}} transakcji.',
      fallbackAlreadyImportedOne: 'Ten wiersz wyciagu zostal juz zaimportowany.',
      fallbackAlreadyImportedMany: 'Te wiersze wyciagu zostaly juz zaimportowane.',
      fallbackNoTransactionsCreated: 'Nie utworzono nowych transakcji.',
      emptyPending: 'Obecnie zadna pozycja wyciagu nie wymaga potwierdzenia.',
      emptyResolved: 'Brak jeszcze automatycznie przetworzonych pozycji wyciagu.',
      emptyIgnored: 'Brak jeszcze zignorowanych duplikatow.',
      pendingTitle: 'Do potwierdzenia',
      pendingDescription: 'Pozycje o niskiej pewnosci pozostaja tutaj, dopoki nie potwierdzisz sposobu ich obslugi.',
      resolvedTitle: 'Przetworzono automatycznie',
      resolvedDescription: 'Te pozycje zostaly utworzone automatycznie lub dopasowane do istniejacej transakcji.',
      ignoredTitle: 'Pominiete',
      ignoredDescription: 'Te pozycje zostaly pominiete i nie utworza nowych transakcji.',
      importBankStatement: 'Importuj wyciag bankowy',
      openBankWorkbench: 'Otworz panel wyciagu bankowego',
      bankWorkbenchHint: 'Otworz panel wyciagu bankowego, aby sprawdzic pozycje o niskiej pewnosci, dopasowac istniejace transakcje i potwierdzic nowe transakcje.',
    }),
      buildBankWorkbenchResolutionHotfix({
        statusRevokedCreate: 'Cofnieto utworzenie',
        statusRevokedMatch: 'Usunieto dopasowanie',
        reasonOrphanRepaired: 'Powiazana transakcja nie jest juz dostepna. Sprawdz ponownie ten wiersz.',
      }),
      buildDocumentReviewHotfix({
        confirmed: 'Potwierdzone',
        confirmedSuccess: 'Dokument potwierdzony',
        saveChanges: 'Zapisz zmiany',
        reviewAction: 'Kontynuuj przeglad',
        reviewActionHint: 'Kliknij, aby zakonczyc potwierdzenie',
        confirmReview: 'Zakonczyc przeglad?',
        receiptEditing: 'Edycja',
        receiptExpandDetails: 'Pokaz szczegoly',
        receiptHideDetails: 'Ukryj szczegoly',
        receiptLinkedTransactionShort: 'Powiazana transakcja',
      }),
      buildDocumentFiltersHotfix('Zastosuj')
    ),
    ...buildProactiveReminderHotfix(
      'Masz {{count}} pozycji zdrowia podatkowego do sprawdzenia. Twoj obecny wynik to {{score}}.'
    ),
    properties: {
      pendingDocuments: {
        title: 'Oczekuj\u0105ce dokumenty aktyw\u00f3w',
        hint:
          'Aktywa wykryte na podstawie um\u00f3w zakupu, faktur lub paragon\u00f3w pojawi\u0105 si\u0119 tutaj. Po potwierdzeniu zostan\u0105 automatycznie zapisane jako aktywa. Dokumenty z brakuj\u0105cymi polami wymagaj\u0105 uzupe\u0142nienia na stronie Dokumenty.',
        needsInput: 'Wymagane dane',
        missingFields: 'Brakuje: {{fields}}',
        awaitingConfirmation: 'Oczekuje na potwierdzenie',
        openSourceDocument: 'Otw\u00f3rz dokument \u017ar\u00f3d\u0142owy',
      },
    },
    liabilities: {
      overview: {
        pageTitle: 'Przegl\u0105d zobowi\u0105za\u0144',
      },
    },
    taxTools: {
      page: {
        transactionsSummary: 'Transakcje',
        txnIncome: 'Przychody',
        txnExpense: 'Wydatki',
        txnDeductible: 'Odliczalne',
      },
    },
    tour: {
      taxTools: {
        employer: {
          title: 'Za\u015bwiadczenie podatkowe pracodawcy',
          message:
            'Wprowad\u017a dane z Lohnzettel (L16), aby uwzgl\u0119dni\u0107 doch\u00f3d z pracy w obliczeniu podatku.',
        },
        audit: {
          title: 'Lista kontrolna audytu',
          message:
            'Sprawd\u017a, czy Twoje dane s\u0105 kompletne i zgodne przed z\u0142o\u017ceniem zeznania podatkowego.',
        },
      },
    },
  },
  tr: {
    ...mergeLocaleHotfixes(
      buildExportAndSearchHotfix(
        'CSV olarak disa aktar',
        'PDF olarak disa aktar',
        'Aciklama veya kategoriye gore ara...',
        'Aciklamaya gore ara...'
      ),
      buildReviewWorkflowHotfix({
        oneClickConfirm: 'Tek tikla onayla',
        bulkConfirmSuccess: '{{count}} oge onaylandi.',
        pendingReview: 'Inceleme bekliyor',
        pendingReviewOnly: 'Yalnizca inceleme bekleyenler',
      }),
      buildTransactionSemanticsHotfix({
        systemGenerated: 'Sistem tarafindan olusturuldu',
        bankReconcileHint: 'Mutabakat icin banka ekstresini Belgeler bolumune yukleyin.',
        ignored: 'Yoksayildi',
        suggestedIgnore: 'Yoksayma onerildi',
        ignore: 'Yoksay',
      }),
      buildBankWorkbenchHotfix({
      title: 'Banka hesap ozeti calisma alani',
      modeImport: 'Ice aktarma calisma alani',
      modeExtracted: 'Cikarilan satirlar',
      initializing: 'Banka hesap ozeti calisma alani hazirlaniyor...',
      loadingLines: 'Ekstre satirlari yukleniyor...',
      loadFailed: 'Banka hesap ozeti calisma alani yuklenemedi.',
      actionFailed: 'Banka hesap ozeti islemi tamamlanamadi.',
      summaryTitle: 'Ice aktarma ozeti',
      fallbackSummaryTitle: 'Cikarilan ekstre ayrintilari',
      localFallbackNotice: 'Bu banka hesap ozeti, bu ortamda banka hesap ozeti calisma alani kullanilamadigi icin cikarilan islem satirlari olarak gosterilmektedir.',
      fallbackTransactionsTitle: 'Cikarilan islem satirlari',
      fallbackTransactionsDescription: 'Bu satirlar dogrudan belgeden cikarildi. Her satiri tek tek onaylayip islem olarak ice aktarabilirsiniz.',
      noExtractedTransactions: 'Bu banka hesap ozetinden henuz hic islem satiri cikarilmadi.',
      importedAt: 'Ice aktarma tarihi',
      accountHolder: 'Hesap sahibi',
      taxYear: 'Vergi yili',
      openingBalance: 'Acilis bakiyesi',
      closingBalance: 'Kapanis bakiyesi',
      totalCount: 'Toplam satir',
      creditCount: 'Alacaklar',
      debitCount: 'Borclar',
      autoProcessed: 'Otomatik islenen',
      pendingReview: 'Onay bekleyen',
      ignoredCount: 'Yoksayilan',
      confidence: 'Guven',
      linkedTransaction: 'Islem',
      noLinkedTransaction: 'Bagli islem yok',
      directionLabel: 'Yon',
      directionCredit: 'Alacak',
      directionDebit: 'Borc',
      directionUnknown: 'Algilandi',
      noCounterparty: 'Karsi taraf bilinmiyor',
      noPurpose: 'Odeme aciklamasi yok.',
      statusAutoCreated: 'Otomatik olusturuldu',
      statusMatchedExisting: 'Mevcut islemle eslesti',
      statusIgnoredDuplicate: 'Yoksayildi',
      statusPendingReview: 'Onay bekleyen',
      suggestedCreate: 'Onerilen olusturma',
      suggestedMatch: 'Onerilen eslestirme',
      suggestedIgnore: 'Onerilen yok sayma',
      actionCreate: 'Islem olustur',
      actionMatch: 'Mevcut islemi eslestir',
      actionIgnore: 'Yoksay',
      actionRestore: 'Yeniden incele',
      actionUndoCreate: 'Olusturmayi geri al',
      actionUnmatch: 'Eslestirmeyi kaldir',
      actionViewUnavailable: 'Onizlenecek islem yok',
      fallbackCreatedOne: '1 islem olusturuldu.',
      fallbackCreatedMany: '{{count}} islem olusturuldu.',
      fallbackAlreadyImportedOne: 'Bu ekstre satiri zaten ice aktarildi.',
      fallbackAlreadyImportedMany: 'Bu ekstre satirlari zaten ice aktarildi.',
      fallbackNoTransactionsCreated: 'Yeni islem olusturulmadi.',
      emptyPending: 'Su anda onay bekleyen banka hareketi yok.',
      emptyResolved: 'Henuz otomatik islenmis banka hareketi yok.',
      emptyIgnored: 'Henuz yoksayilan cift kayit yok.',
      pendingTitle: 'Onay bekleyen',
      pendingDescription: 'Dusuk guvenli ogeler, nasil isleneceklerini onaylayana kadar burada kalir.',
      resolvedTitle: 'Otomatik islenen',
      resolvedDescription: 'Bu satirlar otomatik olarak olusturuldu veya mevcut bir islemle eslestirildi.',
      ignoredTitle: 'Yoksayildi',
      ignoredDescription: 'Bu satirlar yoksayildi ve yeni islem olusturmayacak.',
      importBankStatement: 'Banka hesap ozeti ice aktar',
      openBankWorkbench: 'Calisma alanini ac',
      bankWorkbenchHint: 'Dusuk guvenli ogeleri incelemek, mevcut islemleri eslestirmek ve yeni islemleri onaylamak icin banka hesap ozeti calisma alanini acin.',
    }),
      buildBankWorkbenchResolutionHotfix({
        statusRevokedCreate: 'Olusturma geri alindi',
        statusRevokedMatch: 'Eslestirme kaldirildi',
        reasonOrphanRepaired: 'Bagli islem artik kullanilabilir degil. Bu satiri yeniden inceleyin.',
      }),
      buildDocumentReviewHotfix({
        confirmed: 'Onaylandi',
        confirmedSuccess: 'Belge onaylandi',
        saveChanges: 'Degisiklikleri kaydet',
        reviewAction: 'Incelemeye devam et',
        reviewActionHint: 'Onayi tamamlamak icin tiklayin',
        confirmReview: 'Incelemeyi tamamla?',
        receiptEditing: 'Duzenleniyor',
        receiptExpandDetails: 'Ayrintilari genislet',
        receiptHideDetails: 'Ayrintilari gizle',
        receiptLinkedTransactionShort: 'Bagli islem',
      }),
      buildDocumentFiltersHotfix('Uygula')
    ),
    ...buildProactiveReminderHotfix(
      'Gozden gecirmeniz gereken {{count}} vergi sagligi maddesi var. Mevcut puaniniz {{score}}.'
    ),
    properties: {
      pendingDocuments: {
        title: 'Bekleyen varl\u0131k belgeleri',
        hint:
          'Sat\u0131n alma s\u00f6zle\u015fmeleri, faturalar veya fi\u015flerden tespit edilen varl\u0131klar burada g\u00f6r\u00fcn\u00fcr. Onayland\u0131ktan sonra otomatik olarak varl\u0131k kayd\u0131 olu\u015fturulur. Eksik alanl\u0131 belgeler Belgeler sayfas\u0131nda tamamlanmal\u0131d\u0131r.',
        needsInput: 'Bilgi gerekiyor',
        missingFields: 'Eksik: {{fields}}',
        awaitingConfirmation: 'Onay bekleniyor',
        openSourceDocument: 'Kaynak belgeyi a\u00e7',
      },
    },
    liabilities: {
      overview: {
        pageTitle: 'Y\u00fck\u00fcml\u00fcl\u00fck Genel Bak\u0131\u015f\u0131',
      },
    },
    taxTools: {
      page: {
        transactionsSummary: '\u0130\u015flemler',
        txnIncome: 'Gelir',
        txnExpense: 'Gider',
        txnDeductible: '\u0130ndirilebilir',
      },
    },
    tour: {
      taxTools: {
        employer: {
          title: '\u0130\u015fveren vergi belgesi',
          message:
            '\u0130stihdam gelirini vergi hesab\u0131n\u0131za dahil etmek i\u00e7in Lohnzettel (L16) verilerinizi girin.',
        },
        audit: {
          title: 'Denetim kontrol listesi',
          message:
            'Vergi beyannamenizi g\u00f6ndermeden \u00f6nce kay\u0131tlar\u0131n\u0131z\u0131n eksiksiz ve uyumlu oldu\u011fundan emin olun.',
        },
      },
    },
  },
  bs: {
    ...mergeLocaleHotfixes(
      buildReviewWorkflowHotfix({
        oneClickConfirm: 'Potvrdi jednim klikom',
        bulkConfirmSuccess: 'Potvrdjeno {{count}} stavki.',
        pendingReview: 'Ceka pregled',
        pendingReviewOnly: 'Samo stavke koje cekaju pregled',
      }),
      buildTransactionSemanticsHotfix({
        systemGenerated: 'Sistemski generisano',
        bankReconcileHint: 'Za uskladjivanje otpremite bankovni izvod u Dokumente.',
        ignored: 'Ignorisano',
        suggestedIgnore: 'Predlozeno ignorisanje',
        ignore: 'Ignorisi',
      }),
      buildBankWorkbenchHotfix({
      title: 'Radni prostor bankovnog izvoda',
      modeImport: 'Radni prostor uvoza',
      modeExtracted: 'Izdvojeni redovi',
      initializing: 'Pripremamo radni prostor bankovnog izvoda...',
      loadingLines: 'Ucitajavanje stavki izvoda...',
      loadFailed: 'Radni prostor bankovnog izvoda nije se mogao ucitati.',
      actionFailed: 'Radnja za bankovni izvod nije mogla biti dovrsena.',
      summaryTitle: 'Saetak uvoza',
      fallbackSummaryTitle: 'Izdvojeni detalji izvoda',
      localFallbackNotice: 'Ovaj bankovni izvod je prikazan kao izdvojeni redovi transakcija jer radni prostor bankovnog izvoda nije dostupan u ovom okruzenju.',
      fallbackTransactionsTitle: 'Izdvojeni redovi transakcija',
      fallbackTransactionsDescription: 'Ovi redovi su izdvojeni direktno iz dokumenta. Mozete ih potvrditi pojedinacno i uvesti kao transakcije.',
      noExtractedTransactions: 'Iz ovog bankovnog izvoda jos nisu izdvojeni redovi transakcija.',
      importedAt: 'Uvezeno',
      accountHolder: 'Vlasnik racuna',
      taxYear: 'Poreska godina',
      openingBalance: 'Pocetno stanje',
      closingBalance: 'Zavrsno stanje',
      totalCount: 'Ukupno stavki',
      creditCount: 'Prilivi',
      debitCount: 'Odlivi',
      autoProcessed: 'Automatski obradeno',
      pendingReview: 'Ceka potvrdu',
      ignoredCount: 'Ignorisano',
      confidence: 'Pouzdanost',
      linkedTransaction: 'Transakcija',
      noLinkedTransaction: 'Nema povezane transakcije',
      directionLabel: 'Smjer',
      directionCredit: 'Priliv',
      directionDebit: 'Odliv',
      directionUnknown: 'Prepoznato',
      noCounterparty: 'Nepoznata druga strana',
      noPurpose: 'Nema opisa placanja.',
      statusAutoCreated: 'Automatski kreirano',
      statusMatchedExisting: 'Povezano sa postojecoom transakcijom',
      statusIgnoredDuplicate: 'Ignorisano',
      statusPendingReview: 'Ceka potvrdu',
      suggestedCreate: 'Preporuceno kreiranje',
      suggestedMatch: 'Preporuceno povezivanje',
      suggestedIgnore: 'Preporuceno ignorisanje',
      actionCreate: 'Kreiraj transakciju',
      actionMatch: 'Povezi postojecu',
      actionIgnore: 'Ignorisi',
      actionRestore: 'Pregledaj ponovo',
      actionUndoCreate: 'Ponisti kreiranje',
      actionUnmatch: 'Ukloni povezivanje',
      actionViewUnavailable: 'Nema transakcije za pregled',
      fallbackCreatedOne: 'Kreirana je 1 transakcija.',
      fallbackCreatedMany: 'Kreirano je {{count}} transakcija.',
      fallbackAlreadyImportedOne: 'Ova stavka izvoda je vec uvezena.',
      fallbackAlreadyImportedMany: 'Ove stavke izvoda su vec uvezene.',
      fallbackNoTransactionsCreated: 'Nijedna nova transakcija nije kreirana.',
      emptyPending: 'Trenutno nema stavki izvoda koje cekaju potvrdu.',
      emptyResolved: 'Jos nema automatski obradenih stavki izvoda.',
      emptyIgnored: 'Jos nema ignorisanih duplikata.',
      pendingTitle: 'Ceka potvrdu',
      pendingDescription: 'Stavke sa nizom pouzdanoscu ostaju ovdje dok ne potvrdite kako ih treba obraditi.',
      resolvedTitle: 'Automatski obradeno',
      resolvedDescription: 'Ove stavke su automatski kreirane ili povezane sa postojecom transakcijom.',
      ignoredTitle: 'Ignorisano',
      ignoredDescription: 'Ove stavke su ignorisane i nece kreirati nove transakcije.',
      importBankStatement: 'Uvezi bankovni izvod',
      openBankWorkbench: 'Otvori radni prostor',
      bankWorkbenchHint: 'Otvorite radni prostor bankovnog izvoda da pregledate stavke sa niskom pouzdanoscu, povezete postojece transakcije i potvrdite nove transakcije.',
    }),
      buildBankWorkbenchResolutionHotfix({
        statusRevokedCreate: 'Kreiranje ponisteno',
        statusRevokedMatch: 'Povezivanje uklonjeno',
        reasonOrphanRepaired: 'Povezana transakcija vise nije dostupna. Ponovo pregledajte ovu stavku.',
      }),
      buildDocumentReviewHotfix({
        confirmed: 'Potvrdjeno',
        confirmedSuccess: 'Dokument potvrdjen',
        saveChanges: 'Sacuvaj izmjene',
        reviewAction: 'Nastavi pregled',
        reviewActionHint: 'Kliknite da dovrsite potvrdu',
        confirmReview: 'Zavrsiti pregled?',
        receiptEditing: 'Uredjivanje',
        receiptExpandDetails: 'Prikazi detalje',
        receiptHideDetails: 'Sakrij detalje',
        receiptLinkedTransactionShort: 'Povezana transakcija',
      }),
      buildDocumentFiltersHotfix('Primijeni')
    ),
    ...buildProactiveReminderHotfix(
      'Imate {{count}} stavki poreskog zdravlja za pregled. Vas trenutni rezultat je {{score}}.'
    ),
    properties: {
      pendingDocuments: {
        title: 'Dokumenti imovine na \u010dekanju',
        hint:
          'Imovina prepoznata iz kupoprodajnih ugovora, faktura ili ra\u010duna prikazuje se ovdje. Nakon potvrde automatski postaje zapis o imovini. Dokumente sa nedostaju\u0107im poljima treba dopuniti na stranici Dokumenti.',
        needsInput: 'Potrebni podaci',
        missingFields: 'Nedostaje: {{fields}}',
        awaitingConfirmation: '\u010ceka potvrdu',
        openSourceDocument: 'Otvori izvorni dokument',
      },
    },
    liabilities: {
      overview: {
        pageTitle: 'Pregled obaveza',
      },
    },
    taxTools: {
      page: {
        transactionsSummary: 'Transakcije',
        txnIncome: 'Prihodi',
        txnExpense: 'Rashodi',
        txnDeductible: 'Odbitno',
      },
    },
    tour: {
      taxTools: {
        assetReport: {
          title: 'Izvje\u0161taj o imovini',
          message:
            'Odaberite bilo koju pra\u0107enu nekretninu ili imovinu kako biste generirali detaljne izvje\u0161taje o prihodima i rasporede amortizacije.',
        },
      },
    },
  },
};

const TAX_PACKAGE_HOTFIXES: Record<SupportedLanguage, LocaleObject> = {
  de: buildTaxPackageHotfix({
    exportPackage: 'Steuerpaket exportieren',
    exportPackageLoading: 'Steuerpaket wird exportiert...',
    exportPackageFailed: 'Das Steuerpaket konnte nicht exportiert werden.',
    exportPackagePanelTitle: 'Steuerpaket exportieren',
    exportPackagePanelDescription: 'Bereiten Sie ein herunterladbares Paket fuer das ausgewaehlte Steuerjahr vor.',
    includeFoundationMaterials: 'Grundlagenmaterialien einbeziehen',
    includeFoundationMaterialsHint: 'Fuegt langlebige Grundlagendokumente wie Miet-, Kredit- oder Kaufvertraege hinzu.',
    packageScopeTransactionsCsv: 'Transaktionen CSV',
    packageScopeTransactionsPdf: 'Transaktionen PDF',
    packageScopeSummaryPdf: 'Zusammenfassung PDF',
    packageScopeDocuments: 'Steuerrelevante Quelldokumente',
    packageScopeFoundationOptional: 'Optional: Grundlagenmaterialien',
    preparePackage: 'Paket vorbereiten',
    packageStatusPending: 'Vorbereitung laeuft',
    packageStatusProcessing: 'Paket wird erstellt',
    packageStatusReady: 'Bereit zum Download',
    packageDownloadSingle: 'Paket herunterladen',
    packageDownloadPart: 'Teil {{part}} herunterladen',
    packageFailureTitle: 'Paket konnte nicht vorbereitet werden',
    packageFailureDocumentCount: 'Dokumentanzahl',
    packageFailureEstimatedSize: 'Geschaetzte Groesse',
    packageFailureLargestFamily: 'Groesste Dokumentfamilie',
    exportPackagePreviewLoading: 'Offene Punkte fuer den Export werden geprueft...',
    exportPackagePreviewFailed: 'Die Exportwarnungen konnten nicht geprueft werden.',
    exportPackageWarningTitle: 'Bitte pruefen Sie diese Punkte vor dem Export',
    exportPackageWarningDescription: 'Der Export ist trotzdem moeglich, aber offene Punkte koennen die Qualitaet Ihrer Steuerunterlagen verschlechtern.',
    exportPackageWarningPendingTransactions: 'Noch zu pruefende Transaktionen',
    exportPackageWarningPendingDocuments: 'Noch zu pruefende Dokumente',
    exportPackageWarningFallbackYears: 'Dokumente mit Jahr aus Upload-Datum',
    exportPackageWarningSkippedFiles: 'Nicht exportierte Dateien',
    reviewTransactionsBeforeExport: 'Transaktionen pruefen',
    reviewDocumentsBeforeExport: 'Dokumente pruefen',
    continueExportPackage: 'Trotzdem exportieren',
    reviewWarningsFirst: 'Warnungen zuerst pruefen',
  }),
  en: buildTaxPackageHotfix({
    exportPackage: 'Export tax package',
    exportPackageLoading: 'Exporting tax package...',
    exportPackageFailed: 'Failed to export tax package.',
    exportPackagePanelTitle: 'Export tax package',
    exportPackagePanelDescription: 'Prepare a downloadable package for the selected tax year.',
    includeFoundationMaterials: 'Include foundation materials',
    includeFoundationMaterialsHint: 'Adds long-lived base materials such as rental, loan, purchase, registry, and trade-license documents.',
    packageScopeTransactionsCsv: 'Transaction CSV',
    packageScopeTransactionsPdf: 'Transaction PDF',
    packageScopeSummaryPdf: 'Summary PDF',
    packageScopeDocuments: 'Tax-related source documents',
    packageScopeFoundationOptional: 'Optional: foundation materials',
    preparePackage: 'Prepare package',
    packageStatusPending: 'Preparing',
    packageStatusProcessing: 'Packaging',
    packageStatusReady: 'Ready to download',
    packageDownloadSingle: 'Download package',
    packageDownloadPart: 'Download part {{part}}',
    packageFailureTitle: 'Package could not be prepared',
    packageFailureDocumentCount: 'Document count',
    packageFailureEstimatedSize: 'Estimated size',
    packageFailureLargestFamily: 'Largest family',
    exportPackagePreviewLoading: 'Checking export warnings...',
    exportPackagePreviewFailed: 'Failed to check export warnings.',
    exportPackageWarningTitle: 'Review these items before exporting',
    exportPackageWarningDescription: 'You can still export the package, but these open items may reduce filing quality.',
    exportPackageWarningPendingTransactions: 'Pending review transactions',
    exportPackageWarningPendingDocuments: 'Pending review documents',
    exportPackageWarningFallbackYears: 'Documents assigned by uploaded date fallback',
    exportPackageWarningSkippedFiles: 'Files excluded from export',
    reviewTransactionsBeforeExport: 'Review transactions',
    reviewDocumentsBeforeExport: 'Review documents',
    continueExportPackage: 'Continue export anyway',
    reviewWarningsFirst: 'Review warnings first',
  }),
  zh: buildTaxPackageHotfix({
    exportPackage: '导出税务包',
    exportPackageLoading: '正在导出税务包...',
    exportPackageFailed: '导出税务包失败。',
    exportPackagePanelTitle: '导出税务包',
    exportPackagePanelDescription: '为当前选中的税务年度准备一个可下载的税务包。',
    includeFoundationMaterials: '包含长期基础材料',
    includeFoundationMaterialsHint: '会额外纳入租赁合同、贷款合同、购房合同等长期基础材料。',
    packageScopeTransactionsCsv: '交易 CSV',
    packageScopeTransactionsPdf: '交易 PDF',
    packageScopeSummaryPdf: '总结 PDF',
    packageScopeDocuments: '税务相关原始文档',
    packageScopeFoundationOptional: '可选：长期基础材料',
    preparePackage: '开始准备',
    packageStatusPending: '准备中',
    packageStatusProcessing: '打包中',
    packageStatusReady: '可下载',
    packageDownloadSingle: '下载税务包',
    packageDownloadPart: '下载第 {{part}} 卷',
    packageFailureTitle: '税务包暂时无法准备',
    packageFailureDocumentCount: '文档数量',
    packageFailureEstimatedSize: '预计大小',
    packageFailureLargestFamily: '最大文档家族',
    exportPackagePreviewLoading: '正在检查导出前风险...',
    exportPackagePreviewFailed: '暂时无法检查导出风险。',
    exportPackageWarningTitle: '导出前请先检查这些项目',
    exportPackageWarningDescription: '您仍然可以继续导出，但这些未处理项目可能会降低报税资料质量，建议先处理。',
    exportPackageWarningPendingTransactions: '仍待审核的交易',
    exportPackageWarningPendingDocuments: '仍待审核的文档',
    exportPackageWarningFallbackYears: '按上传日期归入本年度的文档',
    exportPackageWarningSkippedFiles: '未纳入导出的文件',
    reviewTransactionsBeforeExport: '去检查交易',
    reviewDocumentsBeforeExport: '去检查文档',
    continueExportPackage: '仍然继续导出',
    reviewWarningsFirst: '先查看这些提醒',
  }),
  fr: buildTaxPackageHotfix({
    exportPackage: 'Exporter le pack fiscal',
    exportPackageLoading: 'Export du pack fiscal...',
    exportPackageFailed: "Impossible d'exporter le pack fiscal.",
    exportPackagePanelTitle: 'Exporter le pack fiscal',
    exportPackagePanelDescription: "Préparez un pack téléchargeable pour l'année fiscale sélectionnée.",
    includeFoundationMaterials: 'Inclure les documents de base',
    includeFoundationMaterialsHint: "Ajoute les contrats et documents de base à long terme.",
    packageScopeTransactionsCsv: 'CSV des transactions',
    packageScopeTransactionsPdf: 'PDF des transactions',
    packageScopeSummaryPdf: 'PDF de synthèse',
    packageScopeDocuments: 'Documents fiscaux sources',
    packageScopeFoundationOptional: 'Optionnel : documents de base',
    preparePackage: 'Préparer le pack',
    packageStatusPending: 'Préparation',
    packageStatusProcessing: 'Création du pack',
    packageStatusReady: 'Prêt à télécharger',
    packageDownloadSingle: 'Télécharger le pack',
    packageDownloadPart: 'Télécharger la partie {{part}}',
    packageFailureTitle: 'Le pack n’a pas pu être préparé',
    packageFailureDocumentCount: 'Nombre de documents',
    packageFailureEstimatedSize: 'Taille estimée',
    packageFailureLargestFamily: 'Famille la plus volumineuse',
    exportPackagePreviewLoading: 'Vérification des alertes avant export...',
    exportPackagePreviewFailed: "Impossible de vérifier les alertes d'export.",
    exportPackageWarningTitle: "Vérifiez ces points avant l'export",
    exportPackageWarningDescription: "L'export reste possible, mais ces éléments ouverts peuvent réduire la qualité du dossier fiscal.",
    exportPackageWarningPendingTransactions: 'Transactions à vérifier',
    exportPackageWarningPendingDocuments: 'Documents à vérifier',
    exportPackageWarningFallbackYears: "Documents rattachés via la date d'envoi",
    exportPackageWarningSkippedFiles: 'Fichiers exclus de l’export',
    reviewTransactionsBeforeExport: 'Vérifier les transactions',
    reviewDocumentsBeforeExport: 'Vérifier les documents',
    continueExportPackage: 'Exporter quand même',
    reviewWarningsFirst: 'Vérifier les alertes',
  }),
  ru: buildTaxPackageHotfix({
    exportPackage: 'Экспорт налогового пакета',
    exportPackageLoading: 'Экспорт налогового пакета...',
    exportPackageFailed: 'Не удалось экспортировать налоговый пакет.',
    exportPackagePanelTitle: 'Экспорт налогового пакета',
    exportPackagePanelDescription: 'Подготовьте пакет для выбранного налогового года.',
    includeFoundationMaterials: 'Включить базовые долгосрочные материалы',
    includeFoundationMaterialsHint: 'Добавляет договоры аренды, займа, покупки и другие базовые документы.',
    packageScopeTransactionsCsv: 'CSV операций',
    packageScopeTransactionsPdf: 'PDF операций',
    packageScopeSummaryPdf: 'Сводный PDF',
    packageScopeDocuments: 'Налоговые исходные документы',
    packageScopeFoundationOptional: 'Дополнительно: базовые материалы',
    preparePackage: 'Подготовить пакет',
    packageStatusPending: 'Подготовка',
    packageStatusProcessing: 'Упаковка',
    packageStatusReady: 'Готово к загрузке',
    packageDownloadSingle: 'Скачать пакет',
    packageDownloadPart: 'Скачать часть {{part}}',
    packageFailureTitle: 'Не удалось подготовить пакет',
    packageFailureDocumentCount: 'Количество документов',
    packageFailureEstimatedSize: 'Оценочный размер',
    packageFailureLargestFamily: 'Самая большая группа',
    exportPackagePreviewLoading: 'Проверка предупреждений перед экспортом...',
    exportPackagePreviewFailed: 'Не удалось проверить предупреждения экспорта.',
    exportPackageWarningTitle: 'Проверьте эти пункты перед экспортом',
    exportPackageWarningDescription: 'Экспорт всё равно возможен, но открытые вопросы могут ухудшить качество налогового пакета.',
    exportPackageWarningPendingTransactions: 'Операции на проверке',
    exportPackageWarningPendingDocuments: 'Документы на проверке',
    exportPackageWarningFallbackYears: 'Документы, отнесённые по дате загрузки',
    exportPackageWarningSkippedFiles: 'Файлы, исключённые из экспорта',
    reviewTransactionsBeforeExport: 'Проверить операции',
    reviewDocumentsBeforeExport: 'Проверить документы',
    continueExportPackage: 'Все равно экспортировать',
    reviewWarningsFirst: 'Сначала проверить предупреждения',
  }),
  hu: buildTaxPackageHotfix({
    exportPackage: 'Ado csomag exportalasa',
    exportPackageLoading: 'Ado csomag exportalasa folyamatban...',
    exportPackageFailed: 'Az ado csomag exportalasa sikertelen.',
    exportPackagePanelTitle: 'Ado csomag exportalasa',
    exportPackagePanelDescription: 'Letoltheto csomag elokeszitese a kivalasztott adoevre.',
    includeFoundationMaterials: 'Hosszu tavu alapdokumentumok belefoglalasa',
    includeFoundationMaterialsHint: 'Berleti, hitel-, vasarlasi es hasonlo alapdokumentumokat is hozzaad.',
    packageScopeTransactionsCsv: 'Tranzakcio CSV',
    packageScopeTransactionsPdf: 'Tranzakcio PDF',
    packageScopeSummaryPdf: 'Osszefoglalo PDF',
    packageScopeDocuments: 'Adozasi forrasdokumentumok',
    packageScopeFoundationOptional: 'Opcionális: alapdokumentumok',
    preparePackage: 'Csomag elokeszitese',
    packageStatusPending: 'Elokeszites',
    packageStatusProcessing: 'Csomagolas',
    packageStatusReady: 'Letoltesre kesz',
    packageDownloadSingle: 'Csomag letoltese',
    packageDownloadPart: '{{part}}. resz letoltese',
    packageFailureTitle: 'A csomag nem keszitheto elo',
    packageFailureDocumentCount: 'Dokumentumok szama',
    packageFailureEstimatedSize: 'Becsult meret',
    packageFailureLargestFamily: 'Legnagyobb dokumentumcsalad',
    exportPackagePreviewLoading: 'Export elotti figyelmeztetesek ellenorzese...',
    exportPackagePreviewFailed: 'Az export figyelmeztetesek ellenorzese nem sikerult.',
    exportPackageWarningTitle: 'Exportalas elott ellenorizze ezeket',
    exportPackageWarningDescription: 'A csomag igy is exportalhato, de a nyitott tetelek ronthatjak az adoanyag minoseget.',
    exportPackageWarningPendingTransactions: 'Ellenorizendo tranzakciok',
    exportPackageWarningPendingDocuments: 'Ellenorizendo dokumentumok',
    exportPackageWarningFallbackYears: 'Feltoltési dátum alapján besorolt dokumentumok',
    exportPackageWarningSkippedFiles: 'Az exportból kihagyott fájlok',
    reviewTransactionsBeforeExport: 'Tranzakciók ellenőrzése',
    reviewDocumentsBeforeExport: 'Dokumentumok ellenőrzése',
    continueExportPackage: 'Exportálás folytatása',
    reviewWarningsFirst: 'Figyelmeztetések áttekintése',
  }),
  pl: buildTaxPackageHotfix({
    exportPackage: 'Eksport pakietu podatkowego',
    exportPackageLoading: 'Eksportowanie pakietu podatkowego...',
    exportPackageFailed: 'Nie udalo sie wyeksportowac pakietu podatkowego.',
    exportPackagePanelTitle: 'Eksport pakietu podatkowego',
    exportPackagePanelDescription: 'Przygotuj pakiet do pobrania dla wybranego roku podatkowego.',
    includeFoundationMaterials: 'Uwzglednij materialy podstawowe',
    includeFoundationMaterialsHint: 'Dodaje umowy najmu, kredytu, zakupu i podobne dokumenty bazowe.',
    packageScopeTransactionsCsv: 'CSV transakcji',
    packageScopeTransactionsPdf: 'PDF transakcji',
    packageScopeSummaryPdf: 'PDF podsumowania',
    packageScopeDocuments: 'Zrodlowe dokumenty podatkowe',
    packageScopeFoundationOptional: 'Opcjonalnie: materialy podstawowe',
    preparePackage: 'Przygotuj pakiet',
    packageStatusPending: 'Przygotowywanie',
    packageStatusProcessing: 'Pakowanie',
    packageStatusReady: 'Gotowe do pobrania',
    packageDownloadSingle: 'Pobierz pakiet',
    packageDownloadPart: 'Pobierz czesc {{part}}',
    packageFailureTitle: 'Nie udalo sie przygotowac pakietu',
    packageFailureDocumentCount: 'Liczba dokumentow',
    packageFailureEstimatedSize: 'Szacowany rozmiar',
    packageFailureLargestFamily: 'Najwieksza rodzina dokumentow',
    exportPackagePreviewLoading: 'Sprawdzanie ostrzezen przed eksportem...',
    exportPackagePreviewFailed: 'Nie udalo sie sprawdzic ostrzezen eksportu.',
    exportPackageWarningTitle: 'Sprawdz te pozycje przed eksportem',
    exportPackageWarningDescription: 'Pakiet nadal mozna wyeksportowac, ale te otwarte pozycje moga pogorszyc jakosc materialow podatkowych.',
    exportPackageWarningPendingTransactions: 'Transakcje do weryfikacji',
    exportPackageWarningPendingDocuments: 'Dokumenty do weryfikacji',
    exportPackageWarningFallbackYears: 'Dokumenty przypisane po dacie przeslania',
    exportPackageWarningSkippedFiles: 'Pliki wylaczone z eksportu',
    reviewTransactionsBeforeExport: 'Sprawdz transakcje',
    reviewDocumentsBeforeExport: 'Sprawdz dokumenty',
    continueExportPackage: 'Eksportuj mimo to',
    reviewWarningsFirst: 'Najpierw sprawdz ostrzezenia',
  }),
  tr: buildTaxPackageHotfix({
    exportPackage: 'Vergi paketini disa aktar',
    exportPackageLoading: 'Vergi paketi disa aktariliyor...',
    exportPackageFailed: 'Vergi paketi disa aktarilamadi.',
    exportPackagePanelTitle: 'Vergi paketini disa aktar',
    exportPackagePanelDescription: 'Secilen vergi yili icin indirilebilir bir paket hazirlayin.',
    includeFoundationMaterials: 'Uzun sureli temel belgeleri dahil et',
    includeFoundationMaterialsHint: 'Kira, kredi, satin alma ve benzeri temel belgeleri ekler.',
    packageScopeTransactionsCsv: 'Islem CSV',
    packageScopeTransactionsPdf: 'Islem PDF',
    packageScopeSummaryPdf: 'Ozet PDF',
    packageScopeDocuments: 'Vergiyle ilgili kaynak belgeler',
    packageScopeFoundationOptional: 'Istege bagli: temel belgeler',
    preparePackage: 'Paketi hazirla',
    packageStatusPending: 'Hazirlaniyor',
    packageStatusProcessing: 'Paketleniyor',
    packageStatusReady: 'Indirmeye hazir',
    packageDownloadSingle: 'Paketi indir',
    packageDownloadPart: '{{part}}. parcayi indir',
    packageFailureTitle: 'Paket hazirlanamadi',
    packageFailureDocumentCount: 'Belge sayisi',
    packageFailureEstimatedSize: 'Tahmini boyut',
    packageFailureLargestFamily: 'En buyuk belge grubu',
    exportPackagePreviewLoading: 'Disa aktarma uyarilari kontrol ediliyor...',
    exportPackagePreviewFailed: 'Disa aktarma uyarilari kontrol edilemedi.',
    exportPackageWarningTitle: 'Disa aktarmadan once bu maddeleri inceleyin',
    exportPackageWarningDescription: 'Paket yine de disa aktarilabilir, ancak bu acik maddeler vergi dosyasinin kalitesini dusurebilir.',
    exportPackageWarningPendingTransactions: 'Inceleme bekleyen islemler',
    exportPackageWarningPendingDocuments: 'Inceleme bekleyen belgeler',
    exportPackageWarningFallbackYears: 'Yukleme tarihine gore atanan belgeler',
    exportPackageWarningSkippedFiles: 'Disa aktarmaya dahil edilmeyen dosyalar',
    reviewTransactionsBeforeExport: 'Islemleri incele',
    reviewDocumentsBeforeExport: 'Belgeleri incele',
    continueExportPackage: 'Yine de disa aktar',
    reviewWarningsFirst: 'Once uyarilari incele',
  }),
  bs: buildTaxPackageHotfix({
    exportPackage: 'Izvezi poreski paket',
    exportPackageLoading: 'Izvoz poreskog paketa je u toku...',
    exportPackageFailed: 'Izvoz poreskog paketa nije uspio.',
    exportPackagePanelTitle: 'Izvezi poreski paket',
    exportPackagePanelDescription: 'Pripremite paket za preuzimanje za odabranu poresku godinu.',
    includeFoundationMaterials: 'Ukljuci dugorocne osnovne materijale',
    includeFoundationMaterialsHint: 'Dodaje ugovore o najmu, kreditu, kupovini i slicne osnovne dokumente.',
    packageScopeTransactionsCsv: 'CSV transakcija',
    packageScopeTransactionsPdf: 'PDF transakcija',
    packageScopeSummaryPdf: 'PDF sazetka',
    packageScopeDocuments: 'Izvorni poreski dokumenti',
    packageScopeFoundationOptional: 'Opcionalno: osnovni materijali',
    preparePackage: 'Pripremi paket',
    packageStatusPending: 'Priprema',
    packageStatusProcessing: 'Pakovanje',
    packageStatusReady: 'Spremno za preuzimanje',
    packageDownloadSingle: 'Preuzmi paket',
    packageDownloadPart: 'Preuzmi dio {{part}}',
    packageFailureTitle: 'Paket nije mogao biti pripremljen',
    packageFailureDocumentCount: 'Broj dokumenata',
    packageFailureEstimatedSize: 'Procijenjena velicina',
    packageFailureLargestFamily: 'Najveca porodica dokumenata',
    exportPackagePreviewLoading: 'Provjera upozorenja prije izvoza...',
    exportPackagePreviewFailed: 'Upozorenja za izvoz nije bilo moguce provjeriti.',
    exportPackageWarningTitle: 'Pregledajte ove stavke prije izvoza',
    exportPackageWarningDescription: 'Paket i dalje mozete izvesti, ali ove otvorene stavke mogu umanjiti kvalitet poreskog paketa.',
    exportPackageWarningPendingTransactions: 'Transakcije koje cekaju pregled',
    exportPackageWarningPendingDocuments: 'Dokumenti koji cekaju pregled',
    exportPackageWarningFallbackYears: 'Dokumenti svrstani po datumu otpremanja',
    exportPackageWarningSkippedFiles: 'Datoteke izostavljene iz izvoza',
    reviewTransactionsBeforeExport: 'Pregledaj transakcije',
    reviewDocumentsBeforeExport: 'Pregledaj dokumente',
    continueExportPackage: 'Ipak izvezi',
    reviewWarningsFirst: 'Prvo pregledaj upozorenja',
  }),
};

const TAX_PACKAGE_REVIEW_COPY_OVERRIDES: Record<SupportedLanguage, {
  reviewTransactionsBeforeExport: string;
  reviewDocumentsBeforeExport: string;
  reviewDocumentsByYear: string;
}> = {
  de: {
    reviewTransactionsBeforeExport: 'Noch offene Transaktionen pruefen',
    reviewDocumentsBeforeExport: 'Noch offene Dokumente pruefen',
    reviewDocumentsByYear: 'Dokumente dieses Steuerjahres pruefen',
  },
  en: {
    reviewTransactionsBeforeExport: 'Review pending transactions',
    reviewDocumentsBeforeExport: 'Review pending documents',
    reviewDocumentsByYear: 'Review documents from this tax year',
  },
  zh: {
    reviewTransactionsBeforeExport: '查看待审核交易',
    reviewDocumentsBeforeExport: '查看待审核文档',
    reviewDocumentsByYear: '查看该税年文档',
  },
  fr: {
    reviewTransactionsBeforeExport: 'Verifier les transactions en attente',
    reviewDocumentsBeforeExport: 'Verifier les documents en attente',
    reviewDocumentsByYear: 'Verifier les documents de cette annee fiscale',
  },
  ru: {
    reviewTransactionsBeforeExport: 'Проверить ожидающие операции',
    reviewDocumentsBeforeExport: 'Проверить ожидающие документы',
    reviewDocumentsByYear: 'Проверить документы этого налогового года',
  },
  hu: {
    reviewTransactionsBeforeExport: 'Fuggoben levo tranzakciok ellenorzese',
    reviewDocumentsBeforeExport: 'Fuggoben levo dokumentumok ellenorzese',
    reviewDocumentsByYear: 'Ennek az adoevnek a dokumentumai',
  },
  pl: {
    reviewTransactionsBeforeExport: 'Sprawdz oczekujace transakcje',
    reviewDocumentsBeforeExport: 'Sprawdz oczekujace dokumenty',
    reviewDocumentsByYear: 'Sprawdz dokumenty z tego roku podatkowego',
  },
  tr: {
    reviewTransactionsBeforeExport: 'Bekleyen islemleri incele',
    reviewDocumentsBeforeExport: 'Bekleyen belgeleri incele',
    reviewDocumentsByYear: 'Bu vergi yilinin belgelerini incele',
  },
  bs: {
    reviewTransactionsBeforeExport: 'Pregledaj transakcije na cekanju',
    reviewDocumentsBeforeExport: 'Pregledaj dokumente na cekanju',
    reviewDocumentsByYear: 'Pregledaj dokumente ove poreske godine',
  },
};

(Object.keys(TAX_PACKAGE_REVIEW_COPY_OVERRIDES) as SupportedLanguage[]).forEach((language) => {
  const reports = TAX_PACKAGE_HOTFIXES[language].reports as LocaleObject | undefined;
  const taxFormCopy = reports?.taxForm as LocaleObject | undefined;
  if (taxFormCopy) {
    Object.assign(taxFormCopy, TAX_PACKAGE_REVIEW_COPY_OVERRIDES[language]);
  }
});

const DOCUMENT_EXPORT_ZIP_HOTFIXES: Record<SupportedLanguage, LocaleObject> = {
  de: buildDocumentExportZipHotfix({
    exportZipYearHint: 'Waehlen Sie das Dateijahr fuer den Export. Massgeblich ist das zugeordnete Dokumentjahr, nicht das Upload-Datum.',
    exportZipNoYears: 'Es sind noch keine exportierbaren Dokumentjahre verfuegbar.',
    fileYearLabel: 'Dateijahr',
    filesLabel: 'Dateien',
    estimatedSizeLabel: 'Geschaetzte Groesse',
    exportZipLargeHint: 'Ein grosser Export wurde erkannt. Die ZIP-Datei wird direkt im Browser heruntergeladen, damit die Seite das komplette Archiv nicht im Speicher halten muss.',
    exportZipDirectDownloadHint: 'Die ZIP-Datei wird direkt in Ihrem Browser heruntergeladen.',
  }),
  en: buildDocumentExportZipHotfix({
    exportZipYearHint: 'Choose the file year to export. The year is based on the document attribution year, not the upload year.',
    exportZipNoYears: 'No attributable file years are available yet for export.',
    fileYearLabel: 'File year',
    filesLabel: 'files',
    estimatedSizeLabel: 'estimated size',
    exportZipLargeHint: 'Large export detected. The browser will download it directly so the page does not need to keep the full ZIP in memory.',
    exportZipDirectDownloadHint: 'The ZIP will download directly in your browser.',
  }),
  zh: buildDocumentExportZipHotfix({
    exportZipYearHint: '请选择要导出的文件年度。这里使用文档归属年份，而不是上传年份。',
    exportZipNoYears: '目前还没有可按归属年份导出的文件。',
    fileYearLabel: '文件年度',
    filesLabel: '文件',
    estimatedSizeLabel: '预计大小',
    exportZipLargeHint: '检测到较大的导出内容。ZIP 将直接在浏览器中下载，这样页面无需一直保留完整压缩包。',
    exportZipDirectDownloadHint: 'ZIP 将直接在浏览器中下载。',
  }),
  fr: buildDocumentExportZipHotfix({
    exportZipYearHint: "Choisissez l'annee de document a exporter. L'annee utilisee est l'annee d'attribution du document, pas l'annee de televersement.",
    exportZipNoYears: "Aucune annee de document exportable n'est encore disponible.",
    fileYearLabel: 'Annee du document',
    filesLabel: 'fichiers',
    estimatedSizeLabel: 'taille estimee',
    exportZipLargeHint: "Export volumineux detecte. Le fichier ZIP sera telecharge directement dans le navigateur pour eviter de conserver l'archive complete en memoire sur la page.",
    exportZipDirectDownloadHint: 'Le fichier ZIP sera telecharge directement dans votre navigateur.',
  }),
  ru: buildDocumentExportZipHotfix({
    exportZipYearHint: 'Vyberite god dokumentov dlya eksporta. Ispolzuetsya god atributsii dokumenta, a ne god zagruzki.',
    exportZipNoYears: 'Poka net godov dokumentov, dostupnykh dlya eksporta.',
    fileYearLabel: 'God dokumentov',
    filesLabel: 'faily',
    estimatedSizeLabel: 'predpolagaemyi razmer',
    exportZipLargeHint: 'Obnaruzhen eksport bolshogo obema. ZIP budet zagruzhen napryamuyu v brauzere, chtoby stranitsa ne derzhala vsyu arkhivnuyu kopiyu v pamyati.',
    exportZipDirectDownloadHint: 'ZIP budet zagruzhen napryamuyu v vashem brauzere.',
  }),
  hu: buildDocumentExportZipHotfix({
    exportZipYearHint: 'Valassza ki az exportalando dokumentumevet. Itt a dokumentumhoz rendelt evet hasznaljuk, nem a feltoltes evet.',
    exportZipNoYears: 'Meg nincsen exportalhato dokumentumev.',
    fileYearLabel: 'Dokumentumev',
    filesLabel: 'fajl',
    estimatedSizeLabel: 'becsult meret',
    exportZipLargeHint: 'Nagy exportot eszleltunk. A ZIP fajl kozvetlenul a bongeszoben tolodik le, igy az oldalnak nem kell a teljes archivumot memoriaban tartania.',
    exportZipDirectDownloadHint: 'A ZIP fajl kozvetlenul a bongeszoben fog letoltodni.',
  }),
  pl: buildDocumentExportZipHotfix({
    exportZipYearHint: 'Wybierz rok dokumentow do eksportu. Uzywany jest rok przypisania dokumentu, a nie rok przeslania.',
    exportZipNoYears: 'Nie ma jeszcze lat dokumentow dostepnych do eksportu.',
    fileYearLabel: 'Rok dokumentow',
    filesLabel: 'pliki',
    estimatedSizeLabel: 'szacowany rozmiar',
    exportZipLargeHint: 'Wykryto duzy eksport. Plik ZIP zostanie pobrany bezposrednio w przegladarce, aby strona nie musiala trzymac calego archiwum w pamieci.',
    exportZipDirectDownloadHint: 'Plik ZIP zostanie pobrany bezposrednio w przegladarce.',
  }),
  tr: buildDocumentExportZipHotfix({
    exportZipYearHint: 'Disa aktarilacak belge yilini secin. Burada yukleme yili degil, belgeye atanan yil kullanilir.',
    exportZipNoYears: 'Henuz disa aktarilabilecek bir belge yili yok.',
    fileYearLabel: 'Belge yili',
    filesLabel: 'dosya',
    estimatedSizeLabel: 'tahmini boyut',
    exportZipLargeHint: 'Buyuk bir disa aktarim algilandi. ZIP dosyasi dogrudan tarayicida indirilecek; boylece sayfanin tum arsivi bellekte tutmasi gerekmeyecek.',
    exportZipDirectDownloadHint: 'ZIP dosyasi dogrudan tarayicinizda indirilecektir.',
  }),
  bs: buildDocumentExportZipHotfix({
    exportZipYearHint: 'Odaberite godinu dokumenata za izvoz. Koristi se godina pripisana dokumentu, a ne godina uploada.',
    exportZipNoYears: 'Jos nema godina dokumenata dostupnih za izvoz.',
    fileYearLabel: 'Godina dokumenta',
    filesLabel: 'dokumenti',
    estimatedSizeLabel: 'procijenjena velicina',
    exportZipLargeHint: 'Otkriven je veliki izvoz. ZIP ce se preuzeti direktno u pregledniku kako stranica ne bi morala drzati cijelu arhivu u memoriji.',
    exportZipDirectDownloadHint: 'ZIP ce se preuzeti direktno u vasem pregledniku.',
  }),
};

const TAX_FIELD_LABEL_HOTFIXES: Record<SupportedLanguage, LocaleObject> = {
  de: buildTaxFieldLabelHotfix({
    issuer: 'Aussteller',
    recipient: 'Empfaenger',
    documentDate: 'Belegdatum',
    documentYear: 'Dokumentenjahr',
    yearBasis: 'Jahresgrundlage',
    yearConfidence: 'Jahres-Konfidenz',
    referenceNumber: 'Aktenzahl',
  }),
  en: buildTaxFieldLabelHotfix({
    issuer: 'Issuer',
    recipient: 'Recipient',
    documentDate: 'Document date',
    documentYear: 'Document year',
    yearBasis: 'Year basis',
    yearConfidence: 'Year confidence',
    referenceNumber: 'Reference number',
  }),
  zh: buildTaxFieldLabelHotfix({
    issuer: '开票方',
    recipient: '收票方',
    documentDate: '文件日期',
    documentYear: '归属年份',
    yearBasis: '年份依据',
    yearConfidence: '年份置信度',
  }),
  fr: buildTaxFieldLabelHotfix({
    issuer: 'Emetteur',
    recipient: 'Destinataire',
    documentDate: 'Date du document',
    documentYear: 'Annee du document',
    yearBasis: "Base de l'annee",
    yearConfidence: "Confiance de l'annee",
    referenceNumber: 'Numero de reference',
  }),
  ru: buildTaxFieldLabelHotfix({
    issuer: 'Отправитель',
    recipient: 'Получатель',
    documentDate: 'Дата документа',
    documentYear: 'Год документа',
    yearBasis: 'Основание года',
    yearConfidence: 'Уверенность года',
  }),
  hu: buildTaxFieldLabelHotfix({
    issuer: 'Kibocsato',
    recipient: 'Cimzett',
    documentDate: 'Dokumentum datuma',
    documentYear: 'Dokumentum eve',
    yearBasis: 'Ev alapja',
    yearConfidence: 'Ev megbizhatosaga',
    referenceNumber: 'Ugyszam',
  }),
  pl: buildTaxFieldLabelHotfix({
    issuer: 'Wystawca',
    recipient: 'Odbiorca',
    documentDate: 'Data dokumentu',
    documentYear: 'Rok dokumentu',
    yearBasis: 'Podstawa roku',
    yearConfidence: 'Pewnosc roku',
    referenceNumber: 'Numer sprawy',
  }),
  tr: buildTaxFieldLabelHotfix({
    issuer: 'Duzenleyen',
    recipient: 'Alici',
    documentDate: 'Belge tarihi',
    documentYear: 'Belge yili',
    yearBasis: 'Yil temeli',
    yearConfidence: 'Yil guveni',
    referenceNumber: 'Dosya numarasi',
  }),
  bs: buildTaxFieldLabelHotfix({
    issuer: 'Izdavalac',
    recipient: 'Primalac',
    documentDate: 'Datum dokumenta',
    documentYear: 'Godina dokumenta',
    yearBasis: 'Osnova godine',
    yearConfidence: 'Pouzdanost godine',
    referenceNumber: 'Broj predmeta',
  }),
};

const TAX_FIELD_DATE_HOTFIXES: Record<SupportedLanguage, LocaleObject> = {
  de: buildTaxFieldLabelHotfix({
    issuer: 'Aussteller',
    recipient: 'Empfaenger',
    documentDate: 'Belegdatum',
    documentYear: 'Dokumentenjahr',
    yearBasis: 'Jahresgrundlage',
    yearConfidence: 'Jahres-Konfidenz',
    bescheidDate: 'Bescheiddatum',
    referenceNumber: 'Aktenzahl',
    dueDate: 'Faellig am',
  }),
  en: buildTaxFieldLabelHotfix({
    issuer: 'Issuer',
    recipient: 'Recipient',
    documentDate: 'Document date',
    documentYear: 'Document year',
    yearBasis: 'Year basis',
    yearConfidence: 'Year confidence',
    bescheidDate: 'Assessment date',
    referenceNumber: 'Reference number',
    dueDate: 'Due date',
  }),
  zh: buildTaxFieldLabelHotfix({
    issuer: '开票方',
    recipient: '收票方',
    documentDate: '文件日期',
    documentYear: '归属年份',
    yearBasis: '年份依据',
    yearConfidence: '年份置信度',
    bescheidDate: '税单日期',
    dueDate: '到期日',
  }),
  fr: buildTaxFieldLabelHotfix({
    issuer: 'Emetteur',
    recipient: 'Destinataire',
    documentDate: 'Date du document',
    documentYear: 'Annee du document',
    yearBasis: "Base de l'annee",
    yearConfidence: "Confiance de l'annee",
    bescheidDate: "Date d'avis",
    referenceNumber: 'Numero de reference',
    dueDate: "Date d'echeance",
  }),
  ru: buildTaxFieldLabelHotfix({
    issuer: 'Отправитель',
    recipient: 'Получатель',
    documentDate: 'Дата документа',
    documentYear: 'Год документа',
    yearBasis: 'Основание года',
    yearConfidence: 'Уверенность года',
    bescheidDate: 'Дата решения',
    dueDate: 'Срок оплаты',
  }),
  hu: buildTaxFieldLabelHotfix({
    issuer: 'Kibocsato',
    recipient: 'Cimzett',
    documentDate: 'Dokumentum datuma',
    documentYear: 'Dokumentum eve',
    yearBasis: 'Ev alapja',
    yearConfidence: 'Ev megbizhatosaga',
    bescheidDate: 'Hatarozat datuma',
    referenceNumber: 'Ugyszam',
    dueDate: 'Esedekesseg',
  }),
  pl: buildTaxFieldLabelHotfix({
    issuer: 'Wystawca',
    recipient: 'Odbiorca',
    documentDate: 'Data dokumentu',
    documentYear: 'Rok dokumentu',
    yearBasis: 'Podstawa roku',
    yearConfidence: 'Pewnosc roku',
    bescheidDate: 'Data decyzji',
    referenceNumber: 'Numer sprawy',
    dueDate: 'Termin platnosci',
  }),
  tr: buildTaxFieldLabelHotfix({
    issuer: 'Duzenleyen',
    recipient: 'Alici',
    documentDate: 'Belge tarihi',
    documentYear: 'Belge yili',
    yearBasis: 'Yil temeli',
    yearConfidence: 'Yil guveni',
    bescheidDate: 'Vergi karari tarihi',
    referenceNumber: 'Dosya numarasi',
    dueDate: 'Vade tarihi',
  }),
  bs: buildTaxFieldLabelHotfix({
    issuer: 'Izdavalac',
    recipient: 'Primalac',
    documentDate: 'Datum dokumenta',
    documentYear: 'Godina dokumenta',
    yearBasis: 'Osnova godine',
    yearConfidence: 'Pouzdanost godine',
    bescheidDate: 'Datum rjesenja',
    referenceNumber: 'Broj predmeta',
    dueDate: 'Rok dospijeca',
  }),
};

const CLASSIFICATION_MEMORY_HOTFIXES: Record<SupportedLanguage, LocaleObject> = {
  de: buildClassificationMemoryHotfix({
    pageTitle: 'Regeln und Erinnerungen',
    pageSubtitle: 'Diese Erinnerungen entstehen automatisch, wenn Sie Kategorien, Abzugsfaehigkeit oder Bankbuchungsaktionen bestaetigen, damit aehnliche Transaktionen beim naechsten Mal richtig landen.',
    title: 'Regeln und Erinnerungen',
    subtitle: 'Kategorien, Abzugsfaehigkeits-Overrides und Regeln zur automatischen Verarbeitung, die beim naechsten Mal wiederverwendet werden.',
    empty: 'Noch keine Lernregeln. Regeln werden automatisch erstellt, wenn Sie Kategorien, Abzugsentscheidungen oder Bankzeilen bestaetigen.',
    categorySectionDescription: 'Gespeicherte Kategoriekorrekturen, damit aehnliche Transaktionen im richtigen Bereich landen.',
    automationSectionTitle: 'Regeln zur automatischen Verarbeitung',
    automationSectionDescription: 'Aus bestaetigten Bankbuchungs-Erstellungen gelernte Muster, die beim naechsten Mal automatisch erstellt werden koennen.',
    searchAutomationPlaceholder: 'Nach Regeln zur automatischen Verarbeitung suchen...',
    automationEmpty: 'Noch keine Regeln zur automatischen Verarbeitung. Sie erscheinen, nachdem Sie das Erstellen einer Bankbuchung bestaetigt haben.',
    selectAllAutomation: 'Alle Regeln zur automatischen Verarbeitung auswaehlen',
    automationActionAutoCreate: 'Automatisch erstellen',
    reasonAutomation: 'Gelernt, als Sie das Erstellen einer Bankbuchung bestaetigt haben.',
    reasonAutomationFrozen: 'Diese Regel zur automatischen Verarbeitung wurde nach wiederholten widerspruechlichen Korrekturen eingefroren.',
    reasonAutomationConflict: 'Die Regel zur automatischen Verarbeitung wurde durch spaetere Korrekturen in Frage gestellt',
    deductibilitySectionDescription: 'Gespeicherte Abzugsfaehig-/Nicht-abzugsfaehig-Overrides, die beim naechsten Mal wiederverwendet werden.',
    action: 'Aktion',
  }),
  en: buildClassificationMemoryHotfix({
    pageTitle: 'Rules and Memory',
    pageSubtitle: 'These memories are created automatically when you confirm categories, deductibility decisions, or bank statement actions, helping similar transactions land in the right place next time.',
    title: 'Rules and Memory',
    subtitle: 'Category memory, deductibility overrides, and automatic handling rules that the system will reuse next time.',
    empty: 'No learning rules yet. Rules are created automatically when you confirm categories, deductibility decisions, or bank statement actions.',
    categorySectionDescription: 'Saved category corrections that help similar transactions land in the right bucket.',
    automationSectionTitle: 'Automatic handling rules',
    automationSectionDescription: 'Patterns learned from confirmed bank statement creations that can be auto-created next time.',
    searchAutomationPlaceholder: 'Search automatic handling rules...',
    automationEmpty: 'No automatic handling rules yet. They will appear after you confirm creating a bank statement transaction.',
    selectAllAutomation: 'Select all automatic handling rules',
    automationActionAutoCreate: 'Auto-create',
    reasonAutomation: 'Learned when you confirmed creating a bank statement transaction.',
    reasonAutomationFrozen: 'This automatic handling rule was frozen after repeated conflicting corrections.',
    reasonAutomationConflict: 'The automatic handling rule was challenged by later corrections',
    deductibilitySectionDescription: 'Saved deductible and non-deductible overrides that the system will reuse next time.',
    action: 'Action',
  }),
  zh: buildClassificationMemoryHotfix({
    pageTitle: '规则与记忆',
    pageSubtitle: '当您确认分类、抵扣判断或银行流水动作时，系统会自动形成这些记忆，帮助相似交易下次直接落到正确位置。',
    title: '规则与记忆',
    subtitle: '下次会被重复使用的分类记忆、抵扣覆盖规则和自动处理规则。',
    empty: '还没有学习到任何规则。当您确认分类、抵扣判断或银行流水动作后，系统会自动创建规则。',
    categorySectionDescription: '保存的分类纠正，帮助相似交易下次直接进入正确分类。',
    automationSectionTitle: '自动处理规则',
    automationSectionDescription: '从已确认的新建银行流水交易中学到的模式，下次可直接自动创建。',
    searchAutomationPlaceholder: '搜索自动处理规则...',
    automationEmpty: '还没有自动处理规则。您确认创建银行流水交易后，这里就会出现。',
    selectAllAutomation: '全选自动处理规则',
    automationActionAutoCreate: '自动创建',
    reasonAutomation: '当您确认创建银行流水交易时学到的规则。',
    reasonAutomationFrozen: '这条自动处理规则因多次冲突修正已被冻结。',
    reasonAutomationConflict: '这条自动处理规则被后续修正提出了冲突',
    deductibilitySectionDescription: '保存的可抵扣/不可抵扣覆盖规则，下次会自动复用。',
    action: '动作',
  }),
  fr: buildClassificationMemoryHotfix({
    pageTitle: 'Regles et memoire',
    pageSubtitle: 'Ces memoires sont creees automatiquement lorsque vous confirmez des categories, des decisions de deductibilite ou des actions sur des releves bancaires, afin que les transactions similaires tombent au bon endroit la prochaine fois.',
    title: 'Regles et memoire',
    subtitle: 'Memoire de categorie, remplacements de deductibilite et regles de traitement automatique reutilises la prochaine fois.',
    empty: 'Aucune regle apprise pour le moment. Les regles sont creees automatiquement lorsque vous confirmez des categories, des decisions de deductibilite ou des actions sur des releves bancaires.',
    categorySectionDescription: 'Corrections de categorie enregistrees pour orienter les transactions similaires vers le bon classement.',
    automationSectionTitle: 'Regles de traitement automatique',
    automationSectionDescription: 'Modeles appris a partir de creations confirmees dans le releve bancaire pouvant etre recrées automatiquement la prochaine fois.',
    searchAutomationPlaceholder: 'Rechercher des regles de traitement automatique...',
    automationEmpty: 'Aucune regle de traitement automatique pour le moment. Elles apparaitront apres confirmation de la creation d une transaction bancaire.',
    selectAllAutomation: 'Selectionner toutes les regles de traitement automatique',
    automationActionAutoCreate: 'Creation auto',
    reasonAutomation: 'Apprise lorsque vous avez confirme la creation d une transaction de releve bancaire.',
    reasonAutomationFrozen: 'Cette regle de traitement automatique a ete gelee apres des corrections contradictoires repetees.',
    reasonAutomationConflict: 'La regle de traitement automatique a ete contestee par des corrections ulterieures',
    deductibilitySectionDescription: 'Overrides deductibles et non deductibles enregistres pour reutilisation future.',
    action: 'Action',
  }),
  ru: buildClassificationMemoryHotfix({
    pageTitle: 'Pravila i pamyat',
    pageSubtitle: 'Eti pravila sozdajutsya avtomaticheski, kogda vy podtverzhdaete kategorii, resheniya po vychetu ili deistviya po bankovskim vypiskam, chtoby pokhozhie operatsii v sleduyushchiy raz popadali v nuzhnoe mesto.',
    title: 'Pravila i pamyat',
    subtitle: 'Pamyat kategoriy, pereopredeleniya vychetov i pravila avtomaticheskoy obrabotki, kotorye sistema ispolzuet povtorno.',
    empty: 'Pravil poka net. Oni sozdajutsya avtomaticheski, kogda vy podtverzhdaete kategorii, resheniya po vychetu ili deistviya po bankovskim vypiskam.',
    categorySectionDescription: 'Sohranennye ispravleniya kategoriy, chtoby pokhozhie operatsii srazu popadali v pravilnyy razdel.',
    automationSectionTitle: 'Pravila avtomaticheskoy obrabotki',
    automationSectionDescription: 'Shablony, vyuchennye posle podtverzhdennogo sozdaniya operatsii iz bankovskoy vypiski, kotorye mozhno avtomaticheski sozdavat v sleduyushchiy raz.',
    searchAutomationPlaceholder: 'Iskat pravila avtomaticheskoy obrabotki...',
    automationEmpty: 'Pravil avtomaticheskoy obrabotki poka net. Oni poyavyatsya posle podtverzhdeniya sozdaniya operatsii iz bankovskoy vypiski.',
    selectAllAutomation: 'Vybrat vse pravila avtomaticheskoy obrabotki',
    automationActionAutoCreate: 'Sozdavat avtomaticheski',
    reasonAutomation: 'Pravilo sozdano posle podtverzhdeniya sozdaniya operatsii iz bankovskoy vypiski.',
    reasonAutomationFrozen: 'Eto pravilo avtomaticheskoy obrabotki bylo zamorozheno posle povtoryayushchikhsya protivorechivykh ispravleniy.',
    reasonAutomationConflict: 'Pravilo avtomaticheskoy obrabotki bylo osporeno pozdneyshimi ispravleniyami',
    deductibilitySectionDescription: 'Sohranennye pereopredeleniya vycheta i nevycheta, kotorye budut ispolzovatsya povtorno.',
    action: 'Deystvie',
  }),
  hu: buildClassificationMemoryHotfix({
    pageTitle: 'Szabalyok es memoria',
    pageSubtitle: 'Ezek a memoriak automatikusan letrejonnek, amikor kategoriakat, levonhatosagi donteseket vagy bankszamlakivonat-muveleteket hagy jo, hogy a hasonlo tranzakciok legkozelebb a megfelelo helyre keruljenek.',
    title: 'Szabalyok es memoria',
    subtitle: 'Kategoriamemoria, levonhatosagi felulirasok es automatikus feldolgozasi szabalyok, amelyeket a rendszer legkozelebb ujra felhasznal.',
    empty: 'Meg nincsenek tanult szabalyok. A rendszer automatikusan hoz letre szabalyokat, amikor kategoriakat, levonhatosagi donteseket vagy bankszamlakivonat-muveleteket hagy jova.',
    categorySectionDescription: 'Mentett kategoriakorrekciok, hogy a hasonlo tranzakciok kovetkezo alkalommal a megfelelo kategoriaba keruljenek.',
    automationSectionTitle: 'Automatikus feldolgozasi szabalyok',
    automationSectionDescription: 'A megerositett bankszamlakivonat-tranzakcio letrehozasokbol tanult mintak, amelyek legkozelebb automatikusan letrehozhatok.',
    searchAutomationPlaceholder: 'Automatikus feldolgozasi szabalyok keresese...',
    automationEmpty: 'Meg nincsenek automatikus feldolgozasi szabalyok. Akkor jelennek meg, amikor megerositi egy bankszamlakivonat-tranzakcio letrehozasat.',
    selectAllAutomation: 'Osszes automatikus feldolgozasi szabaly kijelolese',
    automationActionAutoCreate: 'Automatikus letrehozas',
    reasonAutomation: 'Akkor tanulta meg a rendszer, amikor megerositette a bankszamlakivonat-tranzakcio letrehozasat.',
    reasonAutomationFrozen: 'Ez az automatikus feldolgozasi szabaly tobbszori ellentmondo javitas utan befagyasztasra kerult.',
    reasonAutomationConflict: 'Az automatikus feldolgozasi szabaly kesobbi javitasok miatt ellentmondasossa valt',
    deductibilitySectionDescription: 'Mentett levonhato es nem levonhato felulirasok, amelyeket a rendszer legkozelebb ujra felhasznal.',
    action: 'Muvelet',
  }),
  pl: buildClassificationMemoryHotfix({
    pageTitle: 'Reguly i pamiec',
    pageSubtitle: 'Ta pamiec powstaje automatycznie, gdy potwierdzasz kategorie, decyzje o odliczalnosci lub akcje na wyciagu bankowym, aby podobne transakcje nastepnym razem trafialy we wlasciwe miejsce.',
    title: 'Reguly i pamiec',
    subtitle: 'Pamiec kategorii, nadpisania odliczalnosci i reguly automatycznej obslugi, ktore system wykorzysta ponownie nastepnym razem.',
    empty: 'Brak wyuczonych regul. Reguly sa tworzone automatycznie, gdy potwierdzasz kategorie, decyzje o odliczalnosci lub akcje na wyciagu bankowym.',
    categorySectionDescription: 'Zapisane korekty kategorii, aby podobne transakcje nastepnym razem trafialy do wlasciwej kategorii.',
    automationSectionTitle: 'Reguly automatycznej obslugi',
    automationSectionDescription: 'Wzorce wyuczone z potwierdzonych utworzen transakcji z wyciagu bankowego, ktore mozna nastepnym razem utworzyc automatycznie.',
    searchAutomationPlaceholder: 'Szukaj regul automatycznej obslugi...',
    automationEmpty: 'Nie ma jeszcze regul automatycznej obslugi. Pojawia sie po potwierdzeniu utworzenia transakcji z wyciagu bankowego.',
    selectAllAutomation: 'Zaznacz wszystkie reguly automatycznej obslugi',
    automationActionAutoCreate: 'Utworz automatycznie',
    reasonAutomation: 'Nauczone po potwierdzeniu utworzenia transakcji z wyciagu bankowego.',
    reasonAutomationFrozen: 'Ta regula automatycznej obslugi zostala zamrozona po powtarzajacych sie sprzecznych korektach.',
    reasonAutomationConflict: 'Regula automatycznej obslugi zostala zakwestionowana przez pozniejsze korekty',
    deductibilitySectionDescription: 'Zapisane nadpisania odliczalne i nieodliczalne, ktore system wykorzysta ponownie.',
    action: 'Akcja',
  }),
  tr: buildClassificationMemoryHotfix({
    pageTitle: 'Kurallar ve hafiza',
    pageSubtitle: 'Bu hafiza, kategorileri, indirilebilirlik kararlarini veya banka ekstresi islemlerini onayladiginizda otomatik olarak olusur; boylece benzer islemler bir sonraki sefer dogru yere duser.',
    title: 'Kurallar ve hafiza',
    subtitle: 'Kategori hafizasi, indirilebilirlik gecersiz kilmalari ve sistemin bir sonraki sefer yeniden kullanacagi otomatik isleme kurallari.',
    empty: 'Henuz ogrenilmis kural yok. Kategorileri, indirilebilirlik kararlarini veya banka ekstresi islemlerini onayladiginizda kurallar otomatik olarak olusturulur.',
    categorySectionDescription: 'Benzer islemlerin bir sonraki sefer dogru kategoriye dusmesine yardimci olan kaydedilmis kategori duzeltmeleri.',
    automationSectionTitle: 'Otomatik isleme kurallari',
    automationSectionDescription: 'Onaylanmis banka ekstresi islem olusturmalarindan ogrenilen ve bir sonraki sefer otomatik olusturulabilen desenler.',
    searchAutomationPlaceholder: 'Otomatik isleme kurallarini ara...',
    automationEmpty: 'Henuz otomatik isleme kurali yok. Bir banka ekstresi islemi olusturmayi onayladiginizda burada gorunurler.',
    selectAllAutomation: 'Tum otomatik isleme kurallarini sec',
    automationActionAutoCreate: 'Otomatik olustur',
    reasonAutomation: 'Bir banka ekstresi islemi olusturmayi onayladiginizda ogrenildi.',
    reasonAutomationFrozen: 'Bu otomatik isleme kurali, tekrar eden celiskili duzeltmelerden sonra donduruldu.',
    reasonAutomationConflict: 'Otomatik isleme kurali daha sonraki duzeltmelerle sorgulandi',
    deductibilitySectionDescription: 'Sistemin tekrar kullanacagi kaydedilmis indirilebilir ve indirilemez gecersiz kilmalar.',
    action: 'Islem',
  }),
  bs: buildClassificationMemoryHotfix({
    pageTitle: 'Pravila i memorija',
    pageSubtitle: 'Ova memorija se automatski stvara kada potvrdite kategorije, odluke o odbitku ili radnje nad bankovnim izvodom, kako bi slicne transakcije sljedeci put zavrsile na pravom mjestu.',
    title: 'Pravila i memorija',
    subtitle: 'Memorija kategorija, preinake odbitka i pravila automatske obrade koja ce sistem sljedeci put ponovo koristiti.',
    empty: 'Jos nema naucenih pravila. Pravila se automatski kreiraju kada potvrdite kategorije, odluke o odbitku ili radnje nad bankovnim izvodom.',
    categorySectionDescription: 'Sacuvane korekcije kategorija kako bi slicne transakcije sljedeci put zavrsile u pravoj grupi.',
    automationSectionTitle: 'Pravila automatske obrade',
    automationSectionDescription: 'Obrasci nauceni iz potvrdjenih kreiranja transakcija sa bankovnog izvoda koji se sljedeci put mogu automatski kreirati.',
    searchAutomationPlaceholder: 'Pretrazi pravila automatske obrade...',
    automationEmpty: 'Jos nema pravila automatske obrade. Pojavice se nakon sto potvrdite kreiranje transakcije sa bankovnog izvoda.',
    selectAllAutomation: 'Oznaci sva pravila automatske obrade',
    automationActionAutoCreate: 'Automatski kreiraj',
    reasonAutomation: 'Nauceno kada ste potvrdili kreiranje transakcije sa bankovnog izvoda.',
    reasonAutomationFrozen: 'Ovo pravilo automatske obrade je zamrznuto nakon ponovljenih kontradiktornih ispravki.',
    reasonAutomationConflict: 'Pravilo automatske obrade je dovedeno u pitanje kasnijim ispravkama',
    deductibilitySectionDescription: 'Sacuvane preinake za odbitno i neodbitno koje ce sistem ponovo koristiti.',
    action: 'Akcija',
  }),
};

const encodeWindows1252 = (value: string): Uint8Array | null => {
  const bytes: number[] = [];

  for (const char of value) {
    const codePoint = char.codePointAt(0);
    if (codePoint == null) {
      return null;
    }

    if (codePoint <= 0xff) {
      bytes.push(codePoint);
      continue;
    }

    const mappedByte = CP1252_BYTE_BY_CODE_POINT.get(codePoint);
    if (mappedByte == null) {
      return null;
    }

    bytes.push(mappedByte);
  }

  return Uint8Array.from(bytes);
};

const replaceWindows1252Controls = (value: string): string =>
  Array.from(value, (char) => {
    const replacement = CP1252_CONTROL_REPLACEMENTS.get(char.charCodeAt(0));
    return replacement ?? char;
  }).join('');

export const repairMojibakeText = (value: string): string => {
  let repaired = value;

  for (let attempt = 0; attempt < 2; attempt += 1) {
    const hasControlChars = /[\u0080-\u009f]/.test(repaired);
    const looksLikeMojibake = MOJIBAKE_HINTS.some((hint) => repaired.includes(hint));

    if (!hasControlChars && !looksLikeMojibake) {
      break;
    }

    const bytes = encodeWindows1252(repaired);
    if (!bytes) {
      break;
    }

    try {
      const decoded = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
      if (decoded === repaired) {
        break;
      }
      repaired = decoded;
      continue;
    } catch {
      break;
    }
  }

  return replaceWindows1252Controls(repaired);
};

const repairLocaleValue = (value: LocaleNode): LocaleNode => {
  if (typeof value === 'string') {
    return repairMojibakeText(value);
  }

  if (Array.isArray(value)) {
    return value.map(repairLocaleValue);
  }

  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([key, nestedValue]) => [key, repairLocaleValue(nestedValue as LocaleNode)])
    );
  }

  return value;
};

const deepMerge = (base: LocaleObject, extra?: LocaleObject): LocaleObject => {
  if (!extra) {
    return base;
  }

  const merged: LocaleObject = { ...base };

  Object.entries(extra).forEach(([key, value]) => {
    const existing = merged[key];

    if (
      existing &&
      value &&
      typeof existing === 'object' &&
      typeof value === 'object' &&
      !Array.isArray(existing) &&
      !Array.isArray(value)
    ) {
      merged[key] = deepMerge(existing as LocaleObject, value as LocaleObject);
      return;
    }

    merged[key] = value;
  });

  return merged;
};

export const sanitizeLocaleResource = (
  language: SupportedLanguage,
  resource: Record<string, unknown>
): Record<string, unknown> =>
  repairLocaleValue(
    deepMerge(
      deepMerge(
        deepMerge(
          deepMerge(
            deepMerge(resource as LocaleObject, LOCALE_HOTFIXES[language]),
            TAX_PACKAGE_HOTFIXES[language]
          ),
          TAX_FIELD_LABEL_HOTFIXES[language]
        ),
        deepMerge(
          TAX_FIELD_DATE_HOTFIXES[language],
          CLASSIFICATION_MEMORY_HOTFIXES[language]
        )
      ),
      DOCUMENT_EXPORT_ZIP_HOTFIXES[language]
    )
  ) as Record<string, unknown>;
