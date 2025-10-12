from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from backend.ejudge import render_statement_xml, write_statement_xml


def test_render_statement_xml_wraps_body_in_cdata() -> None:
    xml_text = render_statement_xml(
        body_html='<p>hello <em>world</em></p>',
        title='Max Colours',
        short_name='A',
        language='en',
    )

    root = ET.fromstring(xml_text)
    assert root.tag == 'problem'
    assert root.findtext('short-name') == 'A'

    statement = root.find('./statements/statement')
    assert statement is not None
    assert statement.attrib['language'] == 'en'
    assert statement.findtext('title') == 'Max Colours'

    description = statement.find('description')
    assert description is not None
    assert description.text == '<p>hello <em>world</em></p>'


def test_render_statement_xml_escapes_short_name_and_title() -> None:
    xml_text = render_statement_xml(
        body_html='body',
        title='Fish & Chips <tasty>',
        short_name='B&',
    )

    root = ET.fromstring(xml_text)
    assert root.findtext('short-name') == 'B&'
    assert root.find('./statements/statement/title').text == 'Fish & Chips <tasty>'


def test_render_statement_xml_handles_cdata_closer() -> None:
    body = 'Intro paragraph ]]> trailing'
    xml_text = render_statement_xml(body_html=body)

    root = ET.fromstring(xml_text)
    description = root.find('./statements/statement/description')
    assert description is not None
    assert description.text == body


def test_write_statement_xml(tmp_path: Path) -> None:
    destination = tmp_path / 'statement.xml'
    write_statement_xml(destination, body_html='<p>ok</p>', title='Sample')

    content = destination.read_text(encoding='utf-8')
    assert content.startswith('<?xml version="1.0" encoding="utf-8"?>')

    parsed = ET.fromstring(content)
    assert parsed.find('./statements/statement/title').text == 'Sample'
