import { describe, expect, it } from 'vitest';

import {
  __test__,
  buildFallbackBankStatementLines,
} from '../utils/bankStatementFallback';

const MONTH_GROUPED_STATEMENT_TEXT = (
  "--- PAGE 1 ---\n"
  + "13 Kontoausgaenge:\n"
  + "\u2212\u200a\u20ac 1.008,24\n"
  + "Dieser Ausdruck gilt nicht als Kontoauszug.\n"
  + "Dipl.-Ing. Ylvie Khoo BSc\n"
  + "AT60 2011 1837 4498 0900\n"
  + "Dezember 2024\n"
  + "3 Kontoausgaenge: \u2212\u200a\u20ac 137,04\n"
  + "19. Dez.\n"
  + "T-Mobile Austria GmbH\n"
  + "Ratenplan 9001004040 vom 22.05.2023\n"
  + "\u2212\u200a\u20ac 2,03\n"
  + "16. Dez.\n"
  + "T-Mobile Austria GmbH\n"
  + "Magenta Mobil Rechnung 908162761224\n"
  + "\u2212\u200a\u20ac 72,78\n"
  + "16. Dez.\n"
  + "T-Mobile Austria GmbH\n"
  + "Magenta offener Saldo per 18.12.202\n"
  + "\u2212\u200a\u20ac 62,23\n"
  + "November 2024\n"
  + "2 Kontoausgaenge: \u2212\u200a\u20ac 137,04\n"
  + "18. Nov.\n"
  + "T-Mobile Austria GmbH\n"
  + "Magenta offener Saldo per 20.11.202\n"
  + "\u2212\u200a\u20ac 64,26\n"
  + "18. Nov.\n"
  + "T-Mobile Austria GmbH\n"
  + "Magenta Mobil Rechnung 910246231124\n"
  + "\u2212\u200a\u20ac 72,78\n"
  + "Oktober 2024\n"
  + "2 Kontoausgaenge: \u2212\u200a\u20ac 137,04\n"
  + "14. Okt.\n"
  + "T-Mobile Austria GmbH\n"
  + "Magenta offener Saldo per 16.10.202\n"
  + "\u2212\u200a\u20ac 64,26\n"
  + "14. Okt.\n"
  + "T-Mobile Austria GmbH\n"
  + "Magenta Mobil Rechnung 911454891024\n"
  + "\u2212\u200a\u20ac 72,78\n"
  + "September 2024\n"
  + "2 Kontoausgaenge: \u2212\u200a\u20ac 139,92\n"
  + "16. Sep.\n"
  + "T-Mobile Austria GmbH\n"
  + "Magenta offener Saldo per 18.09.202\n"
  + "\u2212\u200a\u20ac 67,14\n"
  + "16. Sep.\n"
  + "T-Mobile Austria GmbH\n"
  + "Magenta Mobil Rechnung 911381710924\n"
  + "\u2212\u200a\u20ac 72,78\n"
  + "August 2024\n"
  + "2 Kontoausgaenge: \u2212\u200a\u20ac 261,23\n"
  + "16. Aug.\n"
  + "T-Mobile Austria GmbH\n"
  + "Magenta offener Saldo per 21.08.202\n"
  + "\u2212\u200a\u20ac 69,26\n"
  + "16. Aug.\n"
  + "T-Mobile Austria GmbH\n"
  + "Magenta Mobil Rechnung 908018510824\n"
  + "\u2212\u200a\u20ac 191,97\n"
  + "Juli 2024\n"
  + "1 Kontoausgang: \u2212\u200a\u20ac 162,97\n"
  + "10. Juli\n"
  + "T-Mobile Austria GmbH\n"
  + "1.21848297\n"
  + "\u2212\u200a\u20ac 162,97\n"
  + "Juni 2024\n"
  + "1 Kontoausgang: \u2212\u200a\u20ac 33,00\n"
  + "26. Juni\n"
  + "T-Mobile Austria GmbH\n"
  + "043750601038\n"
  + "\u2212\u200a\u20ac 33,00"
);

describe('bankStatementFallback', () => {
  it('extracts month-grouped statement rows from raw text', () => {
    const rows = __test__.extractFromRawText(MONTH_GROUPED_STATEMENT_TEXT);

    expect(rows).toHaveLength(13);
    expect(rows[0]).toMatchObject({
      line_date: '19.12.2024',
      amount: -2.03,
      counterparty: 'T-Mobile Austria GmbH',
      raw_reference: 'Ratenplan 9001004040 vom 22.05.2023',
      direction: 'debit',
    });
    expect(rows.at(-1)).toMatchObject({
      line_date: '26.06.2024',
      amount: -33,
      counterparty: 'T-Mobile Austria GmbH',
      raw_reference: '043750601038',
      direction: 'debit',
    });
  });

  it('prefers raw text lines over incomplete OCR transaction rows', () => {
    const lines = buildFallbackBankStatementLines(
      [
        {
          date: '2023/5/22',
          amount: 2.03,
          counterparty: '- \u20ac',
          reference: null,
          transaction_type: 'credit',
        },
        {
          date: '18.12.202',
          amount: 62.23,
          counterparty: '- \u20ac',
          reference: null,
          transaction_type: 'credit',
        },
      ],
      MONTH_GROUPED_STATEMENT_TEXT,
    );

    expect(lines).toHaveLength(13);
    expect(lines[0].counterparty).toBe('T-Mobile Austria GmbH');
    expect(lines[0].direction).toBe('debit');
    expect(lines[0].amount).toBe(-2.03);
  });
});
