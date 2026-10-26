"""Validated dashboard controls and arbitrary policy composition on the shared engine."""
import csv
import json
import math
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from . import __version__

from cosanum_sim import __version__ as ENGINE_VERSION
from cosanum_sim.operating import load_operating, configure_operating
from cosanum_sim.annual import calendars, yearly_row
from cosanum_sim.annual_demand import load_profile, annual_fixture
from cosanum_sim.experiments import execute, write_json, table
from cosanum_sim.inputs import load_topics, verify_sources, sha
from cosanum_sim.randomness import seed_map
from cosanum_sim.scenarios import compose_scenario, recognize, diff
from cosanum_sim.uncertainty import summarise

MODES = {
    'annual_same_volume': (False, True, 0),
    'annual_backlog': (True, True, 0),
    'frozen_backlog': (True, False, 0),
    'same_cohort_drain': (False, True, 365),
}
METRICS = ('training_completed', 'ongoing_completed', 'initial_completed',
           'initial_priority1_completed', 'initial_priority1_remaining',
           'year_end_training_stock', 'common_target_service', 'net_chf',
           'trainer_used_hours', 'theory_complete_practice_unfinished',
           'practice_waiting_request_days', 'lower_priority_backlog_request_days',
           'actual_policy_breaches', 'theory_group_sessions', 'theory_individual_sessions',
           'practice_sessions', 'joined_planning_failures')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def bootstrap(root, assets):
    profile = load_profile(root / 'config/annual_profile.json')
    c = {x['input_id']: x['value'] for x in read(root / 'config/prototype_controls.json')['controls']}
    s = {x['input_id']: x['value'] for x in read(root / 'config/source_values.json')['values']}
    v = profile.values
    operating=load_operating(root/'config/operating_configuration.json');o={r['input_id']:r['value'] for r in operating['inputs']}
    spec = read(assets / 'controls.json')
    spec['defaults'] = dict(demand=v['group_training_count'] * v['group_size'] + v['individual_training_count'],
                           days=v['resource_days_per_week'], practice=s['practice_standard_minutes'] / 60,
                           group=o['preferred_group'], wait=c['max_wait_minutes'] / 1440)
    spec['engine_version'] = ENGINE_VERSION
    spec['option_defaults']=dict(actor=o['default_lms_actor'],minimum_working=o['minimum_logistics_working'],pq_practice_qualified=o['pq_practice_qualified'],practice_coaches=o['practice_coach_count'],setup_chf=c['lms_implementation_chf'],course_chf=c['lms_content_chf_per_topic'],care_chf_per_day=c['lms_maintenance_chf_per_day'])
    spec['dashboard_version'] = __version__
    return spec


def validate(payload, spec):
    if not isinstance(payload, dict) or set(payload) != {'values', 'solutions', 'mode', 'seed', 'replications', 'options'}:
        raise ValueError('Eingaben unvollständig oder unbekannt.')
    values = payload['values']
    if not isinstance(values, dict) or set(values) != set(spec['defaults']):
        raise ValueError('Fünf gültige Initialisierungswerte erforderlich.')
    for slider in spec['sliders']:
        k = slider['key']; v = values[k]
        if (isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v)
                or not slider['min'] <= v <= slider['max']
                or abs((v-slider['min'])/slider['step']-round((v-slider['min'])/slider['step'])) > 1e-7):
            raise ValueError(slider['label'] + ': Wert ausserhalb der erlaubten Spanne oder Schrittweite.')
    parts = payload['solutions']
    if not isinstance(parts, list) or len(parts) != 8 or any(type(x) is not bool for x in parts):
        raise ValueError('Acht eindeutige Massnahmenauswahlen erforderlich.')
    options=payload['options']
    if not isinstance(options,dict) or set(options)!=set(spec['option_defaults']):raise ValueError('LMS-/Besetzungsoptionen unvollständig.')
    if options['actor'] not in ('prelaunch_team','daniel_calendar'):raise ValueError('Unbekannte Materialvorbereitung.')
    if type(options['minimum_working']) is not int or not 0<=options['minimum_working']<45:raise ValueError('Mindestbesetzung0–44 erforderlich.')
    if parts[0] and values['group']>45-options['minimum_working']:raise ValueError('Gruppenziel über verfügbarer Freistellung: Mindestbesetzung bewusst anpassen.')
    if type(options['pq_practice_qualified']) is not bool or type(options['practice_coaches']) is not int or options['practice_coaches'] not in (1,2):raise ValueError('Trainerqualifikation/Kapazität ungültig.')
    for k in ('setup_chf','course_chf','care_chf_per_day'):
        val=options[k]
        if isinstance(val,bool) or not isinstance(val,(int,float)) or not math.isfinite(val) or not 0<=val<=100000:raise ValueError('Ungültiges LMS-Budget: '+k)
    if parts[5] and not (parts[0] and parts[4]):
        raise ValueError('Recovery benötigt S1 mit Startfrist und S5 Priorisierung.')
    if not isinstance(payload['mode'],str) or payload['mode'] not in MODES:
        raise ValueError('Unbekannter Untersuchungsmodus.')
    if type(payload['seed']) is not int or not 0 <= payload['seed'] <= spec['maximum_seed']:
        raise ValueError('Seed muss eine ganze Zahl in der angezeigten Spanne sein.')
    if type(payload['replications']) is not int or payload['replications'] not in spec['replication_choices']:
        raise ValueError('1, 5 oder 20 vorab gewählte Paare erforderlich.')
    return deepcopy(payload)


