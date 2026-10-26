"""Immutable deterministic experiment exports; no stochastic scenario claims."""
import csv
import json
import hashlib
import platform
from dataclasses import asdict
from pathlib import Path
from . import __version__
from .inputs import verify_sources, load_topics, sha
from .config import resolve
from .demand import expand_batches
from .engine import simulate
from .metrics import summarize, assert_invariants, cohort_metrics, backlog_series, comparison_metrics
from .costs import reconcile


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False)+'\n', encoding='utf-8')


def table(path, rows):
    if not rows:
        path.write_text('', encoding='utf-8')
        return
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v) if isinstance(v,(list,tuple,dict)) else v for k,v in row.items()})


def run(root, destination, full_workflow=False):
    hashes = verify_sources(root)
    topics = load_topics(root/'data/processed/topic_catalog.csv')
    controls = json.loads((root/'config/prototype_controls.json').read_text())
    source_values = json.loads((root/'config/source_values.json').read_text())
    fixture_path = root/'config'/('workflow_fixture.json' if full_workflow else 'deterministic_fixture.json')
    fixture = json.loads(fixture_path.read_text())
    config = resolve(controls, source_values, topics, full_workflow)
    requests = expand_batches(fixture)
    return execute(root,destination,config,topics,requests,fixture,controls,source_values,hashes,
                   dict(fixture_source_hash=sha(fixture_path)))


def execute(root,destination,config,topics,requests,fixture,controls,source_values,hashes,metadata):
    full_workflow = config.workflow is not None
    code_root = Path(__file__).resolve().parents[1]
    code = {f'src/{p.relative_to(code_root)}':sha(p) for p in sorted(code_root.rglob('*.py'))}
    result = simulate(requests, topics, config)
    assert_invariants(result, topics, config)
    metrics = summarize(result, topics)
    metrics['cohorts'] = cohort_metrics(result,topics)
    if 'comparison_ageing_limit' in metadata:
        metrics['common_comparison'] = comparison_metrics(result,topics,config.max_wait,metadata['comparison_ageing_limit'])
    metrics['urgency_reviews'] = sum(e['type']=='urgency_review' for e in result.events)
    metrics['urgency_individual_releases'] = sum(e['type']=='urgency_review' and e['urgent'] for e in result.events)
    costs = reconcile(result, config.workflow)
    if costs is not None:
        metrics['costs'] = costs['totals']
        metrics['lms_portfolio_cost_chf'] = sum(i['net_chf'] for i in costs['items'] if not i['session_id'])
    if code != {f'src/{p.relative_to(code_root)}':sha(p) for p in sorted(code_root.rglob('*.py'))}:
        raise RuntimeError('Engine sources changed during run; discard and rerun')
    # Refuse replacement even when the existing directory is empty.
    destination.mkdir(parents=True, exist_ok=False)
    write_json(destination/'resolved_config.json', dict(runtime=config.resolved(), controls=controls, source_values=source_values))
    write_json(destination/'demand_fixture.json', fixture)
    write_json(destination/'topics.json', {k:asdict(v) for k,v in topics.items()})
    write_json(destination/'events.json', result.events)
    write_json(destination/'breaches.json', result.breaches)
    write_json(destination/'metrics.json', metrics)
    table(destination/'backlog_series.csv',backlog_series(result,topics))
    write_json(destination/'diagnostics.json', dict(invariants='passed', costs='accrued_and_reconciled' if full_workflow else 'not_modelled', practice='individual_after_theory' if full_workflow else 'not_modelled', proof='separate_completion' if full_workflow else 'not_modelled', scheduler='greedy deadline-ordered provisional plans; not a global feasibility optimizer'))
    if costs is not None:
        write_json(destination/'costs.json', costs)
        table(destination/'cost_items.csv', costs['items'])
        table(destination/'cost_allocations.csv', costs['allocations'])
    write_json(destination/'work_items.json', [asdict(w) for w in result.work_items])
    table(destination/'phase_waits.csv', [dict(work_item_id=w.work_item_id,request_id=w.request.request_id,
          phase=w.phase,ready_at=w.ready_at,first_start=w.first_start,completed_at=w.completed_at,state=w.state,
          wait_or_open_age_minutes=(w.first_start if w.first_start is not None else result.horizon)-w.ready_at,
          attempts=w.attempt) for w in result.work_items])
    table(destination/'sessions.csv', [asdict(s) for s in result.sessions])
    table(destination/'requests.csv', [dict(**asdict(o.request), deadline_at=o.deadline_at, state=o.state,
          first_start=o.first_start, phase_completed_at=o.phase_completed_at, planned_start=o.planned_start,
          session_id=o.session_id, escalated=o.escalated,
          training_completed_at=o.training_completed_at, proof_completed_at=o.proof_completed_at,
          wait_or_open_age_minutes=(o.first_start if o.first_start is not None else result.horizon)-o.request.noticed_at if o.request.noticed_at <= result.horizon else None) for o in result.outcomes])
    try:
        public_code_root = code_root.relative_to(root.resolve()).as_posix()
    except ValueError:
        public_code_root = 'external_install'
    manifest = dict(engine_version=__version__, python=platform.python_version(), code_hashes=code,
                    engine_source_root=public_code_root,
                    engine_content_hash=hashlib.sha256(json.dumps(code,sort_keys=True).encode()).hexdigest(),
                    source_hashes=hashes, source_manifest_hash=sha(root/'SOURCE_MANIFEST.json'),
                    fixture_hash=sha(destination/'demand_fixture.json'),
                    components=['eligible_theory_grouping','hard_wait_fallback','resource_constraints'] + (['required_practice','pq_activity_workload','proof_recording','accrued_costs'] if full_workflow else []),
                    mode=fixture['mode'], replication_id='deterministic', seed_map={},
                    randomness='none; not stochastic replications',
                    run_id=str(destination.name),
                    output_hashes={p.name:sha(p) for p in sorted(destination.iterdir())})
    manifest.update(metadata)
    write_json(destination/'run_manifest.json', manifest)
    return result, metrics


