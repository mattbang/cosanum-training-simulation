"""Source-informed annual experiments around the shared engine, never a second simulator."""
import json
import re
from dataclasses import replace
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from .annual_demand import load_profile, annual_fixture
from .domain import Resource
from .inputs import load_topics, verify_sources, sha
from .randomness import seed_map
from .scenarios import COMPONENTS, compose_scenario, recognize
from .experiments import execute, table, write_json
from .uncertainty import summarise


def theory_benchmark(fixture, sources):
    """Hand-reconcilable scope reference, not a claim about historical invoices."""
    s = {x['input_id']: x['value'] for x in sources['values']}
    annual = fixture['annual_summary']
    groups = annual['group_training_count']
    singles = annual['individual_training_count']
    size = annual['group_size']
    minutes = s['theory_standard_minutes']
    participant = (groups*size+singles)*minutes/60*s['participant_hourly_chf']
    pq = groups*s['theory_group_pq_allowance_chf']
    coach = singles*minutes/60*s['coach_hourly_chf']
    practice_count = annual['practice_required_count']
    practice_gross = practice_count*s['practice_standard_minutes']/60*(s['coach_hourly_chf']+s['participant_hourly_chf'])
    practice_credit = practice_count*s['practice_standard_minutes']/60*s['participant_hourly_chf']*s['participant_practice_credit_fraction']
    return dict(theory_participations=groups*size+singles,
                theory_participant_chf=participant, theory_pq_chf=pq, theory_coach_chf=coach,
                theory_net_chf=participant+pq+coach, practice_required_count=practice_count,
                practice_gross_chf=practice_gross, practice_credit_chf=practice_credit,
                full_cohort_net_chf=participant+pq+coach+practice_gross-practice_credit,
                interpretation='All source-required practice in this synthetic topic mix, no cancellation; fixed 15/50 theory routing reference, not actual annual expenditure')


