"""Versioned paired studies of composable policies and calibrated operating inputs."""
import argparse,json
from dataclasses import asdict,replace
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from . import __version__
from .annual import yearly_row,theory_benchmark
from .annual_demand import annual_fixture,load_profile
from .experiments import execute,table,write_json
from .inputs import load_topics,verify_sources,sha
from .randomness import seed_map
from .scenarios import compose_scenario,recognize
from .operating import load_operating,configure_operating
from .uncertainty import summarise

VARIANTS={k:dict(recipe=k,learning=False,actor=None) for k in ('S0','S1','S2','S3','S4','S5','S7_RECOVERY','S7_RECOVERY_JOINED')}
VARIANTS.update(LMS_TEAM=dict(recipe='S7_RECOVERY',learning=True,actor='prelaunch_team'),
 LMS_DANIEL=dict(recipe='S7_RECOVERY',learning=True,actor='daniel_calendar'),
 LMS_TEAM_JOINED=dict(recipe='S7_RECOVERY_JOINED',learning=True,actor='prelaunch_team'))


def values(payload):return {r['input_id']:r['value'] for r in payload['inputs']}

def experiment(root,destination,case,rep,plan_hash):
    topics=load_topics(root/'data/processed/topic_catalog.csv');profile=load_profile(root/'config/annual_profile.json')
    controls=json.loads((root/'config/prototype_controls.json').read_text());sources=json.loads((root/'config/source_values.json').read_text())
    op=values(load_operating(root/'config/operating_configuration.json'));op.update(case.get('operating_overrides',{}))
    seeds=seed_map(next(x['value'] for x in controls['controls'] if x['input_id']=='stochastic_master_seed'),rep)
    fixture,demand=annual_fixture(topics,seeds,profile,case['include_backlog'],case['include_ongoing'])
    if case['include_ongoing'] and len([r for r in demand if r.cohort_id=='ongoing'])!=op['annual_cases']:raise ValueError('Declared annual volume mismatch')
    fixture['resolved_underlying_requests']=[asdict(r) for r in demand]
    destination.mkdir(parents=True,exist_ok=False);write_json(destination/'underlying_demand.json',fixture)
    write_json(destination/'scope_reference.json',theory_benchmark(fixture,sources));write_json(destination/'operating_values.json',op)
    common=sha(destination/'underlying_demand.json');horizon=(365+case.get('drain_days',0))*1440;rows=[]
    for variant in case['scenarios']:
        spec=VARIANTS[variant];recipe,_=compose_scenario(spec['recipe'],controls,sources,topics,seeds,'ongoing_stochastic_demand',profile.values['recovery_aged_every'])
        cfg=replace(recipe.config,horizon=horizon,use_baseline_delivery='grouping' not in recipe.components)
        cfg,resolved,work=configure_operating(cfg,topics,profile,{r.person_id for r in demand},op,seeds,controls,sources,
            ist='grouping' not in recipe.components,planning_improved='planning' in recipe.components,learning=spec['learning'],actor=spec['actor'])
        result,m=execute(root,destination/variant,cfg,topics,recognize(demand,recipe.recognition_delay),fixture,controls,sources,verify_sources(root),
            dict(scenario_id=variant,components=list(recipe.components)+(['independent_lms'] if spec['learning'] else []),replication_id=rep,seed_map=seeds,
              fixture_hash=common,operating_values=op,learning_actor=spec['actor'],experiment_plan_hash=plan_hash,
              comparison_ageing_limit=next(x['value'] for x in controls['controls'] if x['input_id']=='priority_ageing_minutes'),
              randomness='Paired fixed annual count; identity-keyed arrival/topic/person/assessment streams; fixed durations; no random disruptions',
              calibration='Synthetic45-person roster; retained15x20+50 annual routing; user operating answers and explicit prototype assumptions'))
        row=yearly_row(result,m,cfg,topics,fixture);over=work['trainer_overhead_hours'] if work else 0
        row.update(case_id=case['case_id'],scenario=variant,replication=rep,fixture_hash=common,trainer_training_hours=row['trainer_used_hours'],
          trainer_lms_hours=over,trainer_total_hours=row['trainer_used_hours']+over,
          trainer_gross_available_hours=work['original_trainer_hours'] if work else row['trainer_available_hours'],
          lms_internal_hours=work['internal_hours'] if work else 0,lms_portfolio_chf=m.get('lms_portfolio_cost_chf',0),
          training_work_chf=row['net_chf']-m.get('lms_portfolio_cost_chf',0),
          last_course_ready_day=max(t for _,t in work['topic_ready_at'])/1440 if work else None,
          lms_attempts=m['lms_started'],lms_fallbacks=m.get('lms_instructor_fallbacks',0),
          cost_boundary='fixed350-case cohort; up to730 days' if case.get('drain_days',0) else 'work consumed during first365 days')
        assert row['trainer_total_hours']<=row['trainer_gross_available_hours']+1e-6
        if work:
            assert abs(work['internal_valued_cost_chf']+resolved['annual_licence_chf']*horizon/(365*1440)-row['lms_portfolio_chf'])<1e-6
            write_json(destination/(variant+'_author_schedule.json'),work)
        rows.append(row)
    table(destination/'paired_results.csv',rows);return rows


