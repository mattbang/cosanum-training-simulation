/* The HTML is the canonical German copy. Only text nodes present before app.js
   runs are captured, so language changes never rewrite generated data views. */
(() => {
  const storageKey = 'cosanum-portfolio-language';
  const textEn = {
    'Zum Inhalt springen': 'Skip to content',
    'Praxisprojekt · Simulationsdemo': 'Applied project · simulation demo',
    'Variantenvergleich': 'Compare options',
    'Praxiskapazität': 'Practice capacity',
    'Erkenntnisse': 'Findings',
    'Sensitivität': 'Sensitivity',
    'Methode': 'Method',
    'Selbst testen': 'Try it locally',
    'Reales Praxisprojekt': 'Real-world applied project',
    'Wo Schulungen ins Stocken geraten': 'Where training gets stuck',
    'Bei Cosanum, einem Schweizer Gesundheitslogistiker, analysierte ich im CAS Process Digitalization an der ZHAW den manuellen Schulungsprozess der Logistik. Wir entwickeln automatisierte Terminplanung und digitale Zertifizierung und prüfen eine E-Learning-Plattform für Selbstlernmodule.': 'At Cosanum, a Swiss healthcare logistics company, I analysed the manual logistics training process as part of the ZHAW CAS Process Digitalization. We are developing automated scheduling and digital certification and evaluating an e-learning platform for self-study modules.',
    'Ich habe IST und SOLL in einer Python-Ereignissimulation und einem Dashboard modelliert, um Effizienzpotenziale von Prozessregeln, LMS und Praxiskapazität zu prüfen.': 'I modelled the current process (IST) and proposed process (SOLL) in a Python discrete-event simulation and dashboard to test the potential effects of process rules, an LMS, and practice capacity.',
    'Das Modell zeigt einen Praxisengpass': 'The model points to a practice bottleneck',
    'Eine zweite qualifizierte Praxisbegleitung samt Platz erhöht vollständige Abschlüsse im Mittel um 35.76 gegenüber dem kombinierten SOLL; LMS um 0.54.': 'A second qualified practice coach and training place raise mean full completions by 35.76 over combined SOLL; the LMS branch raises them by 0.54.',
    '50 gepaarte synthetische Jahresläufe · keine gemessene Betriebswirkung': '50 paired synthetic annual runs · no measured operational effect',
    'Varianten vergleichen': 'Compare options',
    'Einflussgrössen erkunden': 'Explore input effects',
    'DER MODELLWEG': 'THE MODEL PATH',
    'Quelle + Annahme getrennt': 'Sources and assumptions kept separate',
    'Bedarf erkannt': 'Need identified',
    'Jeder Fall behält seine eigene Uhr und Frist.': 'Each case keeps its own clock and deadline.',
    'Theorie geplant': 'Theory scheduled',
    'Kompatible Fälle können eine Gruppe bilden.': 'Compatible cases can form a group.',
    'Praxis, falls nötig': 'Practice, when needed',
    'Coach, Person und Ort müssen gleichzeitig frei sein.': 'Coach, learner, and place must be available together.',
    'Engpass': 'Bottleneck',
    'Kompetenz & Nachweis': 'Competence & record',
    'Schulung und Dokumentation sind getrennte Ergebnisse.': 'Training and documentation are distinct outcomes.',
    '50 GEPAARTE JAHRESLÄUFE': '50 PAIRED ANNUAL RUNS',
    'Vier Varianten, derselbe Bedarf': 'Four options, the same demand',
    'Jeder der 50 Läufe nutzt dieselben 350 angenommenen synthetischen Person-Thema-Fälle für alle vier Varianten. Die Karten zeigen mittlere vollständige Schulungsabschlüsse, keine beobachteten Betriebsergebnisse.': 'Each of the 50 runs uses the same 350 assumed synthetic person-topic cases across all four options. The cards show mean full training completions, not observed operational results.',
    'Geprüfte Vergleichswerte werden geladen …': 'Loading audited comparison values …',
    'Vollständige Jahresabschlüsse werden geladen …': 'Loading full-year clearance counts …',
    'Zwei getrennte Modellvarianten:': 'Two separate model branches:',
    'LMS und zusätzliche Praxiskapazität starten jeweils beim kombinierten SOLL. Karte 4 baut nicht auf Karte 3 auf. Im LMS-Modellfall bereitet ein Projektteam Kurse vor der Einführung vor und übernimmt ihre Pflege; die zweite qualifizierte Praxisbegleitung samt Platz ist eine angenommene Kapazitätssensitivität.': 'The LMS and added practice capacity each branch from combined SOLL. Card 4 does not build on card 3. In the LMS model case, a project team prepares courses before launch and maintains them; the second qualified practice coach and place are an assumed capacity sensitivity.',
    'Kostengrenze:': 'Cost boundary:',
    'Ein volles zusätzliches Gehalt, Rekrutierung und Qualifizierung der zweiten Praxisbegleitung sind nicht eingepreist. Die Abschlusszahlen allein begründen daher keine Personalentscheidung.': 'A full additional salary, recruitment, and qualification for the second practice coach are excluded. Completion counts alone therefore do not justify a staffing decision.',
    'Aggregierte Vergleichsdaten und Quellen-Hashes ansehen': 'View aggregate comparison data and source hashes',
    'ENTSCHEIDUNGSGRUNDLAGE AUS DEM MODELL': 'MODEL EVIDENCE FOR A DECISION',
    'Drei Optionen und ihre offenen Fragen für die Umsetzung': 'Three options and the questions to resolve before rollout',
    'Im modellierten Vergleich ist die individuelle Praxis der verbleibende Engpass. Die Differenzen beziehen sich auf dieselben 50 Jahreslagen; die Kosten sind modellierter Nettoaufwand, keine beobachteten Einsparungen.': 'Individual practice remains the bottleneck in this model comparison. Differences use the same 50 annual demand fixtures; costs are modelled net expenditure, not observed savings.',
    'Kombiniertes SOLL': 'Combined SOLL',
    '+2.74 Abschlüsse gegenüber IST.': '+2.74 completions versus IST.',
    'Bedarf früher erkennen, geeignete Theorie gruppieren und Fristen sowie Rückstände gezielt steuern – mit unveränderter modellierter Schulungskapazität.': 'Identify needs earlier, group compatible theory training, and manage deadlines and backlog deliberately, with modelled training capacity unchanged.',
    'Prüfen:': 'Validate:',
    'Umsetzungsaufwand, echte Fristen und reale Kalenderbelegung.': 'Implementation effort, actual deadlines, and real calendar occupancy.',
    'LMS mit Projektteam vor Einführung': 'LMS with a prelaunch project team',
    '+0.54 Abschlüsse gegenüber SOLL.': '+0.54 completions versus SOLL.',
    'Weniger Trainerzeit für Theorie, aber kaum mehr vollständige Fälle; der modellierte Nettoaufwand im ersten Jahr steigt um CHF 34’266.': 'Less trainer time for theory, but scarcely more fully completed cases; modelled first-year net expenditure rises by CHF 34,266.',
    'Lernwirksamkeit, Kursfreigabe und tatsächliche Einführungs- und Betriebskosten.': 'Learning effectiveness, course approval, and actual launch and operating costs.',
    'Zweite qualifizierte Praxisbegleitung + Platz': 'Second qualified practice coach + place',
    '+35.76 Abschlüsse gegenüber SOLL.': '+35.76 completions versus SOLL.',
    'Im Modell werden 348.72 von 350 Fällen vollständig abgeschlossen; in 46 von 50 Läufen alle 350.': 'The model fully completes 348.72 of 350 cases on average; all 350 are completed in 46 of 50 runs.',
    'Reale Praxisnachfrage, Dienstplan und volle Personal-, Raum- und Qualifizierungskosten.': 'Actual practice demand, staff schedules, and full staffing, space, and qualification costs.',
    'Stand der Umsetzung:': 'Implementation status:',
    'Automatisierte Terminplanung und digitale Zertifizierung sind in Entwicklung; eine E-Learning-Plattform für Selbstlernmodule wird evaluiert. Zusätzliche Praxiskapazität bleibt eine zu validierende Modelloption.': 'Automated scheduling and digital certification are in development; an e-learning platform for self-study modules is being evaluated. Added practice capacity remains a model option to validate.',
    'Die Entscheidungstabelle nutzt den 50-Läufe-Vergleich. Die Abschnitte darunter prüfen separat höhere Nachfrage und veränderte Annahmen; ihre Mittelwerte stammen aus anderen Testläufen und sind nicht direkt miteinander zu verrechnen.': 'The decision panel uses the 50-run comparison. The sections below separately test higher demand and changed assumptions; their means come from different runs and should not be combined arithmetically.',
    'SEPARATER NACHFRAGE-STRESSTEST · FÜNF AUSGANGSLAGEN': 'SEPARATE DEMAND STRESS TEST · FIVE FIXTURES',
    'Fünf weitere Gruppen erhöhen die Fallzahl': 'Five additional groups raise the case count',
    'Bei gleicher Schulungskapazität werden aus 15 Gruppen à 20 plus 50 Einzelfällen 20 Gruppen à 20 plus 50 Einzelfälle. Der Nenner steigt von 350 auf 450; zugleich verschiebt sich der Anteil gruppierter Fälle. Mehr absolute Abschlüsse bedeuten hier keine höhere Abschlussquote.': 'With training capacity unchanged, 15 groups of 20 plus 50 individual cases become 20 groups of 20 plus 50 individual cases. The denominator rises from 350 to 450, and the grouped-case share also changes. More completions in absolute terms do not mean a higher completion rate here.',
    'Zum separaten Sensitivitätsscreen': 'Go to the separate sensitivity screen',
    'Gespeicherte Stresswerte werden geladen …': 'Loading saved stress-test values …',
    'SEPARATE KAPAZITÄTSSENSITIVITÄT · 20 GEPAARTE LÄUFE JE PUNKT': 'SEPARATE CAPACITY SENSITIVITY · 20 PAIRED RUNS PER POINT',
    'Wie weit reicht die Praxiskapazität?': 'How far does practice capacity stretch?',
    'Vier angenommene Jahresmengen von 350 bis 650 Person-Thema-Fällen treffen im kombinierten SOLL auf einen oder zwei qualifizierte Praxis-Coaches samt Plätzen. Regeln und übrige Ressourcen bleiben gleich; zusätzliche Fälle entstehen durch weitere 20er-Gruppen.': 'Four assumed annual volumes, from 350 to 650 person-topic cases, meet one or two qualified practice coaches and places under combined SOLL. Rules and other resources stay the same; additional cases come from more groups of 20.',
    'Gestrichelte Linie: angenommener Bedarf. Durchgezogene Linien: mittlere vollständige Abschlüsse aus den ursprünglichen 20 gepaarten Läufen je Nachfragepunkt. Der adaptive 50-Läufe-Check ergänzt die Werte für 350 und 450; die Tabelle nennt die ursprünglichen 20er-Werte.': 'Dashed line: assumed demand. Solid lines: mean full completions from the original 20 paired runs at each demand level. The adaptive 50-run check adds results for 350 and 450; the table reports the original 20-run values.',
    'Abschlüsse bis Tag 365': 'Completions by day 365',
    'Vollständig frei bedeutet: Alle angenommenen Fälle dieses Jahres sind bis Tag 365 geschult. Die Anzahl rechts bezieht sich auf die Variante mit zwei Praxis-Coaches.': 'Full clearance means every assumed case for that year is trained by day 365. The count at right refers to the two-coach option.',
    'Tabelle seitlich wischen oder mit Pfeiltasten verschieben.': 'Swipe the table horizontally or use the arrow keys.',
    'Geprüfte Kapazitätswerte werden geladen …': 'Loading audited capacity values …',
    'Der Vergleich von rechnerischer Termingrenze und tatsächlicher Planung wird geladen …': 'Loading the comparison of arithmetic slot limits and actual scheduling …',
    'Geprüfte Kalendergrenzen werden geladen …': 'Loading audited calendar limits …',
    'Die zusätzlichen Checks bei 350 und 450 Fällen werden geladen …': 'Loading the additional checks at 350 and 450 cases …',
    'Dieser Stresstest nutzt synthetische Bedarfsfälle bei festem 45-Personen-Pool und gleichem Modellbetrieb. Die zweite Fachperson und der zusätzliche Praxisplatz sind angenommen; ein volles zusätzliches Gehalt sowie Rekrutierung und Qualifizierung sind im bewerteten Nettoaufwand nicht enthalten.': 'This stress test uses synthetic demand cases with a fixed pool of 45 people and the same model operation. The second qualified coach and additional practice place are assumed; a full additional salary, recruitment, and qualification are excluded from valued net expenditure.',
    'Aggregierte Daten und Quellen-Hashes ansehen': 'View aggregate data and source hashes',
    'SEPARATER SENSITIVITÄTSSCREEN · FÜNF AUSGANGSLAGEN': 'SEPARATE SENSITIVITY SCREEN · FIVE FIXTURES',
    'Vier Befunde, die den Entscheid verändern': 'Four findings that change the decision',
    'Diese Zahlen stammen aus einem separaten jährlichen Screen mit fünf gepaarten Ausgangslagen. Drei Karten zeigen Einzelfaktor-Tests im kombinierten SOLL; die vierte vergleicht zwei LMS-Basiskonfigurationen.': 'These figures come from a separate annual screen with five paired fixtures. Three cards show single-factor tests under combined SOLL; the fourth compares two LMS baseline configurations.',
    '01 / Kalender': '01 / Calendar',
    'Verfügbare Trainingstage begrenzen den Durchsatz': 'Available training days limit throughput',
    'volle Abschlüsse bei kombiniertem SOLL, wenn beide Trainingsrollen statt zwei nur einen Tag pro Woche verfügbar sind.': 'full completions under combined SOLL when both training roles are available one day rather than two per week.',
    'Was bedeutet das?': 'What does this mean?',
    'Bei vier Tagen erreicht derselbe Test 350 Abschlüsse. Der Faktor ändert die Kalender von Theorie und Praxis zugleich; er beweist keinen isolierten Personalbedarf.': 'At four days, the same test reaches 350 completions. This factor changes theory and practice calendars together; it does not prove an isolated staffing need.',
    '02 / Praxis': '02 / Practice',
    'Individuelle Praxis bleibt der Engpass': 'Individual practice remains the bottleneck',
    'volle Abschlüsse, wenn die angenommene Praxisdauer von 180 auf 240 Minuten steigt.': 'full completions when assumed practice duration rises from 180 to 240 minutes.',
    'Warum ist das wichtig?': 'Why does this matter?',
    'Bei 120 Minuten entstehen 348.2 Abschlüsse. Das ist ein Testbereich für Arbeitslast, keine gemessene Verkürzung durch eine neue Schulungsmethode.': 'At 120 minutes, the model produces 348.2 completions. This is a workload test range, not a measured reduction from a new training method.',
    '03 / Gruppierung': '03 / Grouping',
    'Kleinere Zielgruppen helfen hier kaum': 'Smaller target groups make little difference here',
    '+ CHF 18’039': '+ CHF 18,039',
    'bewerteter Nettoaufwand bei Zielgrösse 5 statt 30, während volle Abschlüsse nahezu gleich bleiben: 306.2 statt 306.4.': 'in valued net expenditure with a target group size of 5 instead of 30, while full completions remain almost unchanged: 306.2 versus 306.4.',
    'Was steckt dahinter?': 'What drives this?',
    'Die begrenzte Erststart-Wartezeit steigt von 2.90 auf 6.05 Tage. Die physische Kapazität bleibt 45; getestet wurde nur die bevorzugte Zielgrösse.': 'Capped wait to first start rises from 2.90 to 6.05 days. Physical capacity stays at 45; only the preferred target size was tested.',
    '04 / LMS-Einführung': '04 / LMS rollout',
    'Materialarbeit braucht eigene Kalenderzeit': 'Course development needs its own calendar time',
    'volle Abschlüsse: Ein Projektteam erstellt LMS-Kurse vor Start, statt den Schulungskalender einer Fachperson aus Process & Quality (P&Q) mit dem Aufbau zu belegen.': 'full completions: a project team builds LMS courses before launch rather than occupying the training calendar of a Process & Quality (P&Q) specialist with development work.',
    'Wie ist das zu lesen?': 'How should this be read?',
    'Die begrenzte Erststart-Wartezeit sinkt von 14.64 auf 1.04 Tage; der bewertete Nettoaufwand im ersten Jahr steigt um CHF 4’953.17. Das Projektteam übernimmt auch die laufende Pflege. Die Variante ändert verfügbare Lehrzeit und Kursfreigabe zugleich; sie isoliert keinen einzelnen Effekt.': 'Capped wait to first start falls from 14.64 to 1.04 days; valued first-year net expenditure rises by CHF 4,953.17. The project team also handles ongoing maintenance. This option changes available teaching time and course approval together; it does not isolate one effect.',
    '„Abschluss“ bedeutet vollständige Schulung eines Person-Thema-Zyklus. Niedrigere Kosten bei weniger Abschlüssen sind keine Einsparung bei gleicher Leistung.': '“Completion” means full training of a person-topic cycle. Lower costs with fewer completions are not savings at equal output.',
    'INTERAKTIVER EINBLICK': 'INTERACTIVE VIEW',
    'Welche Annahme bewegt welches Ergebnis?': 'Which assumption changes which result?',
    'Wähle eine Variante, eine der vier markierten Einflussgrössen und eine Kennzahl. Die Balken zeigen Basis, Test A und Test B – keine Prognose zwischen diesen Punkten.': 'Choose an option, one of four highlighted factors, and a metric. The bars show baseline, test A, and test B, with no forecast between those points.',
    'Aktuelle jährliche Sensitivität · Version 0.10.0': 'Current annual sensitivity · version 0.10.0',
    '365 Tage · kein Altbestand · Basis: 350 synthetische Person-Thema-Fälle · 51 Faktoren × 2 Testwerte · 4 Varianten · 2’060 bedingte Ergebnisse inklusive Basis': '365 days · no initial backlog · baseline: 350 synthetic person-topic cases · 51 factors × 2 test settings · 4 options · 2,060 conditional results including baselines',
    'Fünf gepaarte Seed-IDs (600–604): Die vier Varianten teilen Bedarfsfälle innerhalb jedes Testpunkts. Nachfragefaktoren können die Fallzahl ändern. Die 2’060 Ergebnisse enthalten 20 Basiswerte und sind keine unabhängigen Stichproben. Hier gibt es keine Konfidenzintervalle.': 'Five paired seed IDs (600–604): the four options share demand cases within each test point. Demand factors can change the case count. The 2,060 results include 20 baseline values and are not independent samples. No confidence intervals are shown here.',
    'Gespeicherte Studienwerte werden geladen …': 'Loading saved study values …',
    'Modellvariante': 'Model option',
    'Wähle die Variante für den Einflussindex.': 'Choose an option for the influence index.',
    'Vier markierte Einflussgrössen': 'Four highlighted factors',
    'Der Index vergleicht die Grösse der getesteten A/B-Reaktionen innerhalb einer Variante. Vier Kennzahlen zählen gleich. Er hängt von Testbereichen und Gewichtung ab; hohe Werte bedeuten weder Nutzen noch eine statistisch gesicherte Rangfolge.': 'The index compares the size of tested A/B responses within an option. Four metrics have equal weight. It depends on the test ranges and weighting; high scores imply neither benefit nor a statistically established ranking.',
    'VERGLEICH VON DREI PUNKTEN': 'THREE-POINT COMPARISON',
    'Einflussgrösse': 'Factor',
    'Kennzahl': 'Metric',
    'Abschlüsse': 'Completions',
    'zählen vollständig geschulte Person-Thema-Fälle.': 'count fully trained person-topic cases.',
    'Erststart-Warten': 'Wait to first start',
    'zählt bei noch ungestarteten Fällen bis Tag 365.': 'counts waiting time for cases still without a start through day 365.',
    '14-Tage-Start': 'Start within 14 days',
    'nutzt nur fällige Fälle als Nenner.': 'uses only cases whose comparison deadline has fallen due in its denominator.',
    'ist bewerteter Nettoaufwand: Arbeit und LMS-Portfolio abzüglich Praxisgutschrift, keine beobachtete Einsparung.': 'is valued net expenditure: work and the LMS portfolio less a practice credit, not observed savings.',
    'Die Balken zeigen Mittelwerte der fünf gepaarten Seed-IDs. Die Höhe kodiert einen Wert, keine Empfehlung. Noch nicht gestartete Fälle zählen in der Wartekennzahl bis Tag 365.': 'The bars show means across five paired seed IDs. Bar height encodes a value, not a recommendation. Cases that have not started count in the waiting metric through day 365.',
    'EVIDENZ RICHTIG LESEN': 'READING THE EVIDENCE',
    'Was diese Ergebnisse zeigen – und was offen bleibt': 'What these results show, and what remains open',
    'Das Modell macht Wirkmechanismen prüfbar. Es ersetzt keine Messung im Betrieb.': 'The model makes mechanisms testable. It does not replace measurement in operations.',
    'Gleiche Ausgangslage': 'Same starting conditions',
    'Die 350 Fälle entstehen aus ungefähr 15 genannten Gruppenterminen × angenommener Gruppengrösse 20 plus 50 genannten Einzelterminen. Der Zeitraum der Angabe ist unklar; 45 synthetische Personen verteilen die Fälle. Varianten teilen Bedarf und Zufallsströme je Testpunkt.': 'The 350 cases derive from approximately 15 reported group sessions × an assumed group size of 20, plus 50 reported individual sessions. The reporting period is unclear; 45 synthetic people carry the cases. Options share demand and random streams at each test point.',
    'Zwei Werte pro Faktor': 'Two settings per factor',
    'Die Testpunkte bilden weder eine ganze Wirkungsfläche noch Wechselwirkungen zwischen Annahmen ab. Die markierten Faktoren sind ein Leseweg, keine Siegerliste.': 'The test points do not map a full response surface or interactions among assumptions. The highlighted factors guide reading; they are not a ranking of winners.',
    'Grenzen sichtbar': 'Limits made visible',
    'Kalender, Schichtdeckung, Lernwirksamkeit und Qualifikation enthalten unbestätigte Annahmen. Ein Abgleich mit gemessener Jahresnachfrage, Falldauern und Kalenderbelegung steht aus. CHF zeigt modellierten Nettoaufwand, keine beobachtete Einsparung.': 'Calendars, shift coverage, learning effectiveness, and qualifications include unconfirmed assumptions. Comparison with measured annual demand, case durations, and calendar occupancy is still outstanding. CHF shows modelled net expenditure, not observed savings.',
    'Begriffe und Quellen öffnen': 'Open terms and sources',
    'Ein Fall:': 'One case:',
    'Ein Schulungsbedarf für eine Person zu einem Thema in einem Bedarfszyklus; eine Person kann mehrere Fälle haben. Die 350 Fälle pro Modelljahr sind eine Testannahme, keine gemessene Jahresfallzahl.': 'One training need for one person on one topic in one demand cycle; a person can have several cases. The 350 cases per model year are a test assumption, not a measured annual case count.',
    'Begrenzte Erststart-Wartezeit:': 'Capped wait to first start:',
    'Tage vom erkannten Bedarf bis zum ersten Start; ohne Start zählt die Zeit bis Tag 365.': 'Days from identified need to first start; without a start, time is counted through day 365.',
    'Start binnen 14 Tagen:': 'Start within 14 days:',
    'Anteil rechtzeitiger erster Starts unter Fällen, deren Vergleichsfrist bis Tag 365 fällig wurde. Das ist keine Abschlussquote und keine IST-Timeout-Regel.': 'Share of timely first starts among cases whose comparison deadline fell due by day 365. This is neither a completion rate nor an IST timeout rule.',
    'Bewerteter Nettoaufwand:': 'Valued net expenditure:',
    'Bruttobewertung der Tätigkeiten plus LMS-Portfolio abzüglich Praxisgutschrift. Unterschiedliche Abschlüsse machen den Kostenunterschied nicht zu einer Einsparung bei gleicher Leistung.': 'Gross valuation of activities plus the LMS portfolio less a practice credit. Different completion counts mean the cost difference is not a saving at equal output.',
    'Quellen:': 'Sources:',
    'Der Variantenvergleich kommt aus 50 neu geprüften gepaarten Läufen vom 26.10.2026; seine Auswahl steht in': 'The option comparison comes from 50 newly audited paired runs dated 26 October 2026; its selected data are in',
    '. Der Kapazitätssweep mit ursprünglich 20 Läufen je Bedarfsmenge und adaptiven Zusatzchecks bei 350 und 450 Fällen steht in': '. The capacity sweep, with an original 20 runs per demand level and adaptive additional checks at 350 and 450 cases, is in',
    '. Der separate Sensitivitätsscreen nutzt': '. The separate sensitivity screen uses',
    'und das geprüfte Jahresaudit vom 07.10.2026. Seine Auswahl steht in': 'and the audited annual study dated 7 October 2026. Its selected data are in',
    'DIE ENGINE SELBST TESTEN': 'RUN THE ENGINE YOURSELF',
    'Gespeicherte Einblicke hier. Neue Läufe im lokalen Dashboard.': 'Saved findings here. New runs in the local dashboard.',
    'Diese Seite erklärt geprüfte Ergebnisse aus dem 50-Paar-Vergleich, dem separaten Kapazitätssweep und dem fünf-Fixture-Sensitivitätsscreen. Das Python-Dashboard erlaubt neue gepaarte Experimente mit sichtbaren Annahmen, Seedmap, Ereignissen und Kostennachweis.': 'This page explains audited results from the 50-pair comparison, separate capacity sweep, and five-fixture sensitivity screen. The Python dashboard supports new paired experiments with visible assumptions, seed map, events, and cost records.',
    'LOKALER START': 'RUN LOCALLY',
    'Im Repository-Hauptverzeichnis starten. Das Dashboard öffnet sich auf 127.0.0.1; die README erklärt die Installation.': 'Run from the repository root. The dashboard opens at 127.0.0.1; the README explains setup.',
    'Cosanum · Schulungssimulation · [DEMO]': 'Cosanum · training simulation · [DEMO]',
    'Quellenbasierte Annahmen · synthetische Personen · keine Betriebsmessung': 'Source-based assumptions · synthetic people · no operational measurement',
  };

  const attributeEn = {
    'Cosanum-Praxisprojekt im ZHAW CAS Process Digitalization: Simulation des manuellen Schulungsprozesses als Grundlage für Terminplanung, digitale Zertifizierung und E-Learning-Prüfung.': 'Cosanum applied project in the ZHAW CAS Process Digitalization: simulation of manual logistics training to inform scheduling, digital certification, and e-learning evaluation.',
    'Cosanum Fallstudie, zum Anfang': 'Cosanum case study, back to top',
    'Hauptnavigation': 'Main navigation',
    'Sprache wählen': 'Choose language',
    'Deutsch anzeigen': 'Show in German',
    'Englisch anzeigen': 'Show in English',
    'Modellweg vom Schulungsbedarf bis zum Abschluss': 'Model path from training need to completion',
    'Vergleich von vier Modellvarianten': 'Comparison of four model options',
    'Abschlüsse bei 350 und 450 Fällen': 'Completions at 350 and 450 cases',
    'Linienvergleich der ursprünglichen 20 gepaarten Jahresläufe je Bedarfsmenge: Zwei Praxis-Coaches liegen an allen vier Punkten über einem Coach. Bei 350 Fällen erreicht die Zwei-Coach-Kurve die Nachfrage; der separate 50-Läufe-Check zeigt ein anderes Mittel.': 'Line chart of the original 20 paired annual runs at each demand level: two practice coaches outperform one at all four points. At 350 cases, the two-coach curve reaches demand; the separate 50-run check has a different mean.',
    'Tabelle der vollständigen Abschlüsse nach Jahresmenge und Praxis-Coaches': 'Table of full completions by annual volume and number of practice coaches',
    'Basiswerte des fünf-Fixture-Screens': 'Baseline values from the five-fixture screen',
    'Versuchsaufbau erklären': 'Explain study design',
    'Einflussindex erklären': 'Explain influence index',
    'Einflussgrösse wählen': 'Choose a factor',
    'Kennzahlen erklären': 'Explain metrics',
    'Kennzahl wählen': 'Choose a metric',
    'Vergleich der drei getesteten Werte': 'Comparison of the three tested values',
  };

  const titleDe = document.title;
  const titleEn = 'Cosanum · training capacity case study';
  const imageDe = 'data/completion_frontier.svg';
  const imageEn = 'data/completion_frontier_en.svg';
  const staticText = [];
  const staticAttributes = [];

  for (const element of document.querySelectorAll('[data-i18n-text]')) {
    for (const node of element.childNodes) {
      if (node.nodeType === Node.TEXT_NODE && node.nodeValue.trim()) {
        staticText.push({ node, de: node.nodeValue });
      }
    }
  }
  for (const element of document.querySelectorAll('[data-i18n-attr]')) {
    for (const name of element.dataset.i18nAttr.split(/\s+/)) {
      if (name && element.hasAttribute(name)) {
        staticAttributes.push({ element, name, de: element.getAttribute(name) });
      }
    }
  }

  function browserLocale() {
    const preferred = navigator.languages?.[0] || navigator.language || 'en';
    return preferred.toLowerCase().startsWith('de') ? 'de' : 'en';
  }
  function queryLocale() {
    const value = new URLSearchParams(window.location.search).get('lang');
    return value === 'de' || value === 'en' ? value : null;
  }
  function savedLocale() {
    try {
      const value = localStorage.getItem(storageKey);
      return value === 'de' || value === 'en' ? value : null;
    } catch {
      return null;
    }
  }
  let locale = queryLocale() || savedLocale() || browserLocale();

  function applyStatic() {
    document.documentElement.lang = locale;
    document.title = locale === 'en' ? titleEn : titleDe;
    for (const { node, de } of staticText) {
      const original = de.trim();
      const translated = locale === 'en' ? textEn[original] : null;
      node.nodeValue = translated === undefined || translated === null
        ? de : de.replace(original, translated);
    }
    for (const { element, name, de } of staticAttributes) {
      const translated = name === 'src' && de === imageDe ? imageEn : attributeEn[de];
      element.setAttribute(name, locale === 'en' && translated ? translated : de);
    }
    for (const button of document.querySelectorAll('.language-switch [data-language]')) {
      button.setAttribute('aria-pressed', String(button.dataset.language === locale));
    }
  }

  function setLocale(lang) {
    if (lang !== 'de' && lang !== 'en') return false;
    try { localStorage.setItem(storageKey, lang); } catch { /* Private browsing may block storage. */ }
    try {
      const url = new URL(window.location.href);
      url.searchParams.set('lang', lang);
      window.history.replaceState(window.history.state, '', url.toString());
    } catch { /* Language switching also works when URL updates are unavailable. */ }
    if (locale === lang) return true;
    locale = lang;
    applyStatic();
    window.dispatchEvent(new CustomEvent('portfolio:languagechange', { detail: { lang } }));
    return true;
  }

  window.portfolioI18n = { getLocale: () => locale, setLocale, applyStatic };
  for (const button of document.querySelectorAll('.language-switch [data-language]')) {
    button.addEventListener('click', () => setLocale(button.dataset.language));
  }
  applyStatic();
})();
