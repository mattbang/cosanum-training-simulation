# Cosanum Trainingssimulation

**Sprache:** [English](README.md) · Deutsch

[Fallstudie im Portfolio lesen](https://matthew-bangle-data-portfolio.mattbangle.chatgpt.site/de/work/logistics-training-simulation) · [Interaktive Ergebnisse erkunden](https://matthew-bangle-data-portfolio.mattbangle.chatgpt.site/examples/training-simulation/index.html?lang=de)

Python-Ereignissimulation und Ergebnisauswertung aus dem ZHAW CAS Process Digitalization zur Schulungsorganisation in der Logistik bei Cosanum. Ich entwickelte das Modell und das lokale Dashboard, um Prozessregeln, Selbstlernen und Schulungskapazität vor einer Umsetzungsentscheidung zu prüfen.

**Zentrale Erkenntnis:** Die individuelle Praxis bleibt im Modell der Engpass. In 50 gepaarten synthetischen Jahreslagen erhöht eine zweite qualifizierte Praxisbegleitung mit zusätzlichem Platz die mittlere Zahl vollständiger Abschlüsse von 312,96 auf 348,72. Das ist ein Modellvergleich, keine beobachtete betriebliche Verbesserung.

## Inhalt

- Eine Python-Engine, Version 0.10.0, mit themenkompatiblen Warteschlangen, ursprünglichen Wartefristen, Theorie vor Praxis, begrenzten Kalendern und getrennten Ergebnissen für Schulung und Dokumentation.
- Ein lokales Dashboard, Version 0.3.0, das neue gepaarte Experimente ausführt und Eingänge, Ereignisse, Kennzahlen und Prüfsummen exportiert.
- Eine deutsch-englische statische Ergebnisauswertung in [site/](site/) mit gespeicherten Vergleichen, Kapazitätskurve und interaktivem Sensitivitätstest für 51 Faktoren.
- Anonymisierte Thementitel, aggregierte Eingänge und synthetischer Bedarf. Mitarbeiterdatensätze, Originalquellen und private Git-Historie sind nicht enthalten.

## Gespeicherter Vergleich

Alle vier Optionen nutzen dieselben 50 Jahreslagen und je 350 angenommene Person-Thema-Zyklen über 365 Tage. Ein Fall bezeichnet den Schulungsbedarf einer Person für ein Thema und einen Zyklus, nicht eine eigene Person.

| Modelloption | Mittlere vollständige Abschlüsse | Läufe mit allen 350 Abschlüssen |
| --- | ---: | ---: |
| IST-Prozess | 310,22 | 1 / 50 |
| Kombinierter SOLL-Prozess | 312,96 | 3 / 50 |
| SOLL + durch ein separates Projektteam vorbereitetes LMS | 313,50 | 3 / 50 |
| SOLL + zweite qualifizierte Praxisbegleitung und Platz | 348,72 | 46 / 50 |

LMS und zusätzliche Praxiskapazität sind getrennte Varianten des SOLL-Prozesses. Volle zusätzliche Lohn-, Rekrutierungs- und Qualifizierungskosten sind bei der zweiten Praxisbegleitung nicht enthalten. Die Abschlusszahlen allein begründen deshalb keine Personalentscheidung.

Der separate Sensitivitätstest umfasst 51 Faktoren, zwei Einstellungen, fünf gepaarte Bedarfslagen und vier Regelvarianten: 2.060 bedingte Ergebnisse einschliesslich der Ausgangslagen. Das sind keine unabhängigen Wiederholungen und keine gesicherte Rangfolge der Varianten. Siehe [Methode und Herkunft](docs/METHOD.md).

## Lokal starten

Python ab Version 3.9 genügt; Engine und Dashboard benötigen keine zusätzlichen Pakete. Die Befehle werden im Hauptverzeichnis des Repositorys ausgeführt.

**Interaktive Ergebnisauswertung** — zeigt die gespeicherten Studienergebnisse:

```sh
python3 -m http.server 8767 --directory site --bind 127.0.0.1
```

[localhost:8767](http://127.0.0.1:8767/) öffnen. Die Kopfzeile bietet den Wechsel zwischen Deutsch und Englisch.

**Lokales Dashboard** — führt neue synthetische Experimente aus:

```sh
python3 dashboard/app.py
```

Der Starter öffnet eine nur lokal erreichbare Browsersitzung. Neue Experimente liegen im ignorierten Ordner `local-experiments/`.

**Kleiner reproduzierbarer Ablauf** — bei jeder Ausführung einen neuen Ausgabeordner verwenden:

```sh
PYTHONPATH=src python3 -m cosanum_sim.cli --full-workflow --output local-runs/example-1
```

**Prüfungen:**

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src:dashboard python3 -m unittest discover -s dashboard/tests -v
python3 dashboard/app.py --self-test
```

Das exportierte Paket besteht 85 Engine-Tests, 18 Dashboard-Tests und den Dashboard-Selbsttest. Die geprüften Umgebungen und Exportkontrollen stehen unter [Validierung](docs/VALIDATION.md).

## Aussagegrenzen und Umsetzung

Die gespeicherten Studienauszüge bleiben unverändert und führen die Prüfsummen ihrer ursprünglichen Quellen mit. Neue Läufe des öffentlichen Pakets erhalten eigene Eingangs- und Code-Prüfsummen. Ein erfolgreicher Funktionstest wiederholt oder bestätigt die historische Studie nicht. Die archivierten Quelltabellen der statischen Auswertung sind nicht enthalten; ihre aggregierten Dateien lassen sich deshalb nicht allein aus diesem Repository neu erzeugen. Das lokale Dashboard kann neue Vergleiche mit dem enthaltenen anonymisierten Eingangsbestand ausführen.

Die Eingänge verbinden quellenbasierte Aggregate, berichtete Schätzungen und ausdrückliche Annahmen. Daraus entsteht keine kalibrierte Betriebsprognose. Kosten stehen für modellierten Aufwand, nicht für gemessene Einsparungen.

Automatisierte Terminplanung und digitale Zertifizierung sind eine separate Erweiterung in Entwicklung: [cosanum-automation](https://github.com/mattbang/cosanum-automation). Eine E-Learning-Plattform wird geprüft. Die abgeschlossene Simulation ist kein produktives Schulungssystem.

Der Quellcode ist zur Portfolio-Prüfung öffentlich. Dieser Export erteilt keine neue Lizenz. Quellenbasierte Eingänge und gespeicherte Ergebnisse behalten ihre Herkunftsangaben; siehe [Datenherkunft](docs/DATA_PROVENANCE.md).
