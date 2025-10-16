from __future__ import annotations

from datetime import UTC, datetime

from backend.app.report_config import TopicConfig
from backend.app.reporting import ProblemSummary, ReportsResponse, RunPayload, TopicPayload


def _timestamp(year: int, month: int, day: int) -> float:
    return datetime(year, month, day, tzinfo=UTC).timestamp()


def _build_sample_payloads() -> list[TopicPayload]:
    topics = (
        TopicConfig('Sample Basics', 'https://example.com/sample-basics', (1,)),
        TopicConfig('Sample Loops', 'https://example.com/sample-loops', (2,)),
    )

    problems_basics = [
        ProblemSummary(code='A', name='Simple Sum', points=1),
        ProblemSummary(code='B', name='Absolute Value', points=1),
        ProblemSummary(code='C', name='Average', points=2),
    ]

    problems_loops = [
        ProblemSummary(code='A', name='Counting Stars', points=2),
        ProblemSummary(code='B', name='Fibonacci', points=3),
    ]

    runs_basics = [
        RunPayload({'run_id': 1, 'status_str': 'OK', 'user_name': 'DP1 Altair Akanov', 'prob_name': 'A', 'run_time': _timestamp(2025, 1, 6)}),
        RunPayload({'run_id': 2, 'status_str': 'OK', 'user_name': 'DP1 Altair Akanov', 'prob_name': 'B', 'run_time': _timestamp(2025, 1, 13)}),
        RunPayload({'run_id': 3, 'status_str': 'OK', 'user_name': 'DP1 Artyom Konukhov', 'prob_name': 'A', 'run_time': _timestamp(2025, 1, 6)}),
        RunPayload({'run_id': 4, 'status_str': 'PR', 'user_name': 'DP1 Artyom Konukhov', 'prob_name': 'B', 'run_time': _timestamp(2025, 1, 8)}),
        RunPayload({'run_id': 5, 'status_str': 'OK', 'user_name': 'MYP4 Ada Bezvinner', 'prob_name': 'B', 'run_time': _timestamp(2025, 1, 20)}),
        RunPayload({'run_id': 6, 'status_str': 'OK', 'user_name': 'MYP4 Ada Bezvinner', 'prob_name': 'C', 'run_time': _timestamp(2025, 1, 20)}),
    ]

    runs_loops = [
        RunPayload({'run_id': 7, 'status_str': 'OK', 'user_name': 'DP1 Altair Akanov', 'prob_name': 'A', 'run_time': _timestamp(2025, 1, 27)}),
        RunPayload({'run_id': 8, 'status_str': 'OK', 'user_name': 'DP1 Artyom Konukhov', 'prob_name': 'B', 'run_time': _timestamp(2025, 2, 3)}),
        RunPayload({'run_id': 9, 'status_str': 'OK', 'user_name': 'MYP4 Ada Bezvinner', 'prob_name': 'A', 'run_time': _timestamp(2025, 2, 10)}),
    ]

    return [
        TopicPayload(
            config=topics[0],
            problems=problems_basics,
            runs=list(runs_basics),
        ),
        TopicPayload(
            config=topics[1],
            problems=problems_loops,
            runs=list(runs_loops),
        ),
    ]


def build_sample_report() -> ReportsResponse:
    from backend.app.reporting import _build_topics_report

    return _build_topics_report(_build_sample_payloads())


__all__ = ['build_sample_report']
