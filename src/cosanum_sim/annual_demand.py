"""Daniel-informed annual illustration, distinct from measured annual demand.

Q6 supplies estimated occurrences, not an explicit annual period or phase count.
The profile declares those interpretations before generating any requests.
"""
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping

from .config import number
from .demand import expand_batches, validate_requests
from .randomness import uniform

MINUTES_PER_DAY = 1440
MINUTES_PER_HOUR = 60
_STATUSES = ('verified', 'Daniel-reported', 'derived', 'assumption')
_REQUIRED = ('historical_period_interpretation', 'reported_count_phase_interpretation',
             'horizon_days', 'arrival_window_days', 'arrival_time_rule',
             'group_training_count', 'individual_training_count',
             'reported_typical_group_size_range', 'group_size', 'topic_mix_rule',
             'synthetic_internal_pool_size', 'initial_backlog_age_minutes',
             'baseline_group_release_rule', 'resource_days_per_week',
             'resource_calendar_weekdays', 'resource_calendar_start_minute',
             'resource_calendar_end_minute', 'participant_calendar_weekdays',
             'recovery_aged_every')


@dataclass(frozen=True)
class AnnualProfile:
    values: Mapping
    provenance: dict
    bound_source_values: dict
    source_hashes: dict

    @property
    def horizon_minutes(self):
        return self.values['horizon_days'] * MINUTES_PER_DAY

    def validate(self):
        v = self.values
        if set(v) != set(_REQUIRED):
            raise ValueError('Annual profile has unknown or missing inputs')
        fixed = {'historical_period_interpretation': 'one_model_year',
                 'reported_count_phase_interpretation': 'theory_sessions',
                 'arrival_time_rule': 'uniform_fixed_event_count',
                 'topic_mix_rule': 'uniform_source_eligible',
                 'baseline_group_release_rule': 'complete_batch_subject_to_capacity'}
        if any(v[k] != x for k, x in fixed.items()):
            raise ValueError('Unsupported annual interpretation or fixture rule')
        for k in ('horizon_days', 'arrival_window_days'):
            number(v[k], k, positive=True)
        if v['arrival_window_days'] > v['horizon_days']:
            raise ValueError('Annual arrival window exceeds the horizon')
        if self.horizon_minutes < 1:
            raise ValueError('Annual horizon must include at least one whole minute')
        for k in ('group_training_count', 'individual_training_count'):
            if type(v[k]) is not int or v[k] < 0:
                raise ValueError('Annual occurrence counts must be nonnegative integers')
        if not v['group_training_count'] + v['individual_training_count']:
            raise ValueError('Annual profile must contain at least one occurrence')
        for k in ('group_size', 'synthetic_internal_pool_size'):
            if type(v[k]) is not int or v[k] < 1:
                raise ValueError('Annual group/pool sizes must be positive integers')
        if v['group_size'] > v['synthetic_internal_pool_size']:
            raise ValueError('Annual group size exceeds synthetic pool')
        if v['group_training_count'] and v['group_size'] < 2:
            raise ValueError('A group occurrence requires at least two participants')
        band = v['reported_typical_group_size_range']
        if (not isinstance(band, (list, tuple)) or len(band) != 2 or
                any(type(x) is not int or x < 1 for x in band) or band[0] > band[1]):
            raise ValueError('Invalid preserved reported group-size range')
        # Existing elapsed-time mechanics require noticed_at >= 0; do not silently
        # ignore an override purporting to reconstruct historical waiting ages.
        if v['initial_backlog_age_minutes'] != 0:
            raise ValueError('This annual illustration supports only explicit zero-age initial stock')
        weekdays = v['resource_calendar_weekdays']
        if (not isinstance(weekdays, (list, tuple)) or not weekdays or
                any(type(x) is not int or not 0 <= x <= 6 for x in weekdays) or
                len(set(weekdays)) != len(weekdays)):
            raise ValueError('Invalid annual resource weekdays')
        if type(v['resource_days_per_week']) is not int or v['resource_days_per_week'] != len(weekdays):
            raise ValueError('Annual resource day count contradicts weekdays')
        participant_days = v['participant_calendar_weekdays']
        if (not isinstance(participant_days, (list, tuple)) or not participant_days or
                any(type(x) is not int or not 0 <= x <= 6 for x in participant_days) or
                len(set(participant_days)) != len(participant_days)):
            raise ValueError('Invalid annual participant weekdays')
        if type(v['recovery_aged_every']) is not int or v['recovery_aged_every'] < 1:
            raise ValueError('Annual recovery selection interval must be a positive integer')
        start, end = v['resource_calendar_start_minute'], v['resource_calendar_end_minute']
        if any(type(x) is not int for x in (start, end)) or not 0 <= start < end <= MINUTES_PER_DAY:
            raise ValueError('Invalid annual daily resource window')
        for k in ('theory_minutes', 'practice_minutes', 'group_pq_hours'):
            number(self.bound_source_values[k]['value'], k, positive=True)
        if self.bound_source_values['group_pq_hours']['value'] * MINUTES_PER_HOUR < self.bound_source_values['theory_minutes']['value']:
            raise ValueError('Group included P&Q hours cannot be shorter than theory delivery')
        return self

    def resolved(self):
        return {'profile_id': self.provenance['profile_id'], 'values': deepcopy(dict(self.values)),
                'provenance': deepcopy(self.provenance),
                'bound_source_values': deepcopy(self.bound_source_values),
                'source_hashes': deepcopy(self.source_hashes),
                'derived_closeout_days': self.values['horizon_days'] - self.values['arrival_window_days']}

    def with_overrides(self, overrides):
        if set(overrides) - set(self.values):
            raise ValueError('Unknown annual profile override')
        v = deepcopy(dict(self.values))
        raw = deepcopy(self.provenance)
        changes = {}
        for k, value in overrides.items():
            changes[k] = {'original': deepcopy(v[k]), 'resolved': deepcopy(value),
                          'source_status': 'assumption', 'value_kind': 'explicit_profile_sensitivity',
                          'rationale': 'Declared alternative annual illustration; original source value is preserved.'}
            v[k] = deepcopy(value)
        raw['overrides'] = changes
        return AnnualProfile(v, raw, deepcopy(self.bound_source_values), deepcopy(self.source_hashes)).validate()


