import '../src/style.css';
import {
  ContestReport,
  ContestReportsResponse,
  formatContestInput,
  formatTooltip,
  hasHighlight,
  highlightClass,
  parseContestInput,
  participantDisplayName,
} from './contestReports';

const API_BASE = (import.meta as any).env?.VITE_API_BASE || 'http://localhost:8000';
const accessToken = localStorage.getItem('accessToken');
const refreshToken = localStorage.getItem('refreshToken');

const configInput = document.getElementById('contest-config') as HTMLInputElement;
const configForm = document.getElementById('contest-config-form') as HTMLFormElement;
const statusMessage = document.getElementById('status-message') as HTMLParagraphElement;
const reportsSection = document.getElementById('reports-section') as HTMLElement;
const logoutLink = document.getElementById('logout-link');

if (!accessToken) {
  window.location.href = '/';
}

function setStatus(message: string, kind: 'info' | 'error' = 'info') {
  statusMessage.textContent = message;
  statusMessage.className = kind === 'error' ? 'text-sm text-red-600' : 'text-sm text-gray-600';
}

async function apiRequest(path: string, options: RequestInit = {}) {
  const headers = options.headers ? new Headers(options.headers) : new Headers();
  headers.set('Authorization', `Bearer ${localStorage.getItem('accessToken')}`);
  options.headers = headers;

  const response = await fetch(`${API_BASE}${path}`, options);
  if (response.status === 401 && refreshToken) {
    const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${refreshToken}` },
    });
    if (refreshRes.ok) {
      const data = await refreshRes.json();
      localStorage.setItem('accessToken', data.access_token);
      headers.set('Authorization', `Bearer ${data.access_token}`);
      return fetch(`${API_BASE}${path}`, options);
    }
  }
  return response;
}

async function fetchContestConfig(): Promise<number[]> {
  const response = await apiRequest('/private/contest-config');
  if (!response.ok) {
    const detail = await safeDetail(response);
    throw new Error(detail ?? 'Не удалось загрузить конфигурацию контестов.');
  }
  const payload = (await response.json()) as { contest_ids: number[] };
  return payload.contest_ids ?? [];
}

async function saveContestConfig(ids: number[]): Promise<number[]> {
  const response = await apiRequest('/private/contest-config', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ contest_ids: ids }),
  });
  if (!response.ok) {
    const detail = await safeDetail(response);
    throw new Error(detail ?? 'Не удалось сохранить конфигурацию контестов.');
  }
  const payload = (await response.json()) as { contest_ids: number[] };
  return payload.contest_ids ?? [];
}

async function fetchContestReports(): Promise<ContestReportsResponse> {
  const response = await apiRequest('/private/contest-reports');
  if (!response.ok) {
    const detail = await safeDetail(response);
    throw new Error(detail ?? 'Не удалось загрузить отчёты.');
  }
  return (await response.json()) as ContestReportsResponse;
}

async function safeDetail(response: Response): Promise<string | null> {
  try {
    const payload = await response.json();
    if (payload && typeof payload.detail === 'string') {
      return payload.detail;
    }
  } catch (error) {
    console.warn('Failed to parse error payload', error);
  }
  return null;
}

function renderReports(payload: ContestReportsResponse) {
  reportsSection.innerHTML = '';
  if (!payload.contests.length) {
    const empty = document.createElement('p');
    empty.className = 'text-gray-600';
    empty.textContent = 'Нет данных для отображения. Сохраните конфигурацию, чтобы увидеть таблицы.';
    reportsSection.appendChild(empty);
    return;
  }

  payload.contests.forEach((contest) => {
    reportsSection.appendChild(renderContestReport(contest));
  });
}

function renderContestReport(contest: ContestReport): HTMLElement {
  const wrapper = document.createElement('article');
  wrapper.className = 'space-y-3';

  const heading = document.createElement('div');
  heading.className = 'flex flex-wrap items-baseline justify-between gap-2';

  const title = document.createElement('h2');
  title.className = 'text-2xl font-semibold';
  title.textContent = `${contest.contest_name} (#${contest.contest_id})`;
  heading.appendChild(title);

  wrapper.appendChild(heading);

  if (!contest.problems.length) {
    const noProblems = document.createElement('p');
    noProblems.className = 'text-gray-600';
    noProblems.textContent = 'В этом контесте нет задач для отображения.';
    wrapper.appendChild(noProblems);
    return wrapper;
  }

  const table = document.createElement('table');
  table.className = 'w-full border border-gray-300 bg-white text-sm shadow-sm';

  const thead = document.createElement('thead');
  const headerRow = document.createElement('tr');

  const participantHeader = document.createElement('th');
  participantHeader.textContent = 'Участник';
  participantHeader.className = 'border border-gray-300 bg-gray-100 px-3 py-2 text-left';
  headerRow.appendChild(participantHeader);

  contest.problems.forEach((problem) => {
    const th = document.createElement('th');
    th.textContent = problem.short_name;
    th.title = problem.long_name ?? '';
    th.className = 'border border-gray-300 bg-gray-100 px-3 py-2 text-center';
    headerRow.appendChild(th);
  });

  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  if (!contest.rows.length) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = contest.problems.length + 1;
    cell.className = 'border border-gray-200 px-3 py-4 text-center text-gray-600';
    cell.textContent = 'Нет участников с отправленными решениями.';
    row.appendChild(cell);
    tbody.appendChild(row);
  } else {
    contest.rows.forEach((rowData) => {
      const row = document.createElement('tr');
      const participantCell = document.createElement('td');
      participantCell.className = 'border border-gray-200 px-3 py-2 align-middle';
      participantCell.textContent = participantDisplayName(rowData);
      row.appendChild(participantCell);

      rowData.cells.forEach((cellData) => {
        const td = document.createElement('td');
        td.className = 'border border-gray-200 px-2 py-1 text-center align-middle';

        if (hasHighlight(cellData) && cellData.best_run) {
          const css = highlightClass(cellData.best_run.status);
          if (css) {
            css.split(' ').forEach((klass) => td.classList.add(klass));
          }
          td.title = formatTooltip(cellData.best_run);
          const symbol = document.createElement('span');
          symbol.textContent = '+';
          symbol.className = 'text-lg';
          td.appendChild(symbol);
        }

        row.appendChild(td);
      });

      tbody.appendChild(row);
    });
  }

  table.appendChild(tbody);
  wrapper.appendChild(table);
  return wrapper;
}

async function refreshReports() {
  try {
    setStatus('Загружаем отчёты…');
    const payload = await fetchContestReports();
    renderReports(payload);
    setStatus('Отчёты обновлены.');
  } catch (error) {
    console.error(error);
    setStatus(error instanceof Error ? error.message : 'Не удалось обновить отчёты.', 'error');
  }
}

async function bootstrap() {
  try {
    const ids = await fetchContestConfig();
    configInput.value = formatContestInput(ids);
    if (!ids.length) {
      renderReports({ contests: [] });
      setStatus('Укажите номера контестов и нажмите «Сохранить и загрузить».');
      return;
    }
    await refreshReports();
  } catch (error) {
    console.error(error);
    setStatus(error instanceof Error ? error.message : 'Не удалось загрузить конфигурацию.', 'error');
  }
}

configForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const ids = parseContestInput(configInput.value);
  if (!ids.length) {
    setStatus('Добавьте хотя бы один номер контеста перед сохранением.', 'error');
    renderReports({ contests: [] });
    return;
  }

  try {
    const saved = await saveContestConfig(ids);
    configInput.value = formatContestInput(saved);
    await refreshReports();
  } catch (error) {
    console.error(error);
    setStatus(error instanceof Error ? error.message : 'Не удалось сохранить конфигурацию.', 'error');
  }
});

logoutLink?.addEventListener('click', () => {
  localStorage.clear();
});

bootstrap();
