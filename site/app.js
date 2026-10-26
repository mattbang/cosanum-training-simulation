/* The portfolio view reads audited aggregates of saved studies.
   It does not run the Python model or interpolate untested parameter settings. */
(() => {
  const locale = () => window.portfolioI18n?.getLocale() === 'en' ? 'en' : 'de';
  const tr = (de, en) => locale() === 'en' ? en : de;
  const localized = pair => pair[locale()];
  const comparisonMeta = {
    IST: { label: { de: 'IST', en: 'Current process' }, subtitle: { de: 'Heutiger Ablauf im Modell', en: 'Current workflow in the model' }, tag: { de: 'Ausgangslage', en: 'Baseline' } },
    SOLL: { label: { de: 'Kombiniertes SOLL', en: 'Combined target process' }, subtitle: { de: 'Gleiche Schulungsressourcen', en: 'Same training resources' }, tag: { de: 'Vergleichsbasis', en: 'Reference' } },
    SOLL_LMS_TEAM: { label: { de: 'SOLL + LMS', en: 'Target + LMS' }, subtitle: { de: 'Projektteam vor Einführung', en: 'Project team prepares courses before launch' }, tag: { de: 'Abzweigung A', en: 'Option A' } },
    SOLL_COACH2: { label: { de: 'SOLL + Praxiskapazität', en: 'Target + practice capacity' }, subtitle: { de: 'Zweite qualifizierte Begleitung + Platz', en: 'Second qualified coach and training space' }, tag: { de: 'Abzweigung B', en: 'Option B' } },
  };
  const metricMeta = {
    completed: { label: { de: 'Volle Abschlüsse', en: 'Full training completions' }, short: { de: 'Abschlüsse', en: 'Completions' }, unit: { de: 'Fälle', en: 'cases' }, decimals: 1 },
    mean_time_to_start_or_year_end_days: { label: { de: 'Warten bis Erststart / Jahresende', en: 'Wait to first start or year end' }, short: { de: 'Erststart-Warten', en: 'Wait to start' }, unit: { de: 'Tage', en: 'days' }, decimals: 2 },
    common_14day_start_service: { label: { de: 'Erststart binnen 14 Tagen', en: 'First start within 14 days' }, short: { de: '14-Tage-Start', en: '14-day start' }, unit: { de: '%', en: '%' }, decimals: 1 },
    net_chf: { label: { de: 'Bewerteter Nettoaufwand', en: 'Modelled net cost' }, short: { de: 'Nettoaufwand · CHF', en: 'Net cost · CHF' }, unit: { de: 'CHF', en: 'CHF' }, decimals: 2 },
  };
  const factorNotes = {
    training_days: { de: 'Die getesteten Tage verändern die Kalender von Theorie und Praxis gleichzeitig. Mehr Abschlüsse erfordern zusätzliche verfügbare Trainingszeit; ein einzelner Rollenengpass ist damit nicht isoliert.', en: 'The tested number of days changes theory and practice calendars together. More completions require more available training time; this test does not isolate one role as the bottleneck.' },
    preferred_group: { de: 'Dies ist die bevorzugte Gruppengrösse, nicht die physische Obergrenze. Kleine Gruppen können mehr Termine und Koordination auslösen, ohne den Praxisengpass zu lösen.', en: 'This is the preferred group size, not the physical maximum. Smaller groups may require more sessions and coordination without relieving the practice bottleneck.' },
    pq_qualification: { de: 'Die zusätzliche Praxisqualifikation von P&Q ist im Betrieb nicht bestätigt. Der Test zeigt eine Möglichkeit, keine verfügbare Ressource oder zugesagte Verbesserung.', en: 'P&Q staff being qualified to coach practice has not been confirmed in operations. This test explores a possibility, not an available resource or promised improvement.' },
    practice_minutes: { de: 'Die Praxisdauer ist ein ausdrücklich angenommener Belastungstest. Kürzere Praxis ist keine bereits nachgewiesene Wirkung einer neuen Instruktionsmethode.', en: 'Practice duration is an explicit stress-test assumption. Shorter practice has not been demonstrated as an effect of a new teaching method.' },
    content: { de: 'Das Materialbudget bestimmt im Modell auch die Autorenstunden. Bei der P&Q-Fachperson können mehr Stunden Lehre und Kursfreigabe verzögern; beim Projektteam ändern sich vor allem die bewerteten Kosten.', en: 'In the model, the content budget also determines authoring hours. More P&Q authoring can delay teaching and course release; with the project team, it mainly changes modelled costs.' },
    practice_mix: { de: 'Der Themenmix verändert, wie viele der neuen Fälle individuelle Praxis benötigen. Die Fallzahl bleibt in diesem Test gleich; die zusätzliche Praxisarbeit ist keine reine Effizienzänderung.', en: 'The topic mix changes how many new cases need individual practice. Case count stays constant in this test; the extra practice work is not a pure efficiency change.' },
    unformed: { de: 'Ohne vorgeformten Gruppierungshinweis treffen die gleichen synthetischen Fälle einzelner ein. Das verändert das Bündelungspotenzial, nicht die Zahl der Menschen.', en: 'Without a preformed grouping hint, the same synthetic cases arrive more individually. This changes grouping potential, not the number of people.' },
    author_binding: { de: 'Der Materialbetrag bleibt fest; ein anderer verwendeter Stundensatz verändert daraus abgeleitete Autorenstunden und damit den P&Q-Schulungskalender. Das ist keine gemessene Lohnänderung.', en: 'The content budget stays fixed; using a different hourly rate changes the authoring hours derived from it and thus the P&Q training calendar. It is not a measured pay change.' },
  };
  const scenarioNamesEn = {
    S0: 'Current process',
    S7_RECOVERY: 'Combined target process',
    LMS_PQ_IN_SERVICE: 'Target + LMS (P&Q builds courses during operations)',
    LMS_PRELAUNCH_TEAM: 'Target + LMS (project team before launch)',
  };
  const factorNamesEn = {
    pq_qualification: 'P&Q also qualified to coach practice',
    training_days: 'Training days per week',
    unformed: 'Arrivals without preformed groups',
    practice_mix: 'Practice share among new cases',
    preferred_group: 'Target: preferred group size',
    practice_minutes: 'Individual practice duration',
    content: 'LMS: content budget per topic',
    author_binding: 'Derive authoring hours from budget',
  };
  function scenarioLabel(item) { return locale() === 'en' ? (scenarioNamesEn[item.id] || item.label_de) : item.label_de; }
  function factorLabel(item) { return locale() === 'en' ? (factorNamesEn[item.factor_id] || item.label_de) : item.label_de; }
  const els = {
    comparison: document.getElementById('comparison-grid'),
    comparisonClearance: document.getElementById('comparison-clearance'),
    frontierTable: document.getElementById('frontier-table'),
    frontierArithmetic: document.getElementById('frontier-arithmetic'),
    frontierBound: document.getElementById('frontier-bound'),
    frontierConfirmation: document.getElementById('frontier-confirmation'),
    volume: document.getElementById('volume-stress-values'),
    baseline: document.getElementById('baseline-grid'),
    scenario: document.getElementById('scenario-select'),
    scenarioDescription: document.getElementById('scenario-description'),
    factors: document.getElementById('factor-list'),
    metrics: document.getElementById('metric-tabs'),
    title: document.getElementById('factor-title'),
    settings: document.getElementById('factor-settings'),
    rank: document.getElementById('factor-rank'),
    chart: document.getElementById('factor-chart'),
    insight: document.getElementById('factor-insight'),
  };
  let study;
  let comparisonData;
  let frontierData;
  let comparisonError;
  let frontierError;
  let studyError;
  let scenarioId = 'S7_RECOVERY';
  let factorId = 'training_days';
  let metric = 'completed';

  function number(value, digits) {
    return new Intl.NumberFormat(locale() === 'en' ? 'en-CH' : 'de-CH', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Number(value));
  }
  function displayMetric(value, key) {
    if (key === 'common_14day_start_service') return `${number(value * 100, 1)} %`;
    if (key === 'net_chf') return `CHF ${number(value, 2)}`;
    return `${number(value, metricMeta[key].decimals)} ${localized(metricMeta[key].unit)}`;
  }
  function setting(value, unit) {
    const settingAliases = {
      pq_hourly_chf: { de: 'P&Q-Satz CHF 100/h', en: 'P&Q rate CHF 100/h' },
      coach_hourly_chf: { de: 'Coach-Satz CHF 65/h', en: 'Coach rate CHF 65/h' },
      daniel_calendar: { de: 'P&Q-Schulungskalender', en: 'P&Q training calendar' },
      prelaunch_team: { de: 'Projektteam vor Start', en: 'Project team before launch' },
      'uniformer Themenkatalog': { de: 'uniformer Themenkatalog', en: 'uniform topic catalogue' },
    };
    if (Object.prototype.hasOwnProperty.call(settingAliases, value)) return localized(settingAliases[value]);
    if (value === true || String(value).toLowerCase() === 'true') return tr('Ja', 'Yes');
    if (value === false || String(value).toLowerCase() === 'false') return tr('Nein', 'No');
    if (unit === 'Anteil' || unit === 'Wahrscheinlichkeit') {
      const n = Number(value);
      if (Number.isFinite(n)) return `${number(n * 100, 0)} %`;
    }
    if (unit === 'CHF/Thema') return `CHF ${number(value, 0)} ${tr('je Thema', 'per topic')}`;
    if (typeof value === 'number') {
      const unitLabels = {
        Tage: value === 1 ? { de: 'Tag', en: 'day' } : { de: 'Tage', en: 'days' },
        Personen: value === 1 ? { de: 'Person', en: 'person' } : { de: 'Personen', en: 'people' },
        'Min.': { de: 'Min.', en: 'min' },
      };
      const displayUnit = unitLabels[unit] ? localized(unitLabels[unit]) : unit;
      return `${number(value, Number.isInteger(value) ? 0 : 2)} ${displayUnit}`.trim();
    }
    return `${value}${unit && unit !== 'Bindung' && unit !== 'Organisation' ? ` ${unit}` : ''}`;
  }
  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function renderComparison(data) {
    const cards = data.cards;
    if (data.schema_version !== 1 || data.metadata?.annual_synthetic_cases !== 350
        || data.metadata?.paired_fixture_ids?.length !== 50
        || !Array.isArray(cards) || cards.map(item => item.id).join(',') !== Object.keys(comparisonMeta).join(',')) {
      throw new Error(tr('Vergleichsformat unvollständig', 'Comparison format is incomplete'));
    }
    els.comparison.replaceChildren();
    for (const [index, item] of cards.entries()) {
      const complete = Number(item.training_completed);
      const practiceOpen = Number(item.theory_complete_practice_unfinished);
      if (!Number.isFinite(complete) || !Number.isFinite(practiceOpen)
          || complete < 0 || practiceOpen < 0 || complete > 350 || practiceOpen > 350
          || !Number.isInteger(item.full_clearance_count)
          || item.full_clearance_count < 0 || item.full_clearance_count > 50) {
        throw new Error(tr('Ungültige Vergleichswerte', 'Invalid comparison values'));
      }
      const info = comparisonMeta[item.id];
      const card = element('article', `comparison-card${index === 3 ? ' is-capacity' : ''}`);
      const top = element('div', 'comparison-card-top');
      top.append(element('span', 'comparison-index', `${String(index + 1).padStart(2, '0')} / 04`));
      top.append(element('span', 'comparison-tag', localized(info.tag)));
      card.append(top);
      card.append(element('h3', '', localized(info.label)));
      card.append(element('p', 'comparison-subtitle', localized(info.subtitle)));
      const result = element('p', 'comparison-result');
      result.append(element('strong', '', number(complete, 2)));
      result.append(element('span', '', tr('/ 350 Abschlüsse', '/ 350 completions')));
      card.append(result);
      const detail = element('p', 'comparison-detail');
      detail.append(element('strong', '', number(practiceOpen, 2)));
      detail.append(element('span', '', tr(' Theorie fertig, Praxis offen', ' theory complete, practice pending')));
      card.append(detail);
      els.comparison.append(card);
    }
    els.comparisonClearance.textContent = tr(
      `Alle 350 Fälle bis Tag 365 fertig (je 50 synthetische Läufe): IST ${cards[0].full_clearance_count}/50 · SOLL ${cards[1].full_clearance_count}/50 · LMS-Team ${cards[2].full_clearance_count}/50 · zweiter Coach ${cards[3].full_clearance_count}/50. Diese Stichprobenhäufigkeit ist keine Betriebswahrscheinlichkeit.`,
      `All 350 cases completed by day 365 (50 synthetic runs per option): current ${cards[0].full_clearance_count}/50 · target ${cards[1].full_clearance_count}/50 · LMS team ${cards[2].full_clearance_count}/50 · second coach ${cards[3].full_clearance_count}/50. These sample frequencies are not real-world probabilities.`
    );
  }
  function showComparisonError(error) {
    els.comparison.textContent = tr(
      `Die geprüfte Vergleichsdatei konnte nicht geladen werden (${error}). Starte diese Vorschau über einen lokalen Webserver.`,
      `The verified comparison data could not be loaded (${error}). Open this preview through a local web server.`
    );
    els.comparison.classList.add('load-error');
    els.comparisonClearance.textContent = '';
  }
  async function loadComparison() {
    try {
      const response = await fetch('data/comparison.json', { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      comparisonData = await response.json();
      renderComparison(comparisonData);
    } catch (error) {
      comparisonError = error.message;
      showComparisonError(comparisonError);
    }
  }
  function renderFrontier(data) {
    const rows = data.rows;
    const bound = data.metadata?.practice_slot_bound;
    const boundExamples = data.fixed_fixture_bound_examples;
    const checks = data.confirmations;
    if (data.schema_version !== 1 || data.metadata?.engine_version !== '0.10.0'
        || data.metadata?.paired_fixture_ids?.length !== 20
        || !Array.isArray(rows) || rows.map(item => item.annual_volume).join(',') !== '350,450,550,650'
        || bound?.one_coach !== 208 || bound?.two_coaches !== 416
        || bound?.calendar_days !== 104 || bound?.daily_minutes !== 480
        || bound?.practice_minutes !== 180 || bound?.coordination_minutes !== 5
        || bound?.booking_minutes !== 185 || bound?.slots_per_day_per_coach !== 2
        || bound?.fixed_fixture_formula !== 'theory_only_requests + min(practice_required_requests, coach_count * 208)'
        || !Array.isArray(boundExamples) || boundExamples.map(item => item.annual_volume).join(',') !== '550,650'
        || !Array.isArray(checks) || checks.map(item => item.annual_volume).join(',') !== '350,450') {
      throw new Error(tr('Kapazitätsdaten unvollständig', 'Capacity data is incomplete'));
    }
    for (const item of rows) {
      for (const key of ['one_coach', 'two_coaches']) {
        const arm = item[key];
        if (!Number.isFinite(arm?.completed_mean) || arm.completed_mean < 0
            || arm.completed_mean > item.annual_volume
            || !Number.isInteger(arm.full_clearance_count) || arm.full_clearance_count < 0
            || arm.full_clearance_count > 20) {
          throw new Error(tr('Ungültige Kapazitätswerte', 'Invalid capacity values'));
        }
      }
    }
    for (const item of boundExamples) {
      if (item.paired_fixtures !== 20
          || !Number.isInteger(item.slot_feasible_fixtures)
          || !Number.isInteger(item.slot_infeasible_fixtures)
          || item.slot_feasible_fixtures + item.slot_infeasible_fixtures !== 20
          || !Number.isInteger(item.full_clearance_fixtures)
          || item.full_clearance_fixtures < 0
          || item.full_clearance_fixtures > item.slot_feasible_fixtures) {
        throw new Error(tr('Ungültige Termingrenzen', 'Invalid scheduling bounds'));
      }
    }
    for (const check of checks) {
      if (check.additional_paired_fixtures !== 30 || check.pooled_paired_fixtures !== 50) {
        throw new Error(tr('Ungültiger Zusatzcheck', 'Invalid extension check'));
      }
      for (const key of ['one_coach', 'two_coaches']) {
        const arm = check[key];
        if (!Number.isFinite(arm?.completed_mean) || arm.completed_mean < 0
            || arm.completed_mean > check.annual_volume
            || !Number.isInteger(arm.full_clearance_count) || arm.full_clearance_count < 0
            || arm.full_clearance_count > 50) {
          throw new Error(tr('Ungültiger Zusatzcheck', 'Invalid extension check'));
        }
      }
    }

    const table = element('table', 'frontier-table');
    table.append(element('caption', 'sr-only', tr('20 gepaarte synthetische Jahresläufe je Bedarfsmenge', '20 paired synthetic annual runs per demand volume')));
    const head = element('thead');
    const headerRow = element('tr');
    for (const label of tr(
      ['Jahresfälle', 'Ein Coach · Abschlüsse', 'Zwei Coaches · Abschlüsse', 'Alle Fälle fertig · zwei Coaches'],
      ['Annual cases', 'One coach · completions', 'Two coaches · completions', 'All cases completed · two coaches']
    )) {
      const cell = element('th', '', label);
      cell.scope = 'col';
      headerRow.append(cell);
    }
    head.append(headerRow);
    table.append(head);
    const body = element('tbody');
    for (const item of rows) {
      const row = element('tr');
      row.append(element('td', '', number(item.annual_volume, 0)));
      row.append(element('td', '', number(item.one_coach.completed_mean, 1)));
      row.append(element('td', '', number(item.two_coaches.completed_mean, 1)));
      row.append(element('td', '', `${item.two_coaches.full_clearance_count} / 20 ${tr('Läufe', 'runs')}`));
      body.append(row);
    }
    table.append(body);
    els.frontierTable.replaceChildren(table);

    const [at550, at650] = boundExamples;
    els.frontierArithmetic.replaceChildren(
      element('strong', '', tr('Rechnerisch möglich ≠ bis Jahresende geplant. ', 'Arithmetically feasible ≠ scheduled by year end. ')),
      document.createTextNode(tr(
        `Bei ${at550.annual_volume} Fällen erlauben die Praxis-Termine in allen ${at550.slot_feasible_fixtures} Testläufen mit zwei Coaches einen vollständigen Abschluss; tatsächlich schaffen ihn ${at550.full_clearance_fixtures}. Bei ${at650.annual_volume} Fällen sind ${at650.slot_infeasible_fixtures} von 20 Läufen schon durch die Termingrenze ausgeschlossen. Von den übrigen ${at650.slot_feasible_fixtures} schaffen ${at650.full_clearance_fixtures} den vollständigen Abschluss.`,
        `At ${at550.annual_volume} cases, practice slots with two coaches permit full clearance in all ${at550.slot_feasible_fixtures} runs, but only ${at550.full_clearance_fixtures} actually achieve it. At ${at650.annual_volume} cases, the slot bound alone rules out full clearance in ${at650.slot_infeasible_fixtures} of 20 runs. Of the remaining ${at650.slot_feasible_fixtures}, ${at650.full_clearance_fixtures} fully clear.`
      ))
    );

    els.frontierBound.replaceChildren();
    els.frontierBound.append(element('p', 'eyebrow', tr('RECHNERISCHE PRAXIS-TERMINGRENZE', 'ARITHMETIC PRACTICE-SLOT BOUND')));
    els.frontierBound.append(element('h3', '', tr('Ein oder zwei Kalender', 'One or two coach calendars')));
    els.frontierBound.append(element('strong', 'bound-value', `${bound.one_coach} / ${bound.two_coaches}`));
    els.frontierBound.append(element('p', '', tr(
      'Maximale Praxis-Termine pro Modelljahr: 104 buchbare Tage à 8 Stunden je Coach. 180 Minuten Praxis plus 5 Minuten Koordination ergeben 185 Minuten je Termin; abgerundet passen 480 / 185 = 2 Starts pro Tag.',
      'Maximum practice appointments per model year: 104 bookable eight-hour days per coach. Practice takes 180 minutes plus 5 minutes of coordination, or 185 minutes per appointment; floor(480 / 185) = 2 starts per day.'
    )));
    els.frontierBound.append(element('p', 'bound-formula', tr(
      'Für einen festen Bedarfsdatensatz gilt als optimistische Obergrenze vollständiger Fälle: Fälle ohne Praxis + min(Fälle mit Praxis, verfügbare Praxis-Termine), höchstens die Gesamtfallzahl. Tatsächliche Abschlüsse können durch Ankunftszeiten, Theoriebereitschaft, Kalenderkonflikte und das Jahresende darunter liegen. 350 ist keine strukturelle Obergrenze.',
      'For a fixed demand fixture, an optimistic upper bound on full completions is: cases without practice + min(cases needing practice, available practice slots), capped at the total case count. Arrivals, theory readiness, calendar conflicts and year end can keep actual completions below this bound. The 350 cases are not a structural ceiling.'
    )));

    els.frontierConfirmation.replaceChildren();
    els.frontierConfirmation.append(element('p', 'eyebrow', tr('ADAPTIVER ZUSATZCHECK · 50 LÄUFE JE MENGE', 'ADAPTIVE EXTENSION · 50 RUNS PER VOLUME')));
    els.frontierConfirmation.append(element('h3', '', tr('350 und 450 Fälle nachgeprüft', '350 and 450 cases checked again')));
    for (const check of checks) {
      const row = element('div', 'confirmation-row');
      row.append(element('h4', '', `${check.annual_volume} ${tr('synthetische Fälle', 'synthetic cases')}`));
      const pair = element('div', 'confirmation-pair');
      for (const [key, label] of [['one_coach', tr('Ein Coach', 'One coach')], ['two_coaches', tr('Zwei Coaches', 'Two coaches')]]) {
        const value = element('div');
        value.append(element('span', '', label));
        value.append(element('strong', 'confirmation-value', `${check[key].full_clearance_count} / 50`));
        pair.append(value);
      }
      row.append(pair);
      row.append(element('p', 'confirmation-detail', `${tr('Mittlere Abschlüsse', 'Mean completions')}: ${number(check.one_coach.completed_mean, 2)} / ${number(check.two_coaches.completed_mean, 2)}`));
      els.frontierConfirmation.append(row);
    }
    els.frontierConfirmation.append(element('p', '', tr(
      'Je 30 weitere gepaarte Seeds ergänzen die ursprünglichen 20. Die Nachtests wurden nach Sichtung der ersten Ergebnisse gewählt; die 50er-Werte sind explorativ und belegen keine allgemeine Schwelle.',
      'Thirty additional paired seeds extend the original 20 at each volume. These follow-up tests were chosen after reviewing initial results; the 50-run figures are exploratory and do not establish a general threshold.'
    )));
  }
  function showFrontierError(error) {
    for (const node of [els.frontierTable, els.frontierArithmetic, els.frontierBound, els.frontierConfirmation]) {
      node.textContent = tr(
        `Die geprüften Kapazitätsdaten konnten nicht geladen werden (${error}).`,
        `The verified capacity data could not be loaded (${error}).`
      );
      node.classList.add('load-error');
    }
  }
  async function loadFrontier() {
    try {
      const response = await fetch('data/frontier.json', { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      frontierData = await response.json();
      renderFrontier(frontierData);
    } catch (error) {
      frontierError = error.message;
      showFrontierError(frontierError);
    }
  }
  function scenario() { return study.scenarios.find(item => item.id === scenarioId) || study.scenarios[0]; }
  function factor() { return scenario().top_factors.find(item => item.factor_id === factorId) || scenario().top_factors[0]; }

  function renderBaselines() {
    els.baseline.replaceChildren();
    for (const item of study.scenarios) {
      const card = element('article', 'baseline-card');
      card.append(element('span', 'baseline-label', scenarioLabel(item)));
      card.append(element('strong', 'baseline-value', number(item.baseline.completed, 1)));
      card.append(element('span', 'baseline-unit', tr('volle Abschlüsse / 350', 'full completions / 350')));
      const detail = element('p', 'baseline-detail', tr(
        `${displayMetric(item.baseline.mean_time_to_start_or_year_end_days, 'mean_time_to_start_or_year_end_days')} Erststart-Warten · ${displayMetric(item.baseline.common_14day_start_service, 'common_14day_start_service')} binnen 14 Tagen`,
        `Wait to first start: ${displayMetric(item.baseline.mean_time_to_start_or_year_end_days, 'mean_time_to_start_or_year_end_days')} · first start within 14 days: ${displayMetric(item.baseline.common_14day_start_service, 'common_14day_start_service')}`
      ));
      card.append(detail);
      els.baseline.append(card);
    }
  }
  function renderVolumeStress() {
    const data = study.volume_stress;
    if (data?.paired_fixture_ids?.length !== 5 || data.base_groups !== 15 || data.stress_groups !== 20
        || data.group_size !== 20 || data.single_cases !== 50
        || data.base_cases !== 350 || data.stress_cases !== 450
        || !Array.isArray(data.scenarios) || data.scenarios.map(item => item.id).join(',')
          !== 'S0,S7_RECOVERY,LMS_PRELAUNCH_TEAM') {
      throw new Error(tr('Nachfrage-Stressdaten unvollständig', 'Demand stress data is incomplete'));
    }
    els.volume.replaceChildren();
    for (const item of data.scenarios) {
      const base = Number(item.base_completed);
      const stress = Number(item.stress_completed);
      if (!Number.isFinite(base) || !Number.isFinite(stress)
          || base < 0 || base > 350 || stress < 0 || stress > 450) {
        throw new Error(tr('Ungültige Nachfrage-Stresswerte', 'Invalid demand stress values'));
      }
      const row = element('div', 'volume-row');
      row.append(element('span', '', scenarioLabel(item)));
      row.append(element('strong', '', `${number(base, 1)} → ${number(stress, 1)}`));
      els.volume.append(row);
    }
    els.volume.append(element('small', '', tr('Mittlere volle Abschlüsse · 350 → 450 synthetische Fälle', 'Mean full completions · 350 → 450 synthetic cases')));
  }
  function renderScenarioOptions() {
    els.scenario.replaceChildren();
    for (const item of study.scenarios) {
      const option = element('option', '', scenarioLabel(item));
      option.value = item.id;
      els.scenario.append(option);
    }
    if (!study.scenarios.some(item => item.id === scenarioId)) scenarioId = study.scenarios[0].id;
    els.scenario.value = scenarioId;
  }
  function renderFactors() {
    els.factors.replaceChildren();
    const current = scenario();
    els.scenarioDescription.textContent = tr(
      `${scenarioLabel(current)}: vier markierte Faktoren aus 51 registrierten Grössen. Der Index gilt nur innerhalb dieser Variante.`,
      `${scenarioLabel(current)}: four highlighted factors among 51 registered inputs. The score applies only within this option.`
    );
    if (!current.top_factors.some(item => item.factor_id === factorId)) factorId = current.top_factors[0].factor_id;
    for (const item of current.top_factors) {
      const button = element('button', 'factor-option');
      button.type = 'button';
      button.setAttribute('aria-pressed', String(item.factor_id === factorId));
      button.dataset.factor = item.factor_id;
      button.append(element('span', 'factor-rank', String(item.rank).padStart(2, '0')));
      button.append(element('span', 'factor-name', factorLabel(item)));
      button.append(element('span', 'factor-score', `${tr('Index', 'Score')} ${number(item.score, 0)}`));
      button.addEventListener('click', () => {
        factorId = item.factor_id;
        renderFactors();
        renderChart();
        Array.from(els.factors.children).find(node => node.dataset.factor === factorId)?.focus();
      });
      els.factors.append(button);
    }
  }
  function renderMetricTabs() {
    els.metrics.replaceChildren();
    for (const [key, info] of Object.entries(metricMeta)) {
      const button = element('button', '', localized(info.short));
      button.type = 'button';
      button.dataset.metric = key;
      button.setAttribute('aria-pressed', String(key === metric));
      button.addEventListener('click', () => {
        metric = key;
        renderMetricTabs();
        renderChart();
        Array.from(els.metrics.children).find(node => node.dataset.metric === metric)?.focus();
      });
      els.metrics.append(button);
    }
  }
  function renderChart() {
    const current = factor();
    const info = metricMeta[metric];
    const values = current.values[metric];
    if (!values) return;
    els.title.textContent = factorLabel(current);
    els.settings.textContent = `${tr('Basis', 'Baseline')}: ${setting(current.settings.base, current.settings.unit)} · A: ${setting(current.settings.A, current.settings.unit)} · B: ${setting(current.settings.B, current.settings.unit)}`;
    els.rank.textContent = `${tr('Einflussrang', 'Influence rank')} ${current.rank}`;
    els.chart.replaceChildren();
    const numeric = [Number(values.base), Number(values.A), Number(values.B)];
    const ceiling = metric === 'completed' ? 350 : metric === 'common_14day_start_service' ? 1 : Math.max(...numeric) * 1.08;
    for (const [index, key] of ['base', 'A', 'B'].entries()) {
      const row = element('div', 'chart-row');
      const label = element('div', 'chart-label');
      label.append(element('strong', '', key === 'base' ? tr('Basis', 'Baseline') : `Test ${key}`));
      label.append(element('small', '', setting(current.settings[key], current.settings.unit)));
      const track = element('div', 'chart-track');
      const fill = element('span', `chart-fill ${key === 'base' ? 'is-base' : `is-${key.toLowerCase()}`}`);
      fill.style.width = `${Math.max(0, Math.min(100, ceiling ? numeric[index] / ceiling * 100 : 0))}%`;
      track.append(fill);
      row.append(label, track, element('strong', 'chart-value', displayMetric(numeric[index], metric)));
      els.chart.append(row);
    }
    els.chart.setAttribute('aria-label', `${factorLabel(current)}, ${localized(info.label)}: ${tr('Basis', 'baseline')} ${displayMetric(values.base, metric)}, Test A ${displayMetric(values.A, metric)}, Test B ${displayMetric(values.B, metric)}.`);
    els.insight.textContent = factorNotes[current.factor_id]
      ? localized(factorNotes[current.factor_id])
      : tr('Die beiden registrierten Testpunkte zeigen eine bedingte Modellreaktion. Zwischenwerte und Kombinationen mit anderen Annahmen wurden nicht untersucht.', 'The two registered test points show a conditional model response. Intermediate values and combinations with other assumptions were not tested.');
  }
  function renderStudy() {
    renderBaselines();
    renderVolumeStress();
    renderScenarioOptions();
    renderFactors();
    renderMetricTabs();
    renderChart();
  }
  function showStudyError(error) {
    els.baseline.textContent = tr(
      `Die geprüfte Ergebnisdatei konnte nicht geladen werden (${error}). Starte diese Vorschau über einen lokalen Webserver.`,
      `The verified study data could not be loaded (${error}). Open this preview through a local web server.`
    );
    els.baseline.classList.add('load-error');
    els.volume.textContent = tr('Die Nachfrage-Stresswerte konnten nicht geladen werden.', 'The demand stress values could not be loaded.');
    els.volume.classList.add('load-error');
  }
  async function start() {
    try {
      const response = await fetch('data/sensitivity.json', { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      study = await response.json();
      if (!Array.isArray(study.scenarios) || study.scenarios.length !== 4) throw new Error(tr('Studienformat unvollständig', 'Study format is incomplete'));
      renderStudy();
    } catch (error) {
      studyError = error.message;
      showStudyError(studyError);
    }
  }
  els.scenario.addEventListener('change', () => {
    if (!study) return;
    scenarioId = els.scenario.value;
    factorId = '';
    renderFactors();
    renderChart();
  });
  window.addEventListener('portfolio:languagechange', () => {
    if (comparisonError) showComparisonError(comparisonError);
    else if (comparisonData) renderComparison(comparisonData);
    if (frontierError) showFrontierError(frontierError);
    else if (frontierData) renderFrontier(frontierData);
    if (studyError) showStudyError(studyError);
    else if (study) renderStudy();
  });
  loadComparison();
  loadFrontier();
  start();
})();
