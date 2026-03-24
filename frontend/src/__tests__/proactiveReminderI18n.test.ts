import { describe, expect, it } from 'vitest';

import zh from '../i18n/locales/zh.json';
import { sanitizeLocaleResource } from '../i18n/localeSanitizer';
import { translateReminderContent } from '../utils/proactiveReminderI18n';

const locale = sanitizeLocaleResource('zh', zh) as Record<string, unknown>;

const getValue = (value: Record<string, unknown>, key: string): unknown =>
  key.split('.').reduce<unknown>((current, segment) => {
    if (!current || typeof current !== 'object') {
      return undefined;
    }

    return (current as Record<string, unknown>)[segment];
  }, value);

const t = (key: string, options: Record<string, unknown> = {}): string => {
  const template = getValue(locale, key);
  if (typeof template !== 'string') {
    return key;
  }

  return template.replace(/\{\{\s*(\w+)\s*\}\}/g, (_match, name: string) => {
    const value = options[name];
    return value == null ? `{{${name}}}` : String(value);
  });
};

describe('proactiveReminderI18n', () => {
  it('translates nested deadline keys before interpolation', () => {
    expect(
      translateReminderContent(
        'healthCheck.deadlineApproaching',
        {
          deadline_name: 'healthCheck.deadlines.paperSubmission',
          days_remaining: 37,
          date: '2026-04-30',
        },
        t
      )
    ).toBe('距"年度报税（纸质提交）"还有 37 天（2026-04-30）');
  });

  it('translates document types inside reminder params', () => {
    expect(
      translateReminderContent(
        'healthCheck.missingDocument',
        {
          year: 2025,
          document_type: 'lohnzettel',
        },
        t
      )
    ).toBe('2025 税年尚未上传工资单（L16），此文档对您的报税很重要');
  });

  it('uses the localized health summary reminder hotfix', () => {
    expect(
      translateReminderContent(
        'ai.proactive.healthSummaryReminder',
        {
          count: 3,
          score: 72,
        },
        t
      )
    ).toBe('您有 3 项税务健康提醒待处理，当前健康分为 72 分。');
  });
});
