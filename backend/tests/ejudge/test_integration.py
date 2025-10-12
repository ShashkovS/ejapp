from __future__ import annotations

import asyncio
import os
import xml.etree.ElementTree as ET
from typing import Any, TypedDict

import pytest

from backend.app.config import settings
from backend.ejudge import EjudgeClient

# -- Environment helpers -------------------------------------------------
# Pull credentials for the real ejudge instance from the environment. The
# integration suite is skipped entirely when they are not provided.
EJUDGE_ORIGIN = settings.ejudge_origin
EJUDGE_TOKEN = settings.ejudge_token

# Allow customisation of the contest identifier and filtering behaviour
# without touching the test code. Defaults mirror the shared sandbox.
DEFAULT_CONTEST_ID = 5
DEFAULT_FILTER_EXPR = 'status==OK'
CONTEST_ID = int(os.getenv('EJUDGE_CONTEST_ID', DEFAULT_CONTEST_ID))
FILTER_EXPR = os.getenv('EJUDGE_RUN_FILTER', DEFAULT_FILTER_EXPR)

pytestmark = pytest.mark.skipif(
    not EJUDGE_ORIGIN or not EJUDGE_TOKEN,
    reason='Ejudge integration tests require EJUDGE_ORIGIN and EJUDGE_TOKEN to be configured.',
)


class MasterSnapshot(TypedDict):
    runs_payload: dict[str, Any]
    sample_run: dict[str, Any]
    source_text: str
    languages_payload: dict[str, Any]
    raw_report_text: str


async def _collect_master_snapshot() -> MasterSnapshot:
    assert EJUDGE_ORIGIN is not None
    assert EJUDGE_TOKEN is not None

    async with EjudgeClient(EJUDGE_ORIGIN.rstrip('/'), EJUDGE_TOKEN) as client:
        runs_payload = await client.master.list_runs_json(
            contest_id=CONTEST_ID,
            filter_expr=FILTER_EXPR,
            first_run=0,
            last_run=10,
        )
        if not runs_payload.get('ok'):
            raise RuntimeError('ejudge returned error for list-runs-json call')

        result = runs_payload.get('result', {})
        runs = list(result.get('runs', ()))
        if not runs:
            raise pytest.SkipTest('No ejudge runs available for the provided filter.')

        sample_run = runs[0]
        run_id = sample_run['run_id']

        # Fetch extra material for downstream assertions right away so the
        # surrounding tests can remain synchronous.
        source_payload = await client.master.download_run(contest_id=CONTEST_ID, run_id=run_id)
        raw_report_payload = await client.master.raw_report(contest_id=CONTEST_ID, run_id=run_id)
        languages_payload = await client.master.list_languages(contest_id=CONTEST_ID)

    if isinstance(source_payload, bytes):
        source_text = source_payload.decode('utf-8')
    else:
        source_text = str(source_payload)

    if isinstance(raw_report_payload, bytes):
        raw_report_text = raw_report_payload.decode('utf-8')
    else:
        raw_report_text = str(raw_report_payload)

    snapshot: MasterSnapshot = {
        'runs_payload': runs_payload,
        'sample_run': sample_run,
        'source_text': source_text,
        'languages_payload': languages_payload,
        'raw_report_text': raw_report_text,
    }
    return snapshot


@pytest.fixture(scope='module')
def master_snapshot() -> MasterSnapshot:
    """Eagerly gather a consistent slice of ejudge state for reuse."""

    return asyncio.run(_collect_master_snapshot())


def test_list_runs_json_returns_recent_runs(master_snapshot: MasterSnapshot) -> None:
    runs_payload = master_snapshot['runs_payload']
    assert runs_payload['ok'] is True

    result = runs_payload['result']
    assert isinstance(result['runs'], list)
    assert result['listed_runs'] >= len(result['runs'])

    sample_run = master_snapshot['sample_run']
    assert 'run_id' in sample_run
    assert sample_run['status_str']


def test_download_run_returns_non_empty_source(master_snapshot: MasterSnapshot) -> None:
    source_text = master_snapshot['source_text']
    assert isinstance(source_text, str)
    assert source_text.strip(), 'Expected ejudge to return a non-empty program body.'


def test_list_languages_includes_python(master_snapshot: MasterSnapshot) -> None:
    languages_payload = master_snapshot['languages_payload']
    assert languages_payload['ok'] is True

    languages = languages_payload['languages']
    assert 'python3' in languages
    python_entry = languages['python3']
    assert python_entry['long_name']
    assert python_entry['src_sfx'] == '.py'


def test_raw_report_includes_structured_tests(master_snapshot: MasterSnapshot) -> None:
    root = ET.fromstring(master_snapshot['raw_report_text'])
    assert root.tag == 'testing-report'

    # Attributes should expose contest and run identifiers for traceability.
    assert root.attrib.get('contest-id') == str(CONTEST_ID)
    assert 'run-id' in root.attrib

    tests_node = root.find('tests')
    assert tests_node is not None
    first_test = tests_node.find('test')
    assert first_test is not None
    assert first_test.attrib.get('status')
