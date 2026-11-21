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
from .server import API, make_server

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
    def __init__(self, smoke=None):
        super().__init__()
        self.setWindowTitle(f'DW3 / DW2003 Viewer {__version__}')
        self.resize(1500, 920)
        self.picker = Picker(self)
        self.api = API(picker=self.picker)
        self.server = make_server(self.api)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        profile = QWebEngineProfile('DW3Viewer', self)
        self.view = QWebEngineView(self)
        self.page = QWebEnginePage(profile, self.view)
        self.view.setPage(self.page)
        self.setCentralWidget(self.view)
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
        start = """window.__smoke = ''; (async () => { try { await window.__viewer.ready;
            window.__smoke = JSON.stringify({ok: true, gl: window.__viewer.view.glInfo(), version: window.__viewer.info.version}); }
            catch (e) { window.__smoke = JSON.stringify({ok: false, error: String(e)}); } })(); 1"""
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
    import os
    if smoke or os.environ.get('DW3_SOFTWARE_GL'):
        # build machines and PCs without a working GPU driver: WebGL through SwiftShader
        os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = (os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', '')
                                                   + ' --use-angle=swiftshader --enable-unsafe-swiftshader --ignore-gpu-blocklist').strip()
    app = QApplication(argv)
    app.setApplicationName('DW3 DW2003 Viewer')
    w = Window(smoke)
    app.aboutToQuit.connect(w.cleanup)
    w.show()
    if smoke:
        QTimer.singleShot(60000, lambda: app.exit(2))
    return app.exec()
