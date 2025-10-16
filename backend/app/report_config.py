from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.config import settings


@dataclass(frozen=True, slots=True)
class TopicConfig:
    """Configuration describing a single ejudge topic."""

    title: str
    problems_url: str
    contest_ids: tuple[int, ...]


_DEFAULT_TOPICS: tuple[TopicConfig, ...] = (
    TopicConfig(
        title='cs0010 Simple Calculations',
        problems_url='https://island.leaders.tech/cs/cs0010__Simple_calculations.html',
        contest_ids=(301,),
    ),
    TopicConfig(
        title='cs0020 Integer Computations',
        problems_url='https://island.leaders.tech/cs/cs0020__Integer_calculations.html',
        contest_ids=(302,),
    ),
    TopicConfig(
        title='cs0030 Conditional statement',
        problems_url='https://island.leaders.tech/cs/cs0030__If_statements.html',
        contest_ids=(303,),
    ),
    TopicConfig(
        title='cs0040 For statements',
        problems_url='https://island.leaders.tech/cs/cs0040__For_statements.html',
        contest_ids=(307,),
    ),
    TopicConfig(
        title='cs0050 Float numbers',
        problems_url='https://island.leaders.tech/cs/cs0050__Float_numbers.html',
        contest_ids=(321,),
    ),
)


def _normalise_contest_ids(raw: Any) -> tuple[int, ...]:
    if isinstance(raw, int):
        return (raw,)
    if isinstance(raw, Iterable):
        contest_ids = tuple(int(item) for item in raw)
        if not contest_ids:
            msg = 'contest_ids cannot be an empty iterable.'
            raise ValueError(msg)
        return contest_ids
    msg = f'Unsupported contest identifier payload: {raw!r}'
    raise TypeError(msg)


def _load_topics_from_json(path: Path) -> tuple[TopicConfig, ...]:
    with path.open('r', encoding='utf-8') as fh:
        payload = json.load(fh)

    topics: list[TopicConfig] = []
    for entry in payload:
        if not isinstance(entry, list | tuple) or len(entry) != 3:
            msg = f'Invalid topic entry: {entry!r}'
            raise ValueError(msg)
        title, problems_url, contest_ids = entry
        topics.append(
            TopicConfig(
                title=str(title),
                problems_url=str(problems_url),
                contest_ids=_normalise_contest_ids(contest_ids),
            )
        )
    return tuple(topics)


def load_topics() -> tuple[TopicConfig, ...]:
    """Return the configured list of report topics."""

    path_value = settings.ejudge_topics_path
    if path_value:
        path = Path(path_value)
        if not path.exists():
            msg = f'Ejudge topics file {path} does not exist.'
            raise FileNotFoundError(msg)
        return _load_topics_from_json(path)
    return _DEFAULT_TOPICS


__all__ = ['TopicConfig', 'load_topics']
