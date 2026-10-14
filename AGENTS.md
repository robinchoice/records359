# records359

## Zweck & Links

- Website von 359 Records (Label, Management) unter https://359records.de und vom Studio Klanglabor unter https://klanglabor.359records.de. Statisches HTML, CSS und JS ohne Build im Ordner `site/`.
- Coolify auf VPS 1, Projekt `records359`, Anwendung `records359-site` (Static, nginx). Beide Hostnamen bedient dieselbe Anwendung.
- Gestaltung: Das Label ist gelb und schwarz mit großen Fotos, ohne Ortsschilder und ohne Bous-Strecke. Die Herkunft des Namens steht nur als ein Satz im Netzwerk-Abschnitt. Das Klanglabor folgt dem Wandbild im Studio und dem Türschild (Farben in `css/klanglabor.css`). Schrift Barlow und Barlow Condensed, lokal unter `site/fonts/`.

## Checks

Keine automatischen Checks. Geänderte Seiten lokal ansehen (`python3 -m http.server -d site`, Klanglabor unter `/klanglabor/`), Desktop und Handy, beide Sprachen.

## Texte bearbeiten

`python3 tools/edit.py` startet die Seite lokal unter http://127.0.0.1:8359/ mit Bearbeitungsmodus: Jedes Element mit `data-en` lässt sich anklicken und direkt bearbeiten, in der gerade angezeigten Sprache. Enter speichert ins HTML, Shift+Enter bricht die Zeile um, Esc verwirft. Danach Diff prüfen, committen, pushen. `tools/` wird nicht deployt.

## Deploy

- Coolify deployt per Repo-Webhook bei jedem Push auf `main`, der `site/` ändert. Ein Push geht also direkt live.
- Prüfen: `curl -sI https://359records.de` und `curl -s https://klanglabor.359records.de | grep -o '<title[^<]*'`.

## Fallen

- Deutsch steht im HTML, Englisch im Attribut `data-en` am selben Element (`data-en-content` bei Meta-Tags). `js/main.js` tauscht beim Umschalten `innerHTML`. Jeder neue Text braucht beide Sprachen.
- Die nginx-Konfiguration steht in Coolify (Custom Nginx Configuration), nicht im Repo. Sie leitet `www.359records.de` per 301 auf `359records.de` um und liefert für `klanglabor.359records.de` bei `/` die Datei `klanglabor/index.html` aus, alles andere teilen sich beide Hostnamen. Links zwischen Label und Klanglabor sind deshalb absolut.
- CSP erlaubt nur `'self'`: keine Inline-Skripte, keine `style`-Attribute, keine externen Einbettungen.
- Die Fotos stammen aus dem Archiv `359 Records` auf pi-a und liegen als WebP in 700 und 1400 px vor.
