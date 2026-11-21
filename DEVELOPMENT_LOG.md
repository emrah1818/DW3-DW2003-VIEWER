# Entwicklungsprotokoll

Für die Fortsetzung in späteren Chats: zuerst diese Datei, dann ARCHITECTURE.md und RESEARCH.md lesen.

## Stand 0.2.0 (21.11.2026) – Digimon World 3 (USA) fertig

PAL (Digimon World 2003) ist ausdrücklich zurückgestellt. Alles unten gilt für das USA-Abbild.

### Test-Übersicht
„Windows“ = automatischer Lauf auf dem GitHub-Windows-Rechner (Windows Server 2022, ohne Spieldaten).
**Auf einem echten Windows-10-PC mit Spieldaten wurde nichts davon geprüft**; das kann ich hier nicht ausführen.

| Funktion | implementiert | automatischer Test bestanden | mit echten Spieldaten geprüft | Windows-Test | bekannte Grenzen |
|---|---|---|---|---|---|
| Abbild öffnen, Version, Fehlermeldungen | ja | ja (`test_core`, UI-Test) | ja (USA) | nur Start, ohne Abbild | PAL zurückgestellt |
| Modellliste 470 Dateien, Filter, Markierung „nicht unterstützt“ | ja | ja (UI-Test, `test_real_disc`) | ja: 468 gelesen, 2 markiert | nein | M500WAVE, MEFT0001 ohne Knochenliste |
| Effektmodelle (221, davon 129 aus der Effekttabelle) | ja | ja (`qa_all`) | ja | nein | Namen neutral („Effekt N“); Zuordnung zu Techniken nicht belegt |
| Gesichtsanimation / Blinzeln | ja | ja (`face_real`, 6 Modelle) | ja; alle 257 Gesichtsteile zugeordnet | nein | Takt in 60-Hz-Bildern, Zufall wie im Spiel, nicht dieselbe Folge |
| PS1-Halbtransparenz abr 0–3 | ja | ja (Materialprüfung im UI-Test) | ja; Modus 0: 16, 1: 206, 3: 8 Modelle | nein | Mischung im linearen Farbraum, Zeichenreihenfolge ≠ PS1-Ordering-Table |
| Vom Spiel ausgeblendete Teile | ja | ja (UI-Test WarGreymon) | ja; 184 Modelle betroffen | nein | – |
| Debug: Teile ein/aus, Werte, UV, Export | ja | ja (UI-Test) | ja | nein | – |
| Animationen (15 589 Motions) | ja | ja (`qa_all`: alle abspielbar) | ja | nein | 3 926 von 15 376 Digimon-Motions benannt, Rest „Motion N“ |
| Export GLB | ja | ja: 468/468 glTF-Validator 0 Fehler, 0 Warnungen | ja | nein | – |
| Export OBJ+MTL+PNG | ja | ja: 468/468 mit trimesh wieder eingelesen, Flächenzahl gleich | ja | nein | Ruhepose ohne Animation (OBJ kann keine) |
| Export Motions-JSON, Metadaten, Debug-JSON, PNG | ja | ja (468/468 eingelesen) | ja | nein | – |
| HD-Texturen | ja | ja (UI-Test 2048×4096) | ja | nein | – |
| Stabilität Modell-/Animationswechsel | ja | ja: 40 Wechsel, GPU-Speicher konstant (7 Geometrien, 6 Texturen) | ja | nein | – |
| Vorschaubilder, Kameraansichten | ja | ja (UI-Test) | ja | nein | Vorschau erst nach erstem Öffnen |
| Windows-Paket (ZIP, ohne Installation) | ja | ja: Start, WebGL 2 über D3D11, Server, Konverter | – | ja (GitHub-Runner) | nicht signiert (SmartScreen-Hinweis) |

