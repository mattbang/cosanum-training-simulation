"""Expand explicit synthetic batch fixtures independently of grouping policy."""
from .domain import Request
from .config import number


def expand_batches(fixture):
    if fixture.get('synthetic') is not True:
        raise ValueError('First slice accepts explicitly synthetic fixtures only')
    requests = []
    ids = set()
    for batch in fixture['batches']:
        identity = batch['batch_id']
        if not identity or identity in ids:
            raise ValueError('Duplicate/empty batch ID')
        ids.add(identity)
        if type(batch['size']) is not int or batch['size'] < 1:
            raise ValueError('Batch size must be a positive integer')
        number(batch['noticed_at'], 'noticed_at')
        people = batch.get('person_ids', [f'synthetic-{identity}-{i+1}' for i in range(batch['size'])])
        if len(people) != batch['size']:
            raise ValueError('Batch size/person mapping mismatch')
        kinds = batch.get('case_kinds', [batch.get('case_kind','training_needed')]*batch['size'])
        if len(kinds) != batch['size']:
            raise ValueError('Batch size/case-kind mismatch')
        for i, person in enumerate(people):
            requests.append(Request(f'{identity}-{i+1}', person, batch['topic_id'], batch['noticed_at'],
                                    identity, identity, cycle_id=batch.get('cycle_id','synthetic-cycle-1'),
                                    cohort_id=batch.get('cohort_id',fixture['cohort_id']), case_kind=kinds[i],
                                    baseline_delivery=batch.get('baseline_delivery')))
    return requests


def validate_requests(requests, topics, full_workflow=False):
    ids, keys = set(), set()
    for r in requests:
        number(r.noticed_at, 'noticed_at')
        if r.need_arises_at is not None:
            number(r.need_arises_at, 'need_arises_at')
            if r.need_arises_at > r.noticed_at:
                raise ValueError('Recognition precedes underlying need')
        if not all(isinstance(x, str) and x for x in (r.request_id, r.person_id, r.topic_id, r.cycle_id, r.arrival_event_id, r.batch_id)):
            raise ValueError('Request identity fields must be nonempty strings')
        if r.topic_id not in topics:
            raise ValueError(f'Unknown topic: {r.topic_id}')
        if r.baseline_delivery not in (None, 'group', 'individual'):
            raise ValueError('Unknown baseline delivery hint')
        if r.baseline_delivery == 'group' and not topics[r.topic_id].theory_group_possible:
            raise ValueError('Baseline group hint contradicts source topic eligibility')
        if r.phase != 'theory' or not topics[r.topic_id].theory_required or r.synthetic is not True:
            raise ValueError('This slice supports synthetic first theory phase only')
        if r.case_kind not in ('training_needed','proof_only') or (r.case_kind == 'proof_only' and not full_workflow):
            raise ValueError('Unsupported case kind for configured scope')
        key = (r.person_id, r.topic_id, r.cycle_id)
        if r.request_id in ids or key in keys:
            raise ValueError('Duplicate request or person-topic-cycle')
        ids.add(r.request_id)
        keys.add(key)


# Demand generation is independent of policy. One batch is one compatible topic.
from dataclasses import dataclass
from math import ceil, log1p, isclose
from .randomness import uniform, categorical


@dataclass(frozen=True)
class DemandSpec:
    mode: str
    horizon: int
    events_per_day: float
    batch_probabilities: tuple
    topic_probabilities: tuple
    internal_pool_size: int
    external_pool_size: int
    proof_only_fraction: float

    def validate(self,topics):
        if self.mode not in ('initial_backlog_clearance','ongoing_stochastic_demand'):
            raise ValueError('Unknown demand mode')
        number(self.horizon,'demand horizon',positive=True)
        number(self.events_per_day,'events/day')
        number(self.proof_only_fraction,'proof-only fraction')
        if self.proof_only_fraction>1:
            raise ValueError('Proof-only fraction outside [0,1]')
        for value in (self.internal_pool_size,self.external_pool_size):
            if type(value) is not int or value<1:
                raise ValueError('Synthetic pools require positive integer sizes')
        for name,pairs in (('batch',self.batch_probabilities),('topic',self.topic_probabilities)):
            if not pairs or len({x for x,_ in pairs})!=len(pairs):
                raise ValueError(f'{name}: empty or duplicate distribution')
            for key,p in pairs:
                number(p,f'{name} probability')
                if name=='batch' and (type(key) is not int or key<1 or key>self.internal_pool_size+self.external_pool_size):
                    raise ValueError('Batch size exceeds synthetic pool or is invalid')
                if name=='topic' and key not in topics:
                    raise ValueError('Unknown demand topic')
            if not isclose(sum(p for _,p in pairs),1,abs_tol=1e-12,rel_tol=0):
                raise ValueError(f'{name} probabilities must sum to one')
        if self.mode=='initial_backlog_clearance' and any(t.open_records>self.internal_pool_size+self.external_pool_size for t in topics.values()):
            raise ValueError('Synthetic pools too small for unique person-topic backlog mapping')
        return self


def synthetic_people(spec):
    return ([f'synthetic-internal-{i+1:03d}' for i in range(spec.internal_pool_size)] +
            [f'synthetic-external-{i+1:03d}' for i in range(spec.external_pool_size)])


def generate_fixture(spec,topics,seeds):
    spec.validate(topics)
    pool = synthetic_people(spec)
    batches = []
    def add(identity,topic,time,size,cohort):
        people = sorted(pool,key=lambda person:(uniform(seeds['person_assignment'],identity,person),person))[:size]
        kinds = ['proof_only' if uniform(seeds['case_kind'],identity,i)<spec.proof_only_fraction else 'training_needed' for i in range(size)]
        batches.append(dict(batch_id=identity,topic_id=topic,noticed_at=time,size=size,person_ids=people,
                            case_kinds=kinds,cohort_id=cohort,cycle_id=identity))
    if spec.mode=='initial_backlog_clearance':
        for topic in sorted(topics):
            count = topics[topic].open_records
            if count:
                add(f'initial-{topic}',topic,0,count,'initial')
    elif spec.events_per_day:
        time,index = 0,0
        while True:
            identity = f'arrival-{index:06d}'
            # Exponential gaps discretised upwards to whole elapsed minutes.
            time += max(1,ceil(-log1p(-uniform(seeds['detection'],identity))*1440/spec.events_per_day))
            if time>spec.horizon:
                break
            topic = categorical(seeds['topic_assignment'],(identity,),*[tuple(x) for x in zip(*spec.topic_probabilities)])
            size = categorical(seeds['batch_size'],(identity,),*[tuple(x) for x in zip(*spec.batch_probabilities)])
            add(identity,topic,time,size,'ongoing')
            index += 1
    return dict(fixture_id='generated-demand-v1',synthetic=True,cohort_id='generated',mode=spec.mode,
                source_status='assumption',value_kind='synthetic_mapping_and_arrivals',unit='elapsed_minutes_and_person_topic_records',
                rationale='Source stock only in frozen mode; independent assumed intensity in ongoing mode',
                limitation='Synthetic identities, cycles and proof mix; no real roster or measured arrivals',batches=batches)
