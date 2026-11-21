"""Local HTTP server between the interface (www/) and the library: 127.0.0.1 only, behind a random
token. GET serves the interface, converted models and HD textures; POST /<token>/api/<method> calls
one of API's methods with a JSON list of arguments."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
import mimetypes
import os
from pathlib import Path
import secrets
import threading
import traceback
from urllib.parse import unquote

from . import __version__, export, hd
from .library import Library, resource_root

mimetypes.add_type('text/javascript', '.js')
mimetypes.add_type('model/gltf-binary', '.glb')


def user_dir():
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
        return base / 'DW3-DW2003-Viewer'
    return Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share') / 'dw3-dw2003-viewer'


class API:
    """Every method takes plain JSON values and returns plain JSON values."""

    def __init__(self, data_dir=None, picker=None):
        self.data = Path(data_dir) if data_dir else user_dir()
        self.data.mkdir(parents=True, exist_ok=True)
        self.lib = None
        self.picker = picker          # desktop: callable(kind, suggestion) -> path or None
        self.lock = threading.Lock()
        self.gpu = None                 # desktop: gpu.Graphics
        self.restart_cb = None

    # -- helpers
    def _lib(self):
        if not self.lib:
            raise ValueError('Bitte zuerst ein Abbild öffnen.')
        return self.lib

    def _pick(self, kind, path, suggestion=''):
        if path:
            return path
        if not self.picker:
            raise ValueError('Kein Pfad angegeben.')
        return self.picker(kind, suggestion)

    # -- methods
    def app_info(self):
        return {'version': __version__, 'data_dir': str(self.data), 'desktop': self.picker is not None,
                'gpu': self.gpu.info() if self.gpu else None}

    def gpu_mark(self, what, gl=None):
        if self.gpu and what in ('drawing', 'drawn', 'ready'):
            self.gpu.mark(what, gl)
        return True

    def gpu_set(self, choice, restart=False):
        if not self.gpu:
            raise ValueError('Nur im Programmfenster verfügbar.')
        self.gpu.set_choice(choice)
        if restart and self.restart_cb:
            self.gpu.clean_exit()
            self.restart_cb()
        return self.gpu.info()

    def log_client(self, level, text):
        import logging
        logging.getLogger('dw3viewer.ui').log(logging.ERROR if level == 'error' else logging.INFO, '%s', str(text)[:4000])
        return True

    def open(self, path=None):
        path = self._pick('disc', path)
        if not path:
            return None
        try:
            with self.lock:
                self.lib = Library(path, self.data / 'cache')
        except FileNotFoundError as e:
            raise ValueError(f'Datei nicht gefunden: {e.filename or e}. Bei einer .cue muss die .bin daneben liegen.') from e
        except ValueError as e:
            msg = str(e)
            if 'ISO9660' in msg or 'sector size' in msg.lower() or 'Sector outside' in msg or 'CD sector mode' in msg:
                raise ValueError(f'Kein lesbares CD-Abbild ({msg}). Bitte die .cue oder .bin von Digimon World 3 wählen.') from e
            raise
        return {'summary': self.lib.summary(), 'catalog': self.lib.catalog(), 'cache': self.lib.key}

    def summary(self):
        return self._lib().summary()

    def catalog(self):
        return self._lib().catalog()

    def model(self, ident):
        lib = self._lib()
        with self.lock:
            meta = lib.model(int(ident))
        base = f'cache/{lib.key}/model_{int(ident):04d}/'
        return {'meta': meta, 'base': base, 'hd': self.hd_list(ident)}

    def export(self, ident, kind, dest=None):
        lib = self._lib()
        meta = lib.model(int(ident))
        folder = lib.folder(int(ident))
        stem = f"{meta['code']}_{''.join(c for c in meta['name'] if c.isalnum() or c in '-_') or 'model'}"
        if kind in ('glb', 'json', 'motions', 'debug'):
            ext = {'glb': '.glb', 'json': '.json', 'motions': '.motions.json', 'debug': '.debug.json'}[kind]
            dest = self._pick('save:' + kind, dest, stem + ext)
            if not dest:
                return None
            files = {'glb': lambda: export.glb(folder, dest), 'json': lambda: export.metadata(meta, dest),
                     'motions': lambda: export.motions(folder, meta, dest), 'debug': lambda: export.debug(folder, meta, dest)}[kind]()
        elif kind in ('obj', 'png', 'hd'):
            dest = self._pick('folder', dest)
            if not dest:
                return None
            target = Path(dest) / stem
            if kind == 'obj':
                files = export.obj(folder, target, stem)
            elif kind == 'png':
                files = export.textures(folder, target)
            else:
                files = hd.export_all(self.data, lib.info['id'], meta['file'], target)
        else:
            raise ValueError('Unbekanntes Exportformat')
        return [str(p) for p in files]

    def geometry(self, ident):
        """Bones with their polygons (texture page, mode, UVs in texels) for the debug view; no motion samples."""
        lib = self._lib()
        lib.model(int(ident))
        src = json.loads((lib.folder(int(ident)) / 'native_source.json').read_text(encoding='utf-8'))
        return {'bones': [{'parent': b['parent'], 'vertices': len(b['vertices']),
                           'faces': [{'image': f['image'], 'abr': f['abr'], 'uv': f['uv']} for f in b['faces']]}
                          for b in src['bones']], 'images': src['images']}

    def hd_list(self, ident):
        lib = self._lib()
        meta = lib.rows[int(ident)]
        found = hd.listing(self.data, lib.info['id'], meta['file'])
        stem = Path(meta['file']).stem.upper()
        return {k: dict(v, url=f"hd/{lib.info['id']}/{stem}/{k}?v={v['mtime']}") for k, v in found.items()}

    def hd_import(self, ident, texture, path=None):
        lib = self._lib()
        path = self._pick('png', path)
        if not path:
            return None
        hd.import_png(self.data, lib.info['id'], lib.rows[int(ident)]['file'], texture, path)
        return self.hd_list(ident)

    def hd_remove(self, ident, texture):
        lib = self._lib()
        hd.remove(self.data, lib.info['id'], lib.rows[int(ident)]['file'], texture)
        return self.hd_list(ident)

    def save_thumb(self, ident, data_url):
        """A small preview of model IDENT (PNG data URL, at most 64 KB), kept in the image's cache."""
        import base64
        lib = self._lib()
        lib._check(int(ident))
        if not str(data_url).startswith('data:image/png;base64,'):
            raise ValueError('Kein PNG')
        data = base64.b64decode(data_url.split(',', 1)[1])
        if len(data) > 64 * 1024 or not data.startswith(b'\x89PNG'):
            raise ValueError('Vorschaubild zu groß')
        folder = lib.cache / 'thumbs'
        folder.mkdir(exist_ok=True)
        tmp = folder / f'{int(ident)}.tmp'
        tmp.write_bytes(data)
        tmp.replace(folder / f'{int(ident)}.png')
        return f'cache/{lib.key}/thumbs/{int(ident)}.png'

    def save_png(self, data_url, suggestion='screenshot.png', dest=None):
        import base64
        if not str(data_url).startswith('data:image/png;base64,'):
            raise ValueError('Kein PNG')
        dest = self._pick('save:png', dest, suggestion)
        if not dest:
            return None
        Path(dest).write_bytes(base64.b64decode(data_url.split(',', 1)[1]))
        return str(dest)

    METHODS = ('app_info', 'open', 'summary', 'catalog', 'model', 'export', 'geometry', 'hd_list', 'hd_import', 'hd_remove', 'save_png', 'save_thumb', 'gpu_mark', 'gpu_set', 'log_client')