Testläufe am 21.11.2026 (Linux, Chromium, SwiftShader):
- `pytest` mit `DW3_TEST_DISC`: 25 bestanden (19 ohne Spieldaten, 6 mit USA-Abbild).
- `tests/integration/ui_real.py`: 34 Prüfungen bestanden (inkl. Debug-Ansicht, Mischmodus, ausgeblendete Teile, Kamera, Speicher), 0 Fehler, keine JS-Fehler.
- `tests/integration/face_real.py`: Guilmon, Agumon, Kumamon, WarGreymon, Veemon, Renamon – alle bestanden.
- `tools/qa_all.py`: siehe Zahlen oben; `tools/contact_sheets.py`: alle 471 Einträge (vor dem Entfernen des Doppeleintrags) gezeichnet, ohne JS-Fehler,
  Sichtprüfung der Übersichtsbilder ohne erkennbar kaputte Modelle oder falsch sichtbare Teile.

### Gefundene Besonderheiten der Spieldaten
- **146 entartete Dreiecke in 20 Dateien** (Fläche 0 in der Ruhepose), u. a. Persiamon 32, MEFT0113 32,
  Gallantmon 16, Ghoulmon 14, Kabuterimon 12. Der Konverter übernimmt die Indizes unverändert aus der Datei;
  die PS1 zeichnet solche Flächen nicht. Sie bleiben erhalten, damit der Export der Datei entspricht.
- **14 überlappende Gesichtsrechtecke** (BK Imperialdramon): ein Ziel überdeckt die Quelle eines späteren
  Teils. Darum kopiert der Viewer wie das Spiel nacheinander auf den echten Seitenbytes statt fertige
  Ausschnitte zu verwenden.
- Effekt-Hüllen (MEFT0040–0060, MEFT1001–1016) sind große Kuppeln bzw. Bühnenkulissen; viele Effekte bestehen
  nur aus einem Punkt oder Strich, das ist ihr Inhalt.

### Behobene Fehler in 0.2.0
- Effekt 310 stand doppelt in der Liste, weil die Effekttabelle des Spiels ihn zweimal enthält; jetzt einmal.
  Dadurch neue Nummerierung, darum neuer Cache-Schlüssel (alter Zwischenspeicher wird nicht weiterverwendet).
- GPU-Speicherleck: Die Knochentextur jedes Skeletts wurde beim Modellwechsel nicht freigegeben (+1 Textur je
  Wechsel). Jetzt werden Skelette, Materialien und Texturen freigegeben.
- 1 097 glTF-Validator-Meldungen im Konverter behoben (Min/Max-Genauigkeit, Quaternionen normalisiert,
  Ein-Bild-Motions, `alphaCutoff` nur bei MASK).

### Offene Punkte
1. Test auf einem echten Windows-10-PC mit Spieldaten (durch dich).
2. PAL (zurückgestellt).
3. Namen für Technik-Skripte (5/6/8 sind Technikvarianten, welche Technik genau hängt vom Digimon ab).
4. Verteidigung/Guard: im Code nicht eindeutig einer Motion zuzuordnen, daher unbenannt.
5. Kampfbühnen-Licht nicht nachgebildet.

## Stand 0.1.0 (21.11.2026)

### Entschlüsselte Formate
| Format | Stand | Geprüft mit |
|---|---|---|
| Abbild (ISO9660, versteckte Einträge, CUE) | fertig | DW3 USA |
| Dateitabelle des Programms | fertig für USA, EU, JP (Adressen aus dw3_decomp) | nur USA |
| Kämpfertabelle, Gesichtsrechtecke | fertig | USA |
| Namen (DIGNAM) | USA fertig, EU vorbereitet (ungeprüft), JP nicht gelesen | USA: 248/249 |
| Modell (Knochen, Meshes, Polygone) | fertig (Konverter) | USA: 248/249 Dateien |
| Texturen (TIM, RLE, 4/8 Bit, CLUT) | fertig (Konverter) | USA |
| Animationen (Schlüssel, Schritte, Schleifen, Überblendung, ausgeblendete Knochen) | fertig (Konverter + Viewer) | USA |
| Aktionsskripte (welche Motion ein Skript startet) | fertig (Konverter `--scripts`) | USA |