def scenario(parts):
    if parts==[False]*8:return 'S0'
    if all(parts[:6]) and not parts[6] and parts[7]:return 'LMS_DANIEL_OR_TEAM'
    if all(parts[:6]) and not parts[7]:return 'S7_RECOVERY_JOINED' if parts[6] else 'S7_RECOVERY'
    return 'CUSTOM'


def prepare(root, payload, spec, replication):
    topics = load_topics(root/'data/processed/topic_catalog.csv')
    profile = load_profile(root/'config/annual_profile.json')
    controls = read(root/'config/prototype_controls.json'); sources = read(root/'config/source_values.json')
    p, v = profile.values, payload['values']
    n = int(v['demand'])
    # Preserve the base count exactly; do not confuse an output group target with arrival batch size.
    groups = math.floor(n * p['group_training_count'] / spec['defaults']['demand'])
    weekdays = spec['weekday_patterns'][str(int(v['days']))]
    overrides = dict(group_training_count=groups, individual_training_count=n-groups*p['group_size'],
                     resource_days_per_week=int(v['days']), resource_calendar_weekdays=weekdays)
    profile = profile.with_overrides(overrides)
    for item in sources['values']:
        if item['input_id']=='practice_standard_minutes' and item['value'] != v['practice']*60:
            item.update(base_value=item['value'], value=v['practice']*60, source_status='assumption',
                        value_kind='dashboard_sensitivity', rationale='Explizite Praxisdauer-Sensitivität; Originalwert bleibt als base_value erhalten.')
    profile.bound_source_values['practice_minutes'] = next(deepcopy(x) for x in sources['values'] if x['input_id']=='practice_standard_minutes')
    for item in controls['controls']:
        if item['input_id']=='max_wait_minutes':
            item.update(base_value=item['value'], value=v['wait']*1440, source_status='assumption',
                        rationale='Gemeinsame Erststart-Vergleichsfrist; nur SOLL aktiviert die harte Policy-Frist.')
    for item in controls['controls']:
        binding={'lms_implementation_chf':'setup_chf','lms_content_chf_per_topic':'course_chf','lms_maintenance_chf_per_day':'care_chf_per_day'}.get(item['input_id'])
        if binding:item.update(base_value=item['value'],value=payload['options'][binding],source_status='assumption',rationale='Explizites Dashboard-Budget, ohne doppelte Arbeitskosten.')
    c = {x['input_id']:x['value'] for x in controls['controls']}
    seeds = seed_map(c['stochastic_master_seed'], replication)
    backlog, ongoing, drain = MODES[payload['mode']]
    fixture, underlying = annual_fixture(topics, seeds, profile, backlog, ongoing)
    horizon = (profile.values['horizon_days']+drain)*1440
    resources = calendars(profile, topics, {r.person_id for r in underlying}, horizon)
    mode = 'ongoing_stochastic_demand'
    aged = profile.values['recovery_aged_every']
    base, _ = compose_scenario('S0', controls, sources, topics, seeds, mode, aged)
    cfg, recognition = base.config, base.recognition_delay
    parts = payload['solutions']; names = []
    for index, identity in enumerate(('S1_GROUPING_WITH_DEADLINE','S2','S3','S4','S5')):
        if not parts[index]: continue
        recipe, _ = compose_scenario(identity, controls, sources, topics, seeds, mode, aged)
        if index==0: cfg=replace(cfg,group_preferred=recipe.config.group_preferred,grouping_topics=recipe.config.grouping_topics,
                                  deadline_enabled=recipe.config.deadline_enabled,urgency_review=recipe.config.urgency_review)
        elif index==1: recognition=recipe.recognition_delay
        elif index==2: cfg=replace(cfg,workflow=replace(cfg.workflow,proof_delay=recipe.config.workflow.proof_delay,
                                                     proof_recovery_duration=recipe.config.workflow.proof_recovery_duration))
        elif index==3: cfg=replace(cfg,planning_delay=recipe.config.planning_delay)
        elif index==4: cfg=replace(cfg,priority=recipe.config.priority)
        names.extend(recipe.components)
    if parts[5]:
        recipe, _ = compose_scenario('S7_RECOVERY', controls, sources, topics, seeds, mode, aged)
        cfg=replace(cfg,phase_allocation=recipe.config.phase_allocation,recovery_aged_every=aged);names.append('recovery')
    if parts[6]: cfg=replace(cfg,joined_scheduling=True);names.append('joined_scheduling')
    operating=load_operating(root/'config/operating_configuration.json')
    op={r['input_id']:r['value'] for r in operating['inputs']}
    op.update(annual_cases=n,training_days=int(v['days']),preferred_group=int(v['group']) if parts[0] else min(p['group_size'],45-payload['options']['minimum_working']),
              minimum_logistics_working=payload['options']['minimum_working'],pq_practice_qualified=payload['options']['pq_practice_qualified'],practice_coach_count=payload['options']['practice_coaches'])
    shared=dict(horizon=horizon)
    base_cfg,_,_=configure_operating(replace(base.config,**shared,use_baseline_delivery=True),topics,profile,{r.person_id for r in underlying},op,seeds,controls,sources,ist=True,planning_improved=False)
    cfg,learning,workload=configure_operating(replace(cfg,**shared,use_baseline_delivery=not parts[0]),topics,profile,{r.person_id for r in underlying},op,seeds,controls,sources,
                    ist=not parts[0],planning_improved=parts[3],learning=parts[7],actor=payload['options']['actor'])
    if parts[7]:names.append('independent_lms')
    return dict(topics=topics,profile=profile,controls=controls,sources=sources,seeds=seeds,fixture=fixture,
                underlying=underlying,baseline=base_cfg,chosen=cfg,recognition=recognition,
                baseline_recognition=base.recognition_delay,components=list(dict.fromkeys(names)),
                control_map=c,identity=scenario(parts),workload=workload,learning=learning,operating=op)