def frozen(root,plan):
    paths=sorted((root/'src').rglob('*.py'))+sorted((root/'config').glob('*.json'))+[root/'pyproject.toml',root/'data/processed/topic_catalog.csv',root/'SOURCE_MANIFEST.json',plan]
    return {str(p.relative_to(root)):sha(p) for p in paths}


def run(root,out,plan_path,workers=1):
    plan=json.loads(plan_path.read_text());seen=set()
    for c in plan['cases']:
        if c['case_id'] in seen or not c['scenarios'] or c['scenarios'][0]!='S0' or any(s not in VARIANTS for s in c['scenarios']):raise ValueError('Invalid paired study cell')
        if len(set(c['replications']))!=len(c['replications']) or any(type(r) is not int or r<0 for r in c['replications']):raise ValueError('Invalid replication IDs')
        seen.add(c['case_id'])
    before=frozen(root,plan_path);raw=verify_sources(root);out.mkdir(parents=True,exist_ok=False);write_json(out/'plan.json',plan)
    ph=sha(out/'plan.json');tasks=[(root,out/c['case_id']/f'rep-{r}',c,r,ph) for c in plan['cases'] for r in c['replications']];rows=[]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        pending={pool.submit(experiment,*t):t for t in tasks}
        for f in as_completed(pending):
            batch=f.result();rows.extend(batch);t=pending[f]
            print(f"{t[2]['case_id']} rep{t[3]}: "+', '.join(f"{r['scenario']}={r['training_completed']}" for r in batch),flush=True)
    if before!=frozen(root,plan_path) or raw!=verify_sources(root):raise RuntimeError('Study inputs changed during execution')
    rows.sort(key=lambda r:(r['case_id'],r['replication'],r['scenario']))
    a,p,c=summarise(rows,plan['metrics'],plan['precision_targets'],20,plan['contrasts'])
    # Small screens are descriptive only: do not publish t intervals for n<20.
    for entry in a+p:
        if entry['n']<20:entry.update(lower=None,upper=None,half_width=None,precision_status='descriptive_only')
    table(out/'replications.csv',rows);table(out/'absolute_intervals.csv',a);table(out/'paired_intervals.csv',p);table(out/'clearance.csv',c)
    write_json(out/'study_manifest.json',dict(engine_version=__version__,plan_hash=ph,runs=len(rows),comparisons=len(tasks),frozen_input_and_code_hashes=before,source_hashes=raw,
      output_hashes={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()},
      limitations=plan['limitations']))
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--plan',type=Path,default=Path('config/integrated_study_plan.json'));p.add_argument('--workers',type=int,default=3)
    a=p.parse_args();run(Path.cwd(),a.output.resolve(),a.plan.resolve(),a.workers)
