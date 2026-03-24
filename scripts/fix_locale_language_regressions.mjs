import fs from 'fs';
import path from 'path';

const localesDir = path.resolve(
  'frontend',
  'src',
  'i18n',
  'locales',
);

const pendingTranslations = {
  en: {
    pendingHint:
      'Confirmed contracts become liabilities automatically. Contracts still waiting for review or missing fields stay here until you finish them in Documents.',
    pendingMissingFields: 'Missing: {{fields}}',
    pendingNeedsInput: 'Needs input',
    pendingReview: 'Awaiting confirmation',
    pendingTitle: 'Pending loan contracts',
  },
  zh: {
    pendingHint:
      '已确认的合同会自动成为负债。仍在复核中或缺少字段的合同会暂时显示在这里，直到您在文档页完成处理。',
    pendingMissingFields: '缺少：{{fields}}',
    pendingNeedsInput: '需要补充信息',
    pendingReview: '等待确认',
    pendingTitle: '待确认贷款合同',
  },
  de: {
    pendingHint:
      'Bestätigte Verträge werden automatisch zu Verbindlichkeiten. Verträge, die noch geprüft werden oder bei denen Felder fehlen, bleiben hier, bis Sie sie in Dokumente abschließen.',
    pendingMissingFields: 'Fehlt: {{fields}}',
    pendingNeedsInput: 'Eingaben erforderlich',
    pendingReview: 'Warten auf Bestätigung',
    pendingTitle: 'Ausstehende Darlehensverträge',
  },
  fr: {
    pendingHint:
      'Les contrats confirmés deviennent automatiquement des dettes. Les contrats encore en révision ou avec des champs manquants restent ici jusqu’à ce que vous les terminiez dans Documents.',
    pendingMissingFields: 'Champs manquants : {{fields}}',
    pendingNeedsInput: 'Informations requises',
    pendingReview: 'En attente de confirmation',
    pendingTitle: 'Contrats de prêt en attente',
  },
  ru: {
    pendingHint:
      'Подтвержденные договоры автоматически становятся обязательствами. Договоры, которые еще проверяются или имеют пропущенные поля, остаются здесь, пока вы не завершите их в разделе «Документы».',
    pendingMissingFields: 'Отсутствуют: {{fields}}',
    pendingNeedsInput: 'Требуются данные',
    pendingReview: 'Ожидает подтверждения',
    pendingTitle: 'Ожидающие подтверждения кредитные договоры',
  },
  hu: {
    pendingHint:
      'A megerősített szerződések automatikusan kötelezettséggé válnak. Az ellenőrzésre váró vagy hiányos szerződések itt maradnak, amíg be nem fejezi őket a Dokumentumokban.',
    pendingMissingFields: 'Hiányzik: {{fields}}',
    pendingNeedsInput: 'Adatok szükségesek',
    pendingReview: 'Jóváhagyásra vár',
    pendingTitle: 'Függő kölcsönszerződések',
  },
  pl: {
    pendingHint:
      'Potwierdzone umowy automatycznie stają się zobowiązaniami. Umowy, które nadal wymagają przeglądu lub mają brakujące pola, pozostają tutaj, dopóki nie dokończysz ich w Dokumentach.',
    pendingMissingFields: 'Brakuje: {{fields}}',
    pendingNeedsInput: 'Wymagane dane',
    pendingReview: 'Oczekuje na potwierdzenie',
    pendingTitle: 'Oczekujące umowy pożyczki',
  },
  tr: {
    pendingHint:
      'Onaylanan sözleşmeler otomatik olarak borç kaydına dönüşür. Hâlâ incelenen veya eksik alanları olan sözleşmeler, Belgeler bölümünde tamamlayana kadar burada kalır.',
    pendingMissingFields: 'Eksik: {{fields}}',
    pendingNeedsInput: 'Bilgi gerekiyor',
    pendingReview: 'Onay bekleniyor',
    pendingTitle: 'Bekleyen kredi sözleşmeleri',
  },
  bs: {
    pendingHint:
      'Potvrđeni ugovori automatski postaju obaveze. Ugovori koji su još u provjeri ili imaju polja koja nedostaju ostaju ovdje dok ih ne završite u Dokumentima.',
    pendingMissingFields: 'Nedostaje: {{fields}}',
    pendingNeedsInput: 'Potrebni podaci',
    pendingReview: 'Čeka potvrdu',
    pendingTitle: 'Ugovori o kreditu na čekanju',
  },
};