def run_experiment(root, assets, destination, payload, progress=lambda *args: None):
    spec=bootstrap(root,assets); payload=validate(payload,spec)
    hashes=verify_sources(root)
    prepared=prepare(root,payload,spec,payload['seed'])  # validate all before creating output
    destination.mkdir(parents=True,exist_ok=False)
    write_json(destination/'settings.json',payload)
    write_json(destination/'dashboard_provenance.json',dict(dashboard_version=__version__,engine_version=ENGINE_VERSION,
        source_status='assumption',synthetic=True,controls=spec,
        scope='New exploratory experiments; not extra replications of the completed annual study',
        input_hashes=hashes,engine_snapshot_manifest=sha(root/'HANDOVER_MANIFEST.json')))
    rows=[]; sample=[]
    total=payload['replications']*(1 if prepared['identity']=='S0' else 2)
    done=0
    for i in range(payload['replications']):
        rep=payload['seed']+i
        x=prepared if i==0 else prepare(root,payload,spec,rep)
        parent=destination/f'rep-{rep}';parent.mkdir()
        write_json(parent/'underlying_demand.json',x['fixture'])
        write_json(parent/'annual_profile.json',x['profile'].resolved())
        fixture_hash=sha(parent/'underlying_demand.json')
        variants=[('S0',x['baseline'],x['baseline_recognition'],[])]
        if x['identity']!='S0': variants.append((x['identity'],x['chosen'],x['recognition'],x['components']))
        for identity,cfg,delay,components in variants:
            progress(done,total,f'Paar {i+1}/{payload["replications"]} · {identity}')
            result,metrics=execute(root,parent/identity,cfg,x['topics'],recognize(x['underlying'],delay),
                x['fixture'],x['controls'],x['sources'],hashes,dict(scenario_id=identity,components=components,
                replication_id=rep,seed_map=x['seeds'],recognition_delay=delay,
                comparison_ageing_limit=x['control_map']['priority_ageing_minutes'],
                annual_profile=x['profile'].resolved(),dashboard_settings=payload,
                parameter_diff=diff(x['baseline'].resolved(),cfg.resolved()),
                calibration='Source-informed synthetic prototype; dashboard overrides are assumptions',
                randomness='Paired fixed annual count; identity-keyed streams, constant durations, no random disruptions'))
            row=yearly_row(result,metrics,cfg,x['topics'],x['fixture'])
            work=x['workload'] if identity!='S0' else None
            if work:write_json(parent/(identity+'_author_schedule.json'),work)
            row.update(trainer_lms_hours=work['trainer_overhead_hours'] if work else 0,lms_internal_hours=work['internal_hours'] if work else 0,lms_portfolio_chf=metrics.get('lms_portfolio_cost_chf',0),trainer_total_hours=row['trainer_used_hours']+(work['trainer_overhead_hours'] if work else 0),lms_attempts=metrics['lms_started'],lms_fallbacks=metrics['lms_instructor_fallbacks'])
            row.update(case_id=payload['mode'],scenario=identity,replication=rep,fixture_hash=fixture_hash)
            rows.append(row)
            if i==0:
                sessions=[dict(session_id=s.session_id,phase=s.phase,topic_id=s.topic_id,start=s.start,end=s.end,
                               size=len(s.request_ids),reason=s.reason) for s in sorted(result.sessions,key=lambda s:(s.start,s.session_id))[:12]]
                sample.append(dict(scenario=identity,sessions=sessions,events=result.events[:12],
                                   diagnostics=read(parent/identity/'diagnostics.json'),
                                   ledger=metrics['costs'],resolved=dict(group_preferred=cfg.group_preferred,
                                   target=cfg.target,threshold=cfg.threshold,capacity=cfg.capacity,
                                   start_deadline_enabled=cfg.deadline_enabled,urgency_review=cfg.resolved()['urgency_review'],
                                   recognition_minutes=delay,planning_minutes=cfg.planning_delay,
                                   practice_minutes=cfg.workflow.practice_duration,proof_minutes=cfg.workflow.proof_delay,
                                   phase_allocation=cfg.phase_allocation,joined_scheduling=cfg.joined_scheduling,coordination_minutes=cfg.workflow.coordination_minutes,learning_enabled=cfg.workflow.learning is not None,minimum_logistics_working=x['operating']['minimum_logistics_working'],learning_portfolio=x['learning'] if cfg.workflow.learning else None)))
            done+=1;progress(done,total,f'{done}/{total} Läufe geprüft')
    targets=read(root/'config/annual_joined_study_plan.json').get('precision_targets',{})
    absolute,paired,clearance=summarise(rows,METRICS,targets,20)
    for entry in absolute+paired:
        if entry['n']<20:entry.update(lower=None,upper=None,half_width=None,precision_status='descriptive_only')
    table(destination/'replications.csv',rows);table(destination/'paired_intervals.csv',paired)
    result=dict(settings=payload,engine_version=ENGINE_VERSION,identity=prepared['identity'],rows=rows,
                absolute=absolute,paired=paired,clearance=clearance,samples=sample,
                verification=dict(invariants='passed',costs='gross_minus_credit_equals_net',
                common_demand=True,pairs=payload['replications']),
                interpretation='Einzellauf/Exploration oder feste Paare; keine Ergänzung der gespeicherten Jahresstudie.')
    write_json(destination/'result.json',result)
    write_json(destination/'experiment_manifest.json',dict(files={str(p.relative_to(destination)):sha(p)
        for p in sorted(destination.rglob('*')) if p.is_file()}))
    return result