def run_ist(root,destination,mode,replication=0):
    from .baseline import compose_ist
    from .demand import generate_fixture
    from .randomness import seed_map
    hashes = verify_sources(root)
    topics = load_topics(root/'data/processed/topic_catalog.csv')
    controls = json.loads((root/'config/prototype_controls.json').read_text())
    source_values = json.loads((root/'config/source_values.json').read_text())
    c = {x['input_id']:x['value'] for x in controls['controls']}
    seeds = seed_map(c['stochastic_master_seed'],replication)
    config,spec = compose_ist(controls,source_values,topics,seeds,mode)
    fixture = generate_fixture(spec,topics,seeds)
    return execute(root,destination,config,topics,expand_batches(fixture),fixture,controls,source_values,hashes,
                   dict(scenario_id='S0',replication_id=replication,seed_map=seeds,
                        demand_spec=asdict(spec),
                        components=['assumed_topic_routing','three_week_urgency_review','individual_practice',
                                    'resource_constraints','prototype_proof_workflow','accrued_costs'],
                        randomness='Identity-keyed streams v1; durations constant and random disruptions disabled',
                        inactive_streams=['duration','disruption'],
                        calibration='Source-informed prototype assumptions; not measured IST'))


def run_policies(root,destination,mode,replication=0,identities=None,control_overrides=None,experiment_metadata=None):
    from .scenarios import compose_scenario, recognize
    from .demand import generate_fixture
    from .randomness import seed_map
    identities = identities or ('S0','S1','S2','S3','S4','S5','S6','S7','S1_GROUPING_WITH_DEADLINE','DEADLINE_ONLY')
    if not identities or identities[0]!='S0' or len(set(identities))!=len(identities):
        raise ValueError('Comparisons require S0 first and unique scenario IDs')
    hashes = verify_sources(root)
    topics = load_topics(root/'data/processed/topic_catalog.csv')
    controls = json.loads((root/'config/prototype_controls.json').read_text())
    sources = json.loads((root/'config/source_values.json').read_text())
    overrides = control_overrides or {}
    known = {x['input_id'] for x in controls['controls']}
    if set(overrides)-known:
        raise ValueError('Unknown experiment control override')
    for control in controls['controls']:
        if control['input_id'] in overrides:
            control['base_value'] = control['value']
            control['value'] = overrides[control['input_id']]
            control['experiment_override'] = True
    c = {x['input_id']:x['value'] for x in controls['controls']}
    seeds = seed_map(c['stochastic_master_seed'],replication)
    recipes = [compose_scenario(identity,controls,sources,topics,seeds,mode) for identity in identities]
    spec = recipes[0][1]
    assert all(other==spec for _,other in recipes)
    fixture = generate_fixture(spec,topics,seeds)
    fixture['time_semantics'] = 'Batch noticed_at is pre-policy underlying need time; resolved requests carry recognition delay; initial stock is already noticed'
    underlying = expand_batches(fixture)
    destination.mkdir(parents=True,exist_ok=False)
    write_json(destination/'underlying_demand.json',fixture)
    fixture_hash = sha(destination/'underlying_demand.json')
    rows,run_hashes = [],{}
    for recipe,_ in recipes:
        requests = recognize(underlying,recipe.recognition_delay)
        folder = destination/recipe.scenario_id
        result,m = execute(root,folder,recipe.config,topics,requests,fixture,controls,sources,hashes,
            dict(scenario_id=recipe.scenario_id,components=list(recipe.components),replication_id=replication,seed_map=seeds,
                 parameter_diff=recipe.parameter_diff,baseline_extensions=recipe.baseline_extensions,
                 recognition_delay=recipe.recognition_delay,comparison_ageing_limit=c['priority_ageing_minutes'],
                 demand_spec=asdict(spec),inactive_streams=['duration','disruption'],
                 experiment_controls=overrides,experiment=experiment_metadata or {},
                 randomness='Common pre-generated needs; identity-keyed streams; constant durations and no random disruptions',
                 calibration='Hypothetical effects and resource assumptions, not measured savings'))
        manifest = json.loads((folder/'run_manifest.json').read_text())
        assert manifest['fixture_hash']==fixture_hash
        common = m['common_comparison']
        row = dict(scenario=recipe.scenario_id,mode=mode,replication=replication,
                   underlying_needs=sum(x['underlying_needs'] for x in m['cohorts'].values()),
                   noticed=m['arrived'],training_completed=m['training_completed'],proof_completed=m['proof_completed'],
                   priority1_completed=common['by_priority']['1']['completed'],
                   priority2_completed=common['by_priority']['2']['completed'],priority3_completed=common['by_priority']['3']['completed'],
                   common_due_needs=common['common_due_needs'],common_target_service=common['common_target_service'],
                   actual_policy_breaches=m['breach_count'],over_age_guard=common['phase_waiters_over_ageing_limit'],
                   gross_chf=m['costs']['gross_chf'],net_chf=m['costs']['net_chf'],fixture_hash=fixture_hash)
        row.update(lms_started=m['lms_started'],lms_assessments_passed=m['lms_assessments_passed'],
                   lms_instructor_fallbacks=m['lms_instructor_fallbacks'],lms_portfolio_cost_chf=m['lms_portfolio_cost_chf'],
                   trainer_work_minutes=m['trainer_total_work_minutes'],participant_minutes=m['participant_delivery_minutes'])
        row.update(priority1_backlog_request_days=common['by_priority']['1']['backlog_request_days'],
                   lower_priority_backlog_request_days=sum(common['by_priority'][str(p)]['backlog_request_days'] for p in (2,3)),
                   supervised_sessions_started=sum(s.trainer_id!='' and s.phase!='proof' and s.start<=recipe.config.horizon
                       and (s.cancelled_at is None or s.cancelled_at>s.start) for s in result.sessions),
                   priority1_clearance_minutes=m['cohorts'].get('initial',{}).get('priority1_training_clearance_minutes'))
        initial=m['cohorts'].get('initial',{})
        row['priority1_clearance_observed'] = int(initial['priority1_training_clearance_minutes'] is not None) if initial.get('priority1_training_needed',0)>0 else None
        rows.append(row)
        run_hashes[recipe.scenario_id] = sha(folder/'run_manifest.json')
    baseline = rows[0]
    for row in rows:
        for field in ('training_completed','proof_completed','priority1_completed','net_chf','common_target_service'):
            row[field+'_delta_vs_S0'] = row[field]-baseline[field] if row[field] is not None and baseline[field] is not None else None
    table(destination/'paired_differences.csv',rows)
    write_json(destination/'comparison_manifest.json',dict(fixture_hash=fixture_hash,replication=replication,mode=mode,
        scenarios=list(identities),run_manifest_hashes=run_hashes,paired_table_hash=sha(destination/'paired_differences.csv'),
        experiment_controls=overrides,experiment=experiment_metadata or {},
        limitations=['Single-replication differences, not confidence intervals','Cost totals accompany unequal completion counts',
                     'LMS suitability, equivalent assessment, support and full-cost controls are unmeasured hypotheses'],
        baseline_extensions=recipes[0][0].baseline_extensions))
    return rows
