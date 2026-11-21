# Anleitung (Windows 10 / 11)

Du brauchst **nichts zu installieren** – kein Python, kein Qt, keinen Compiler.

1. Unter **Releases** die Datei `DW3_DW2003_Viewer_Windows_x64.zip` herunterladen.
2. Die ZIP-Datei **vollständig entpacken** (Rechtsklick → „Alle extrahieren …“). Nicht aus der ZIP heraus starten.
3. Im entpackten Ordner `DW3_DW2003_Viewer.exe` doppelklicken.
   Windows zeigt eventuell „Der Computer wurde durch Windows geschützt“ an (das Programm ist nicht signiert):
   „Weitere Informationen“ → „Trotzdem ausführen“.
4. Oben auf **„Abbild öffnen …“** klicken und dein eigenes Abbild von *Digimon World 3 (USA)* wählen
   (`.cue` oder `.bin`). Das Abbild wird nur gelesen, nie verändert.
5. Links ein Digimon anklicken. Mit den Pfeiltasten ↑ ↓ blätterst du direkt durch die Liste.

## Bedienung
- **Maus:** linke Taste drehen, rechte Taste verschieben, Mausrad zoomen. „Zentrieren“ setzt die Kamera zurück.
- **Animationen:** rechts im Reiter „Animationen“ auswählen. Leertaste = Abspielen/Pause, ← → = Einzelbild.
- **HD-Texturen:** Reiter „Texturen“ → „HD-PNG …“ je Texturseite; oben „HD“ einschalten.
- **Export:** Reiter „Export“, Format wählen, Ziel wählen.
- **Ansichten:** Vorne / Seite / Hinten / Oben neben „Zentrieren“.
- **Liste:** Filter oben (Digimon, Partner, Gegner, Effekte, Nicht unterstützt). Vorschaubilder entstehen beim
  ersten Öffnen eines Modells.
- **Gesicht:** Schalter „Gesicht“ in der Leiste; blinzelt nur, solange eine Animation läuft.
- **Debug:** Reiter „Debug“: Körperteile einzeln ein-/ausblenden, Teil anklicken für Werte und UV-Ansicht.
- **F11:** Vollbild.

## Wenn die 3D-Ansicht schwarz bleibt
Sehr alte oder fehlende Grafiktreiber: Grafiktreiber aktualisieren. Notlösung: Umgebungsvariable
`DW3_SOFTWARE_GL=1` setzen (z. B. Verknüpfung auf `cmd /c "set DW3_SOFTWARE_GL=1 && DW3_DW2003_Viewer.exe"`);
dann zeichnet der Prozessor statt der Grafikkarte (langsamer).

## Wo speichert der Viewer etwas?
`%LOCALAPPDATA%\DW3-DW2003-Viewer`: Zwischenspeicher der gelesenen Modelle und deine HD-Texturen.
Löschen ist gefahrlos (die HD-Texturen gehen dabei verloren).

## Meldungen
- „Datei nicht gefunden … .bin“: Die `.cue` verweist auf eine `.bin`, die nicht daneben liegt.
- „Kein lesbares CD-Abbild“: falsche oder beschädigte Datei.
- „Nicht unterstützt“ in der Liste: Diese Datei enthält kein Modell, das der Viewer lesen kann (z. B. `M500WAVE.BIN`).