def yearly_row(result, metrics, cfg, topics, fixture):
    """Reconcile person-topic training stock independently of session counts."""
    cohorts = metrics['cohorts']
    initial = cohorts.get('initial', {})
    ongoing = cohorts.get('ongoing', {})
    initial_n = initial.get('training_needed', 0)
    ongoing_n = ongoing.get('training_needed', 0)
    initial_done = initial.get('training_completed', 0)
    ongoing_done = ongoing.get('training_completed', 0)
    p1_initial = initial.get('priority1_training_needed', 0)
    p1_done = initial.get('priority1_training_completed', 0)
    finished = metrics['training_completed']
    assert initial_n+ongoing_n == len(result.outcomes)
    assert finished == initial_done+ongoing_done
    uncompleted = initial_n+ongoing_n-finished
    assert uncompleted == sum(o.training_completed_at is None for o in result.outcomes)
    available = sum(end-start for r in cfg.resources if r.role=='trainer' for start,end in r.intervals)
    occupied = metrics['trainer_total_work_minutes']
    assert occupied <= available+1e-7
    completed_sessions = [s for s in result.sessions if s.end<=result.horizon and s.cancelled_at is None and s.phase!='proof']
    theory = [s for s in completed_sessions if s.phase=='theory']
    groups = [s for s in theory if len(s.request_ids)>1]
    practice = [s for s in completed_sessions if s.phase=='practice']
    common = metrics['common_comparison']
    clear = initial.get('priority1_training_clearance_minutes')
    outcomes = {o.request.request_id:o for o in result.outcomes}
    required_practice = [o for o in result.outcomes if o.request.case_kind=='training_needed'
                         and topics[o.request.topic_id].practice_required]
    # Count observed readiness, not a provisional future prerequisite timestamp.
    ready_practice = [w for w in result.work_items if w.phase=='practice'
                      and outcomes[w.request.request_id].phase_completed_at is not None
                      and w.ready_at<=result.horizon]
    practice_wait = sum(max(0,min(w.first_start if w.first_start is not None else result.horizon,
                                result.horizon)-w.ready_at) for w in ready_practice)
    pipeline = dict(
        practice_required_needs=len(required_practice),
        practice_completed=sum(o.training_completed_at is not None for o in required_practice),
        theory_complete_practice_unfinished=sum(o.phase_completed_at is not None and o.training_completed_at is None
                                               for o in required_practice),
        practice_started=sum(w.first_start is not None for w in ready_practice),
        practice_ready_censored=sum(w.first_start is None for w in ready_practice),
        practice_waiting_request_days=practice_wait/1440,
        joined_practice_reservations=sum(s.reason=='joined_follow_up' for s in result.sessions),
        joined_bundles=sum(e['type']=='joined_bundle_reserved' for e in result.events),
        joined_planning_failures=sum(e['type']=='joined_follow_up_escalation' for e in result.events))
    return dict(mode=fixture['mode'], horizon_days=result.horizon/1440,
        underlying_needs=initial_n+ongoing_n, annual_new_needs=ongoing_n,
        initial_stock=initial_n, training_completed=finished,
        ongoing_completed=ongoing_done, ongoing_remaining=ongoing_n-ongoing_done,
        initial_completed=initial_done, initial_remaining=initial_n-initial_done,
        year_end_training_stock=uncompleted,
        initial_priority1_stock=p1_initial, initial_priority1_completed=p1_done,
        initial_priority1_remaining=p1_initial-p1_done,
        ongoing_priority1_completed=ongoing.get('priority1_training_completed',0),
        priority1_completed=common['by_priority']['1']['completed'],
        priority2_completed=common['by_priority']['2']['completed'],
        priority3_completed=common['by_priority']['3']['completed'],
        lower_priority_backlog_request_days=sum(common['by_priority'][str(p)]['backlog_request_days'] for p in (2,3)),
        theory_sessions=len(theory), theory_group_sessions=len(groups),
        theory_individual_sessions=len(theory)-len(groups),
        theory_participations=sum(len(s.request_ids) for s in theory),
        practice_sessions=len(practice), total_training_sessions=len(completed_sessions),
        first_starts=sum(o.first_start is not None for o in result.outcomes),
        synthetic_people_represented=len({o.request.person_id for o in result.outcomes}),
        trainer_available_hours=available/60, trainer_used_hours=occupied/60,
        trainer_utilisation=occupied/available if available else None,
        gross_chf=metrics['costs']['gross_chf'], credit_chf=metrics['costs']['credit_chf'],
        net_chf=metrics['costs']['net_chf'],
        common_due_needs=common['common_due_needs'],common_target_service=common['common_target_service'],
        actual_policy_breaches=metrics['breach_count'], proof_completed=metrics['proof_completed'],
        priority1_clearance_minutes=clear,
        priority1_clearance_observed=int(clear is not None) if p1_initial else None,
        all_training_complete=int(uncompleted==0),
        full_cohort_reconciled=int(uncompleted==0 and metrics['proof_completed']==initial_n+ongoing_n and
                                  all((getattr(s,'work_end',s.end) or s.end)<=result.horizon for s in result.sessions)),
        cohort_completion_days=max((o.training_completed_at for o in result.outcomes),default=None)/1440 if result.outcomes and uncompleted==0 else None,
        **pipeline)


