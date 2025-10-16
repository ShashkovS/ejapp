export interface ProblemSummary {
  code: string;
  name: string;
  points: number;
}

export interface TopicUserRow {
  user: string;
  solved: boolean[];
  solvedCount: number;
  score: number;
}

export interface TopicReport {
  name: string;
  problems: ProblemSummary[];
  rows: TopicUserRow[];
}

export interface SummaryCell {
  solved: number;
  score: number;
}

export interface ReportsSummary {
  [user: string]: {
    [topic: string]: SummaryCell;
  };
}

export interface WeeklySummary {
  weeks: string[];
  data: Record<string, Record<string, number>>;
}

export interface ReportsResponse {
  users: string[];
  topics: TopicReport[];
  summary: ReportsSummary;
  weekly: WeeklySummary;
}
