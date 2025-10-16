import { useEffect, useMemo, useState } from 'react';
import { fetchReports, logout } from './api';
import type { ReportsResponse, TopicReport } from './types';

const HEATMAP_STOPS: ReadonlyArray<{ stop: number; color: [number, number, number] }> = [
  { stop: 0, color: [248, 105, 107] },
  { stop: 0.5, color: [255, 235, 132] },
  { stop: 1, color: [99, 190, 123] },
];

type HeatmapMode = 'solved' | 'score';

type TableCellStyle = { backgroundColor: string; color: string } | undefined;

function interpolateColor(ratio: number): string {
  const clamped = Math.min(1, Math.max(0, ratio));
  let lower = HEATMAP_STOPS[0];
  let upper = HEATMAP_STOPS[HEATMAP_STOPS.length - 1];
  for (let i = 0; i < HEATMAP_STOPS.length - 1; i += 1) {
    const next = HEATMAP_STOPS[i + 1];
    if (clamped <= next.stop) {
      lower = HEATMAP_STOPS[i];
      upper = next;
      break;
    }
  }
  const span = upper.stop - lower.stop || 1;
  const factor = (clamped - lower.stop) / span;
  const [r, g, b] = lower.color.map((component, index) => {
    const delta = upper.color[index] - component;
    return Math.round(component + delta * factor);
  });
  const toHex = (value: number) => value.toString(16).padStart(2, '0');
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

function textColorForBackground(hex: string): string {
  const value = hex.replace('#', '');
  const r = parseInt(value.slice(0, 2), 16);
  const g = parseInt(value.slice(2, 4), 16);
  const b = parseInt(value.slice(4, 6), 16);
  const brightness = (r * 299 + g * 587 + b * 114) / 1000;
  return brightness > 150 ? '#1a1a1a' : '#ffffff';
}

function cellStyle(value: number, min: number, max: number): TableCellStyle {
  if (Number.isNaN(value) || max <= min) {
    return undefined;
  }
  const ratio = (value - min) / (max - min);
  const backgroundColor = interpolateColor(ratio);
  return { backgroundColor, color: textColorForBackground(backgroundColor) };
}

function deriveGroup(user: string): string | null {
  const match = user.match(/^(DP\d+|MYP\d+)/i);
  return match ? match[0] : null;
}

function TopicTable({ topic, users }: { topic: TopicReport; users: string[] }) {
  if (!users.length || topic.problems.length === 0) {
    return (
      <div className="topic" key={topic.name}>
        <h2>{topic.name}</h2>
        <p>No data.</p>
      </div>
    );
  }

  const rowMap = new Map(topic.rows.map((row) => [row.user, row]));

  return (
    <div className="topic" key={topic.name}>
      <h2>{topic.name}</h2>
      <div className="table-wrapper">
        <table className="report-table" data-testid="topic-table">
          <thead>
            <tr>
              <th>User</th>
              {topic.problems.map((problem) => (
                <th key={problem.code} title={`${problem.name} (${problem.points} pt)`}>
                  {problem.code}
                </th>
              ))}
              <th>Total</th>
              <th>Score</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => {
              const row = rowMap.get(user);
              const solved = row?.solved ?? new Array(topic.problems.length).fill(false);
              const solvedCount = row?.solvedCount ?? 0;
              const score = row?.score ?? 0;
              return (
                <tr key={user}>
                  <td>{user}</td>
                  {solved.map((flag, index) => (
                    <td key={`${user}-${topic.problems[index].code}`}>{flag ? '+' : ''}</td>
                  ))}
                  <td>{solvedCount}</td>
                  <td>{score}</td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr>
              <td>Points</td>
              {topic.problems.map((problem) => (
                <td key={`points-${problem.code}`}>{problem.points}</td>
              ))}
              <td></td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}

interface SummaryTableProps {
  title: string;
  users: string[];
  topics: TopicReport[];
  summary: ReportsResponse['summary'];
  mode: HeatmapMode;
}

function SummaryTable({ title, users, topics, summary, mode }: SummaryTableProps) {
  if (!users.length || !topics.length) {
    return null;
  }

  const ranges = useMemo(() => {
    const map = new Map<string, { min: number; max: number }>();
    topics.forEach((topic) => {
      let min = Number.POSITIVE_INFINITY;
      let max = Number.NEGATIVE_INFINITY;
      users.forEach((user) => {
        const value = summary[user]?.[topic.name]?.[mode] ?? 0;
        if (value < min) min = value;
        if (value > max) max = value;
      });
      if (min === Number.POSITIVE_INFINITY) min = 0;
      if (max === Number.NEGATIVE_INFINITY) max = 0;
      map.set(topic.name, { min, max });
    });
    return map;
  }, [users, topics, summary, mode]);

  return (
    <div className="summary">
      <h2>{title}</h2>
      <div className="table-wrapper">
        <table className="summary-table">
          <thead>
            <tr>
              <th>User</th>
              {topics.map((topic) => (
                <th key={topic.name}>{topic.name}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user}>
                <td>{user}</td>
                {topics.map((topic) => {
                  const value = summary[user]?.[topic.name]?.[mode] ?? 0;
                  const range = ranges.get(topic.name)!;
                  const style = cellStyle(value, range.min, range.max);
                  return (
                    <td key={`${user}-${topic.name}`} style={style}>
                      {value}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

interface WeeklyActivityTableProps {
  users: string[];
  weeks: string[];
  data: ReportsResponse['weekly']['data'];
}

function WeeklyActivityTable({ users, weeks, data }: WeeklyActivityTableProps) {
  if (!users.length || !weeks.length) {
    return (
      <div className="weekly">
        <h2>Weekly activity (solved problems)</h2>
        <p>No data for weekly report.</p>
      </div>
    );
  }

  const maxValue = Math.max(
    0,
    ...users.flatMap((user) => weeks.map((week) => data[user]?.[week] ?? 0)),
  );

  return (
    <div className="weekly">
      <h2>Weekly activity (solved problems)</h2>
      <div className="table-wrapper">
        <table className="summary-table">
          <thead>
            <tr>
              <th>User</th>
              {weeks.map((week) => (
                <th key={week}>{week}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user}>
                <td>{user}</td>
                {weeks.map((week) => {
                  const value = data[user]?.[week] ?? 0;
                  const style = value > 0 && maxValue > 0 ? cellStyle(value, 0, maxValue) : undefined;
                  return (
                    <td key={`${user}-${week}`} style={style}>
                      {value}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function App(): JSX.Element {
  const [data, setData] = useState<ReportsResponse | null>(null);
  const [status, setStatus] = useState<'idle' | 'loading' | 'loaded' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    let cancelled = false;
    setStatus('loading');
    fetchReports()
      .then((payload) => {
        if (!cancelled) {
          setData(payload);
          setStatus('loaded');
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err.message);
          setStatus('error');
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const groups = useMemo(() => {
    if (!data) return [] as string[];
    const set = new Set<string>();
    data.users.forEach((user) => {
      const group = deriveGroup(user);
      if (group) {
        set.add(group);
      }
    });
    return Array.from(set).sort();
  }, [data]);

  const filteredUsers = useMemo(() => {
    if (!data) return [] as string[];
    if (filter === 'all') return data.users;
    return data.users.filter((user) => deriveGroup(user) === filter);
  }, [data, filter]);

  return (
    <main className="reports-container">
      <header className="reports-header">
        <h1>Ejudge reports</h1>
        <div className="header-actions">
          {data && groups.length > 0 && (
            <label className="filter" htmlFor="reports-filter">
              <span>Filter:</span>
              <select
                id="reports-filter"
                data-testid="reports-filter"
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
              >
                <option value="all">All students</option>
                {groups.map((group) => (
                  <option key={group} value={group}>
                    {group}
                  </option>
                ))}
              </select>
            </label>
          )}
          <button type="button" className="logout" data-testid="logout-button" onClick={logout}>
            Logout
          </button>
        </div>
      </header>

      {status === 'loading' && <p className="status">Loading reports…</p>}
      {status === 'error' && <p className="status error">{error ?? 'Failed to load reports.'}</p>}

      {status === 'loaded' && data && (
        <section className="reports-content">
          {data.topics.map((topic) => (
            <TopicTable key={topic.name} topic={topic} users={filteredUsers} />
          ))}

          <SummaryTable
            title="Total by solved problems"
            users={filteredUsers}
            topics={data.topics}
            summary={data.summary}
            mode="solved"
          />
          <SummaryTable
            title="Total by point"
            users={filteredUsers}
            topics={data.topics}
            summary={data.summary}
            mode="score"
          />
          <WeeklyActivityTable users={filteredUsers} weeks={data.weekly.weeks} data={data.weekly.data} />
        </section>
      )}
    </main>
  );
}
