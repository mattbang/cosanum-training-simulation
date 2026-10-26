"""Composable recommendation components; scenario IDs never reach engine logic."""
from dataclasses import dataclass, replace
from .baseline import compose_ist
from .config import PriorityPolicy, LearningPolicy, number
from .domain import Resource
from .demand import synthetic_people

COMPONENTS = {
    'S0': (),
    'S0_JOINED': ('joined_scheduling',),
    'S1': ('grouping',),
    'S2': ('recognition',),
    'S3': ('proof',),
    'S4': ('planning',),
    'S5': ('priority',),
    'S6': ('learning',),
    'S7': ('grouping','recognition','proof','planning','priority','hard_wait'),
    'S7_RECOVERY': ('grouping','recognition','proof','planning','priority','hard_wait','recovery'),
    'S7_RECOVERY_JOINED': ('grouping','recognition','proof','planning','priority','hard_wait','recovery','joined_scheduling'),
    'S7_PLUS_LMS': ('grouping','recognition','proof','planning','priority','hard_wait','learning'),
    'S1_GROUPING_ONLY': ('grouping',),
    'S1_GROUPING_WITH_DEADLINE': ('grouping','hard_wait'),
    'DEADLINE_ONLY': ('hard_wait',),
}


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    components: tuple
    config: object
    recognition_delay: float
    parameter_diff: dict
    baseline_extensions: dict


def diff(before,after):
    return {k:{'before':before[k],'after':after[k]} for k in before if before[k]!=after[k]}


def compose_scenario(identity,controls,source_values,topics,seeds,mode,recovery_aged_every=None):
    if identity not in COMPONENTS:
        raise ValueError(f'Unsupported scenario {identity}')
    c = {x['input_id']:x['value'] for x in controls['controls']}
    for key in ('comparison_ist_recognition_delay','soll_recognition_delay','comparison_ist_planning_delay',
                'soll_planning_delay','soll_proof_recording_delay','soll_proof_recovery_minutes'):
        number(c[key],key,positive=key=='soll_proof_recovery_minutes')
    original,spec = compose_ist(controls,source_values,topics,seeds,mode)
    if c['comparison_participant_calendar']!='same_as_ist_calendar':
        raise ValueError('Unsupported comparison participant calendar')
    participant_resources = tuple(Resource(person,'participant',tuple(sorted(topics)),original.resources[0].intervals)
                                  for person in synthetic_people(spec))
    base = replace(original,planning_delay=c['comparison_ist_planning_delay'],resources=original.resources+participant_resources)
    cfg,recognition = base,c['comparison_ist_recognition_delay']
    parts = COMPONENTS[identity]
    for part in parts:
        if part=='grouping':
            cfg = replace(cfg,group_preferred=True,grouping_topics=None)
        elif part=='recognition':
            recognition = c['soll_recognition_delay']
        elif part=='proof':
            cfg = replace(cfg,workflow=replace(cfg.workflow,proof_delay=c['soll_proof_recording_delay'],
                                              proof_recovery_duration=c['soll_proof_recovery_minutes']))
        elif part=='planning':
            cfg = replace(cfg,planning_delay=c['soll_planning_delay'])
        elif part=='priority':
            cfg = replace(cfg,priority=PriorityPolicy(c['priority_imminent_minutes'],c['priority_ageing_minutes']))
        elif part=='hard_wait':
            cfg = replace(cfg,deadline_enabled=True,urgency_review=None)
        elif part=='recovery':
            cfg = replace(cfg,phase_allocation='recover_after_infeasible_start',recovery_aged_every=recovery_aged_every)
        elif part=='joined_scheduling':
            cfg = replace(cfg,joined_scheduling=True)
        elif part=='learning':
            learning = LearningPolicy(tuple(c['lms_suitable_topic_ids']),c['lms_study_minutes'],
                c['lms_assessment_minutes'],c['lms_support_minutes'],c['lms_pass_probability'],seeds['assessment'],
                c['lms_implementation_chf'],c['lms_content_chf_per_topic'],c['lms_licence_chf_per_day'],c['lms_maintenance_chf_per_day'])
            cfg = replace(cfg,workflow=replace(cfg.workflow,learning=learning))
    cfg.validate(topics)
    before = dict(runtime=base.resolved(),recognition_delay=c['comparison_ist_recognition_delay'])
    after = dict(runtime=cfg.resolved(),recognition_delay=recognition)
    parameters = diff(base.resolved(),cfg.resolved())
    if before['recognition_delay']!=after['recognition_delay']:
        parameters['recognition_delay'] = {'before':before['recognition_delay'],'after':after['recognition_delay']}
    return Scenario(identity,parts,cfg,recognition,parameters,
                    dict(planning_delay={'prior_ist_smoke':original.planning_delay,'comparison':base.planning_delay},
                         recognition_delay={'prior_ist_smoke':0,'comparison':c['comparison_ist_recognition_delay']},
                         participant_calendar='Explicit synthetic participant calendars match IST resource calendar in every comparison scenario',
                         interpretation='New latency hypotheses; prior IST smoke results remain immutable')),spec


def recognize(requests,delay):
    number(delay,'recognition delay')
    # Frozen backlog is already noticed at t0. S2 cannot retroactively accelerate it.
    resolved = []
    for r in requests:
        need = r.need_arises_at if r.need_arises_at is not None else r.noticed_at
        resolved.append(replace(r,need_arises_at=need,noticed_at=need+delay if r.cohort_id=='ongoing' else r.noticed_at))
    return resolved
