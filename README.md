# DW3 / DW2003 Viewer 0.1.0

Betrachter für die Kampfmodelle von **Digimon World 3** (USA) und **Digimon World 2003** (PAL): echte Modelle,
Originaltexturen und Originalanimationen, gelesen aus deinem eigenen Abbild. **Es sind keine Spieldaten
enthalten**, und das Abbild wird nie verändert.

*A viewer for the battle models of Digimon World 3 (USA) and Digimon World 2003 (PAL), read from your own disc
image. No game data included; the image is never changed.*

## Funktionen
- Abbild öffnen (`.cue`/`.bin`, `.iso`), Version erkennen (SLUS_014.36 / SLES_039.36 / SLPS_034.46).
- Liste aller Kampfmodelle mit den Namen aus dem Spiel, Suche (Name, Kürzel, Nummer), Filter Partner/Gegner.
  Pfeiltasten öffnen direkt das nächste Modell.
- 3D-Ansicht: drehen (linke Maustaste), verschieben (rechte), zoomen (Rad), zentrieren; PS1-Pixel (nearest)
  oder geglättet; Drahtgitter, Gitter, Rückseiten, Skelett, Hintergrundfarbe, Bild speichern.
- Animationen: alle Motions des Modells, benannt nur dort, wo der Spielcode die Bedeutung zeigt (Idle,
  Treffer, K. o., Skriptnummer), sonst „Motion N“. Abspielen, Pause, Einzelbild vor/zurück (← →, Leertaste),
  Tempo, Schleife, Bildnummer, Dauer, Vergleich zweier Motions nebeneinander.
- Infos: Modell-ID, Datei, Knochen, Vertices und Polygone (Spiel und Anzeige), Texturseiten (Größe, Farbtiefe,
  tpage/CLUT), Sektor, Größe, Dateinummer, Kämpfer, Aktionsskripte.
- HD-Modus: eigene PNG je Texturseite in beliebiger Größe (z. B. 2048 × 4096), ohne Farbreduzierung, je Modell
  gespeichert und automatisch wieder geladen.
- Export: glTF/GLB (Skelett + alle Animationen), OBJ + MTL + PNG (Ruhepose), Texturen als PNG, Animationen als
  JSON (30 Bilder/s), technische Daten als JSON.
- Deutsch / Englisch (folgt der Systemsprache, umschaltbar).

## Start
**Windows:** Paket aus den GitHub-Actions-Artefakten entpacken, `DW3_DW2003_Viewer.exe` starten, „Abbild öffnen“.

**Aus dem Quellcode** (Python 3.12, C++17-Compiler):
```
python -m pip install -r requirements.txt
python tools/build_native.py
python run.py
```
Ohne Grafikkarte/Treiber: `DW3_SOFTWARE_GL=1` setzen.

## Stand und Grenzen
Geprüft mit **Digimon World 3 (USA)**: 248 von 249 Modelldateien, Oberfläche mit automatischem Test.
**Digimon World 2003 (PAL) ist noch nicht geprüft** (kein Abbild vorhanden). Offen sind u. a. Gesichtsanimation,
PS1-Mischmodi, Effektmodelle. Details: [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md), Formate und Quellen:
[RESEARCH.md](RESEARCH.md), Aufbau: [ARCHITECTURE.md](ARCHITECTURE.md).

## Tests
```
python -m pytest -q                                   # ohne Spieldaten
DW3_TEST_DISC="…/Digimon World 3 (USA).cue" python -m pytest -q        # mit eigenem Abbild
python tests/integration/ui_real.py "…/Digimon World 3 (USA).cue" out/  # Oberfläche (Chrome + Playwright)
```

## Herkunft und Lizenzen
- Modell-, Textur- und Animationsleser: `native/dw3_converter`, aus
  [Feerdus95/dw3-model-viewer](https://github.com/Feerdus95/dw3-model-viewer) (MIT), dieses portiert aus
  [ReGame-Labs/dw3_decomp](https://github.com/ReGame-Labs/dw3_decomp) (MIT). Siehe `licenses/` und
  `native/dw3_converter/CREDITS.md`.
- three.js r160 (MIT).
- Digimon ist eine Marke von Bandai Namco. Fanprojekt ohne Verbindung zu den Rechteinhabern.
