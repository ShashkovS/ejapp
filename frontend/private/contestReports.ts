export type ContestRunSummary = {
  run_id: number;
  status: string;
  language?: string | null;
  submitted_at?: string | null;
};

export type ContestCell = {
  problem_id: number;
  best_run: ContestRunSummary | null;
};

export type ContestRow = {
  user_id: number;
  user_login: string;
  user_name?: string | null;
  cells: ContestCell[];
};

export type ContestProblem = {
  id: number;
  short_name: string;
  long_name?: string | null;
};

export type ContestReport = {
  contest_id: number;
  contest_name: string;
  problems: ContestProblem[];
  rows: ContestRow[];
};

export type ContestReportsResponse = {
  contests: ContestReport[];
};

const STATUS_CLASSES: Record<string, string> = {
  OK: 'bg-green-200 text-green-900 font-semibold',
  AC: 'bg-yellow-200 text-yellow-900 font-semibold',
  PR: 'bg-yellow-200 text-yellow-900 font-semibold',
  SM: 'bg-yellow-200 text-yellow-900 font-semibold',
};

export function highlightClass(status?: string | null): string | null {
  if (!status) {
    return null;
  }
  const normalized = status.trim().toUpperCase();
  return STATUS_CLASSES[normalized] ?? null;
}

export function hasHighlight(cell: ContestCell): boolean {
  return Boolean(cell.best_run && highlightClass(cell.best_run.status));
}

export function formatTooltip(run: ContestRunSummary): string {
  const parts: string[] = [];
  if (run.language) {
    parts.push(run.language);
  }

  if (run.submitted_at) {
    const date = new Date(run.submitted_at);
    if (!Number.isNaN(date.valueOf())) {
      parts.push(date.toLocaleString());
    }
  }

  parts.push(`run #${run.run_id}`);
  return parts.join(' • ');
}

export function participantDisplayName(row: ContestRow): string {
  const trimmedName = row.user_name?.trim();
  if (trimmedName) {
    if (trimmedName.toLowerCase() === row.user_login.toLowerCase()) {
      return trimmedName;
    }
    return `${trimmedName} (${row.user_login})`;
  }
  return row.user_login;
}

export function parseContestInput(value: string): number[] {
  const unique = new Set<number>();
  value
    .split(',')
    .map((part) => part.trim())
    .filter((part) => part.length > 0)
    .forEach((part) => {
      const numeric = Number(part);
      if (Number.isInteger(numeric) && numeric > 0) {
        unique.add(numeric);
      }
    });

  return Array.from(unique).sort((a, b) => a - b);
}

export function formatContestInput(ids: number[]): string {
  return ids.join(', ');
}