def load_profile(path):
    """Load the authoritative labelled annual controls and existing source bindings."""
    path = Path(path)
    raw = json.loads(path.read_text())
    if raw.get('schema_version') != '1.0' or not raw.get('profile_id'):
        raise ValueError('Unsupported annual profile schema or missing identity')
    values = {}
    fields = ('value', 'unit', 'scope', 'source_status', 'value_kind', 'source',
              'rationale', 'limitation', 'sensitivity')
    for item in raw.get('inputs', ()):
        key = item.get('input_id')
        if not key or key in values or any(k not in item for k in fields):
            raise ValueError('Missing or duplicate annual input/provenance')
        if item['source_status'] not in _STATUSES:
            raise ValueError('Invalid annual input source status')
        values[key] = deepcopy(item['value'])
    binding = raw['source_bindings']
    source_path = path.parent / binding['file']
    source_raw = json.loads(source_path.read_text())
    source_values = {x['input_id']: x for x in source_raw['values']}
    try:
        bound = {k: deepcopy(source_values[binding[k]]) for k in
                 ('theory_minutes', 'practice_minutes', 'group_pq_hours')}
    except KeyError as e:
        raise ValueError('Annual source-duration binding is missing') from e
    hashes = {'profile_file': sha256(path.read_bytes()).hexdigest(),
              'bound_source_file': sha256(source_path.read_bytes()).hexdigest()}
    return AnnualProfile(values, raw, bound, hashes).validate()


