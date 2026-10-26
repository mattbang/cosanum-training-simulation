/* Plain German explanations for the local adapter; numerical bounds come from bootstrap. */
window.CosanumHelp = {
  mount(spec) {
    const root = document.getElementById('cosanum-review-app');
    const number = n => Number(n).toLocaleString('de-CH');
    const choice = id => root.querySelector('#' + id).value;
    const optionName = id => root.querySelector('#' + id).selectedOptions[0].textContent;
    const sliders = Object.fromEntries(spec.sliders.map(s => [s.key, s]));
    const limits = key => {
      const s = sliders[key];
      return `${number(s.min)}–${number(s.max)} ${s.unit}; Schritte von ${number(s.step)} ${s.unit}. Referenz: ${number(spec.defaults[key])} ${s.unit}.`;
    };
    const modes = {
      annual_same_volume: 'Neue Fälle eines Modelljahres, ohne Altbestand. Beobachtung: 365 Tage.',
      annual_backlog: '1’305 offene Person-Thema-Einträge als synthetischer Altbestand plus neue Fälle. Beobachtung: 365 Tage. Die 1’305 Einträge sind keine 1’305 nachgewiesen ungeschulten Personen.',
      frozen_backlog: 'Nur die 1’305 synthetischen Altfälle, ohne neue Nachfrage. Beobachtung: 365 Tage. Der Regler «Neue Fälle pro Jahr» hat hier keine Wirkung.',
      same_cohort_drain: 'Neue Fälle aus dem ersten Modelljahr, ohne Altbestand. Danach bis Tag 730 weiterarbeiten, ohne neue Fälle im zweiten Jahr. Zeigt Nachlauf und Restbestand; garantiert keinen vollständigen Abschluss.'
    };
    const presets = {
      S0: 'Alle acht Massnahmen aus. Zeigt die IST-Regeln mit den gewählten Nachfrage-, Kalender- und Praxiswerten. Das ist eine modellierte Ausgangslage.',
      S7_RECOVERY: 'S1–S5 und Recovery an; gemeinsame Theorie-/Praxisbuchung aus. Prüft das kombinierte SOLL-Paket gegenüber IST bei gleicher Nachfrage.',
      S7_RECOVERY_JOINED: 'S1–S5, Recovery und gemeinsame Theorie-/Praxisbuchung an. Die zusätzliche Buchung ist eine Testhypothese, keine nachgewiesene Verbesserung.',
      custom: 'Die Checkboxen ergeben eine eigene Mischung. Die Anzeige wird automatisch gesetzt; «Eigene Kombination» ist keine zusätzliche Massnahme.'
    };
    const explanations = {
      'cs-exp-mode': () => [
        ['Gewählt', modes[choice('cs-exp-mode')]],
        ['Was wird verändert?', 'Welche Fälle in die Warteschlange kommen und wie lange wir sie beobachten. Ein Fall bedeutet eine Person, ein Schulungsthema und einen Schulungszyklus; eine Person kann mehrere Fälle haben.'],
        ['Die vier Möglichkeiten', 'Jahresbedarf: nur neue Fälle. Altbestand + Jahresbedarf: beide zusammen. Nur Altbestand: keine Zugänge. Gleiche Kohorte: Jahresfälle bis Tag 730 beobachten.'],
        ['Modellgrenze', 'Die Fälle und Personenzuordnungen sind synthetisch. Jahresbedarf wird innerhalb der ersten 330 Tage erzeugt; 35 Tage bleiben für den Abschluss. Das ist keine gemessene Saisonalität.']
      ],
      'cs-preset': () => [
        ['Gewählt', presets[choice('cs-preset')]],
        ['Was wird verändert?', 'Der Ausgangspunkt stellt nur die Massnahmen-Checkboxen ein. Ihre Regler, der Nachfrage-Modus und die Zufallsserie bleiben erhalten.'],
        ['Die Möglichkeiten', 'IST: alles aus. SOLL kombiniert: S1–S5 + Recovery. SOLL mit gemeinsamer Buchung: zusätzlich die Kopplung. Eigene Kombination: automatisch bei anderen Checkbox-Mischungen.'],
        ['Ausgeschaltet', 'Die jeweilige IST- oder Bypass-Regel gilt wieder. Dauer, Kosten und Schulungspflichten werden dadurch nicht pauschal null.']
      ],
      'cs-seed': () => [
        ['Was ist das?', 'Eine Nummer für die reproduzierbare Zufallsserie, keine Zahl von Personen oder Schulungen. Sie beeinflusst zum Beispiel die Zeitpunkte neuer Fälle.'],
        ['Vergleich', 'IST und gewählte Variante nutzen je Paar dieselbe Nachfrage. Weitere Paare verwenden die nächsten Seed-Nummern. Gleicher Seed und gleiche Eingaben erzeugen mit derselben Engine dasselbe Ergebnis.'],
        ['Unter- und Obergrenze', `Ganze Zahlen von 0 bis ${number(spec.maximum_seed)} für den ersten Seed. Kleine und grosse Nummern haben keine betriebliche Bedeutung und bedeuten nicht wenig oder viel Nachfrage.`]
      ],
      'cs-reps': () => [
        ['Was ist ein Paar?', 'Ein IST-Lauf und ein Lauf Ihrer Variante mit derselben Nachfrage und denselben verfügbaren Ressourcen. Jedes weitere Paar verwendet eine andere Zufallsserie. Bei «IST» allein gibt es nur einen IST-Lauf je Serie.'],
        ['Auswahl und Grenzen', `${spec.replication_choices.join(', ')} feste Paare. 1: anschaulicher Einzellauf, kein Intervall. 5: erste Orientierung. 20: stabilerer Mittelwert und approximatives 95%-Intervall für Modellzufall; mehr Rechenzeit.`],
        ['Was bleibt unsicher?', 'Mehr Paare prüfen keine unbekannten Ausgangswerte und machen die Simulation nicht zu einer Messung der Realität. Die Anzahl wird vor dem Experiment festgelegt.']
      ],
      'cs-slider-demand': () => [
        ['Was ist das?', 'Neue Person-Thema-Schulungsfälle im Modelljahr, nicht einzelne Mitarbeitende und nicht die Zahl der Schulungstermine. Beide Vergleichspartner erhalten denselben Bedarf.'],
        ['Bezug zur Praxis', `Der Referenzwert ${number(spec.defaults.demand)} ist aus Daniels grober Angabe von 15 Gruppenanlässen × 20 Fällen + 50 Einzelfällen abgeleitet. Jahresperiode und Theoriebezug sind angenommene Interpretationen, keine bestätigte Jahresmessung.`],
        ['Unter- und Obergrenze', limits('demand') + ' Bewusst gewählte Spanne für geringe bis hohe Nachfrage; keine betrieblich belegten Mindest- oder Höchstwerte.'],
        ['Im Modell', 'Gruppenzugänge werden proportional skaliert und auf ganze Anlässe abgerundet; ihre Eingangsgrösse bleibt 20. Der Rest kommt als Einzeltheoriebedarf. Bei «Nur Altbestand» wird dieser Regler ignoriert.']
      ],
      'cs-slider-days': () => [
        ['Was ist das?', 'Wochentage, an denen modellierter Trainer/P&Q und Raum Schulungen ermöglichen. Mehr Tage schaffen Kalenderzeit; sie schaffen keinen zweiten Trainer. Gilt für IST und Ihre Variante.'],
        ['Unter- und Obergrenze', limits('days') + ' 1 Tag: Dienstag. 2: Dienstag/Donnerstag. 3: Montag/Mittwoch/Freitag. 4: Montag/Dienstag/Donnerstag/Freitag. 5: Montag–Freitag.'],
        ['Modellgrenze', 'Ein Tag hat 8 verfügbare Stunden (09–17 Uhr). Die Kalender sind Prototypannahmen; individuelle Schichtpläne werden damit nicht rekonstruiert. Die obere Grenze schliesst Wochenenden aus.']
      ],
      'cs-slider-practice': () => [
        ['Was ist das?', 'Dauer einer individuellen Praxisschulung. Währenddessen sind Teilnehmer und Trainer belegt. Der Wert beeinflusst mögliche Abschlüsse, Wartezeiten und den bewerteten Arbeitsaufwand in beiden Vergleichspartnern.'],
        ['Unter- und Obergrenze', limits('practice') + ' Der Referenzwert stammt aus Daniels Praxiszeit. 1 Stunde prüft eine kurze, 5 Stunden eine lange Praxisphase; diese Grenzen sind Sensitivitätsannahmen.'],
        ['Bezug zur Praxis', 'Eine kürzere Einstellung beweist keine ausreichende Kompetenz und keine erreichbare Zeitersparnis. Die Praxis bleibt individuell; der vorgeschlagene strukturierte Instruktionsablauf ist hier nicht als Zeitgewinn modelliert.']
      ],
      'cs-slider-group': () => [
        ['Was ist das?', 'Angestrebte Teilnehmerzahl eines kompatiblen Theorie-Termins mit S1. Gleicher Bedarf wird in kleinere oder grössere Termine gebündelt. Nur passende Themen dürfen zusammenkommen.'],
        ['Unter- und Obergrenze', limits('group') + ' Schwelle4; physisch45 Personen. Mit Mindestbesetzung15 sind30 gleichzeitig freigestellt. Gruppenziel45 erfordert bewusst Mindestbesetzung0; Eingangsnachfrage bleibt gleich.'],
        ['Frist geht vor Zielgrösse', 'Bei drohendem Fristablauf darf eine kleinere kompatible Gruppe starten, auch drei Personen oder eine Einzelperson. Neue Zugänge setzen ältere Wartezeiten nicht zurück. Fehlende Ressourcen werden als Fristverletzung und Eskalation sichtbar.'],
        ['Wann wirkt der Regler?', 'Nur wenn S1 eingeschaltet ist. Bei ausgeschaltetem S1 bleibt er deaktiviert und die IST-Zuteilung gilt.']
      ],
      'cs-slider-wait': () => [
        ['Was ist das?', 'Ein Zeitbudget in Kalendertagen für den ersten Schulungsstart. Gemeint ist der Start, nicht der Abschluss von Theorie und Praxis.'],
        ['Unter- und Obergrenze', limits('wait') + ' 7 Tage prüfen eine engere Frist, 28 Tage mehr Spielraum. Beides sind gewählte Prototypgrenzen, keine bestätigten Vorgaben.'],
        ['Zwei Funktionen und Uhren', 'Die gemeinsame Kennzahl misst ab Entstehen des Bedarfs. Die harte SOLL-Planungsfrist beginnt ab Erkennen/Bekanntwerden des Falls und wirkt nur mit S1: rechtzeitig starten, nötigenfalls klein oder einzeln. Beide nutzen denselben Regler, aber verschiedene Startzeitpunkte. Früheres Erkennen (S2) verkürzt diese Lücke.'],
        ['IST bleibt IST', 'Die IST-Dringlichkeitsprüfung nach drei Wochen wird dadurch nicht zu einer harten Startfrist. Nicht verfügbare Kapazität wird nicht erfunden; Fristverletzungen bleiben sichtbar.']
      ],
      'cs-solution-0': () => [
        ['An', 'Kompatible Theoriebedarfe bündeln und bis zur Startfrist einen Termin ermöglichen. Nötigenfalls eine kleine Gruppe oder eine Einzelperson schulen. Individuell vorgeschriebene Themen bleiben individuell.'],
        ['Aus', 'IST-Zuteilung und IST-Dreiwochenprüfung; die Theorie-Zielgrösse wirkt nicht. Recovery wird ebenfalls ausgeschaltet.'],
        ['Modellgrenze', 'Dieser Dashboard-Schalter aktiviert Gruppierung und harte Startfrist zusammen. Der einzelne S1-Test in der gespeicherten Jahresstudie prüft nur Gruppierung.']
      ],
      'cs-solution-1': () => [
        ['An', 'Neue Bedarfe früher sichtbar machen, beispielsweise durch einen regelmässigen Abgleich. Im Modell wird die Erkennungsverzögerung reduziert; der eigentliche Bedarf bleibt gleich.'],
        ['Aus', 'Die konfigurierte IST-Erkennungsverzögerung gilt.'],
        ['Modellgrenze', 'Ein bereits bekannter Altfall kann nicht rückwirkend früher erkannt werden. Die Verzögerungen sind Prototypannahmen, keine gemessenen Erkennungszeiten.']
      ],
      'cs-solution-2': () => [
        ['An', 'Nachweise nach der Schulung digital erfassen und fehlende Nachweise effizienter nachholen. Im Modell ändern sich die Zeiten dieser Dokumentationsschritte.'],
        ['Aus', 'IST-Nachweiszeiten gelten.'],
        ['Modellgrenze', 'Dokumentierter Abschluss und erworbene Kompetenz sind verschiedene Ergebnisse. Ein digitaler Nachweis macht eine Person nicht automatisch geschult.']
      ],
      'cs-solution-3': () => [
        ['An', 'Die Verzögerung zwischen Schulungsentscheidung und Terminplanung reduzieren, etwa durch klare Zuständigkeiten oder Terminunterstützung.'],
        ['Aus', 'Die konfigurierte IST-Planungsverzögerung gilt.'],
        ['Modellgrenze', 'Schnellere Planung erzeugt keine zusätzlichen Trainer, Räume oder verfügbare Teilnehmer. Die Zeitannahme ist keine nachgewiesene Einsparung.']
      ],
      'cs-solution-4': () => [
        ['An', 'Offene Fälle nach Frist, Themenpriorität und Wartealter ordnen. Prio-1-Themen stehen für besonders wichtige, unter anderem einkommensrelevante Schulungen.'],
        ['Aus', 'Die IST-Auswahlreihenfolge gilt; Recovery wird ebenfalls ausgeschaltet.'],
        ['Modellgrenze', 'Priorisieren verschiebt verfügbare Kapazität; es schafft keine neue. Auch Wartezeiten niedrigerer Prioritäten werden erfasst. Daraus wird kein gemessener Umsatzgewinn abgeleitet.']
      ],
      'cs-solution-5': () => [
        ['An', 'Wenn ein fristgerechter Neustart nicht mehr machbar ist, verfügbare Zeit auch für offene Praxis und überfällige Fälle nutzen. Gealterte Fälle erhalten regelmässig eine Chance.'],
        ['Aus', 'Die bisherige Aufteilung zwischen neuen Starts und Nachholung gilt.'],
        ['Voraussetzung und Grenze', 'Nur mit S1 und S5 auswählbar. Ausschalten einer Voraussetzung schaltet Recovery aus. Nachholen löscht frühere Fristverletzungen nicht und vergrössert die Kapazität nicht.']
      ],
      'cs-solution-6': () => [
        ['An', 'Bei der Theorieplanung gleich passende spätere Praxistermine mitreservieren. Der Theorie-Start kann dadurch warten, bis ein vollständiger Plan machbar ist.'],
        ['Aus', 'Praxis nach der Theorie separat planen.'],
        ['Modellgrenze', 'Praxis bleibt individuell und gleich lang. Das ist eine getestete Hypothese: frühe Reservationen können auch Starts verzögern und andere Fälle blockieren. Kein automatischer Vorteil und keine zusätzliche Kapazität.']
      ],
      'cs-case': () => [
        ['Was ist das?', 'Auswahl eines bereits gerechneten Falls der gespeicherten Jahresstudie. Dieser Filter startet keine neue Simulation und übernimmt Ihre aktuellen Regler nicht.'],
        ['Gewählt', modes[choice('cs-case')] || 'Gespeicherte Einzeltests von S1–S5 beim gleichen neuen Jahresbedarf. S1 prüft hier Gruppierung allein; der Dashboard-S1-Schalter umfasst zusätzlich die Startfrist.'],
        ['Grenze', 'Es gibt nur die angezeigten gespeicherten Fälle; eigene Kombinationen werden im Bereich «Experiment» neu gerechnet.']
      ],
      'cs-reference': () => [
        ['Was ist das?', 'Die Vergleichsbasis für Differenzen der gespeicherten Ergebnisse. «Gegenüber IST» zeigt die Veränderung zum Ausgangsprozess; «gegenüber SOLL + Recovery» isoliert insbesondere die zusätzliche gemeinsame Buchung.'],
        ['Grenze', 'Die Auswahl ändert die Darstellung, keine Prozesse, Eingaben oder gespeicherten Rechenläufe.']
      ],
      'cs-metric': () => [
        ['Was ist das?', `Die angezeigte Ergebnisgrösse: ${optionName('cs-metric')}. Sie ist ein berechneter Output, kein Initialisierungswert.`],
        ['Vergleich', 'Die Grafik zeigt Variante minus Vergleichsbasis. Mehr Abschlüsse oder fristgerechte Starts sind günstig; mehr offene Fälle, Warten oder Arbeitsaufwand sind ungünstig. Kosten bei unterschiedlich vielen Abschlüssen sind kein gleichwertiger Sparnachweis.'],
        ['Grenze', 'Die auswählbaren Kennzahlen stammen aus der gespeicherten Studie. Intervalle beschreiben Modellzufall; Fallzahlen zählen keine eindeutig verschiedenen Personen.']
      ]
    };
    let active = null, pinned = false, closeTimer;
    const close = () => {
      clearTimeout(closeTimer);
      if (active) { active.tip.hidden = true; active.button.setAttribute('aria-expanded', 'false'); }
      active = null; pinned = false;
    };
    const render = entry => {
      entry.tip.replaceChildren();
      const title = document.createElement('h3'); title.textContent = entry.title; entry.tip.append(title);
      for (const [name, explanation] of explanations[entry.id]()) {
        const paragraph = document.createElement('p');
        const heading = document.createElement('strong'); heading.textContent = name + ': ';
        paragraph.append(heading, document.createTextNode(explanation)); entry.tip.append(paragraph);
      }
    };
    const place = entry => {
      const r = entry.button.getBoundingClientRect(), t = entry.tip.getBoundingClientRect();
      const left = Math.max(12, Math.min(r.left, window.innerWidth - t.width - 12));
      const below = Math.max(r.bottom, entry.control.getBoundingClientRect().bottom) + 8;
      const top = below + t.height <= window.innerHeight - 12 ? below : Math.max(12, r.top - t.height - 8);
      entry.tip.style.left = left + 'px'; entry.tip.style.top = top + 'px';
    };
    const open = (entry, pin = false) => {
      clearTimeout(closeTimer);
      if (active !== entry) close();
      active = entry; pinned = pinned || pin;
      render(entry); entry.tip.hidden = false; entry.button.setAttribute('aria-expanded', 'true'); place(entry);
    };
    const laterClose = () => { if (!pinned) closeTimer = setTimeout(close, 180); };
    for (const id of Object.keys(explanations)) {
      const control = root.querySelector('#' + id);
      if (!control) continue;
      const label = root.querySelector(`label[for="${id}"]`) || control.closest('label');
      const title = label.textContent.trim();
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'cs-help-button'; button.textContent = 'i';
      button.setAttribute('aria-label', 'Erklärung: ' + title); button.setAttribute('aria-expanded', 'false');
      const tip = document.createElement('div');
      tip.id = id + '-help'; tip.className = 'cs-help-tooltip'; tip.hidden = true; tip.setAttribute('role', 'tooltip');
      button.setAttribute('aria-controls', tip.id); button.setAttribute('aria-describedby', tip.id);
      control.setAttribute('aria-describedby', [control.getAttribute('aria-describedby'), tip.id].filter(Boolean).join(' '));
      const row = document.createElement('div'); row.className = control.type === 'checkbox' ? 'cs-help-check' : 'cs-help-label';
      label.before(row); row.append(label, button); root.append(tip);
      const entry = {id, control, label, title, button, tip}; render(entry);
      for (const target of [label, button, control]) {
        target.addEventListener('pointerenter', () => { if (!pinned) open(entry); });
        target.addEventListener('pointerleave', laterClose);
      }
      for (const target of [button, control]) {
        target.addEventListener('focus', () => open(entry)); target.addEventListener('blur', laterClose);
      }
      button.addEventListener('click', () => { if (active === entry && pinned) close(); else open(entry, true); });
      tip.addEventListener('pointerenter', () => clearTimeout(closeTimer)); tip.addEventListener('pointerleave', laterClose);
      const refresh = () => { render(entry); if (active === entry) place(entry); };
      control.addEventListener('change', refresh);
    }
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && active) { close(); e.preventDefault(); } });
    document.addEventListener('pointerdown', e => {
      if (active && !active.tip.contains(e.target) && !active.button.contains(e.target) && !active.label.contains(e.target) && e.target !== active.control) close();
    });
    window.addEventListener('resize', close);
    window.addEventListener('scroll', e => { if (active && !active.tip.contains(e.target)) close(); }, true);
  }
};
