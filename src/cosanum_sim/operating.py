"""Validated, composable training resources and independent LMS; one shared engine."""
import json,math
from dataclasses import replace
from pathlib import Path
from .annual import calendars
from .config import LearningPolicy,number
from .randomness import uniform
from .lms_workload import apply_workload


def load_operating(path):
    payload=json.loads(Path(path).read_text());entries=payload['inputs']
    if len({r['input_id'] for r in entries})!=len(entries):raise ValueError('Duplicate operating parameter')
    for r in entries:
        if not {'input_id','value','unit','scope','source_status','value_kind','source','rationale','limitation','sensitivity'}<=r.keys():
            raise ValueError('Incomplete operating provenance: '+r.get('input_id','?'))
    v={r['input_id']:r['value'] for r in entries};validate_operating(v);return payload


def validate_operating(v):
    for k in ('annual_cases','logistics_pool','physical_group_capacity','preferred_group','theory_trainer_count','practice_coach_count','training_days','training_hours_per_day','provider_user_limit','monthly_periods_per_model_year','calendar_days_per_model_year','maintenance_batch_days'):
        if type(v[k]) is not int or v[k]<1:raise ValueError('Positive integer required: '+k)
    for k in ('minimum_logistics_working','max_self_retries','additional_admin_accounts','extra_paid_addon_count'):
        if type(v[k]) is not int or v[k]<0:raise ValueError('Nonnegative integer required: '+k)
    if v['logistics_pool']!=45 or v['physical_group_capacity']>v['logistics_pool']:
        raise ValueError('Physical class capacity cannot exceed the45-person logistics roster')
    if v['minimum_logistics_working']>=v['logistics_pool']:raise ValueError('At least one learner must be releasable')
    if not 1<=v['preferred_group']<=min(v['physical_group_capacity'],v['logistics_pool']-v['minimum_logistics_working']):
        raise ValueError('Group target exceeds physical capacity or release/staffing guard')
    if v['theory_trainer_count']!=1:raise ValueError('This release supports one P&Q trainer with optional extra practice coaches')
    if not 1<=v['training_days']<=4 or v['training_hours_per_day']!=8:raise ValueError('Use one to four eight-hour teaching days')
    if type(v['pq_practice_qualified']) is not bool:raise ValueError('Explicit boolean qualification required')
    if v['default_lms_actor'] not in ('prelaunch_team','daniel_calendar'):raise ValueError('Unknown author allocation')
    if v['course_order']!='priority_then_topic_id':raise ValueError('Unknown course publication order')
    if v['calendar_days_per_model_year']!=365:raise ValueError('This annual release uses a365-day model year')
    for k in ('theory_only_coverage','mixed_topic_coverage','pass_probability'):
        number(v[k],k)
        if v[k]>1:raise ValueError('Fraction cannot exceed one: '+k)
    if v['theory_only_coverage']!=1:raise ValueError('Declared model includes all theory-only topics')
    for k in ('study_minutes','supplier_usd_per_account_month','fx_chf_per_usd'):
        number(v[k],k,positive=True)
    for k in ('coordination_ist_minutes','coordination_soll_minutes','supplier_setup_chf','addon_usd_per_account_month'):number(v[k],k)
    if v['logistics_pool']+v['additional_admin_accounts']>v['provider_user_limit']:raise ValueError('Account count exceeds priced Team plan')
    if not 1<=v['practice_coach_count']<=2:raise ValueError('Use one or two practice coaches')
    for key in ('1','2','3','4'):
        pattern=v['weekday_patterns'][key]
        if len(pattern)!=int(key) or len(set(pattern))!=len(pattern) or any(type(d) is not int or not 0<=d<7 for d in pattern):
            raise ValueError('Invalid teaching weekday pattern')
    return v