def annual_fixture(topics, seeds, profile, include_backlog=False, include_ongoing=True):
    """Return (common fixture, requests), with optional separately identified stock.

    Fixed counts are interpreted annual theory occurrences. Topic assignment and
    synthetic identities are keyed independently of detection times or policies.
    """
    if type(include_backlog) is not bool or type(include_ongoing) is not bool:
        raise ValueError('Annual demand scope flags must be boolean')
    if not include_ongoing and not include_backlog:
        raise ValueError('Frozen annual scope requires initial stock')
    profile.validate()
    v = profile.values
    group_count = v['group_training_count'] if include_ongoing else 0
    individual_count = v['individual_training_count'] if include_ongoing else 0
    theory = sorted(k for k, t in topics.items() if t.theory_required)
    groups = sorted(k for k in theory if topics[k].theory_group_possible)
    if not theory or (v['group_training_count'] and not groups):
        raise ValueError('Annual profile requires appropriate source-eligible theory topics')
    if any(k not in seeds or type(seeds[k]) is not int or seeds[k] < 0
           for k in ('detection', 'topic_assignment', 'person_assignment')):
        raise ValueError('Annual fixture needs valid independent keyed streams')
    people = [f'synthetic-internal-{i+1:03d}' for i in range(v['synthetic_internal_pool_size'])]
    batches = []

    def add(identity, topic, time, size, cohort, delivery=None):
        chosen = sorted(people, key=lambda person: (uniform(seeds['person_assignment'], identity, person), person))[:size]
        batches.append({'batch_id': identity, 'topic_id': topic, 'noticed_at': time,
                        'size': size, 'person_ids': chosen, 'case_kind': 'training_needed',
                        'cohort_id': cohort, 'cycle_id': identity, 'baseline_delivery': delivery})

    for delivery, count, size, candidates in (
            ('group', group_count, v['group_size'], groups),
            ('individual', individual_count, 1, theory)):
        for i in range(count):
            identity = f'annual-{delivery}-{i:04d}'
            topic = candidates[int(uniform(seeds['topic_assignment'], identity) * len(candidates))]
            # Uniform whole-minute detection in [0, arrival_window), independent
            # of topic and person streams. Event IDs remain stable if size varies.
            time = int(uniform(seeds['detection'], identity) * v['arrival_window_days'] * MINUTES_PER_DAY)
            add(identity, topic, time, size, 'ongoing', delivery)
    batches.sort(key=lambda b: (b['noticed_at'], b['batch_id']))
    if include_backlog:
        initial = []
        for topic in sorted(topics):
            count = topics[topic].open_records
            if type(count) is not int or count < 0:
                raise ValueError('Initial source-stock count must be a nonnegative integer')
            if count > len(people):
                raise ValueError('Synthetic pool too small for unique initial person-topic mapping')
            if count:
                if not topics[topic].theory_required:
                    raise ValueError('Initial stock contains unsupported non-theory topic')
                add(f'annual-initial-{topic}', topic, 0, count, 'initial')
                initial.append(batches.pop())
        batches = initial + batches
    fixture = {'fixture_id': profile.provenance['profile_id'], 'synthetic': True,
               'cohort_id': 'annual-synthetic',
               'mode': 'annual_with_backlog' if include_backlog else 'annual_ongoing',
               'source_status': 'assumption', 'value_kind': 'annual_interpretation_and_synthetic_mapping',
               'unit': 'elapsed_minutes_and_person_topic_records', 'horizon_minutes': profile.horizon_minutes,
               'rationale': 'Estimated Q6 occurrences interpreted as annual theory; source-eligible uniform topics, synthetic people, independent event times.',
               'limitation': 'No confirmed annual period, phase breakdown, arrival distribution, employee mapping, actual cost or available shifts.',
               'annual_profile': profile.resolved(), 'batches': batches}
    if not include_ongoing:
        fixture.update(mode='frozen_initial_backlog', ongoing_enabled=False,
                       rationale='Source initial stock only; no new annual arrivals. The labelled historical 15/50 interpretation remains unchanged in the profile.')
    requests = expand_batches(fixture)
    validate_requests(requests, topics, full_workflow=True)
    annual = [r for r in requests if r.cohort_id == 'ongoing']
    initial = [r for r in requests if r.cohort_id == 'initial']
    practice = sum(topics[r.topic_id].practice_required for r in annual)
    group_pq = profile.bound_source_values['group_pq_hours']['value'] * MINUTES_PER_HOUR
    theory_minutes = profile.bound_source_values['theory_minutes']['value']
    practice_minutes = profile.bound_source_values['practice_minutes']['value']
    baseline_theory_work = group_count * group_pq + individual_count * theory_minutes
    fixture['annual_summary'] = {
        'group_training_count': group_count,
        'individual_training_count': individual_count,
        'group_size': v['group_size'],
        'practice_required_count': practice,
        'interpreted_group_theory_occurrences': group_count,
        'interpreted_individual_theory_occurrences': individual_count,
        'interpreted_total_theory_occurrences': group_count + individual_count,
        'annual_person_topic_participations': len(annual),
        'annual_unique_synthetic_people': len({r.person_id for r in annual}),
        'annual_practice_required_participations': practice,
        'annual_priority_counts': {str(p): sum(topics[r.topic_id].priority == p for r in annual) for p in (1, 2, 3)},
        'initial_person_topic_records': len(initial),
        'initial_priority_counts': {str(p): sum(topics[r.topic_id].priority == p for r in initial) for p in (1, 2, 3)},
        'rough_baseline_theory_trainer_minutes': baseline_theory_work,
        'rough_annual_individual_practice_trainer_minutes': practice * practice_minutes,
        'rough_baseline_annual_trainer_minutes': baseline_theory_work + practice * practice_minutes,
        'rough_annual_participant_minutes': len(annual) * theory_minutes + practice * practice_minutes,
        'workload_scope': 'Theoretical annual work before calendar constraints, split classes, cancellations or partial horizon. No initial-stock work included. Group P&Q allowance counted once; practice remains individual.',
        'practice_count_limitation': 'Practice demand is derived from synthetic topic draws and source phase flags; Q6 alone does not identify practice counts.',
        'initial_mapping_limitation': 'Initial raw stock stays unchanged. All person IDs are synthetic placeholders; no inference about real internal/external employees.'}
    expected = group_count * v['group_size'] + individual_count
    if len(annual) != expected:
        raise AssertionError('Annual participation count does not reconcile')
    return fixture, requests