def calendars(profile, topics, people, horizon):
    v = profile.values
    def intervals(weekdays):
        return tuple((day*1440+v['resource_calendar_start_minute'],min(day*1440+v['resource_calendar_end_minute'],horizon))
                     for day in range(int(horizon)//1440+1) if day%7 in weekdays and day*1440+v['resource_calendar_start_minute']<horizon)
    calendar = intervals(v['resource_calendar_weekdays'])
    # Availability is an independent assumption; work consumed by IST is not its denominator.
    resources = [Resource('annual-pooled-trainer','trainer',tuple(sorted(topics)),calendar),
                 Resource('annual-room','room',tuple(sorted(topics)),calendar)]
    participants = intervals(v['participant_calendar_weekdays'])
    resources.extend(Resource(person,'participant',tuple(sorted(topics)),participants) for person in sorted(people))
    return tuple(resources)


def _frozen(root, plan_path):
    paths = [root/'config/annual_profile.json',root/'config/prototype_controls.json',root/'config/source_values.json',
             root/'config/scenario_registry.json',root/'pyproject.toml',
             root/'SOURCE_MANIFEST.json',root/'data/processed/topic_catalog.csv',plan_path]
    paths += sorted((root/'src').rglob('*.py'))
    return {str(p.relative_to(root)):sha(p) for p in paths}


def run_annual_comparison(root, destination, case, replication, plan_hash):
    topics = load_topics(root/'data/processed/topic_catalog.csv')
    profile = load_profile(root/'config/annual_profile.json').with_overrides(case.get('profile_overrides',{}))
    controls = json.loads((root/'config/prototype_controls.json').read_text())
    sources = json.loads((root/'config/source_values.json').read_text())
    c = {x['input_id']:x['value'] for x in controls['controls']}
    seeds = seed_map(c['stochastic_master_seed'],replication)
    fixture, underlying = annual_fixture(topics,seeds,profile,include_backlog=case['include_backlog'],
                                         include_ongoing=case.get('include_ongoing',True))
    horizon = (profile.values['horizon_days']+case.get('drain_days',0))*1440
    resources = calendars(profile,topics,{r.person_id for r in underlying},horizon)
    destination.mkdir(parents=True,exist_ok=False)
    write_json(destination/'underlying_demand.json',fixture)
    write_json(destination/'annual_profile.json',profile.resolved())
    write_json(destination/'scope_reference.json',theory_benchmark(fixture,sources))
    fixture_hash = sha(destination/'underlying_demand.json')
    resource_hash = sha(destination/'annual_profile.json')
    rows, run_hashes = [], {}
    for identity in case['scenarios']:
        recipe, _ = compose_scenario(identity,controls,sources,topics,seeds,'ongoing_stochastic_demand',
                                     recovery_aged_every=profile.values['recovery_aged_every'])
        baseline_delivery = 'grouping' not in recipe.components
        cfg = replace(recipe.config,horizon=horizon,resources=resources,capacity=profile.values['group_size'],
                      target=profile.values['group_size'],use_baseline_delivery=baseline_delivery,
                      recovery_aged_every=profile.values['recovery_aged_every']
                      if recipe.config.phase_allocation!='legacy' else None).validate(topics)
        requests = recognize(underlying,recipe.recognition_delay)
        result, metrics = execute(root,destination/identity,cfg,topics,requests,fixture,controls,sources,verify_sources(root),
            dict(scenario_id=identity,components=list(recipe.components),replication_id=replication,seed_map=seeds,
                 recognition_delay=recipe.recognition_delay,comparison_ageing_limit=c['priority_ageing_minutes'],
                 annual_profile=profile.resolved(), annual_profile_hash=resource_hash,
                 annual_runtime_overrides=dict(horizon_days=horizon/1440,group_capacity=profile.values['group_size'],
                     group_target=profile.values['group_size'],baseline_delivery_hints=baseline_delivery,
                     resource_basis='one cross-qualified pooled trainer and one room; explicit independent calendar budget'),
                 parameter_diff=recipe.parameter_diff, experiment=dict(case_id=case['case_id'],plan_hash=plan_hash),
                 calibration='Annual interpretation of Q6 is assumed; topic mix and pooled training availability are synthetic',
                 randomness='Fixed annual counts; identity-keyed arrival times, topics and synthetic people; constant durations; no disruptions'))
        row = yearly_row(result,metrics,cfg,topics,fixture)
        row.update(case_id=case['case_id'],replication=replication,scenario=identity,fixture_hash=fixture_hash,
                   cost_boundary='fixed annual cohort plus no-arrival drain' if case.get('drain_days',0) else 'work consumed within first365days')
        rows.append(row)
        run_hashes[identity] = sha(destination/identity/'run_manifest.json')
    assert all(row['underlying_needs']==rows[0]['underlying_needs'] and row['common_due_needs']==rows[0]['common_due_needs'] for row in rows)
    table(destination/'paired_results.csv',rows)
    write_json(destination/'comparison_manifest.json',dict(fixture_hash=fixture_hash,run_manifest_hashes=run_hashes,
        annual_profile_hash=resource_hash,rows_hash=sha(destination/'paired_results.csv'),
        scope_reference_hash=sha(destination/'scope_reference.json'),replication=replication,case=case,plan_hash=plan_hash))
    return rows


def validate_plan(plan):
    if type(plan.get('minimum_n')) is not int or plan['minimum_n']<2:
        raise ValueError('Invalid minimum replication floor')
    ids = set()
    for case in plan['cases']:
        if not isinstance(case['case_id'],str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,80}',case['case_id']) or case['case_id'] in ids:
            raise ValueError('Unique annual case IDs required')
        ids.add(case['case_id'])
        if type(case['include_backlog']) is not bool or type(case.get('drain_days',0)) is not int or case.get('drain_days',0)<0:
            raise ValueError('Invalid annual backlog/drain scope')
        if type(case.get('include_ongoing',True)) is not bool or not (case['include_backlog'] or case.get('include_ongoing',True)):
            raise ValueError('Invalid annual ongoing/frozen demand scope')
        if not case['scenarios'] or case['scenarios'][0]!='S0' or len(set(case['scenarios']))!=len(case['scenarios']):
            raise ValueError('Unique scenarios with S0 first required')
        if any(x not in COMPONENTS or 'learning' in COMPONENTS[x] for x in case['scenarios']):
            raise ValueError('Unsupported annual scenario')
        if not case['replications'] or len(set(case['replications']))!=len(case['replications']) or any(type(x) is not int or x<0 for x in case['replications']):
            raise ValueError('Invalid annual replication identities')
    contrasts = plan.get('contrasts',[])
    if not isinstance(contrasts,list):
        raise ValueError('Annual contrasts must be a list')
    seen = set()
    for contrast in contrasts:
        if not isinstance(contrast,dict) or set(contrast)!={'scenario','reference'}:
            raise ValueError('Contrast requires explicit scenario and reference')
        pair = (contrast['scenario'],contrast['reference'])
        if pair[0]==pair[1] or pair in seen or any(x not in COMPONENTS for x in pair):
            raise ValueError('Invalid or duplicate annual contrast')
        if not any(all(x in case['scenarios'] for x in pair) for case in plan['cases']):
            raise ValueError('Annual contrast has no paired case')
        seen.add(pair)
    return plan


def run_annual_study(root, destination, plan_path, workers=1):
    plan = validate_plan(json.loads(plan_path.read_text()))
    frozen = _frozen(root,plan_path)
    source_hashes = verify_sources(root)
    destination.mkdir(parents=True,exist_ok=False)
    write_json(destination/'plan.json',plan)
    plan_hash = sha(destination/'plan.json')
    tasks = [(root,destination/case['case_id']/f'rep-{rep}',case,rep,plan_hash) for case in plan['cases'] for rep in case['replications']]
    rows = []
    if workers>1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(run_annual_comparison,*task):task for task in tasks}
            for future in as_completed(futures):
                batch = future.result(); rows.extend(batch)
                print(f"Completed {futures[future][2]['case_id']} replication {futures[future][3]}",flush=True)
    else:
        for task in tasks:
            rows.extend(run_annual_comparison(*task))
            print(f"Completed {task[2]['case_id']} replication {task[3]}",flush=True)
    if frozen!=_frozen(root,plan_path) or source_hashes!=verify_sources(root):
        raise RuntimeError('Annual inputs or code changed during study')
    rows.sort(key=lambda r:(r['case_id'],r['replication'],r['scenario']))
    absolute,paired,clearance = summarise(rows,plan['metrics'],plan['precision_targets'],plan['minimum_n'],plan.get('contrasts'))
    table(destination/'replications.csv',rows)
    table(destination/'absolute_intervals.csv',absolute)
    table(destination/'paired_intervals.csv',paired)
    table(destination/'clearance.csv',clearance)
    comparisons = {str(path.parent.relative_to(destination)):sha(path) for path in sorted(destination.rglob('comparison_manifest.json'))}
    write_json(destination/'study_manifest.json',dict(plan_hash=plan_hash,runs=len(rows),comparisons=len(tasks),
        source_hashes=source_hashes,frozen_input_and_code_hashes=frozen,comparison_manifest_hashes=comparisons,
        output_hashes={name:sha(destination/name) for name in ('plan.json','replications.csv','absolute_intervals.csv','paired_intervals.csv','clearance.csv')},
        limitations=['Annual Q6 interpretation is an assumption, not historical measurement',
                    'Participations are person-topic cycles, not unique employees',
                    'Constant durations and synthetic topic mix; no employee-level source reconstruction',
                    'Pooled trainer calendar is assumed, not Daniel availability',
                    'First-year consumed work cost differs from cost to finish the fixed cohort',
                    'IT, implementation, materials and room cash cost remain unknown and excluded',
                    'Pointwise approximate intervals describe simulation variation, not uncertainty in source assumptions',
                    'Five-replication sensitivity screens remain preliminary']))
    return rows
