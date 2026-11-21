"""Tests with your own disc image (skipped in CI): set DW3_TEST_DISC to the .cue/.bin of
Digimon World 3 (USA) or Digimon World 2003 (PAL)."""
import json, os
from pathlib import Path
import pytest

from dw3viewer.server import API
from dw3viewer import export

DISC = os.environ.get('DW3_TEST_DISC')
pytestmark = pytest.mark.skipif(not DISC, reason='DW3_TEST_DISC nicht gesetzt (eigenes Abbild nötig)')


@pytest.fixture(scope='module')
def api(tmp_path_factory):
    a = API(data_dir=tmp_path_factory.mktemp('data'))
    a.result = a.open(DISC)
    return a


def test_version_and_catalog(api):
    s = api.result['summary']
    assert s['version'] in ('us', 'eu') and s['models'] >= 200 and s['fighters'] >= 200
    named = [m for m in api.result['catalog'] if m['status'] in ('unique', 'shared')]
    assert len(named) >= 0.9 * s['models']


def test_image_is_never_written(api):
    st = Path(api.lib.path).stat()
    api.model(0)
    assert (st.st_size, st.st_mtime_ns) == api.lib.stamp


def test_every_model_converts_or_reports(api):
    ok, failed = 0, []
    for m in api.result['catalog']:
        try:
            meta = api.model(m['id'])['meta']
            assert meta['counts']['triangles_gpu'] > 0 and meta['textures']
            assert all(t['width'] > 0 for t in meta['textures'])
            ok += 1
        except ValueError as e:
            failed.append((m['file'], str(e)))
    assert ok >= len(api.result['catalog']) - 2, failed


def _by_name(api, name):
    return next(m for m in api.result['catalog'] if m['name'] == name)


@pytest.mark.skipif(not DISC or 'USA' not in DISC, reason='nur USA geprüft')
def test_guilmon_known_values(api):
    meta = api.model(_by_name(api, 'Guilmon')['id'])['meta']
    assert meta['file'] == 'M366GIRU.BIN' and meta['counts']['bones'] == 24
    assert meta['motions'][0]['name'].startswith('Idle') and 0 in meta['motions'][0]['scripts']
    assert any(m['name'] == 'K. o.' for m in meta['motions'])
    assert meta['motion_count'] == 62


def test_obj_matches_glb(api, tmp_path):
    ident = _by_name(api, 'Agumon')['id']
    meta = api.model(ident)['meta']
    files = export.obj(api.lib.folder(ident), tmp_path, 'agumon')
    text = files[0].read_text()
    assert text.count('\nf ') == meta['counts']['triangles_gpu']
    assert text.count('\nv ') == meta['counts']['vertices_gpu']


def test_hidden_bones_recorded(api):
    meta = api.model(_by_name(api, 'WarGreymon')['id'])['meta']
    assert meta['motions'][0]['hidden'], 'WarGreymons Effekt-Knochen sind im Idle ausgeblendet'