const fieldTranslations = {
  en: {
    employee_name: 'Employee name',
    sv_nummer: 'Social insurance number',
    social_insurance: 'Social insurance',
    document_transaction_direction: 'Document transaction direction',
    document_transaction_direction_source: 'Direction source',
    document_transaction_direction_confidence: 'Direction confidence',
    commercial_document_semantics: 'Commercial document semantics',
    is_reversal: 'Reversal',
    extraction_method: 'Extraction method',
    utilities_included: 'Utilities included',
    llm_fallback: 'LLM fallback',
    employer: 'Employer',
    employee: 'Employee',
    familienbonus: 'Family bonus',
    telearbeitspauschale: 'Remote work allowance',
  },
  zh: {
    employee_name: '雇员姓名',
    sv_nummer: '社保号码',
    social_insurance: '社会保险',
    document_transaction_direction: '文档交易方向',
    document_transaction_direction_source: '方向来源',
    document_transaction_direction_confidence: '方向置信度',
    commercial_document_semantics: '商业文档语义',
    is_reversal: '是否冲销',
    extraction_method: '提取方式',
    utilities_included: '是否包含杂费',
    llm_fallback: 'LLM 补全',
    employer: '雇主',
    employee: '雇员',
    familienbonus: '家庭奖金',
    telearbeitspauschale: '远程办公补贴',
  },
  de: {
    employee_name: 'Arbeitnehmername',
    sv_nummer: 'SV-Nummer',
    social_insurance: 'Sozialversicherung',
    document_transaction_direction: 'Belegrichtung',
    document_transaction_direction_source: 'Quelle der Richtungsentscheidung',
    document_transaction_direction_confidence:
      'Sicherheit der Richtungsentscheidung',
    commercial_document_semantics: 'Belegsemantik',
    is_reversal: 'Storno',
    extraction_method: 'Extraktionsmethode',
    utilities_included: 'Betriebskosten enthalten',
    llm_fallback: 'LLM-Fallback',
    employer: 'Arbeitgeber',
    employee: 'Arbeitnehmer',
    familienbonus: 'Familienbonus',
    telearbeitspauschale: 'Telearbeitspauschale',
  },
  fr: {
    employee_name: "Nom de l'employé",
    sv_nummer: "Numéro d'assurance sociale",
    social_insurance: 'Assurance sociale',
    document_transaction_direction: 'Sens de transaction du document',
    document_transaction_direction_source: 'Source du sens',
    document_transaction_direction_confidence: 'Confiance du sens',
    commercial_document_semantics: 'Sémantique du document commercial',
    is_reversal: 'Contrepassation',
    extraction_method: "Méthode d'extraction",
    utilities_included: 'Charges comprises',
    llm_fallback: 'Secours LLM',
    employer: 'Employeur',
    employee: 'Employé',
    familienbonus: 'Bonus familial',
    telearbeitspauschale: 'Indemnité de télétravail',
  },
  ru: {
    employee_name: 'Имя сотрудника',
    sv_nummer: 'Номер соцстрахования',
    social_insurance: 'Социальное страхование',
    document_transaction_direction: 'Направление операции в документе',
    document_transaction_direction_source:
      'Источник определения направления',
    document_transaction_direction_confidence:
      'Уверенность определения направления',
    commercial_document_semantics: 'Семантика коммерческого документа',
    is_reversal: 'Сторно',
    extraction_method: 'Метод извлечения',
    utilities_included: 'Коммунальные включены',
    llm_fallback: 'Резерв LLM',
    employer: 'Работодатель',
    employee: 'Сотрудник',
    familienbonus: 'Семейный бонус',
    telearbeitspauschale: 'Доплата за удаленную работу',
  },
  hu: {
    employee_name: 'Munkavállaló neve',
    sv_nummer: 'Társadalombiztosítási szám',
    social_insurance: 'Társadalombiztosítás',
    document_transaction_direction: 'Dokumentum tranzakciós iránya',
    document_transaction_direction_source:
      'Az irány meghatározásának forrása',
    document_transaction_direction_confidence: 'Irány-megbízhatóság',
    commercial_document_semantics:
      'Kereskedelmi dokumentum szemantikája',
    is_reversal: 'Sztornó',
    extraction_method: 'Kinyerési módszer',
    utilities_included: 'Rezsi benne van',
    llm_fallback: 'LLM tartalék',
    employer: 'Munkáltató',
    employee: 'Munkavállaló',
    familienbonus: 'Családi bónusz',
    telearbeitspauschale: 'Távmunka-átalány',
  },
  pl: {
    employee_name: 'Imię i nazwisko pracownika',
    sv_nummer: 'Numer ubezpieczenia społecznego',
    social_insurance: 'Ubezpieczenie społeczne',
    document_transaction_direction: 'Kierunek transakcji dokumentu',
    document_transaction_direction_source: 'Źródło kierunku',
    document_transaction_direction_confidence: 'Pewność kierunku',
    commercial_document_semantics: 'Semantyka dokumentu handlowego',
    is_reversal: 'Storno',
    extraction_method: 'Metoda ekstrakcji',
    utilities_included: 'Media w cenie',
    llm_fallback: 'Zapas LLM',
    employer: 'Pracodawca',
    employee: 'Pracownik',
    familienbonus: 'Bonus rodzinny',
    telearbeitspauschale: 'Ryczałt za pracę zdalną',
  },
  tr: {
    employee_name: 'Çalışan adı',
    sv_nummer: 'Sosyal sigorta numarası',
    social_insurance: 'Sosyal sigorta',
    document_transaction_direction: 'Belge işlem yönü',
    document_transaction_direction_source: 'Yön kaynağı',
    document_transaction_direction_confidence: 'Yön güveni',
    commercial_document_semantics: 'Ticari belge semantiği',
    is_reversal: 'Ters kayıt',
    extraction_method: 'Çıkarma yöntemi',
    utilities_included: 'Aidatlar dahil',
    llm_fallback: 'LLM yedeği',
    employer: 'İşveren',
    employee: 'Çalışan',
    familienbonus: 'Aile bonusu',
    telearbeitspauschale: 'Uzaktan çalışma ödeneği',
  },
  bs: {
    employee_name: 'Ime zaposlenika',
    sv_nummer: 'Broj socijalnog osiguranja',
    social_insurance: 'Socijalno osiguranje',
    document_transaction_direction: 'Smjer transakcije dokumenta',
    document_transaction_direction_source: 'Izvor smjera',
    document_transaction_direction_confidence: 'Pouzdanost smjera',
    commercial_document_semantics: 'Semantika poslovnog dokumenta',
    is_reversal: 'Storno',
    extraction_method: 'Metoda izdvajanja',
    utilities_included: 'Režije uključene',
    llm_fallback: 'LLM rezervna opcija',
    employer: 'Poslodavac',
    employee: 'Zaposlenik',
    familienbonus: 'Porodični bonus',
    telearbeitspauschale: 'Naknada za rad na daljinu',
  },
};

const languages = Object.keys(fieldTranslations);

for (const lang of languages) {
  const localePath = path.join(localesDir, `${lang}.json`);
  const locale = JSON.parse(fs.readFileSync(localePath, 'utf8'));

  locale.documents ??= {};
  locale.documents.review ??= {};
  locale.documents.review.taxFieldLabels ??= {};
  Object.assign(locale.documents.review.taxFieldLabels, fieldTranslations[lang]);

  locale.liabilities ??= {};
  locale.liabilities.documents ??= {};
  Object.assign(locale.liabilities.documents, pendingTranslations[lang]);

  fs.writeFileSync(localePath, `${JSON.stringify(locale, null, 2)}\n`, 'utf8');
}
