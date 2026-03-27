/**
 * Translate German deduction_reason text to the current UI language.
 * The backend LLM generates reasons in German; this maps them to zh/en.
 */
export const translateDeductionReason = (reason: string, language: string): string => {
  if (!reason || language.startsWith('de')) return reason;
  const lang = language.startsWith('zh') ? 'zh'
    : language.startsWith('fr') ? 'fr'
    : language.startsWith('ru') ? 'ru'
    : language.startsWith('hu') ? 'hu'
    : language.startsWith('pl') ? 'pl'
    : language.startsWith('tr') ? 'tr'
    : language.startsWith('bs') ? 'bs'
    : 'en';

  const trimmed = reason.trim();

  // Full-sentence translations (common LLM-generated reasons)
  const sentences: Record<string, Record<string, string>> = {
    'Betrieblich veranlasste Fahrzeugwartung': {
      zh: '与经营相关的车辆维护',
      en: 'Business-related vehicle maintenance',
    },
    'Betrieblich veranlasst': { zh: '与经营相关', en: 'Business-related' },
    'Nicht abzugsfähig': { zh: '不可抵税', en: 'Not deductible' },
    'Keine betriebliche Veranlassung': { zh: '非经营用途', en: 'No business purpose' },
    'Gemischte Nutzung': { zh: '混合用途', en: 'Mixed use' },
    'Rein privat': { zh: '纯私人用途', en: 'Purely private' },
    'Income is not deductible': { zh: '收入不可抵税', en: 'Income is not deductible' },
    'Rental income is not deductible': {
      zh: '租金收入不可抵税',
      en: 'Rental income is not deductible',
    },
    'SVS contributions are deductible as Sonderausgaben': {
      zh: 'SVS社保缴费可作为特殊扣除',
      en: 'SVS contributions are deductible as special expenses',
    },
  };

  if (sentences[trimmed]) return sentences[trimmed][lang] || sentences[trimmed]['en'] || reason;

  // Keyword replacements — longest first so longer phrases match before substrings
  const map: Record<string, Record<string, string>> = {
    'Private Lebensführung — kein Wareneinsatz bei IT-Dienstleistung': {
      zh: '个人生活支出 — IT服务业无商品采购',
      en: 'Private living — no goods procurement for IT services',
    },
    'kein Wareneinsatz bei IT-Dienstleistung': {
      zh: 'IT服务业无商品采购',
      en: 'No goods procurement for IT services',
    },
    'kein Wareneinsatz': { zh: '无商品采购', en: 'No goods procurement' },
    'Werbungskosten': { zh: '工作相关费用', en: 'Work-related expenses' },
    'Instandhaltung': { zh: '维修保养', en: 'Maintenance' },
    'Fortbildung': { zh: '继续教育', en: 'Further education' },
    'Grundsteuer': { zh: '房产税', en: 'Property tax' },
    'Kreditzinsen': { zh: '贷款利息', en: 'Loan interest' },
    'Gebäudeversicherung': { zh: '建筑保险', en: 'Building insurance' },
    'Betriebskosten': { zh: '运营费用', en: 'Operating costs' },
    'Hausverwaltung/Rechtsanwalt': { zh: '物业管理/律师', en: 'Property mgmt/Lawyer' },
    'Büromaterial': { zh: '办公用品', en: 'Office supplies' },
    'Nachrichtenaufwand': { zh: '通讯费用', en: 'Communication costs' },
    'Bankspesen': { zh: '银行手续费', en: 'Bank fees' },
    'KFZ für Objektbetreuung': { zh: '物业维护车辆', en: 'Vehicle for property' },
    'Fahrzeugwartung': { zh: '车辆维护', en: 'Vehicle maintenance' },
    'Fahrzeug': { zh: '车辆', en: 'Vehicle' },
    'Ausstattung': { zh: '设备', en: 'Equipment' },
    'Fahrtkosten Objektbetreuung': { zh: '物业维护交通费', en: 'Travel for property' },
    'Fahrtkosten': { zh: '交通费', en: 'Travel costs' },
    'Inserate': { zh: '广告', en: 'Advertising' },
    'Reinigung': { zh: '清洁', en: 'Cleaning' },
    'Software': { zh: '软件', en: 'Software' },
    'Treibstoff für Objektbetreuung': { zh: '物业维护燃油', en: 'Fuel for property' },
    'Treibstoff': { zh: '燃油', en: 'Fuel' },
    'Betriebsausgabe': { zh: '经营费用', en: 'Business expense' },
    'Betrieblich veranlasste': { zh: '与经营相关的', en: 'Business-related' },
    'Betrieblich veranlasst': { zh: '与经营相关', en: 'Business-related' },
    'Betrieblich': { zh: '经营性', en: 'Business' },
    'Sonderausgaben': { zh: '特殊扣除', en: 'Special expenses' },
    'Pendlerpauschale': { zh: '通勤补贴', en: 'Commuter allowance' },
    'Home-office-Pauschale': { zh: '居家办公补贴', en: 'Home office allowance' },
    'Private Lebensführung': { zh: '个人生活支出', en: 'Private living expenses' },
    'SVS/SVA Pflichtbeiträge': { zh: 'SVS/SVA社保缴费', en: 'SVS/SVA contributions' },
    'AfA': { zh: '折旧', en: 'Depreciation' },
    'Gebäudeabschreibung': { zh: '建筑折旧', en: 'Building depreciation' },
    'Steuerberater/Rechtsanwalt': { zh: '税务顾问/律师', en: 'Tax advisor/Lawyer' },
    'Steuerberater': { zh: '税务顾问', en: 'Tax advisor' },
    'KFZ-Aufwand': { zh: '车辆费用', en: 'Vehicle expenses' },
    'Zinsen': { zh: '利息', en: 'Interest' },
    'Miete': { zh: '租金', en: 'Rent' },
    'Versicherung': { zh: '保险', en: 'Insurance' },
    'Reparatur': { zh: '维修', en: 'Repair' },
    'Wartung': { zh: '保养', en: 'Maintenance' },
    'Abschreibung': { zh: '折旧', en: 'Depreciation' },
    'nicht abzugsfähig': { zh: '不可抵税', en: 'not deductible' },
    'abzugsfähig': { zh: '可抵税', en: 'deductible' },
    'Lebensmittel': { zh: '食品', en: 'Groceries' },
    'Haushalt': { zh: '家用', en: 'Household' },
    'Privat': { zh: '私人', en: 'Private' },
  };

  let result = reason;
  const sortedKeys = Object.keys(map).sort((a, b) => b.length - a.length);
  for (const de of sortedKeys) {
    if (result.includes(de)) {
      const escaped = de.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      result = result.replace(new RegExp(escaped, 'g'), map[de][lang] || map[de]['en'] || de);
    }
  }
  return result;
};
