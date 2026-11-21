"""Windows/Linux desktop window: Qt WebEngine shows the interface from the local server; file dialogs
are Qt's own. The GPU draws the 3D view through WebGL (ANGLE / Direct3D 11 on Windows)."""
import json
import queue
import sys
import threading
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, QTimer, QUrl, pyqtSignal, pyqtSlot, QLocale
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QFileDialog, QMainWindow
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView

from . import __version__
from .gpu import Graphics, setup_logging, log
from .server import API, make_server, user_dir

GERMAN = (QLocale.system().uiLanguages() or ['en'])[0].lower().startswith('de')
TXT = {
    'disc': ('Abbild von Digimon World 3 / 2003 öffnen', 'Open Digimon World 3 / 2003 disc image'),
    'disc_filter': ('Abbild (*.cue *.bin *.iso *.img);;Alle Dateien (*)', 'Disc image (*.cue *.bin *.iso *.img);;All files (*)'),
    'png': ('HD-Textur (PNG) wählen', 'Choose HD texture (PNG)'),
    'folder': ('Zielordner wählen', 'Choose target folder'),
    'save': ('Speichern unter', 'Save as'),
}


def tr(key):
    return TXT[key][0 if GERMAN else 1]


class Picker(QObject):
    """Runs file dialogs on the GUI thread for the server's threads."""
    asked = pyqtSignal(str, str, object)

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.last = str(Path.home())
        self.asked.connect(self._ask, Qt.ConnectionType.QueuedConnection)

    def __call__(self, kind, suggestion=''):
        box = queue.Queue(1)
        self.asked.emit(kind, suggestion, box)
        return box.get()

    @pyqtSlot(str, str, object)
    def _ask(self, kind, suggestion, box):
        path = ''
        try:
            if kind == 'disc':
                path, _ = QFileDialog.getOpenFileName(self.window, tr('disc'), self.last, tr('disc_filter'))
            elif kind == 'png':
                path, _ = QFileDialog.getOpenFileName(self.window, tr('png'), self.last, 'PNG (*.png)')
            elif kind == 'folder':
                path = QFileDialog.getExistingDirectory(self.window, tr('folder'), self.last)
            elif kind.startswith('save:'):
                ext = Path(suggestion).suffix or '.bin'
                path, _ = QFileDialog.getSaveFileName(self.window, tr('save'), str(Path(self.last) / suggestion), f'*{ext}')
            if path:
                self.last = str(Path(path).parent if kind != 'folder' else Path(path))
        finally:
            box.put(path or None)


class Window(QMainWindow):
    def __init__(self, smoke=None, gpu=None, restart=None):
        super().__init__()
        self.setWindowTitle(f'DW3 / DW2003 Viewer {__version__}')
        self.resize(1500, 920)
        self.picker = Picker(self)
        self.api = API(picker=self.picker)
        self.api.gpu = gpu
        self.api.restart_cb = restart
        self.server = make_server(self.api)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        profile = QWebEngineProfile('DW3Viewer', self)
        self.view = QWebEngineView(self)
        self.page = QWebEnginePage(profile, self.view)
        self.view.setPage(self.page)
        self.setCentralWidget(self.view)
        self.page.renderProcessTerminated.connect(
            lambda status, code: log.error('Darstellungsprozess beendet: %s, Code %s', status, code))
        full = QAction('Vollbild' if GERMAN else 'Full screen', self)
        full.setShortcut('F11')
        full.triggered.connect(lambda: self.showNormal() if self.isFullScreen() else self.showFullScreen())
        self.addAction(full)
        self.smoke = smoke
        self.page.loadFinished.connect(self._loaded)
        self.view.setUrl(QUrl(self.server.url))

    def _loaded(self, ok):
        if not self.smoke:
            return
        start = """window.__smoke = ''; (async () => { try { const v = window.__viewer; await v.ready;
            const gl = v.view.renderer.getContext();
            await v.view.load('test/model.glb', {textures: [{file: 'tex0.png', width: 64, height: 64}], face: {parts: []}, motions: [], bones: []});
            const inst = v.view.a, clip = [...inst.clips.values()][0];
            inst.mixer.clipAction(clip).play(); v.view.playing = true;
            await new Promise(r => setTimeout(r, 1500));
            const err = gl.getError(), info = v.view.renderer.info;
            window.__smoke = JSON.stringify({ok: err === 0 && info.render.calls > 0, gl: v.view.glInfo(), version: v.info.version,
                gpu: v.info.gpu, drew: {calls: info.render.calls, triangles: info.render.triangles, glError: err,
                textures: info.memory.textures, semi: [...inst.semiModes]}}); }
            catch (e) { window.__smoke = JSON.stringify({ok: false, error: String(e && e.stack || e)}); } })(); 1"""
        self.page.runJavaScript(start, 0, lambda _r: QTimer.singleShot(300, lambda: self._poll(ok)))

    def _poll(self, ok):
        def got(r):
            if not r:
                return QTimer.singleShot(300, lambda: self._poll(ok))
            doc = json.loads(r)
            doc['loaded'] = bool(ok)
            Path(self.smoke).write_text(json.dumps(doc), encoding='utf-8')
            QApplication.instance().exit(0 if doc.get('ok') and ok else 1)
        self.page.runJavaScript("window.__smoke || ''", 0, got)

    def cleanup(self):
        try:
            self.server.shutdown()
        except Exception:
            pass
        self.view.setPage(None)
        self.page.deleteLater()

    def closeEvent(self, e):
        self.cleanup()
        super().closeEvent(e)


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    smoke = next((a.split('=', 1)[1] for a in argv if a.startswith('--smoke-test=')), None)
    forced = next((a.split('=', 1)[1] for a in argv if a.startswith('--angle=')), None)
    import os
    data = user_dir()
    data.mkdir(parents=True, exist_ok=True)
    logs = setup_logging(data)
    if os.environ.get('DW3_SOFTWARE_GL') and not forced:
        forced = 'swiftshader'      # PCs without a working GPU driver
    gpu = Graphics(data, forced)
    log.info('DW3 / DW2003 Viewer %s, Python %s, %s; Grafik %s (Wahl %s)', __version__, sys.version.split()[0],
             sys.platform, gpu.backend, gpu.choice)
    flags = os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', '').split() + gpu.chromium_flags(logs)
    os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = ' '.join(flags)
    log.info('Chromium-Schalter: %s', os.environ['QTWEBENGINE_CHROMIUM_FLAGS'])

    from PyQt6.QtCore import qInstallMessageHandler, QProcess
    qInstallMessageHandler(lambda mode, ctx, msg: log.info('Qt: %s', msg))
    app = QApplication(argv)
    app.setApplicationName('DW3 DW2003 Viewer')

    def restart():
        args = [a for a in argv[1:] if not a.startswith('--angle=')]
        QTimer.singleShot(0, lambda: (QProcess.startDetached(sys.executable, args if getattr(sys, 'frozen', False) else [argv[0]] + args),
                                      app.quit()))
    w = Window(smoke, gpu, restart)
    app.aboutToQuit.connect(w.cleanup)
    app.aboutToQuit.connect(gpu.clean_exit)
    w.show()
    if smoke:
        QTimer.singleShot(60000, lambda: app.exit(2))
    code = app.exec()
    log.info('Beendet mit Code %s', code)
    return code
