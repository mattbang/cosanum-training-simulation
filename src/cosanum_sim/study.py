"""Validated fixed experiment plans, immutable runs and independently paired cells."""
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from .experiments import run_policies, write_json, table
from .inputs import sha
from .scenarios import COMPONENTS
from .uncertainty import summarise, revalue_overhead

METRICS = {'training_completed','proof_completed','priority1_completed','net_chf','gross_chf',
           'common_target_service','actual_policy_breaches','priority1_backlog_request_days',
           'lower_priority_backlog_request_days','trainer_work_minutes','participant_minutes',
           'lms_assessments_passed','lms_instructor_fallbacks'}


def validate_plan(plan, controls):
    if plan['confidence_level']!=.95 or plan['stopping_rule']!='fixed_replications_no_optional_stopping':
        raise ValueError('Only fixed-n pointwise 95% intervals implemented')
    if type(plan['minimum_precision_replications']) is not int or plan['minimum_precision_replications']<2:
        raise ValueError('Invalid minimum precision count')
    allowed={x['input_id'] for x in controls['controls']}
    if not plan['metrics'] or len(set(plan['metrics']))!=len(plan['metrics']) or set(plan['metrics'])-METRICS:
        raise ValueError('Invalid metric list')
    if not plan['cases'] or 'net_chf' not in plan['precision_targets']:
        raise ValueError('Study cases and cost precision target required')
    revalue_overhead([],plan['cost_scope_sensitivity']['chf_per_supervised_session'])
    from .uncertainty import interval
    for metric,target in plan['precision_targets'].items():
        if metric not in plan['metrics']: raise ValueError('Target metric not exported')
        interval([],target,plan['minimum_precision_replications'])
    ids=set()
    for case in plan['cases']:
        identity=case['case_id']
        if not identity or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_' for c in identity) or identity in ids:
            raise ValueError('Invalid/duplicate case ID')
        ids.add(identity)
        scenarios=case['scenarios']
        if not scenarios or scenarios[0]!='S0' or len(set(scenarios))!=len(scenarios) or set(scenarios)-COMPONENTS.keys():
            raise ValueError('Invalid paired scenarios')
        reps=case['replication_ids']
        if not reps or len(set(reps))!=len(reps) or any(type(r) is not int or r<0 for r in reps):
            raise ValueError('Invalid fixed replication IDs')
        if case['mode'] not in ('initial_backlog_clearance','ongoing_stochastic_demand'):
            raise ValueError('Unknown demand mode')
        if set(case['overrides'])-allowed or 'stochastic_master_seed' in case['overrides']:
            raise ValueError('Unknown override or changed shared master seed')
        if not case['rationale']: raise ValueError('Sensitivity rationale required')
    return plan


def _job(root,destination,case,rep,plan_hash):
    folder=destination/case['case_id']/f'{rep:03d}'
    rows=run_policies(root,folder,case['mode'],rep,tuple(case['scenarios']),case['overrides'],
                      dict(case_id=case['case_id'],plan_hash=plan_hash,rationale=case['rationale']))
    return [dict(case_id=case['case_id'],**r) for r in rows],str(folder.relative_to(destination)),sha(folder/'comparison_manifest.json')


def run_study(root,destination,plan_path,workers=1,progress=None):
    if type(workers) is not int or workers<1: raise ValueError('Positive worker count required')
    plan=validate_plan(json.loads(plan_path.read_text()),json.loads((root/'config/prototype_controls.json').read_text()))
    protected=list((root/'src').rglob('*.py'))+[root/'config/prototype_controls.json',root/'config/source_values.json']
    frozen_hashes={str(p.relative_to(root)):sha(p) for p in protected}
    # Resolve every cell before creating output or starting costly simulations.
    from .scenarios import compose_scenario
    from .inputs import load_topics
    from .randomness import seed_map
    import copy
    controls=json.loads((root/'config/prototype_controls.json').read_text())
    sources=json.loads((root/'config/source_values.json').read_text())
    topics=load_topics(root/'data/processed/topic_catalog.csv')
    master=next(c['value'] for c in controls['controls'] if c['input_id']=='stochastic_master_seed')
    for case in plan['cases']:
        resolved=copy.deepcopy(controls)
        for c in resolved['controls']:
            if c['input_id'] in case['overrides']: c['value']=case['overrides'][c['input_id']]
        for scenario in case['scenarios']:
            compose_scenario(scenario,resolved,sources,topics,seed_map(master,case['replication_ids'][0]),case['mode'])
    destination.mkdir(parents=True,exist_ok=False)
    write_json(destination/'plan.json',plan)
    ph=sha(destination/'plan.json')
    jobs=[(root,destination,case,rep,ph) for case in plan['cases'] for rep in case['replication_ids']]
    rows=[];hashes={}
    def collect(value):
        data,folder,h=value;rows.extend(data);hashes[folder]=h
        if progress: progress(dict(completed_comparisons=len(hashes),total_comparisons=len(jobs),folder=folder,runs=len(data)))
    if workers==1:
        for job in jobs: collect(_job(*job))
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for future in as_completed([pool.submit(_job,*job) for job in jobs]): collect(future.result())
    if any(sha(root/name)!=h for name,h in frozen_hashes.items()):
        raise RuntimeError('Study code or base inputs changed; no aggregate published')
    rows.sort(key=lambda r:(r['case_id'],r['replication'],r['scenario']))
    table(destination/'replications.csv',rows)
    a,p,c=summarise(rows,plan['metrics'],plan['precision_targets'],plan['minimum_precision_replications'])
    table(destination/'absolute_intervals.csv',a);table(destination/'paired_intervals.csv',p);table(destination/'initial_clearance.csv',c)
    overhead_rows=revalue_overhead(rows,plan['cost_scope_sensitivity']['chf_per_supervised_session'])
    _,overhead,_=summarise(overhead_rows,['net_chf'],{'net_chf':plan['precision_targets']['net_chf']},plan['minimum_precision_replications'])
    table(destination/'extra_overhead_paired_intervals.csv',overhead)
    targeted=[x for x in p if x['precision_target'] is not None]
    write_json(destination/'study_manifest.json',dict(plan_hash=ph,comparison_manifest_hashes=hashes,runs=len(rows),
        frozen_input_and_code_hashes=frozen_hashes,
        output_hashes={f.name:sha(f) for f in sorted(destination.iterdir()) if f.is_file()},
        precision_status_counts={s:sum(x['precision_status']==s for x in targeted) for s in sorted({x['precision_status'] for x in targeted})},
        interpretation='Pointwise paired t intervals under fixed assumptions; not simultaneous ranks, input confidence or observed savings',
        method_reference='https://www.itl.nist.gov/div898/handbook/prc/section3/prc311.htm'))
    return rows,p