def resolve_learning(topics,profile,controls,sources,operating):
    v=operating if 'inputs' not in operating else {r['input_id']:r['value'] for r in operating['inputs']}
    validate_operating(v)
    c={x['input_id']:x['value'] for x in controls['controls']};s={x['input_id']:x['value'] for x in sources['values']}
    pure=sorted(k for k,t in topics.items() if t.theory_required and not t.practice_required)
    mixed=sorted((k for k,t in topics.items() if t.theory_required and t.practice_required),key=lambda k:(uniform(c['stochastic_master_seed'],'independent-lms-topics-v1',k),k))
    selected_mixed=mixed[:math.ceil(len(mixed)*v['mixed_topic_coverage'])]
    selected=tuple(sorted(pure+selected_mixed));accounts=v['logistics_pool']+v['additional_admin_accounts']
    annual_usd=accounts*(v['supplier_usd_per_account_month']+v['extra_paid_addon_count']*v['addon_usd_per_account_month'])*v['monthly_periods_per_model_year']
    annual_chf=annual_usd*v['fx_chf_per_usd']
    if v['authoring_rate_binding'] not in s:raise ValueError('Unknown authoring valuation binding')
    rate=s[v['authoring_rate_binding']]
    number(rate,'authoring valuation',positive=True)
    setup=c['lms_implementation_chf'];content=c['lms_content_chf_per_topic'];care=c['lms_maintenance_chf_per_day']
    return dict(selected_topic_ids=selected,theory_only_topic_ids=pure,selected_mixed_topic_ids=sorted(selected_mixed),all_mixed_topic_count=len(mixed),
        accounts=accounts,annual_licence_usd=annual_usd,annual_licence_chf=annual_chf,licence_chf_per_day=annual_chf/v['calendar_days_per_model_year'],
        internal_setup_chf=setup,content_chf_per_topic=content,maintenance_chf_per_day=care,
        first_year_portfolio_chf=setup+v['supplier_setup_chf']+len(selected)*content+annual_chf+365*care,
        effort=dict(authoring_rate_chf=rate,setup_hours=setup/rate,course_hours_each=content/rate,content_hours=len(selected)*content/rate,
            maintenance_hours_per_day=care/rate,maintenance_batch_days=v['maintenance_batch_days'],source_status='assumption',rationale='Internal budgets divided by task rate; already included labour costs'))


def configure_operating(cfg,topics,profile,people,operating,seeds,controls,sources,*,ist=False,learning=False,actor=None,planning_improved=True):
    v=operating if 'inputs' not in operating else {r['input_id']:r['value'] for r in operating['inputs']}
    validate_operating(v)
    changed=profile.with_overrides(dict(resource_calendar_weekdays=v['weekday_patterns'][str(v['training_days'])],resource_days_per_week=v['training_days']))
    base=calendars(changed,topics,people,cfg.horizon);trainer=next(r for r in base if r.role=='trainer');room=next(r for r in base if r.role=='room')
    resources=(replace(trainer,resource_id='theory-pq',phases=('theory','proof','practice') if v['pq_practice_qualified'] else ('theory','proof')),)
    resources+=tuple(replace(trainer,resource_id=f'practice-coach-{i+1}',phases=('practice',)) for i in range(v['practice_coach_count']))
    # Separate practice places for every qualified practice provider: rooms do not bind.
    places=v['practice_coach_count']+int(v['pq_practice_qualified'])
    resources+=(replace(room,resource_id='theory-place',phases=('theory',)),)
    resources+=tuple(replace(room,resource_id=f'practice-place-{i+1}',phases=('practice',)) for i in range(places))
    resources+=tuple(r for r in base if r.role=='participant')
    limit=v['logistics_pool']-v['minimum_logistics_working'];capacity=min(v['physical_group_capacity'],limit)
    wf=replace(cfg.workflow,learning=None,coordination_minutes=v['coordination_ist_minutes' if not planning_improved else 'coordination_soll_minutes'])
    target=min(profile.values['group_size'],capacity) if ist else v['preferred_group']
    cfg=replace(cfg,resources=resources,workflow=wf,capacity=capacity,target=target,participant_absence_limit=limit)
    resolved=resolve_learning(topics,profile,controls,sources,operating);work=None
    if learning:
        l=LearningPolicy(resolved['selected_topic_ids'],v['study_minutes'],0,0,v['pass_probability'],seeds['assessment'],
            resolved['internal_setup_chf']+v['supplier_setup_chf'],resolved['content_chf_per_topic'],resolved['licence_chf_per_day'],resolved['maintenance_chf_per_day'],
            assessment_mode='automated',max_self_retries=v['max_self_retries'])
        cfg=replace(cfg,workflow=replace(wf,learning=l))
        cfg,work=apply_workload(cfg,topics,changed,resolved['effort'],actor or v['default_lms_actor'])
    return cfg.validate(topics),resolved,work