def make_server(api, host='127.0.0.1', port=0):
    token = secrets.token_hex(16)
    www = resource_root() / 'www'

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype='application/json; charset=utf-8', extra=None):
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _file(self, root, rel):
            root = Path(root).resolve()
            p = (root / rel).resolve()
            if root not in p.parents and p != root or not p.is_file():
                return self._send(404, b'not found', 'text/plain')
            ctype = mimetypes.guess_type(p.name)[0] or 'application/octet-stream'
            self._send(200, p.read_bytes(), ctype)

        def do_GET(self):
            path = unquote(self.path.split('?', 1)[0])
            prefix = f'/{token}/'
            if not path.startswith(prefix):
                return self._send(403, b'forbidden', 'text/plain')
            rel = path[len(prefix):]
            if rel.startswith('cache/'):
                return self._file(api.data / 'cache', rel[6:])
            if rel.startswith('hd/'):
                return self._file(api.data / 'hd', rel[3:])
            return self._file(www, rel or 'index.html')

        def do_POST(self):
            path = self.path.split('?', 1)[0]
            prefix = f'/{token}/api/'
            if not path.startswith(prefix):
                return self._send(403, b'{}')
            name = path[len(prefix):]
            if name not in API.METHODS:
                return self._send(404, json.dumps({'ok': False, 'error': 'Unbekannte Methode'}).encode())
            try:
                n = int(self.headers.get('Content-Length') or 0)
                args = json.loads(self.rfile.read(n) or b'[]') if n else []
                if not isinstance(args, list):
                    raise ValueError('Argumente müssen eine Liste sein')
                if name in ('open', 'model', 'export'):
                    import logging
                    logging.getLogger('dw3viewer.api').info('%s %s', name, args[:2])
                result = getattr(api, name)(*args)
                body = {'ok': True, 'data': result}
            except Exception as e:  # report every failure to the interface, keep serving
                import logging
                logging.getLogger('dw3viewer.api').warning('%s%s fehlgeschlagen', name, tuple(args) if 'args' in dir() else '', exc_info=True)
                body = {'ok': False, 'error': str(e) or e.__class__.__name__}
            self._send(200, json.dumps(body, ensure_ascii=False).encode('utf-8'))

    srv = ThreadingHTTPServer((host, port), Handler)
    srv.daemon_threads = True
    srv.token = token
    srv.url = f'http://{host}:{srv.server_port}/{token}/'
    return srv
