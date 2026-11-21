# Entwicklungsprotokoll

Für die Fortsetzung in späteren Chats: zuerst diese Datei, dann ARCHITECTURE.md und RESEARCH.md lesen.

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
