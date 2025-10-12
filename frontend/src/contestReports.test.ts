import { describe, expect, test } from 'vitest';

import { formatContestInput, formatTooltip, hasHighlight, highlightClass, parseContestInput, participantDisplayName } from '../private/contestReports';

const GREEN_CLASS = 'bg-green-200 text-green-900 font-semibold';
const YELLOW_CLASS = 'bg-yellow-200 text-yellow-900 font-semibold';

describe('contest report helpers', () => {
  test('parseContestInput trims, filters and sorts values', () => {
    expect(parseContestInput('302, 301, 302, -1, abc, 400')).toEqual([301, 302, 400]);
    expect(parseContestInput('')).toEqual([]);
  });

  test('formatContestInput joins ids with comma and space', () => {
    expect(formatContestInput([301, 302])).toBe('301, 302');
  });

  test('highlightClass maps supported statuses', () => {
    expect(highlightClass('OK')).toBe(GREEN_CLASS);
    expect(highlightClass('ok')).toBe(GREEN_CLASS);
    expect(highlightClass('PR')).toBe(YELLOW_CLASS);
    expect(highlightClass('WA')).toBeNull();
  });

  test('hasHighlight detects highlighted cells', () => {
    expect(
      hasHighlight({
        problem_id: 1,
        best_run: { run_id: 1, status: 'AC', language: 'Python', submitted_at: null },
      })
    ).toBe(true);
    expect(hasHighlight({ problem_id: 1, best_run: null })).toBe(false);
  });

  test('formatTooltip combines language, date and run id', () => {
    const tooltip = formatTooltip({ run_id: 10, status: 'OK', language: 'Python', submitted_at: '1970-01-01T00:00:01Z' });
    expect(tooltip).toContain('Python');
    expect(tooltip).toContain('run #10');
  });

  test('participantDisplayName prefers full name', () => {
    expect(
      participantDisplayName({
        user_id: 1,
        user_login: 'ivanov',
        user_name: 'Иван Иванов',
        cells: [],
      })
    ).toBe('Иван Иванов (ivanov)');

    expect(
      participantDisplayName({
        user_id: 2,
        user_login: 'petrov',
        user_name: 'petrov',
        cells: [],
      })
    ).toBe('petrov');

    expect(
      participantDisplayName({
        user_id: 3,
        user_login: 'sidorov',
        user_name: undefined,
        cells: [],
      })
    ).toBe('sidorov');
  });
});
