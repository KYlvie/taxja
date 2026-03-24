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
  initializing: string;
  loadingLines: string;
  loadFailed: string;
  actionFailed: string;
  summaryTitle: string;
  importedAt: string;
  totalCount: string;
  autoProcessed: string;
  pendingReview: string;
  ignoredCount: string;
  confidence: string;
  linkedTransaction: string;
  noCounterparty: string;
  noPurpose: string;
  statusAutoCreated: string;
  statusMatchedExisting: string;
  statusIgnoredDuplicate: string;
  statusPendingReview: string;
  actionCreate: string;
  actionMatch: string;
  actionIgnore: string;
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
      initializing: config.initializing,
      loadingLines: config.loadingLines,
      loadFailed: config.loadFailed,
      actionFailed: config.actionFailed,
      summaryTitle: config.summaryTitle,
      importedAt: config.importedAt,
      totalCount: config.totalCount,
      autoProcessed: config.autoProcessed,
      pendingReview: config.pendingReview,
      ignoredCount: config.ignoredCount,
      confidence: config.confidence,
      linkedTransaction: config.linkedTransaction,
      noCounterparty: config.noCounterparty,
      noPurpose: config.noPurpose,
      status: {
        autoCreated: config.statusAutoCreated,
        matchedExisting: config.statusMatchedExisting,
        ignoredDuplicate: config.statusIgnoredDuplicate,
        pendingReview: config.statusPendingReview,
      },
      actions: {
        create: config.actionCreate,
        match: config.actionMatch,
        ignore: config.actionIgnore,
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

const buildProactiveReminderHotfix = (healthSummaryReminder: string): LocaleObject => ({
  ai: {
    proactive: {
      healthSummaryReminder,
    },
  },
});

const LOCALE_HOTFIXES: Partial<Record<SupportedLanguage, LocaleObject>> = {
  de: {
    ...buildExportAndSearchHotfix(
      'CSV exportieren',
      'PDF exportieren',
      'Nach Beschreibung oder Kategorie suchen...',
      'Nach Beschreibung suchen...'
    ),
    ...buildBankWorkbenchHotfix({
      title: 'Kontoauszugs-Arbeitsbereich',
      initializing: 'Kontoauszugs-Arbeitsbereich wird vorbereitet...',
      loadingLines: 'Kontoauszugszeilen werden geladen...',
      loadFailed: 'Der Kontoauszugs-Arbeitsbereich konnte nicht geladen werden.',
      actionFailed: 'Die Aktion fuer den Kontoauszug konnte nicht abgeschlossen werden.',
      summaryTitle: 'Importzusammenfassung',
      importedAt: 'Importiert am',
      totalCount: 'Gesamtzeilen',
      autoProcessed: 'Automatisch verarbeitet',
      pendingReview: 'Zur Bestaetigung',
      ignoredCount: 'Ignoriert',
      confidence: 'Konfidenz',
      linkedTransaction: 'Transaktion',
      noCounterparty: 'Unbekannte Gegenpartei',
      noPurpose: 'Kein Verwendungszweck verfuegbar.',
      statusAutoCreated: 'Automatisch erstellt',
      statusMatchedExisting: 'Bestehende Transaktion zugeordnet',
      statusIgnoredDuplicate: 'Duplikat ignoriert',
      statusPendingReview: 'Zur Bestaetigung',
      actionCreate: 'Transaktion erstellen',
      actionMatch: 'Bestehende zuordnen',
      actionIgnore: 'Als Duplikat ignorieren',
      emptyPending: 'Derzeit muessen keine Kontoauszugszeilen bestaetigt werden.',
      emptyResolved: 'Es gibt noch keine automatisch verarbeiteten Kontoauszugszeilen.',
      emptyIgnored: 'Es gibt noch keine ignorierten Duplikate.',
      pendingTitle: 'Zur Bestaetigung',
      pendingDescription: 'Positionen mit niedriger Konfidenz bleiben hier, bis Sie die passende Verarbeitung bestaetigen.',
      resolvedTitle: 'Automatisch verarbeitet',
      resolvedDescription: 'Diese Zeilen wurden automatisch erstellt oder einer bestehenden Transaktion zugeordnet.',
      ignoredTitle: 'Ignorierte Duplikate',
      ignoredDescription: 'Diese Zeilen wurden als Duplikate ignoriert und erzeugen keine neuen Transaktionen.',
      importBankStatement: 'Kontoauszug importieren',
      openBankWorkbench: 'Kontoauszugs-Arbeitsbereich oeffnen',
      bankWorkbenchHint: 'Oeffnen Sie den Kontoauszugs-Arbeitsbereich, um Eintraege mit niedriger Konfidenz zu pruefen, bestehende Transaktionen zuzuordnen und neue Transaktionen zu bestaetigen.',
    }),
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
    ...buildBankWorkbenchHotfix({
      title: 'Bank statement workbench',
      initializing: 'Preparing the bank statement workbench...',
      loadingLines: 'Loading statement lines...',
      loadFailed: 'Failed to load the bank statement workbench.',
      actionFailed: 'The bank statement action could not be completed.',
      summaryTitle: 'Import summary',
      importedAt: 'Imported',
      totalCount: 'Total lines',
      autoProcessed: 'Auto processed',
      pendingReview: 'Pending review',
      ignoredCount: 'Ignored',
      confidence: 'Confidence',
      linkedTransaction: 'Transaction',
      noCounterparty: 'Unknown counterparty',
      noPurpose: 'No payment purpose available.',
      statusAutoCreated: 'Auto-created',
      statusMatchedExisting: 'Matched existing',
      statusIgnoredDuplicate: 'Ignored duplicate',
      statusPendingReview: 'Pending review',
      actionCreate: 'Create transaction',
      actionMatch: 'Match existing',
      actionIgnore: 'Ignore duplicate',
      emptyPending: 'No bank statement lines need confirmation right now.',
      emptyResolved: 'No automatically processed statement lines yet.',
      emptyIgnored: 'No ignored duplicate lines yet.',
      pendingTitle: 'Pending review',
      pendingDescription: 'Low-confidence items stay here until you confirm how they should be handled.',
      resolvedTitle: 'Automatically processed',
      resolvedDescription: 'These lines were auto-created or matched to an existing transaction.',
      ignoredTitle: 'Ignored duplicates',
      ignoredDescription: 'These lines were ignored as duplicates and will not create transactions.',
      importBankStatement: 'Import bank statement',
      openBankWorkbench: 'Open bank statement workbench',
      bankWorkbenchHint: 'Open the bank statement workbench to review low-confidence items, match existing transactions, and confirm new transactions.',
    }),
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
    ...buildExportAndSearchHotfix(
      '\u5bfc\u51fa CSV',
      '\u5bfc\u51fa PDF',
      '\u6309\u63cf\u8ff0\u6216\u7c7b\u522b\u641c\u7d22...',
      '\u6309\u63cf\u8ff0\u641c\u7d22...'
    ),
    ...buildBankWorkbenchHotfix({
      title: '\u94f6\u884c\u6d41\u6c34\u5de5\u4f5c\u53f0',
      initializing: '\u6b63\u5728\u51c6\u5907\u94f6\u884c\u6d41\u6c34\u5de5\u4f5c\u53f0...',
      loadingLines: '\u6b63\u5728\u52a0\u8f7d\u94f6\u884c\u660e\u7ec6...',
      loadFailed: '\u52a0\u8f7d\u94f6\u884c\u6d41\u6c34\u5de5\u4f5c\u53f0\u5931\u8d25\u3002',
      actionFailed: '\u94f6\u884c\u6d41\u6c34\u64cd\u4f5c\u672a\u80fd\u5b8c\u6210\u3002',
      summaryTitle: '\u5bfc\u5165\u6458\u8981',
      importedAt: '\u5bfc\u5165\u65f6\u95f4',
      totalCount: '\u603b\u6761\u6570',
      autoProcessed: '\u5df2\u81ea\u52a8\u5904\u7406',
      pendingReview: '\u5f85\u786e\u8ba4',
      ignoredCount: '\u5df2\u5ffd\u7565',
      confidence: '\u7f6e\u4fe1\u5ea6',
      linkedTransaction: '\u5173\u8054\u4ea4\u6613',
      noCounterparty: '\u672a\u77e5\u5bf9\u624b\u65b9',
      noPurpose: '\u6682\u65e0\u4ed8\u6b3e\u8bf4\u660e\u3002',
      statusAutoCreated: '\u5df2\u81ea\u52a8\u65b0\u589e',
      statusMatchedExisting: '\u5df2\u5339\u914d\u73b0\u6709\u4ea4\u6613',
      statusIgnoredDuplicate: '\u5df2\u5ffd\u7565\u91cd\u590d\u9879',
      statusPendingReview: '\u5f85\u786e\u8ba4',
      actionCreate: '\u65b0\u589e\u4ea4\u6613',
      actionMatch: '\u5339\u914d\u5df2\u6709\u4ea4\u6613',
      actionIgnore: '\u5ffd\u7565\u91cd\u590d',
      emptyPending: '\u76ee\u524d\u6ca1\u6709\u9700\u8981\u60a8\u786e\u8ba4\u7684\u94f6\u884c\u660e\u7ec6\u3002',
      emptyResolved: '\u6682\u65e0\u5df2\u81ea\u52a8\u5904\u7406\u7684\u94f6\u884c\u660e\u7ec6\u3002',
      emptyIgnored: '\u6682\u65e0\u5df2\u5ffd\u7565\u7684\u91cd\u590d\u660e\u7ec6\u3002',
      pendingTitle: '\u5f85\u786e\u8ba4',
      pendingDescription: '\u4f4e\u7f6e\u4fe1\u5ea6\u9879\u76ee\u4f1a\u6682\u65f6\u4fdd\u7559\u5728\u8fd9\u91cc\uff0c\u7b49\u60a8\u786e\u8ba4\u5e94\u5982\u4f55\u5904\u7406\u3002',
      resolvedTitle: '\u5df2\u81ea\u52a8\u5904\u7406',
      resolvedDescription: '\u8fd9\u4e9b\u660e\u7ec6\u5df2\u81ea\u52a8\u65b0\u589e\u4ea4\u6613\uff0c\u6216\u5df2\u5339\u914d\u5230\u73b0\u6709\u4ea4\u6613\u3002',
      ignoredTitle: '\u5df2\u5ffd\u7565\u91cd\u590d\u9879',
      ignoredDescription: '\u8fd9\u4e9b\u660e\u7ec6\u88ab\u5224\u5b9a\u4e3a\u91cd\u590d\u9879\u5e76\u5df2\u5ffd\u7565\uff0c\u4e0d\u4f1a\u518d\u751f\u6210\u4ea4\u6613\u3002',
      importBankStatement: '\u5bfc\u5165\u94f6\u884c\u6d41\u6c34',
      openBankWorkbench: '\u6253\u5f00\u94f6\u884c\u6d41\u6c34\u5de5\u4f5c\u53f0',
      bankWorkbenchHint: '\u6253\u5f00\u94f6\u884c\u6d41\u6c34\u5de5\u4f5c\u53f0\uff0c\u590d\u6838\u4f4e\u7f6e\u4fe1\u5ea6\u9879\u76ee\uff0c\u5339\u914d\u5df2\u6709\u4ea4\u6613\uff0c\u5e76\u786e\u8ba4\u9700\u8981\u65b0\u589e\u7684\u4ea4\u6613\u3002',
    }),
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
    ...buildExportAndSearchHotfix(
      'Exporter en CSV',
      'Exporter en PDF',
      'Rechercher par description ou cat\u00e9gorie...',
      'Rechercher par description...'
    ),
    ...buildBankWorkbenchHotfix({
      title: 'Espace de traitement du releve bancaire',
      initializing: 'Preparation de l espace de traitement du releve bancaire...',
      loadingLines: 'Chargement des lignes du releve...',
      loadFailed: 'Impossible de charger l espace de traitement du releve bancaire.',
      actionFailed: 'L action sur le releve bancaire n a pas pu etre effectuee.',
      summaryTitle: 'Resume de l import',
      importedAt: 'Importe le',
      totalCount: 'Nombre total de lignes',
      autoProcessed: 'Traite automatiquement',
      pendingReview: 'A confirmer',
      ignoredCount: 'Ignore',
      confidence: 'Confiance',
      linkedTransaction: 'Transaction',
      noCounterparty: 'Contrepartie inconnue',
      noPurpose: 'Aucun motif de paiement disponible.',
      statusAutoCreated: 'Cree automatiquement',
      statusMatchedExisting: 'Associe a une transaction existante',
      statusIgnoredDuplicate: 'Doublon ignore',
      statusPendingReview: 'A confirmer',
      actionCreate: 'Creer la transaction',
      actionMatch: 'Associer a l existant',
      actionIgnore: 'Ignorer le doublon',
      emptyPending: 'Aucune ligne de releve ne necessite de confirmation pour le moment.',
      emptyResolved: 'Aucune ligne de releve traitee automatiquement pour le moment.',
      emptyIgnored: 'Aucun doublon ignore pour le moment.',
      pendingTitle: 'A confirmer',
      pendingDescription: 'Les elements a faible confiance restent ici jusqu a ce que vous confirmiez le traitement approprie.',
      resolvedTitle: 'Traitement automatique',
      resolvedDescription: 'Ces lignes ont ete creees automatiquement ou rapprochees d une transaction existante.',
      ignoredTitle: 'Doublons ignores',
      ignoredDescription: 'Ces lignes ont ete ignorees comme doublons et ne creeront pas de transactions.',
      importBankStatement: 'Importer le releve bancaire',
      openBankWorkbench: 'Ouvrir l espace de traitement',
      bankWorkbenchHint: 'Ouvrez l espace de traitement du releve bancaire pour verifier les elements a faible confiance, rapprocher les transactions existantes et confirmer les nouvelles transactions.',
    }),
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
    ...buildBankWorkbenchHotfix({
      title: '\u0420\u0430\u0431\u043e\u0447\u0430\u044f \u043e\u0431\u043b\u0430\u0441\u0442\u044c \u0431\u0430\u043d\u043a\u043e\u0432\u0441\u043a\u043e\u0439 \u0432\u044b\u043f\u0438\u0441\u043a\u0438',
      initializing: '\u041f\u043e\u0434\u0433\u043e\u0442\u0430\u0432\u043b\u0438\u0432\u0430\u0435\u043c \u0440\u0430\u0431\u043e\u0447\u0443\u044e \u043e\u0431\u043b\u0430\u0441\u0442\u044c \u0431\u0430\u043d\u043a\u043e\u0432\u0441\u043a\u043e\u0439 \u0432\u044b\u043f\u0438\u0441\u043a\u0438...',
      loadingLines: '\u0417\u0430\u0433\u0440\u0443\u0436\u0430\u0435\u043c \u0441\u0442\u0440\u043e\u043a\u0438 \u0432\u044b\u043f\u0438\u0441\u043a\u0438...',
      loadFailed: '\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0437\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u0440\u0430\u0431\u043e\u0447\u0443\u044e \u043e\u0431\u043b\u0430\u0441\u0442\u044c \u0431\u0430\u043d\u043a\u043e\u0432\u0441\u043a\u043e\u0439 \u0432\u044b\u043f\u0438\u0441\u043a\u0438.',
      actionFailed: '\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0432\u044b\u043f\u043e\u043b\u043d\u0438\u0442\u044c \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0435 \u0434\u043b\u044f \u0431\u0430\u043d\u043a\u043e\u0432\u0441\u043a\u043e\u0439 \u0432\u044b\u043f\u0438\u0441\u043a\u0438.',
      summaryTitle: '\u0421\u0432\u043e\u0434\u043a\u0430 \u0438\u043c\u043f\u043e\u0440\u0442\u0430',
      importedAt: '\u0418\u043c\u043f\u043e\u0440\u0442\u0438\u0440\u043e\u0432\u0430\u043d\u043e',
      totalCount: '\u0412\u0441\u0435\u0433\u043e \u0441\u0442\u0440\u043e\u043a',
      autoProcessed: '\u041e\u0431\u0440\u0430\u0431\u043e\u0442\u0430\u043d\u043e \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438',
      pendingReview: '\u041e\u0436\u0438\u0434\u0430\u0435\u0442 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f',
      ignoredCount: '\u0418\u0433\u043d\u043e\u0440\u0438\u0440\u043e\u0432\u0430\u043d\u043e',
      confidence: '\u0423\u0432\u0435\u0440\u0435\u043d\u043d\u043e\u0441\u0442\u044c',
      linkedTransaction: '\u0422\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u044f',
      noCounterparty: '\u041a\u043e\u043d\u0442\u0440\u0430\u0433\u0435\u043d\u0442 \u043d\u0435 \u0443\u043a\u0430\u0437\u0430\u043d',
      noPurpose: '\u041d\u0435\u0442 \u043e\u043f\u0438\u0441\u0430\u043d\u0438\u044f \u043f\u043b\u0430\u0442\u0435\u0436\u0430.',
      statusAutoCreated: '\u0421\u043e\u0437\u0434\u0430\u043d\u043e \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438',
      statusMatchedExisting: '\u0421\u043e\u043f\u043e\u0441\u0442\u0430\u0432\u043b\u0435\u043d\u043e \u0441 \u0441\u0443\u0449\u0435\u0441\u0442\u0432\u0443\u044e\u0449\u0435\u0439 \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0435\u0439',
      statusIgnoredDuplicate: '\u0414\u0443\u0431\u043b\u0438\u043a\u0430\u0442 \u0438\u0433\u043d\u043e\u0440\u0438\u0440\u043e\u0432\u0430\u043d',
      statusPendingReview: '\u041e\u0436\u0438\u0434\u0430\u0435\u0442 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f',
      actionCreate: '\u0421\u043e\u0437\u0434\u0430\u0442\u044c \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u044e',
      actionMatch: '\u0421\u043e\u043f\u043e\u0441\u0442\u0430\u0432\u0438\u0442\u044c \u0441 \u0441\u0443\u0449\u0435\u0441\u0442\u0432\u0443\u044e\u0449\u0435\u0439',
      actionIgnore: '\u0418\u0433\u043d\u043e\u0440\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0434\u0443\u0431\u043b\u0438\u043a\u0430\u0442',
      emptyPending: '\u0421\u0435\u0439\u0447\u0430\u0441 \u043d\u0435\u0442 \u0441\u0442\u0440\u043e\u043a \u0432\u044b\u043f\u0438\u0441\u043a\u0438, \u043a\u043e\u0442\u043e\u0440\u044b\u0435 \u043d\u0443\u0436\u043d\u043e \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044c.',
      emptyResolved: '\u0415\u0449\u0435 \u043d\u0435\u0442 \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438 \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u0430\u043d\u043d\u044b\u0445 \u0441\u0442\u0440\u043e\u043a \u0432\u044b\u043f\u0438\u0441\u043a\u0438.',
      emptyIgnored: '\u0415\u0449\u0435 \u043d\u0435\u0442 \u0438\u0433\u043d\u043e\u0440\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u044b\u0445 \u0434\u0443\u0431\u043b\u0438\u043a\u0430\u0442\u043e\u0432.',
      pendingTitle: '\u041e\u0436\u0438\u0434\u0430\u0435\u0442 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f',
      pendingDescription: '\u042d\u043b\u0435\u043c\u0435\u043d\u0442\u044b \u0441 \u043d\u0438\u0437\u043a\u043e\u0439 \u0443\u0432\u0435\u0440\u0435\u043d\u043d\u043e\u0441\u0442\u044c\u044e \u043e\u0441\u0442\u0430\u044e\u0442\u0441\u044f \u0437\u0434\u0435\u0441\u044c, \u043f\u043e\u043a\u0430 \u0432\u044b \u043d\u0435 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u0435, \u043a\u0430\u043a \u0438\u0445 \u043d\u0443\u0436\u043d\u043e \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u0430\u0442\u044c.',
      resolvedTitle: '\u041e\u0431\u0440\u0430\u0431\u043e\u0442\u0430\u043d\u043e \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438',
      resolvedDescription: '\u042d\u0442\u0438 \u0441\u0442\u0440\u043e\u043a\u0438 \u0431\u044b\u043b\u0438 \u0441\u043e\u0437\u0434\u0430\u043d\u044b \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438 \u0438\u043b\u0438 \u0441\u043e\u043f\u043e\u0441\u0442\u0430\u0432\u043b\u0435\u043d\u044b \u0441 \u0443\u0436\u0435 \u0441\u0443\u0449\u0435\u0441\u0442\u0432\u0443\u044e\u0449\u0435\u0439 \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0435\u0439.',
      ignoredTitle: '\u0418\u0433\u043d\u043e\u0440\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u044b\u0435 \u0434\u0443\u0431\u043b\u0438\u043a\u0430\u0442\u044b',
      ignoredDescription: '\u042d\u0442\u0438 \u0441\u0442\u0440\u043e\u043a\u0438 \u0431\u044b\u043b\u0438 \u0438\u0433\u043d\u043e\u0440\u0438\u0440\u043e\u0432\u0430\u043d\u044b \u043a\u0430\u043a \u0434\u0443\u0431\u043b\u0438\u043a\u0430\u0442\u044b \u0438 \u043d\u0435 \u0441\u043e\u0437\u0434\u0430\u0434\u0443\u0442 \u043d\u043e\u0432\u044b\u0445 \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0439.',
      importBankStatement: '\u0418\u043c\u043f\u043e\u0440\u0442 \u0431\u0430\u043d\u043a\u043e\u0432\u0441\u043a\u043e\u0439 \u0432\u044b\u043f\u0438\u0441\u043a\u0438',
      openBankWorkbench: '\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u0440\u0430\u0431\u043e\u0447\u0443\u044e \u043e\u0431\u043b\u0430\u0441\u0442\u044c',
      bankWorkbenchHint: '\u041e\u0442\u043a\u0440\u043e\u0439\u0442\u0435 \u0440\u0430\u0431\u043e\u0447\u0443\u044e \u043e\u0431\u043b\u0430\u0441\u0442\u044c \u0431\u0430\u043d\u043a\u043e\u0432\u0441\u043a\u043e\u0439 \u0432\u044b\u043f\u0438\u0441\u043a\u0438, \u0447\u0442\u043e\u0431\u044b \u043f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c \u044d\u043b\u0435\u043c\u0435\u043d\u0442\u044b \u0441 \u043d\u0438\u0437\u043a\u043e\u0439 \u0443\u0432\u0435\u0440\u0435\u043d\u043d\u043e\u0441\u0442\u044c\u044e, \u0441\u043e\u043f\u043e\u0441\u0442\u0430\u0432\u0438\u0442\u044c \u0441\u0443\u0449\u0435\u0441\u0442\u0432\u0443\u044e\u0449\u0438\u0435 \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0438 \u0438 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044c \u043d\u043e\u0432\u044b\u0435 \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0438.',
    }),
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
    ...buildBankWorkbenchHotfix({
      title: 'Bankszamlakivonat munkafelulet',
      initializing: 'A bankszamlakivonat munkafelulet elokeszitese...',
      loadingLines: 'A kivonatsorok betoltese...',
      loadFailed: 'Nem sikerult betolteni a bankszamlakivonat munkafeluletet.',
      actionFailed: 'A bankszamlakivonat muveletet nem sikerult befejezni.',
      summaryTitle: 'Import osszegzes',
      importedAt: 'Importalva',
      totalCount: 'Sorok osszesen',
      autoProcessed: 'Automatikusan feldolgozva',
      pendingReview: 'Megerositesre var',
      ignoredCount: 'Figyelmen kivul hagyva',
      confidence: 'Megbizhatosag',
      linkedTransaction: 'Tranzakcio',
      noCounterparty: 'Ismeretlen partner',
      noPurpose: 'Nincs elerheto kozlemeny.',
      statusAutoCreated: 'Automatikusan letrehozva',
      statusMatchedExisting: 'Meglevo tranzakciohoz kapcsolva',
      statusIgnoredDuplicate: 'Duplikatum figyelmen kivul hagyva',
      statusPendingReview: 'Megerositesre var',
      actionCreate: 'Tranzakcio letrehozasa',
      actionMatch: 'Meglevo parositasa',
      actionIgnore: 'Duplikatum figyelmen kivul hagyasa',
      emptyPending: 'Jelenleg nincs megerositesre varo kivonatsor.',
      emptyResolved: 'Meg nincs automatikusan feldolgozott kivonatsor.',
      emptyIgnored: 'Meg nincs figyelmen kivul hagyott duplikatum.',
      pendingTitle: 'Megerositesre var',
      pendingDescription: 'Az alacsony megbizhatosagu elemek itt maradnak, amig meg nem erositi a megfelelo kezelest.',
      resolvedTitle: 'Automatikusan feldolgozva',
      resolvedDescription: 'Ezek a sorok automatikusan letrejottek vagy egy meglevo tranzakciohoz lettek kapcsolva.',
      ignoredTitle: 'Figyelmen kivul hagyott duplikatumok',
      ignoredDescription: 'Ezeket a sorokat duplikatumkent figyelmen kivul hagytuk, es nem hoznak letre uj tranzakciot.',
      importBankStatement: 'Bankszamlakivonat importalasa',
      openBankWorkbench: 'Munkafelulet megnyitasa',
      bankWorkbenchHint: 'Nyissa meg a bankszamlakivonat munkafeluletet az alacsony megbizhatosagu elemek ellenorzesehez, a meglevo tranzakciok parositasahoz es az uj tranzakciok megerositesehez.',
    }),
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
    ...buildExportAndSearchHotfix(
      'Eksportuj CSV',
      'Eksportuj PDF',
      'Szukaj po opisie lub kategorii...',
      'Szukaj po opisie...'
    ),
    ...buildBankWorkbenchHotfix({
      title: 'Panel wyciagu bankowego',
      initializing: 'Przygotowywanie panelu wyciagu bankowego...',
      loadingLines: 'Ladowanie pozycji wyciagu...',
      loadFailed: 'Nie udalo sie zaladowac panelu wyciagu bankowego.',
      actionFailed: 'Nie udalo sie wykonac operacji dla wyciagu bankowego.',
      summaryTitle: 'Podsumowanie importu',
      importedAt: 'Zaimportowano',
      totalCount: 'Laczna liczba pozycji',
      autoProcessed: 'Przetworzono automatycznie',
      pendingReview: 'Do potwierdzenia',
      ignoredCount: 'Pominiete',
      confidence: 'Pewnosc',
      linkedTransaction: 'Transakcja',
      noCounterparty: 'Nieznana strona transakcji',
      noPurpose: 'Brak opisu platnosci.',
      statusAutoCreated: 'Utworzono automatycznie',
      statusMatchedExisting: 'Dopasowano do istniejacej transakcji',
      statusIgnoredDuplicate: 'Zignorowano duplikat',
      statusPendingReview: 'Do potwierdzenia',
      actionCreate: 'Utworz transakcje',
      actionMatch: 'Dopasuj istniejaca',
      actionIgnore: 'Ignoruj duplikat',
      emptyPending: 'Obecnie zadna pozycja wyciagu nie wymaga potwierdzenia.',
      emptyResolved: 'Brak jeszcze automatycznie przetworzonych pozycji wyciagu.',
      emptyIgnored: 'Brak jeszcze zignorowanych duplikatow.',
      pendingTitle: 'Do potwierdzenia',
      pendingDescription: 'Pozycje o niskiej pewnosci pozostaja tutaj, dopoki nie potwierdzisz sposobu ich obslugi.',
      resolvedTitle: 'Przetworzono automatycznie',
      resolvedDescription: 'Te pozycje zostaly utworzone automatycznie lub dopasowane do istniejacej transakcji.',
      ignoredTitle: 'Zignorowane duplikaty',
      ignoredDescription: 'Te pozycje zostaly zignorowane jako duplikaty i nie utworza nowych transakcji.',
      importBankStatement: 'Importuj wyciag bankowy',
      openBankWorkbench: 'Otworz panel wyciagu bankowego',
      bankWorkbenchHint: 'Otworz panel wyciagu bankowego, aby sprawdzic pozycje o niskiej pewnosci, dopasowac istniejace transakcje i potwierdzic nowe transakcje.',
    }),
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
    ...buildExportAndSearchHotfix(
      'CSV olarak disa aktar',
      'PDF olarak disa aktar',
      'Aciklama veya kategoriye gore ara...',
      'Aciklamaya gore ara...'
    ),
    ...buildBankWorkbenchHotfix({
      title: 'Banka hesap ozeti calisma alani',
      initializing: 'Banka hesap ozeti calisma alani hazirlaniyor...',
      loadingLines: 'Ekstre satirlari yukleniyor...',
      loadFailed: 'Banka hesap ozeti calisma alani yuklenemedi.',
      actionFailed: 'Banka hesap ozeti islemi tamamlanamadi.',
      summaryTitle: 'Ice aktarma ozeti',
      importedAt: 'Ice aktarma tarihi',
      totalCount: 'Toplam satir',
      autoProcessed: 'Otomatik islenen',
      pendingReview: 'Onay bekleyen',
      ignoredCount: 'Yoksayilan',
      confidence: 'Guven',
      linkedTransaction: 'Islem',
      noCounterparty: 'Karsi taraf bilinmiyor',
      noPurpose: 'Odeme aciklamasi yok.',
      statusAutoCreated: 'Otomatik olusturuldu',
      statusMatchedExisting: 'Mevcut islemle eslesti',
      statusIgnoredDuplicate: 'Cift kayit yoksayildi',
      statusPendingReview: 'Onay bekleyen',
      actionCreate: 'Islem olustur',
      actionMatch: 'Mevcut islemi eslestir',
      actionIgnore: 'Cift kaydi yoksay',
      emptyPending: 'Su anda onay bekleyen banka hareketi yok.',
      emptyResolved: 'Henuz otomatik islenmis banka hareketi yok.',
      emptyIgnored: 'Henuz yoksayilan cift kayit yok.',
      pendingTitle: 'Onay bekleyen',
      pendingDescription: 'Dusuk guvenli ogeler, nasil isleneceklerini onaylayana kadar burada kalir.',
      resolvedTitle: 'Otomatik islenen',
      resolvedDescription: 'Bu satirlar otomatik olarak olusturuldu veya mevcut bir islemle eslestirildi.',
      ignoredTitle: 'Yoksayilan cift kayitlar',
      ignoredDescription: 'Bu satirlar cift kayit olarak yoksayildi ve yeni islem olusturmayacak.',
      importBankStatement: 'Banka hesap ozeti ice aktar',
      openBankWorkbench: 'Calisma alanini ac',
      bankWorkbenchHint: 'Dusuk guvenli ogeleri incelemek, mevcut islemleri eslestirmek ve yeni islemleri onaylamak icin banka hesap ozeti calisma alanini acin.',
    }),
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
    ...buildBankWorkbenchHotfix({
      title: 'Radni prostor bankovnog izvoda',
      initializing: 'Pripremamo radni prostor bankovnog izvoda...',
      loadingLines: 'Ucitajavanje stavki izvoda...',
      loadFailed: 'Radni prostor bankovnog izvoda nije se mogao ucitati.',
      actionFailed: 'Radnja za bankovni izvod nije mogla biti dovrsena.',
      summaryTitle: 'Saetak uvoza',
      importedAt: 'Uvezeno',
      totalCount: 'Ukupno stavki',
      autoProcessed: 'Automatski obradeno',
      pendingReview: 'Ceka potvrdu',
      ignoredCount: 'Ignorisano',
      confidence: 'Pouzdanost',
      linkedTransaction: 'Transakcija',
      noCounterparty: 'Nepoznata druga strana',
      noPurpose: 'Nema opisa placanja.',
      statusAutoCreated: 'Automatski kreirano',
      statusMatchedExisting: 'Povezano sa postojecoom transakcijom',
      statusIgnoredDuplicate: 'Duplikat ignorisan',
      statusPendingReview: 'Ceka potvrdu',
      actionCreate: 'Kreiraj transakciju',
      actionMatch: 'Povezi postojecu',
      actionIgnore: 'Ignorisi duplikat',
      emptyPending: 'Trenutno nema stavki izvoda koje cekaju potvrdu.',
      emptyResolved: 'Jos nema automatski obradenih stavki izvoda.',
      emptyIgnored: 'Jos nema ignorisanih duplikata.',
      pendingTitle: 'Ceka potvrdu',
      pendingDescription: 'Stavke sa nizom pouzdanoscu ostaju ovdje dok ne potvrdite kako ih treba obraditi.',
      resolvedTitle: 'Automatski obradeno',
      resolvedDescription: 'Ove stavke su automatski kreirane ili povezane sa postojecom transakcijom.',
      ignoredTitle: 'Ignorisani duplikati',
      ignoredDescription: 'Ove stavke su ignorisane kao duplikati i nece kreirati nove transakcije.',
      importBankStatement: 'Uvezi bankovni izvod',
      openBankWorkbench: 'Otvori radni prostor',
      bankWorkbenchHint: 'Otvorite radni prostor bankovnog izvoda da pregledate stavke sa niskom pouzdanoscu, povezete postojece transakcije i potvrdite nove transakcije.',
    }),
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
    deepMerge(resource as LocaleObject, LOCALE_HOTFIXES[language])
  ) as Record<string, unknown>;
