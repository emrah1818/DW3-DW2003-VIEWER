# Architektur

```
 Abbild (.cue/.bin/.iso, nur gelesen)
        │
 ┌──────▼───────────┐   dw3viewer/disc.py       1 Disc Reader: ISO9660, 2048/2352-Byte-Sektoren, CUE
 │ Disc Reader      │   dw3viewer/recovery.py     versteckte Verzeichnissätze wiederfinden
 └──────┬───────────┘
 ┌──────▼───────────┐   dw3viewer/game.py       2 Asset Scanner: Version (SLUS/SLES/SLPS), Dateitabelle
 │ Asset Scanner    │   dw3viewer/names.py        des Programms, Kämpfertabelle, DIGNAM-Namen
 │                  │   dw3viewer/library.py      Katalog der Modelldateien, Cache je Abbild
 └──────┬───────────┘
 ┌──────▼───────────┐   native/dw3_converter    3–5 Model Parser, Texture Decoder, Animation Parser
 │ Konverter (C++)  │   (MIT, aus dw3-model-      (aus dw3_decomp portiert): schreibt model.glb,
 │                  │    viewer)                  texN.png, native_source.json; --scripts für Skripte
 └──────┬───────────┘
 ┌──────▼───────────┐   dw3viewer/library.py    Details je Modell (meta.json): Zählungen, Texturen,
 │ Modell-Details   │   dw3viewer/motions.py      Motions mit Namen aus dem Code, ausgeblendete Knochen
 └──────┬───────────┘
 ┌──────▼───────────┐   dw3viewer/export.py     8 Export: GLB, OBJ+MTL+PNG, PNG, Motions-JSON, Metadaten
 │ Export / HD      │   dw3viewer/hd.py           HD-Texturen je Version und Modelldatei
 └──────┬───────────┘
 ┌──────▼───────────┐   dw3viewer/server.py     lokaler HTTP-Server 127.0.0.1 + Zufallstoken,
 │ API              │                             JSON-Methoden, liefert Oberfläche und Cache
 └──────┬───────────┘
 ┌──────▼───────────┐   www/view3d.js           6 3D Renderer: three.js/WebGL 2, Skinning, Nearest-Filter,
 │ 3D Renderer      │                             Drahtgitter, Gitter, Skelett, HD-Seiten, Vergleich
 ├──────────────────┤   www/app.js, index.html  7 Oberfläche: Liste | 3D | Info/Animationen/Texturen/
 │ Oberfläche       │                             Export, Timeline unten; Deutsch/Englisch
 └──────┬───────────┘
 ┌──────▼───────────┐   dw3viewer/desktop.py    Windows-/Linux-Fenster (PyQt6 + Qt WebEngine),
 │ Desktop          │   run.py, *.spec            Dateidialoge, PyInstaller-Paket
 └──────────────────┘
```

## Grundsätze
- **Nur lesen.** Das Abbild wird nie geschrieben; der Cache liegt unter `%LOCALAPPDATA%\DW3-DW2003-Viewer`
  (Linux: `~/.local/share/dw3-dw2003-viewer`), je Abbild ein Ordner (Pfad, Größe, Änderungszeit als Schlüssel).
  Ändert sich das Abbild, verlangt der Viewer ein erneutes Öffnen.
- **Nichts erfinden.** Versatz, Tabelle, Name oder Bedeutung kommen aus dw3_decomp oder werden gemessen; was
  nicht passt, wird gemeldet (z. B. Datei ohne Knochenliste), nicht geraten.
- **Stabil bei fremden Daten.** Jeder Fehler eines Modells wird als Meldung angezeigt; der Server läuft weiter.
- **Eigenständig.** Eigenes Repository, keine Abhängigkeit vom Mod Studio zur Laufzeit. Übernommene Teile sind
  kopiert und hier dokumentiert (DEVELOPMENT_LOG.md).

## Erweiterbarkeit (geplant)
- Editor: Der C++-Konverter kann Meshes, Schlüssel und TIMs bereits zurückschreiben (`patch_vecs`,
  `patch_keys`, `patch_tims`, `replace_entries`); eine Bearbeitung würde nur als Mod-Datei neben dem Abbild
  gespeichert.
- Import in den DW2-PC-Port: Der gleiche Konverter wird im DW2 Mod Studio dafür benutzt; der Viewer kann
  später Modelle direkt als Mod-Paket übergeben.
- Weitere Modelle (Effekte, DNA-Formen), Gesichtsanimation, Kampfbühnen-Licht: im selben Ablauf über neue
  Felder in `meta.json` und Schalter in der Oberfläche.
