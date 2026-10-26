"""Grouping eligibility and preference remain separate from scheduling."""
from dataclasses import dataclass
from collections import defaultdict
from ..randomness import uniform


@dataclass(frozen=True)
class Candidate:
    members: tuple
    reason: str
    latest: bool


def candidates(waiting, topics, config, now=0):
    def age_key(out):
        tie = uniform(config.selection_seed,out.request.request_id) if config.selection_seed is not None else 0
        return out.request.noticed_at,tie,out.request.request_id
    queues = defaultdict(list)
    for out in waiting:
        hint = (getattr(out.request,'baseline_delivery',None) if config.use_baseline_delivery
                and out.phase=='theory' and not out.learning_fallback else None)
        # Historical groups are already formed batches. Never merge two such
        # batches, or put a historically individual need into their queue.
        routing = 'group:'+out.request.batch_id if hint=='group' else ('individual' if hint=='individual' else '')
        queues[(out.request.topic_id, out.phase, routing)].append(out)
    result = []
    for key in sorted(queues):
        queue = sorted(queues[key], key=age_key)
        historical_group = key[2].startswith('group:')
        grouped = (key[1] == 'theory' and topics[key[0]].theory_group_possible and key[2]!='individual'
                   and (historical_group or (config.group_preferred and (config.grouping_topics is None or key[0] in config.grouping_topics))))
        released = [w for w in queue if w.learning_fallback or w.urgent_release or
                    (config.phase_allocation=='legacy' and config.priority is not None
                     and now-w.ready_at>=config.priority.ageing_minutes)]
        result.extend(Candidate((w,), 'instructor_theory_fallback' if w.learning_fallback else ('urgency_review_individual' if w.urgent_release else 'ageing_individual'), False) for w in released)
        released_ids = {w.work_item_id for w in released}
        queue = [w for w in queue if w.work_item_id not in released_ids]
        while queue:
            if not grouped:
                size, reason, latest = 1, 'individual', False
            elif historical_group:
                size, reason, latest = config.capacity, 'historical_group_batch', False
            elif len(queue) >= config.threshold:
                size, reason, latest = config.target or config.capacity, 'threshold', False
            elif config.deadline_enabled:
                size, reason, latest = config.capacity, 'deadline_fallback', True
            else:
                break
            # One modelled person cannot occupy two seats in a session.
            members, people = [], set()
            for out in queue:
                if out.request.person_id not in people and len(members) < size:
                    members.append(out)
                    people.add(out.request.person_id)
            if reason == 'threshold' and len(members) < config.threshold:
                if not config.deadline_enabled:
                    break
                reason, latest = 'deadline_fallback', True
            result.append(Candidate(tuple(members), reason, latest))
            chosen = {o.request.request_id for o in members}
            queue = [o for o in queue if o.request.request_id not in chosen]
    def selection_key(candidate):
        if config.priority is None:
            return (min(w.deadline_at if w.deadline_at is not None else float('inf') for w in candidate.members),
                    min(age_key(w) for w in candidate.members))
        policy = config.priority
        imminent = [w.deadline_at for w in candidate.members if w.deadline_at is not None and w.deadline_at-now<=policy.imminent_minutes]
        urgent = any(w.urgent_release for w in candidate.members)
        aged = any(now-w.ready_at>=policy.ageing_minutes for w in candidate.members)
        tier = 0 if imminent or urgent else (1 if aged else 2)
        # Within protected work, earlier deadlines precede ageing and ordinary priority.
        priority_key = (tier,min(imminent,default=float('inf')) if tier==0 else 0,
                        0 if aged else min(topics[w.request.topic_id].priority for w in candidate.members),
                        min(w.ready_at for w in candidate.members) if aged else 0,
                        min(age_key(w) for w in candidate.members))
        hard_deadlines = [w.deadline_at for w in candidate.members if w.deadline_at is not None]
        # Protect known hard-deadline slots even when a weekend lies outside the
        # nominal urgency window. Priority must not consume those reserved slots.
        return (0,min(hard_deadlines),priority_key) if hard_deadlines else (1,float('inf'),priority_key)
    return sorted(result,key=selection_key)


def recovery_order(candidate, topics, config, now):
    """Order unprotected work after feasible first-start slots have been held.

    Priority one whole-workflow progress precedes lower-priority work, and
    downstream phases precede new starts within a priority. The engine applies
    the explicit aged-work reservation share separately, so a simultaneously
    ageing stock cannot erase whole-workflow priority. No clock is changed.
    """
    members = candidate.members
    phase_rank = {'proof':0, 'practice':1, 'assessment':2, 'theory':3, 'self_learning':4}
    return (min(topics[w.request.topic_id].priority for w in members),
            min(phase_rank[w.phase] for w in members), min(w.ready_at for w in members),
            min(w.request.request_id for w in members))


class RecoveryQueue:
    """Stable recovery/fairness selection without rescanning every waiting case.

    Eligibility is fixed during one plan() call: readiness, priority and now
    do not change while tentative slots are allocated. The sorted index keeps
    the previous stable min() tie order, including identical fairness keys.
    """
    def __init__(self, choices, topics, config, now):
        from heapq import heapify
        self.pending = sorted(choices,key=lambda c:recovery_order(c,topics,config,now))
        self.active = [True]*len(self.pending)
        self.remaining = len(self.pending)
        self.next_priority = 0
        self.every = config.recovery_aged_every
        self.aged = [(min(w.ready_at for w in c.members),
                      min(w.request.request_id for w in c.members),index)
                     for index,c in enumerate(self.pending)
                     if min(topics[w.request.topic_id].priority for w in c.members)>1
                     and any(now-w.ready_at>=config.priority.ageing_minutes for w in c.members)]
        heapify(self.aged)

    def __bool__(self):
        return bool(self.remaining)

    def pop(self, planned_bookings):
        from heapq import heappop
        if not self.remaining:
            raise IndexError('Empty recovery queue')
        while self.aged and not self.active[self.aged[0][2]]:
            heappop(self.aged)
        fairness_turn = (planned_bookings+1)%self.every==0 and bool(self.aged)
        if fairness_turn:
            index = heappop(self.aged)[2]
            allocation = 'recovery_aged:'
        else:
            while not self.active[self.next_priority]:
                self.next_priority += 1
            index = self.next_priority
            self.next_priority += 1
            allocation = 'recovery_priority:'
        self.active[index] = False
        self.remaining -= 1
        return self.pending[index],allocation