### Funktionierende Modelle
- 248 von 249 Modelldateien der USA-Version werden konvertiert und angezeigt (Test `test_every_model_converts_or_reports`).
- Sichtgeprüft (Bildschirmfotos): Guilmon, WarGreymon, Imperialdramon-F, Agumon.
- `M500WAVE.BIN`: keine Knochenliste, wird mit Meldung abgelehnt.

### Animationen
- Alle Motions mit mehr als einem Bild werden als glTF-Animation abgespielt (z. B. Guilmon 34 von 62; die
  übrigen 28 sind Ein-Bild-Motions ohne glTF-Spur und werden als solche markiert).
- Abspielen, Pause, Einzelbild vor/zurück, Tempo, Schleife, Bild- und Zeitanzeige, Vergleich zweier Motions
  nebeneinander: geprüft (UI-Test `tests/integration/ui_real.py`).
- Namen: Idle, Idle geschwächt, Treffer, K. o. aus dem Code; sonst „Aktion (Skript N)“ oder „Motion N“.
- Ausgeblendete Knochen (Skalierung ≤ 48) werden je Bild ausgeblendet (z. B. WarGreymons Flammen im Idle).

### Offene Probleme
1. **PAL (Digimon World 2003) ungeprüft** – Abbild fehlt; Adressen stammen aus dw3_decomp.
2. Gesichtsanimation (Blinzeln) wird noch nicht abgespielt.
3. PS1-Halbtransparenzmodi (`abr` 0–3) werden als einfache Mischung gezeigt.
4. Effektmodelle (FIGHT/EFFECT) fehlen in der Liste.
5. Kampfbühnen-Licht nicht nachgebildet (Ansicht unbeleuchtet).
6. Debug-Ansicht einzelner Körperteile/Textursegmente: nur Skelett und Drahtgitter.
7. Windows-Paket: nur der automatische Starttest auf dem GitHub-Runner; noch nicht auf deinem PC geprüft.

### Aus dem DW2 Mod Studio übernommen
| Teil | Herkunft | Änderung |
|---|---|---|
| `dw3viewer/disc.py`, `recovery.py` | `dw2studio/core/disc.py`, `recovery.py` | PAK-Unterstützung entfernt |
| `dw3viewer/game.py` | `dw2studio/dw3_fighters.py` | JP-Adressen ergänzt, Versionsangaben |
| `dw3viewer/names.py` | `dw2studio/dw3_names.py` | EU-Lesepfad (ungeprüft), neue Aufrufform |
| `native/dw3_converter` | `third_party/dw3_converter` (aus Feerdus95/dw3-model-viewer, MIT) | unverändert |
| Motion-Namen | Erkenntnisse aus `dw3_motion_map.py` / `dw3_actions.py` | nur die im Code belegten Bedeutungen |
| three.js r160 | `www/lib` | unverändert |
Neu geschrieben: Bibliothek (`library.py`), Export, HD-Texturen, Server, Desktop-Fenster, gesamte Oberfläche.

### Nächste Schritte
1. PAL-Abbild prüfen (Versionserkennung, Dateitabelle, Namen, alle Modelle).
2. Gesichtsanimation abspielen (VRAM-Rechtecke aus `FighterInfo.face`, `step_face` im Konverter).
3. Effektmodelle und DNA-Formen in die Liste.
4. PS1-Mischmodi und optional Kampfbühnen-Licht.
5. Debug-Ansicht: Knochen/Mesh einzeln ein-/ausblenden, UV-Überlagerung auf den Texturseiten.
6. Danach: Übergabe an den DW2-PC-Port (Mod-Paket).
