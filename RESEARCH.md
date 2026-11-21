# Recherche: Datenformate von Digimon World 3 / Digimon World 2003

Stand: 21.11.2026. Alles hier ist entweder in einer genannten Quelle belegt oder mit einem echten Abbild
(Digimon World 3, USA) nachgeprüft. Was nur aus einer Quelle stammt und hier nicht geprüft werden konnte,
ist als **ungeprüft** markiert.

## 1. Quellen

| Projekt | Was es liefert | Lizenz | Stand |
|---|---|---|---|
| [ReGame-Labs/dw3_decomp](https://github.com/ReGame-Labs/dw3_decomp) | Byte-genaue Dekompilierung aller drei Versionen (EU `SLES_039.36`, USA `SLUS_014.36`, JP `SLPS_034.46`), Programm und 21 Overlays zu 100 % in C. Maßgebliche Quelle für alle Datenstrukturen. | MIT | Commit `791932b` (15.10.2026) |
| [Feerdus95/dw3-model-viewer](https://github.com/Feerdus95/dw3-model-viewer) | C++-Viewer für die Kampfmodelle von DW2003 (PAL): Modell-, Textur-, Animations-, Gesichts- und Skriptleser, aus dw3_decomp portiert. Unterstützt offiziell nur PAL (die Dateitabellen liest er aus dem europäischen Programm). | MIT | Commit `550f93a` (18.11.2026) |
| [Feerdus95/dw3-native-port](https://github.com/feerdus95/dw3-native-port) | Nativer PC-Port von DW2003 (PAL) aus dw3_decomp; nur Hintergrund. | MIT | – |
| Eigenes Projekt `emrah1818/dw2-dw3-viewer` (DW2 Mod Studio) | Abbild-Leser mit Wiederherstellung versteckter Einträge, Versionsprüfung, Dateitabelle für USA und EU, Kämpfertabelle, DIGNAM-Namen, Aktionsskripte. Eingebunden ist ein headless-Konverter aus dw3-model-viewer (Commit `b8a77d3`). | eigener Code | 0.98.5 |

## 2. Gefundene Formate

### 2.1 Abbild (Disc Reader) – bekannt und geprüft
- ISO9660, 2352-Byte-Rohsektoren (Mode 2 Form 1) oder 2048-Byte-ISO; `.cue` mit einer BINARY-Spur.
- Im Verzeichnisbaum stehen nur `SLUS_014.36` und `SYSTEM.CNF` (USA). Die Spieldateien sind **aus dem
  Verzeichnisbaum versteckt**: Ihre ISO9660-Verzeichnissätze liegen noch im Abbild und werden durch Suchen
  nach gültigen Sätzen (Name, LBA und Größe in Little- und Big-Endian gleich) gefunden. Geprüft: 2194 Dateien in
  der Programmtabelle, 249 Modelldateien `M###XXXX.BIN`.
- Zusätzlich hat das Programm eine eigene Dateitabelle (dw3_decomp `config/*/symbols.txt`):

| Version | Programm | `FILE_SECTORS` | `FILE_SECTOR_COUNTS` | Kämpferdatei |
|---|---|---|---|---|
| USA | SLUS_014.36 | 0x80044B78 | 0x80046DD4 | 0x1BE |
| Europa | SLES_039.36 | 0x80044F6C | 0x800474A4 | 0x1CC |
| Japan | SLPS_034.46 | 0x80044D98 | 0x80047284 | 0x1BE |

  USA geprüft (Tabelle passt zum Abbild, alle 249 Modelle per LBA zugeordnet). Europa und Japan: **ungeprüft**
  (kein Abbild vorhanden), die Werte stammen aus dw3_decomp.

### 2.2 Modelldatei (Model Parser) – bekannt, geprüft für USA
Quelle: dw3_decomp `src/fightstg/fightstg.c`, `include/fightstg/model.h`, umgesetzt in
`native/dw3_converter/model.cpp`.
- Die Datei ist ein Archiv: eine Tabelle von Versätzen ab Dateianfang, Anzahl = erster Versatz / 4.
- Eintrag „Knochenliste“: `{texFile, count, (parent, mesh, keys) × count}`.
- Meshes: Vertices als `SVECTOR` (int16 x, y, z), Polygone als GPU-Befehle (Drei- und Vierecke, texturiert,
  flach oder Gouraud, mit tpage/CLUT, Halbtransparenzmodus `abr`).
- Geprüft: 248 von 249 Modelldateien der USA-Version werden gelesen. `M500WAVE.BIN` hat keine Knochenliste
  (vermutlich kein Kampfmodell; der Viewer meldet das, statt abzustürzen).

### 2.3 Texturen (Texture Decoder) – bekannt, geprüft für USA
Quelle: dw3_decomp `src/main/gfx/tim_loader.c`, `src/main/file/decompressor.c`.
- TIM-Bilder im Archiv, teils RLE-gepackt, nebeneinander im VRAM ab `TEX_X/TEX_Y` abgelegt.
- 4-Bit- (16 Farben) und 8-Bit-Seiten mit CLUT; Seite und Palette kommen aus jedem Polygon (tpage, clut).
- Der Konverter löst jede (tpage, CLUT)-Kombination zu einer RGBA-Seite auf (256 × 256), UVs bleiben die des
  Spiels (0–255 je Seite). Transparenz: Farbe 0x0000 ist durchsichtig (Alpha-Test), Halbtransparenz wird als
  Mischung gezeigt (der genaue PS1-Mischmodus pro `abr` ist **noch nicht** nachgebildet).

### 2.4 Animationen (Animation Parser) – bekannt, geprüft für USA
Quelle: dw3_decomp `model_mesh.c` (`FIGHTSTG_setMotion`, `FIGHTSTG_stepMotion`, `FIGHTSTG_updateModel`).
- Je Knochen drei Schlüsselspuren: Position, Rotation (4096 = 360°), Skalierung (4096 = 1), Rotation als
  Rz · Ry · Rx.
- Eine Motion ist eine Liste von Schritten `{index, count, frame, endFrame}`; das Ende ist `0xFFFF` (halten
  oder zurück zum Idle) oder `0x8000` (Schleife ab einem Keyframe). Überblendungen zwischen Motions sind Teil
  der Schritte.
- Ein Knochen mit Skalierung ≤ 48 wird in diesem Bild **nicht gezeichnet** und behält seine letzte Matrix
  (z. B. die Flammen-Effektteile von WarGreymon). Der Viewer blendet diese Teile Bild für Bild aus.
- Abgetastet mit 30 Bildern pro Sekunde (Keyframe 1 + 2 i), wie das Spiel bei 60 Hz mit Schritt 2.

### 2.5 Namen und Zuordnung – bekannt, geprüft für USA
- Kämpfertabelle (Datei 0x1BE / 0x1CC): `FighterEntry {u16 id, u8 index, u8 kind}`, Partner-Info 0xC4 Byte,
  Gegner-Info 0x48 Byte (kind ≥ 0x3A); `model / motions / effects = (Dateinummer << 16) | Archiveintrag`.
- Namen: Textdatei DIGNAM (0x4F, `getString(DIGNAM, kind)`), Zeichen über `FONT_GLYPH_MAP`/`FONT_ICON_MAP`.
  USA: 248 von 249 Modellen haben ihren Spielnamen. Europa: Kopie 1 der Sprachkopien liegt laut
  dw3_decomp an der USA-Nummer; **ungeprüft**. Japan: Shift-JIS-Text, noch nicht gelesen.

### 2.6 Bedeutung der Motions – nur was der Code zeigt
- Motion 1 = Idle, Motion 2 = Idle bei ≤ ¼ KP (`techs.c WFIGHTMN_setIdleMotion`, `idleMotion + 1`).
- Motion 13 = Sieg (`menu.c`).
- Skript 1 = Treffer (nicht der letzte), 2 = Treffer, 3 = K. o., 4 = Ausweichen/Verfehlt
  (`effect.h`: `HitEffect.result`, Skript = result + 1).
- Skripte 5, 6, 8 = Technikvarianten (`choosePartnerScript`); 12 ruft ein Modell; 10, 14, 15, 17 = Items
  (`item.c`). Diese erscheinen mit Skriptnummer.
- Alle anderen Motions bleiben „Motion N“. Verteidigung, Spezialattacke usw. sind nicht eindeutig belegt.

### 2.7 Gesichtsanimation (`face.c`) – umgesetzt
- Teil 0/1 = Augen: Motion 4–11 → zu (Bild 2), Motion 2 → halb (1), sonst offen mit Blinzeln:
  Timer = rand(0..127) + 60 Bilder (60 Hz); Zustand nach Timer >> 1: 1, 2, 5, 6 halb; 3, 4 zu.
- Übrige Teile: Bild = (Zeit % 18) / 6.
- Rechtecke in VRAM-Halbworten relativ zum Texturursprung; Texel = x·4 (4 Bit) bzw. x·2 (8 Bit). Alle 257
  benutzten Teile haben Quelle und Ziel in derselben tpage. Kopiert wird nacheinander in Spielreihenfolge
  (14 Überlappungen bei BK Imperialdramon).

### 2.8 Halbtransparenz – umgesetzt
- Materialname `texN_abrM`, M = abr + 1. Nur Texel mit STP-Bit mischen (Konverter: Alpha 128).
- 0: B/2 + F/2, 1: B + F, 2: B − F, 3: B + F/4. Zwei Durchgänge: deckend (Alpha ≥ 0,75), halbtransparent.

### 2.9 Effektmodelle – umgesetzt
- Tabelle `FIGHTSTG_effectModels` (USA, 130 Einträge `{id, (Datei << 16) | Eintrag, Motionsdatei}`; Eintrag `{310, …}` steht doppelt und wird einmal gelistet) aus
  dw3_decomp `effect_model.c`; weitere `MEFT*.BIN` ohne Tabelleneintrag werden ebenfalls gelistet.
- Nicht lesbar: `MEFT0001.BIN`, `M500WAVE.BIN` (keine Knochenliste).

### 2.10 Noch unbekannt oder nicht umgesetzt
- PAL: zurückgestellt.
- Welche Technik welches Effektmodell nutzt: nicht ausgewertet; Effekte bleiben neutral benannt.
- Kampfbühnen-Licht (drei Lichter + Umgebungsfarbe): nicht nachgebildet.

## 3. Warum diese Technik (Sprache, Rendering)

| Teil | Wahl | Grund |
|---|---|---|
| Modell-, Textur-, Animationsleser | C++ (aus dw3-model-viewer, MIT) | 1:1 aus der Dekompilierung portiert und mit 248 Modellen geprüft; neu schreiben hieße, gelöste Fehler neu zu machen. |
| Abbild, Versionen, Tabellen, Namen, Export, Server | Python 3.12 | Aus dem Mod Studio übernommen und dort getestet; leicht prüfbar (Tests ohne Spieldaten). |
| 3D-Ansicht | three.js (WebGL 2) in Qt WebEngine | Nutzt die Grafikkarte (unter Windows über ANGLE/Direct3D 11), glTF mit Skinning und Animationen ist Standard, Nearest-Filter wie PS1 möglich. |
| Austauschformat | glTF 2.0 (GLB) | Skelett, Gewichte, UVs, Texturen und alle Animationen in einer Datei; direkt in Blender importierbar. |
| Fenster, Dateidialoge | PyQt6 | Eigenständiges Windows-Programm (PyInstaller), keine Browser-Installation nötig. |

Langfristig (Editor, Import in den DW2-PC-Port) bleibt der C++-Teil die Stelle für Lesen und Schreiben der
Spielformate; Python und das Web-Frontend bleiben Bedienung und Austausch.
