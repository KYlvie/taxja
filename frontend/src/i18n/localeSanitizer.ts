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

const LOCALE_HOTFIXES: Partial<Record<SupportedLanguage, LocaleObject>> = {
  de: {
    ...buildExportAndSearchHotfix(
      'CSV exportieren',
      'PDF exportieren',
      'Nach Beschreibung oder Kategorie suchen...',
      'Nach Beschreibung suchen...'
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
