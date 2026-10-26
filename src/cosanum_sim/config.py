"""Resolve only controls used by this increment; unknown future inputs stay null."""
from dataclasses import dataclass, asdict
from math import isfinite
from typing import Optional, Tuple
from .domain import Resource


def number(value, name, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{name}: finite number required")
    if value < 0 or (positive and value == 0):
        raise ValueError(f"{name}: {'positive' if positive else 'nonnegative'} required")


@dataclass(frozen=True)
class Cancellation:
    request_id: str
    phase: str
    attempt: int
    minutes_after_booking: float


@dataclass(frozen=True)
class LearningPolicy:
    topic_ids: Tuple[str, ...]
    study_minutes: float
    assessment_minutes: float
    support_minutes: float
    pass_probability: float
    seed: int
    implementation_chf: float
    content_chf_per_topic: float
    licence_chf_per_day: float
    maintenance_chf_per_day: float
    assessment_mode: str = 'expert'
    max_self_retries: int = 0
    topic_ready_at: Tuple[Tuple[str, float], ...] = ()

    def validate(self, topics):
        if len({t for t,_ in self.topic_ready_at}) != len(self.topic_ready_at) or any(t not in self.topic_ids for t,_ in self.topic_ready_at):
            raise ValueError('Invalid LMS course-availability topic list')
        for topic,time in self.topic_ready_at:
            number(time, 'LMS course available time')
        if self.assessment_mode not in ('expert', 'automated'):
            raise ValueError('Unsupported LMS assessment mode')
        if type(self.max_self_retries) is not int or self.max_self_retries < 0:
            raise ValueError('LMS self retries must be a nonnegative integer')
        if self.assessment_mode == 'expert' and self.max_self_retries:
            raise ValueError('Expert assessment keeps the original one-attempt rule')
        if self.assessment_mode == 'automated' and (self.assessment_minutes or self.support_minutes):
            raise ValueError('Automated quiz is included in study time; no scheduled expert assessment/support')
        if len(set(self.topic_ids)) != len(self.topic_ids) or set(self.topic_ids)-topics.keys():
            raise ValueError('Invalid LMS suitability topic list')
        if any(not topics[t].theory_required for t in self.topic_ids):
            raise ValueError('LMS requires a theory phase')
        for name in ('study_minutes','assessment_minutes','support_minutes','pass_probability',
                     'implementation_chf','content_chf_per_topic','licence_chf_per_day','maintenance_chf_per_day'):
            number(getattr(self,name),name,positive=name == 'study_minutes' or
                   (name == 'assessment_minutes' and self.assessment_mode == 'expert'))
        if self.pass_probability>1 or type(self.seed) is not int or self.seed<0:
            raise ValueError('Invalid LMS probability/seed')


@dataclass(frozen=True)
class Workflow:
    practice_duration: float
    preparation: float
    follow_up: float
    proof_delay: float
    proof_recovery_duration: float
    participant_rate: float
    coach_rate: float
    pq_rate: float
    group_allowance: float
    included_pq_hours: float
    practice_credit: float
    exclusions: Tuple[str, ...]
    cancellations: Tuple[Cancellation, ...] = ()
    learning: Optional[LearningPolicy] = None
    coordination_minutes: float = 0

    def validate(self, theory_duration):
        number(self.coordination_minutes,'coordination minutes')
        if self.coordination_minutes>self.preparation:
            raise ValueError('Group coordination must fit inside included preparation')
        for name in ('practice_duration', 'preparation', 'follow_up', 'proof_delay',
                     'proof_recovery_duration', 'participant_rate', 'coach_rate', 'pq_rate',
                     'group_allowance', 'included_pq_hours', 'practice_credit'):
            number(getattr(self, name), name, positive=name in ('practice_duration', 'proof_recovery_duration', 'included_pq_hours'))
        if self.practice_credit > 1:
            raise ValueError('practice credit must be in [0,1]')
        if abs(self.preparation + theory_duration + self.follow_up - 60*self.included_pq_hours) > 1e-9:
            raise ValueError('P&Q activity split must reconcile to included hours')
        keys = set()
        for c in self.cancellations:
            key = (c.request_id, c.phase, c.attempt)
            if key in keys or not c.request_id or c.phase not in ('theory','practice') or type(c.attempt) is not int or c.attempt < 1:
                raise ValueError('Invalid/duplicate cancellation trigger')
            number(c.minutes_after_booking, 'cancellation offset', positive=True)
            keys.add(key)


@dataclass(frozen=True)
class UrgencyReview:
    interval_minutes: float
    urgent_probability: float
    seed: int

    def validate(self):
        number(self.interval_minutes, 'review interval', positive=True)
        number(self.urgent_probability, 'urgent probability')
        if self.urgent_probability > 1 or type(self.seed) is not int or self.seed < 0:
            raise ValueError('Invalid review probability/seed')


@dataclass(frozen=True)
class PriorityPolicy:
    imminent_minutes: float
    ageing_minutes: float

    def validate(self):
        number(self.imminent_minutes, 'imminent deadline window')
        number(self.ageing_minutes, 'ageing safeguard', positive=True)


@dataclass(frozen=True)
class Config:
    threshold: int
    target: Optional[int]
    capacity: int
    max_wait: float
    horizon: float
    duration: float
    group_preferred: bool
    deadline_enabled: bool
    resources: Tuple[Resource, ...]
    workflow: Optional[Workflow] = None
    grouping_topics: Optional[Tuple[str, ...]] = None
    urgency_review: Optional[UrgencyReview] = None
    selection_seed: Optional[int] = None
    planning_delay: float = 0
    priority: Optional[PriorityPolicy] = None
    phase_allocation: str = 'legacy'
    use_baseline_delivery: bool = False
    recovery_aged_every: Optional[int] = None
    joined_scheduling: bool = False
    participant_absence_limit: Optional[int] = None

    def validate(self, topics):
        if self.participant_absence_limit is not None and (type(self.participant_absence_limit) is not int or self.participant_absence_limit<1):
            raise ValueError('Positive participant absence limit required')
        for name, value in (("threshold", self.threshold), ("capacity", self.capacity)):
            if type(value) is not int or value < 1:
                raise ValueError(f"{name}: positive integer required")
        if self.threshold > self.capacity:
            raise ValueError("threshold exceeds capacity")
        if self.target is not None and (type(self.target) is not int or not self.threshold <= self.target <= self.capacity):
            raise ValueError("target must lie between threshold and capacity")
        for name in ("max_wait", "horizon", "duration"):
            number(getattr(self, name), name, positive=name != "max_wait")
        if type(self.group_preferred) is not bool or type(self.deadline_enabled) is not bool:
            raise ValueError("policy switches must be boolean")
        if type(self.use_baseline_delivery) is not bool:
            raise ValueError('baseline delivery switch must be boolean')
        if type(self.joined_scheduling) is not bool:
            raise ValueError('joined scheduling switch must be boolean')
        if self.joined_scheduling and self.workflow is None:
            raise ValueError('Joined scheduling requires the full theory/practice workflow')
        if self.phase_allocation not in ('legacy', 'recover_after_infeasible_start'):
            raise ValueError('Unsupported phase allocation policy')
        if self.recovery_aged_every is not None and (type(self.recovery_aged_every) is not int or self.recovery_aged_every<1):
            raise ValueError('Recovery aged-work interval must be a positive integer')
        if self.phase_allocation!='legacy' and self.recovery_aged_every is None:
            raise ValueError('Recovery allocation requires an explicit aged-work interval')
        if self.phase_allocation!='legacy' and (self.priority is None or not self.deadline_enabled or self.workflow is None):
            raise ValueError('Recovery allocation requires priority, hard start deadlines and full workflow')
        if self.workflow is not None:
            self.workflow.validate(self.duration)
            if self.workflow.learning is not None:
                self.workflow.learning.validate(topics)
        if self.grouping_topics is not None and set(self.grouping_topics) - topics.keys():
            raise ValueError('Unknown grouping-policy topic')
        if self.selection_seed is not None and (type(self.selection_seed) is not int or self.selection_seed<0):
            raise ValueError('Invalid selection seed')
        if self.urgency_review is not None:
            self.urgency_review.validate()
        number(self.planning_delay, 'planning delay')
        if self.priority is not None:
            self.priority.validate()
        ids = set()
        for resource in self.resources:
            if not resource.resource_id or resource.resource_id in ids or resource.role not in ("trainer", "room", "participant"):
                raise ValueError("invalid or duplicate resource identity/role")
            ids.add(resource.resource_id)
            if set(resource.topic_ids) - topics.keys():
                raise ValueError("resource has unknown topic qualification")
            if not resource.phases or set(resource.phases) - {"theory", "practice", "proof"}:
                raise ValueError("Unknown/empty resource phase qualification")
            previous = -1
            for start, end in resource.intervals:
                number(start, "calendar start")
                number(end, "calendar end")
                if start >= end or start < previous:
                    raise ValueError("calendar intervals must be ordered, disjoint and positive length")
                previous = end
        # Empty availability is intentional infeasibility, not invented capacity.
        return self

    def resolved(self):
        return asdict(self)


def resolve(controls, source_values, topics, full_workflow=False):
    c = {x['input_id']: x['value'] for x in controls['controls']}
    s = {x['input_id']: x['value'] for x in source_values['values']}
    resource_key = 'workflow_resources' if full_workflow else 'slice_resources'
    workflow = None
    if full_workflow:
        if c['cancelled_allowance_valuation'] != 'proportional_consumed_pq_work':
            raise ValueError('Unsupported cancellation valuation rule')
        if c['practice_credit_scope'] != 'all_synthetic_practice_participants':
            raise ValueError('Unsupported practice credit scope')
        if c['training_completion_rule'] != 'required_sessions_delivered':
            raise ValueError('Unsupported training completion rule')
        split = c['pq_activity_split']
        if split['delivery'] != s['theory_standard_minutes']:
            raise ValueError('P&Q delivery split contradicts theory duration')
        workflow = Workflow(s['practice_standard_minutes'], split['preparation'], split['follow_up'],
                            c['proof_recording_delay_minutes'], c['proof_recovery_minutes'],
                            s['participant_hourly_chf'], s['coach_hourly_chf'], s['pq_hourly_chf'],
                            s['theory_group_pq_allowance_chf'], s['theory_group_included_pq_hours'],
                            s['participant_practice_credit_fraction'], tuple(c['cost_scope_exclusions']))
    resources = tuple(Resource(x['resource_id'], x['role'], tuple(x['topic_ids']),
                               tuple(tuple(i) for i in x['intervals']), tuple(x.get('phases',('theory','practice','proof')))) for x in c[resource_key])
    return Config(c['preferred_group_threshold'], c['target_session_size'], c['max_session_capacity'],
                  c['max_wait_minutes'], c['horizon_minutes'], s['theory_standard_minutes'],
                  c['slice_group_preferred'], c['slice_deadline_enabled'], resources, workflow).validate(topics)
