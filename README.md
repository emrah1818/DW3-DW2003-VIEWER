# DW3 / DW2003 Viewer 0.2.0

Betrachter für die Kampfmodelle von **Digimon World 3** (USA) und **Digimon World 2003** (PAL): echte Modelle,
Originaltexturen und Originalanimationen, gelesen aus deinem eigenen Abbild. **Es sind keine Spieldaten
enthalten**, und das Abbild wird nie verändert.

*A viewer for the battle models of Digimon World 3 (USA) and Digimon World 2003 (PAL), read from your own disc
image. No game data included; the image is never changed.*

## Funktionen
- Abbild öffnen (`.cue`/`.bin`, `.iso`), Version erkennen (SLUS_014.36 / SLES_039.36 / SLPS_034.46). Verständliche
  Meldung bei fehlender `.bin`, fremdem oder beschädigtem Abbild.
- **Liste aller 470 Modelldateien** (USA): 249 Digimon-Kampfmodelle mit Spielnamen und 221 Effektmodelle
  (129 aus der Effekttabelle des Spiels, die übrigen `MEFT*.BIN`). Filter: Alle, Digimon, Partner, Gegner,
  Sonstige, Effekte, Nicht unterstützt. Nicht lesbare Dateien sind markiert. Vorschaubilder, Suche, Pfeiltasten.
- 3D-Ansicht: drehen, verschieben, zoomen, zentrieren, Ansichten Vorne/Seite/Hinten/Oben; PS1-Pixel oder
  geglättet; Drahtgitter, Gitter, Rückseiten, Skelett, Hintergrundfarbe, Bild speichern.
- **Gesichtsanimation wie im Spiel** (`face.c`): Augen offen/halb/zu mit dem Zufalls-Blinzeln des Spiels,
  geschlossene Augen in den Motions 4–11, halb in Motion 2; weitere Gesichtsteile im 18-Bilder-Takt. Die
  Rechtecke werden byte-genau auf den Texturseiten kopiert, in der Reihenfolge des Spiels; auch mit HD-Texturen.
- **PS1-Halbtransparenz** (`abr` 0–3): ½B+½F, B+F, B−F, B+¼F, nur für Texel mit gesetztem STP-Bit.
- Animationen: alle Motions, benannt nur, wo Spielcode oder -daten die Bedeutung belegen; Abspielen, Pause,
  Einzelbild, Tempo, Schleife wie im Spiel, Übergang zurück in Idle, Vergleich zweier Motions. Vom Spiel
  ausgeblendete Teile (Skalierung ≤ 48) werden Bild für Bild ausgeblendet.
- **Debug-Ansicht**: Knochenbaum, jeden Körperteil einzeln ein-/ausblenden, „Nur Auswahl“, Hervorhebung,
  Position/Rotation/Skalierung live, Vertex-/Polygonzahl, Texturseite und Mischmodus je Teil, UV-Überlagerung
  auf der Texturseite, Debug-Export (JSON).
- Infos, HD-Texturen (beliebige Größe), Export GLB/OBJ+MTL+PNG/PNG/Motions-JSON/Metadaten/Debug-JSON.
- Deutsch / Englisch (folgt der Systemsprache, umschaltbar).

## Start
**Windows:** [Neueste Version unter Releases](https://github.com/emrah1818/DW3-DW2003-VIEWER/releases/latest) – `DW3_DW2003_Viewer_Windows_x64.zip` entpacken, `DW3_DW2003_Viewer.exe` starten, „Abbild öffnen“. Nichts muss installiert werden ([ANLEITUNG.md](ANLEITUNG.md)).

**Aus dem Quellcode** (Python 3.12, C++17-Compiler):
```
python -m pip install -r requirements.txt
python tools/build_native.py
python run.py
```
Ohne Grafikkarte/Treiber: `DW3_SOFTWARE_GL=1` setzen.

## Stand und Grenzen
Fertig für **Digimon World 3 (USA)**: 468 von 470 Modelldateien werden gelesen, alle 468 Exporte sind laut
Khronos glTF-Validator fehlerfrei. **Digimon World 2003 (PAL) ist ausdrücklich zurückgestellt.** Die
Test-Übersicht (implementiert / getestet / mit echten Daten / Windows) steht in
[DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md), Formate und Quellen in [RESEARCH.md](RESEARCH.md), Aufbau in
[ARCHITECTURE.md](ARCHITECTURE.md), Änderungen in [CHANGELOG.md](CHANGELOG.md).

## Tests
```
python -m pytest -q                                                       # ohne Spieldaten
DW3_TEST_DISC="…/Digimon World 3 (USA).cue" python -m pytest -q             # mit eigenem Abbild
python tests/integration/ui_real.py   "…/Digimon World 3 (USA).cue" out/    # Oberfläche (Chrome + Playwright)
python tests/integration/face_real.py "…/Digimon World 3 (USA).cue" out/    # Gesichtsanimation
python tools/qa_all.py "…/Digimon World 3 (USA).cue" out/                   # alle Modelle + glTF-Validator
```
Die Spieldaten werden nur lokal gelesen und nie ins Repository übernommen.

## Herkunft und Lizenzen
- Modell-, Textur- und Animationsleser: `native/dw3_converter`, aus
  [Feerdus95/dw3-model-viewer](https://github.com/Feerdus95/dw3-model-viewer) (MIT), dieses portiert aus
  [ReGame-Labs/dw3_decomp](https://github.com/ReGame-Labs/dw3_decomp) (MIT). Siehe `licenses/` und
  `native/dw3_converter/CREDITS.md`.
- three.js r160 (MIT).
- Digimon ist eine Marke von Bandai Namco. Fanprojekt ohne Verbindung zu den Rechteinhabern.
