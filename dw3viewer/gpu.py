"""Graphics backend for the 3D view, crash guard and log files (desktop only).

Qt WebEngine draws WebGL through ANGLE in the viewer's own process. On some PCs one ANGLE backend crashes inside the
graphics driver (seen: Direct3D 11 on an NVIDIA PC, access violation in Qt6WebEngineCore.dll while the first model
is drawn), which ends the whole program. So:
- the backend can be chosen (settings.json, the menu in the interface, or --angle=NAME);
- in "auto" mode a session that ended without a clean exit after it started drawing a model moves the next start
  to the next backend in FALLBACK;
- everything is logged to <data>/logs (viewer.log, chromium.log)."""
import faulthandler
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path

_IGN = ['--ignore-gpu-blocklist']   # otherwise Chromium refuses WebGL on blocklisted drivers (and on WARP)
if os.name == 'nt':
    BACKENDS = {
        'd3d11': {'flags': ['--use-angle=d3d11'] + _IGN, 'label': 'Direct3D 11'},
        'gl': {'flags': ['--use-angle=gl'] + _IGN, 'label': 'OpenGL'},
        'd3d11on12': {'flags': ['--use-angle=d3d11on12'] + _IGN, 'label': 'Direct3D 11 über 12'},
        'warp': {'flags': ['--use-angle=d3d11-warp'] + _IGN, 'label': 'Software (WARP, langsamer)'},
    }
    FALLBACK = ['d3d11', 'gl', 'd3d11on12', 'warp']
else:
    BACKENDS = {
        'gl': {'flags': _IGN, 'label': 'OpenGL'},
        'swiftshader': {'flags': ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] + _IGN,
                        'label': 'Software (SwiftShader, langsamer)'},
    }
    FALLBACK = ['gl', 'swiftshader']
SOFTWARE = FALLBACK[-1]
CHOICES = ['auto'] + FALLBACK

log = logging.getLogger('dw3viewer')
_fault_file = None


def setup_logging(data):
    """viewer.log (Python, Qt messages, fatal errors with stack); the previous session is kept as viewer.1.log."""
    global _fault_file
    folder = Path(data) / 'logs'
    folder.mkdir(parents=True, exist_ok=True)
    for name in ('viewer', 'chromium'):
        cur, old = folder / f'{name}.log', folder / f'{name}.1.log'
        try:
            if cur.exists():
                cur.replace(old)
        except OSError:
            pass
    handler = logging.FileHandler(folder / 'viewer.log', encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(threadName)s: %(message)s'))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    _fault_file = open(folder / 'fatal.log', 'a', encoding='utf-8')
    _fault_file.write(f'\n--- start {time.strftime("%Y-%m-%d %H:%M:%S")} pid {os.getpid()}\n')
    _fault_file.flush()
    faulthandler.enable(_fault_file, all_threads=True)
    sys.excepthook = lambda t, v, tb: log.critical('Unbehandelter Fehler', exc_info=(t, v, tb))
    threading.excepthook = lambda a: log.critical('Fehler im Thread %s', a.thread and a.thread.name,
                                                  exc_info=(a.exc_type, a.exc_value, a.exc_traceback))
    if sys.stderr is None:           # windowed build: give Python and C stderr somewhere to go
        sys.stderr = open(folder / 'stderr.log', 'w', encoding='utf-8', buffering=1)
    if sys.stdout is None:
        sys.stdout = sys.stderr
    return folder


class Graphics:
    """Settings (settings.json: {"backend": "auto" | name}) and the crash guard (gpu_state.json)."""

    def __init__(self, data, forced=None):
        self.data = Path(data)
        self.settings_file = self.data / 'settings.json'
        self.state_file = self.data / 'gpu_state.json'
        self.choice = forced or self._read(self.settings_file).get('backend', 'auto')
        if self.choice not in CHOICES:
            self.choice = 'auto'
        state = self._read(self.state_file)
        self.switched_from = None
        if self.choice == 'auto':
            backend = state.get('backend') if state.get('backend') in FALLBACK else FALLBACK[0]
            # the last session ended without a clean exit while drawing, or before the view was even ready (hang)
            if state and not state.get('clean', True) and (state.get('drawing') or not state.get('ready')):
                k = FALLBACK.index(backend)
                if k + 1 < len(FALLBACK):
                    self.switched_from = backend
                    backend = FALLBACK[k + 1]
                    log.warning('Letzte Sitzung mit %s ist abgestürzt (zeichnete: %s); wechsle zu %s',
                                self.switched_from, bool(state.get('drawing')), backend)
            self.backend = backend
        else:
            self.backend = self.choice
        self.state = {'backend': self.backend, 'clean': False, 'drawing': False, 'ready': False, 'started': time.time(),
                      'pid': os.getpid(), 'gl': None, 'ok_backend': state.get('ok_backend')}
        self._write(self.state_file, self.state)

    @staticmethod
    def _read(p):
        try:
            return json.loads(Path(p).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}

    @staticmethod
    def _write(p, doc):
        tmp = Path(p).with_suffix('.tmp')
        tmp.write_text(json.dumps(doc, indent=1), encoding='utf-8')
        tmp.replace(p)

    def chromium_flags(self, log_folder=None):
        flags = list(BACKENDS[self.backend]['flags'])
        if log_folder:
            flags += ['--enable-logging', f'--log-file={Path(log_folder) / "chromium.log"}', '--log-level=0']
        return flags

    # called from the interface
    def mark(self, what, gl=None):
        if what == 'ready':
            self.state['ready'] = True
        elif what == 'drawing':
            self.state['drawing'] = True
        elif what == 'drawn':                  # a model was drawn and the next frames came through
            self.state['ok_backend'] = self.backend
        if gl:
            self.state['gl'] = gl
        self._write(self.state_file, self.state)
        log.info('Grafik %s: %s %s', what, self.backend, gl or '')

    def clean_exit(self):
        self.state['clean'] = True
        self._write(self.state_file, self.state)

    def info(self):
        return {'backend': self.backend, 'label': BACKENDS[self.backend]['label'], 'choice': self.choice,
                'choices': [{'id': c, 'label': 'Automatisch' if c == 'auto' else BACKENDS[c]['label']} for c in CHOICES],
                'switched_from': self.switched_from, 'gl': self.state.get('gl')}

    def set_choice(self, choice):
        if choice not in CHOICES:
            raise ValueError(f'Unbekannte Grafikschnittstelle: {choice}')
        doc = self._read(self.settings_file)
        doc['backend'] = choice
        self._write(self.settings_file, doc)
        if choice != 'auto':                     # an explicit choice also resets the automatic sequence
            st = self._read(self.state_file)
            st['backend'] = choice
            self._write(self.state_file, st)
        log.info('Grafikschnittstelle gewählt: %s (ab dem nächsten Start)', choice)
        return choice
