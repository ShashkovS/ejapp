"""Utilities for producing ejudge-compatible ``statement.xml`` files."""

from __future__ import annotations

from pathlib import Path
from typing import Final
from xml.sax.saxutils import escape as xml_escape

_XML_DECLARATION_TEMPLATE: Final[str] = '<?xml version="1.0" encoding="{encoding}"?>\n'


def _sanitize_cdata_payload(payload: str) -> str:
    """Ensure the payload is safe to embed inside a CDATA section."""

    # ejudge tolerates HTML fragments inside ``<description>`` but expects the
    # enclosing XML document to remain well formed. Wrapping the raw fragment in
    # a CDATA node keeps the HTML untouched while avoiding mismatched tag
    # failures during config reloads. The only sequence that needs escaping is
    # ``]]>`` which prematurely terminates the CDATA block.
    return payload.replace(']]>', ']]]]><![CDATA[>')


def render_statement_xml(
    *,
    body_html: str,
    title: str | None = None,
    short_name: str | None = None,
    language: str = 'ru',
    encoding: str = 'utf-8',
) -> str:
    """Render an ejudge ``statement.xml`` document wrapping ``body_html``.

    The generated XML mirrors the structure produced by the official ejudge
    tooling (`<problem><statements><statement ...></statement></statements>`)
    but keeps the description body inside a CDATA section. This avoids parser
    crashes when the HTML fragment contains unbalanced tags, which the ejudge
    UI happily emits.
    """

    normalized_body = _sanitize_cdata_payload(body_html.replace('\r\n', '\n'))

    parts: list[str] = [_XML_DECLARATION_TEMPLATE.format(encoding=encoding)]
    parts.append('<problem>')
    if short_name:
        parts.append(f'  <short-name>{xml_escape(short_name)}</short-name>')
    parts.append('  <statements>')
    parts.append(f'    <statement language="{xml_escape(language)}">')
    if title:
        parts.append(f'      <title>{xml_escape(title)}</title>')
    parts.append(f'      <description><![CDATA[{normalized_body}]]></description>')
    parts.append('    </statement>')
    parts.append('  </statements>')
    parts.append('</problem>\n')
    return '\n'.join(parts)


def write_statement_xml(
    destination: str | Path,
    *,
    body_html: str,
    title: str | None = None,
    short_name: str | None = None,
    language: str = 'ru',
    encoding: str = 'utf-8',
) -> Path:
    """Persist a rendered statement document to ``destination``.

    Returns the :class:`Path` pointing at the written file so callers can chain
    operations (e.g. copying alongside tests). The helper writes atomically by
    going through a temporary file in the same directory.
    """

    path = Path(destination)
    document = render_statement_xml(
        body_html=body_html,
        title=title,
        short_name=short_name,
        language=language,
        encoding=encoding,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + '.tmp')
    with temp_path.open('w', encoding=encoding, newline='\n') as handle:
        handle.write(document)
    temp_path.replace(path)
    return path


__all__ = ['render_statement_xml', 'write_statement_xml']
