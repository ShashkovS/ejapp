from __future__ import annotations

from backend.app.report_samples import build_sample_report
from backend.app.reporting import parse_problems


def test_parse_problems_extracts_metadata() -> None:
    html = """
    <div>
      <h3 class="prob_name">A: Sample Problem (3 pt)</h3>
      <h3 class="prob_name">B★: Stars &amp; Bars (2 pts)</h3>
      <!-- Comment should be ignored -->
      <h3 class="prob_name">C*: Hidden Name</h3>
    </div>
    """

    problems = parse_problems(html)

    assert [p.code for p in problems] == ['A', 'B', 'C']
    assert problems[1].name == 'Stars & Bars'
    assert problems[0].points == 3
    assert problems[2].points == 1


def test_build_sample_report_provides_consistent_summary() -> None:
    report = build_sample_report()

    assert report.users == ['DP1 Altair Akanov', 'DP1 Artyom Konukhov', 'MYP4 Ada Bezvinner']
    assert len(report.topics) == 2

    basics = next(topic for topic in report.topics if topic.name == 'Sample Basics')
    ada_row = next(row for row in basics.rows if row.user == 'MYP4 Ada Bezvinner')
    assert ada_row.solved == [False, True, True]
    assert ada_row.solved_count == 2
    assert ada_row.score == 3

    loops_summary = report.summary['DP1 Artyom Konukhov']['Sample Loops']
    assert loops_summary.solved == 1
    assert loops_summary.score == 3

    assert report.weekly.weeks
    assert report.weekly.data['DP1 Altair Akanov'][report.weekly.weeks[0]] >= 0
