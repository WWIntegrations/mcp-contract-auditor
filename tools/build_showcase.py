"""Build an offline viewer from a fresh, trusted local fixture capture."""
from pathlib import Path
import base64
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def script_data(text):
    """Escape HTML delimiters without changing the decoded JSON data."""
    return (text.replace('&', '\\u0026').replace('<', '\\u003c')
            .replace('>', '\\u003e').replace('\u2028', '\\u2028')
            .replace('\u2029', '\\u2029'))


def build():
    from mcp_auditor.demo import run_demo
    from mcp_auditor.strict_json import artifact_json

    data = run_demo()
    raw = artifact_json(data, limit=16 * 1024 * 1024).decode('utf-8')
    artifacts = {'demo': raw}
    for name in ('baseline_transcript', 'candidate_transcript',
                 'baseline_snapshot', 'candidate_snapshot', 'report', 'receipt'):
        artifacts[name] = artifact_json(data[name], limit=16 * 1024 * 1024).decode('utf-8')
    licenses = {
        'Anton OFL': (ROOT / 'docs/fonts/anton/OFL.txt').read_text(),
        'Departure Mono OFL': (ROOT / 'docs/fonts/departure-mono/OFL.txt').read_text(),
        'Three.js 0.187.0 MIT': (ROOT / 'showcase/vendor-licenses/three-LICENSE.txt').read_text(),
        'esbuild 0.28.2 MIT': (ROOT / 'showcase/vendor-licenses/esbuild-LICENSE.txt').read_text(),
    }
    script = (ROOT / 'showcase/bundle.js').read_text()
    if '</script' in script.lower():
        raise ValueError('Unexpected script closing tag in bundle')
    html = (ROOT / 'showcase/template.html').read_text()
    replacements = {
        '/*__STYLE__*/': (ROOT / 'showcase/style.css').read_text(),
        '__DATA__': script_data(raw),
        '__ARTIFACTS__': script_data(json.dumps(artifacts, ensure_ascii=True, separators=(',', ':'))),
        '__LICENSES__': script_data(json.dumps(licenses, ensure_ascii=True, separators=(',', ':'))),
        '<!--__DIAGRAM__-->': (ROOT / 'docs/architecture.svg').read_text(),
        '/*__SCRIPT__*/': script,
    }
    for token, value in replacements.items():
        if html.count(token) != 1:
            raise ValueError(f'Expected one template token: {token}')
        html = html.replace(token, value)
    for token, name in (
        ('__ANTON__', 'docs/fonts/anton/Anton-Regular.ttf'),
        ('__DEPARTURE__', 'docs/fonts/departure-mono/DepartureMono-Regular.woff2'),
    ):
        html = html.replace(token, base64.b64encode((ROOT / name).read_bytes()).decode('ascii'))
    html = html.rstrip() + '\n'
    target = ROOT / 'docs/index.html'
    target.write_text(html)
    print(f'{target.relative_to(ROOT)}: {len(html.encode())} bytes sha256={hashlib.sha256(html.encode()).hexdigest()}')


if __name__ == '__main__':
    build()
