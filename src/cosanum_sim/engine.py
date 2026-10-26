"""One deterministic event clock for queue-only and complete-workflow experiments."""
from dataclasses import dataclass, replace
from .domain import Outcome, Session, WorkItem
from .demand import validate_requests
from .policies import Candidate, candidates, RecoveryQueue
from .scheduler import Scheduler
from .randomness import uniform


@dataclass
class Result:
    outcomes: list
    sessions: list
    events: list
    breaches: list
    horizon: float
    work_items: list
    full_workflow: bool


def simulate(requests, topics, config):
    config.validate(topics)
    workflow = config.workflow
    learning = workflow.learning if workflow else None
    validate_requests(requests,topics,workflow is not None)
    structural = {r.resource_id for r in config.resources if r.role!='participant'}
    if structural.intersection(r.person_id for r in requests):
        raise ValueError('Participant identities collide with trainer/room identities')
    by_request = {r.request_id:r for r in requests}
    if workflow:
        for trigger in workflow.cancellations:
            r = by_request.get(trigger.request_id)
            if r is None or r.case_kind=='proof_only' or (trigger.phase=='practice' and not topics[r.topic_id].practice_required):
                raise ValueError('Cancellation references missing request or required phase')
    outcomes = [Outcome(r,r.noticed_at+config.max_wait if config.deadline_enabled and r.case_kind!='proof_only' else None)
                for r in sorted(requests,key=lambda r:(r.noticed_at,r.request_id))]
    lookup = {o.request.request_id:o for o in outcomes}
    sessions,events,breaches,work_items = [],[],[],[]
    recovery_bookings = 0
    now = 0

    def log(kind,**fields):
        events.append(dict(sequence=len(events),time=now,type=kind,**fields))

    def add_work(out,phase,learning_attempt=1):
        if phase=='practice' and config.joined_scheduling:
            existing = next((w for w in work_items if w.request.request_id==out.request.request_id
                             and w.phase=='practice' and w.state in ('blocked','awaiting_prerequisite')),None)
            if existing is not None:
                existing.ready_at,existing.eligible_at = now,now+config.planning_delay
                existing.state = 'reserved' if existing.session_id else 'waiting'
                out.state = 'reserved' if existing.session_id else 'waiting'
                if existing.session_id:
                    out.session_id = existing.session_id
                log('phase_ready',request_id=out.request.request_id,work_item_id=existing.work_item_id,
                    phase=phase,ready_at=now,eligible_at=existing.eligible_at)
                log('joined_follow_up_activated',request_id=out.request.request_id,
                    work_item_id=existing.work_item_id,session_id=existing.session_id,
                    prerequisite_session_id=existing.prerequisite_session_id)
                return
        suffix = f':retry-{learning_attempt-1}' if phase=='self_learning' and learning_attempt>1 else ''
        w = WorkItem(f'{out.request.request_id}:{phase}{suffix}',out.request,phase,now,
                     out.deadline_at if phase in ('theory','self_learning') and out.first_start is None else None,
                     eligible_at=now+config.planning_delay,learning_attempt=learning_attempt)
        work_items.append(w)
        out.state = 'proof_pending' if phase=='proof' else 'waiting'
        log('phase_ready',request_id=out.request.request_id,work_item_id=w.work_item_id,phase=phase,ready_at=now,eligible_at=w.eligible_at)

    def dimensions(phase,count):
        if phase=='self_learning':
            return learning.study_minutes,0,0
        if phase=='assessment':
            return learning.assessment_minutes+learning.support_minutes,0,0
        if phase=='practice':
            return workflow.practice_duration,workflow.coordination_minutes,0
        if phase=='proof':
            return workflow.proof_recovery_duration,0,0
        return config.duration, (workflow.preparation if count>1 else workflow.coordination_minutes) if workflow else 0, workflow.follow_up if workflow and count>1 else 0

    def needs_urgency_review(w):
        # Annual historical hints describe already formed delivery occurrences;
        # the IST collecting review still applies to unhinted source stock.
        formed = config.use_baseline_delivery and w.request.baseline_delivery in ('group','individual')
        return w.phase=='theory' and not w.urgent_release and not formed

    def plan(waiting):
        scheduler = Scheduler(config.resources,sessions,event_history_only=True,absence_limit=config.participant_absence_limit)
        plans = []
        def find(members,latest,deadline):
            phase = members[0].phase
            duration,prep,post = dimensions(phase,len(members))
            people = [w.request.person_id for w in members] if phase!='proof' else []
            return scheduler.find(members[0].request.topic_id,people,now,duration,deadline,latest,phase,prep,post)
        choices = candidates(waiting,topics,config,now)
        if config.phase_allocation=='recover_after_infeasible_start':
            protected, recovery = [], []
            def first_deadline(w):
                # A cancelled delivery retains its first-start clock. Retrying
                # that work is competence recovery, not another initial start.
                return w.deadline_at if lookup[w.request.request_id].first_start is None else None
            # Hold latest physically feasible starts, rather than reserving
            # unnecessary early slots ahead of ready practice/assessment.
            # No late slot is held in this pass: infeasible work joins recovery.
            for candidate in choices:
                members = candidate.members
                deadlines = [first_deadline(w) for w in members if first_deadline(w) is not None]
                if not deadlines:
                    recovery.append(candidate)
                    continue
                slot = find(members,True,min(deadlines))
                if slot:
                    scheduler.reserve(slot)
                    protected.append((members,candidate.reason,slot))
                    continue
                individual_slots = [find((w,),True,first_deadline(w)) if first_deadline(w) is not None else None
                                    for w in members]
                if len(members)>1 and any(individual_slots):
                    # The group cannot meet its earliest deadline. Protect each
                    # feasible individual in deadline order, using actual busy
                    # calendars after each reservation; all others recover.
                    for w in sorted(members,key=lambda w:(first_deadline(w) if first_deadline(w) is not None else float('inf'),
                                                         w.request.noticed_at,w.request.request_id)):
                        single = find((w,),True,first_deadline(w)) if first_deadline(w) is not None else None
                        if single:
                            scheduler.reserve(single)
                            protected.append(((w,),'resource_individual_fallback',single))
                        else:
                            recovery.append(Candidate((w,),'resource_individual_fallback',False))
                else:
                    recovery.append(candidate)
            pending = RecoveryQueue(recovery,topics,config,now)
            # Count only appointments that can actually be committed at this
            # event time. Far-future provisional plans never spend a fairness
            # turn, since a later event may change those plans completely.
            planned_recovery_bookings = recovery_bookings
            while pending:
                candidate,allocation = pending.pop(planned_recovery_bookings)
                members = candidate.members
                slot = find(members,False,None)
                if slot:
                    scheduler.reserve(slot)
                    if slot.preparation_start==now:
                        planned_recovery_bookings += 1
                    plans.append((members,allocation+candidate.reason,slot))
                elif len(members)>1:
                    # A late group may have no common future slot, while
                    # individual participants remain physically schedulable.
                    for w in members:
                        single = find((w,),False,None)
                        if single:
                            scheduler.reserve(single)
                            if single.preparation_start==now:
                                planned_recovery_bookings += 1
                        plans.append(((w,),allocation+'resource_individual_fallback',single))
                else:
                    plans.append((members,allocation+candidate.reason,None))
            # Move protected starts into unused earlier gaps. All other held
            # slots remain occupied during each move, so no successful deadline
            # reservation or recovery work is displaced. With no ready later
            # phases this returns an ordinary early start, not an artificial wait.
            for index,(members,reason,slot) in enumerate(protected):
                scheduler = Scheduler(config.resources,sessions,event_history_only=True,absence_limit=config.participant_absence_limit)
                for j,(_,_,other) in enumerate(protected):
                    if j!=index:
                        scheduler.reserve(other)
                for _,_,other in plans:
                    if other:
                        scheduler.reserve(other)
                deadline = min(first_deadline(w) for w in members if first_deadline(w) is not None)
                earlier = find(members,False,deadline)
                if earlier is None:
                    raise AssertionError('Protected feasible start lost during recovery planning')
                protected[index] = (members,reason,earlier)
            return protected+plans
        for candidate in choices:
            members = candidate.members
            deadlines = [w.deadline_at for w in members if w.deadline_at is not None]
            deadline = min(deadlines) if deadlines else None
            slot = find(members,candidate.latest,deadline)
            late_group = find(members,False,None) if slot is None else None
            recoverable = any(find((w,),candidate.latest,w.deadline_at) is not None for w in members) if slot is None and deadline is not None else False
            if slot is None and deadline is not None and len(members)>1 and (recoverable or late_group is None):
                for w in members:
                    single = find((w,),candidate.latest,w.deadline_at) or find((w,),False,None)
                    if single:
                        scheduler.reserve(single)
                    plans.append(((w,),'resource_individual_fallback',single))
            else:
                slot = slot or late_group
                if slot:
                    scheduler.reserve(slot)
                plans.append((members,candidate.reason,slot))
        return plans

    def start(w,session):
        out = lookup[w.request.request_id]
        w.state = 'training'
        if w.first_start is None:
            w.first_start = now
        if w.phase!='proof' and out.first_start is None:
            out.first_start = now
        out.state = 'proof_pending' if w.phase=='proof' else 'training'
        log('start',request_id=w.request.request_id,work_item_id=w.work_item_id,session_id=session.session_id,phase=w.phase)

    def commit(members,reason,slot,blocked=False):
        nonlocal recovery_bookings
        identity = f'session-{len(sessions)+1:04d}'
        for w in members:
            w.attempt += 1
            if workflow:
                for trigger in workflow.cancellations:
                    if (trigger.request_id,trigger.phase,trigger.attempt)==(w.request.request_id,w.phase,w.attempt) and trigger.minutes_after_booking>=slot.end-now:
                        raise ValueError('Cancellation must occur before delivery completion')
        session = Session(identity,members[0].request.topic_id,members[0].phase,
                          tuple(w.request.request_id for w in members),slot.people,reason,
                          min(w.ready_at for w in members) if blocked else now,now,
                          slot.start,slot.end,slot.trainer_id,slot.room_id,slot.preparation_start,slot.work_end,
                          work_item_ids=tuple(w.work_item_id for w in members))
        sessions.append(session)
        if reason.startswith('recovery_'):
            recovery_bookings += 1
        log('reservation',session_id=identity,request_ids=session.request_ids,phase=session.phase,
            attempts={w.work_item_id:w.attempt for w in members},actual_start_planned=slot.start,reason=reason,
            selection_policy=(config.phase_allocation if config.phase_allocation!='legacy' else
                              ('deadline_urgency_ageing_priority' if config.priority else 'deadline_age_neutral_tie')))
        for w in members:
            w.state,w.session_id = ('blocked' if blocked else 'reserved'),identity
            if blocked:
                continue
            out = lookup[w.request.request_id]
            out.session_id = identity
            out.state = 'reserved' if w.phase!='proof' else 'proof_pending'
            if slot.start==now:
                start(w,session)
        return session

    def join_follow_ups(theory,members,plans):
        practice_members = [w for w in members if topics[w.request.topic_id].practice_required]
        if not practice_members:
            return
        scheduler = Scheduler(config.resources,sessions,event_history_only=True,absence_limit=config.participant_absence_limit)
        current_ids = {w.work_item_id for w in members}
        # Already-known feasible initial deadlines retain their held slots.
        # Future, unknown demand is never treated as known at booking time.
        for others,_,slot in plans:
            if slot and not current_ids.intersection(w.work_item_id for w in others):
                deadlines = [w.deadline_at for w in others
                             if lookup[w.request.request_id].first_start is None and w.deadline_at is not None]
                if deadlines and slot.start<=min(deadlines):
                    scheduler.reserve(slot)
        slots = scheduler.find_follow_ups(theory.topic_id,[w.request.person_id for w in practice_members],
                                         theory.end+config.planning_delay,workflow.practice_duration,config.horizon,
                                         preparation=workflow.coordination_minutes)
        if slots is None:
            log('joined_follow_up_escalation',theory_session_id=theory.session_id,
                request_ids=tuple(w.request.request_id for w in practice_members),
                reason='no_complete_chain_within_observation_horizon',
                decision='retain_first_start_and_use_normal_follow_up_queue',
                completion_limit=config.horizon,partial_reservations_committed=0)
            return
        follow_ups = []
        for original,slot in zip(practice_members,slots):
            w = next((item for item in work_items if item.request.request_id==original.request.request_id
                      and item.phase=='practice' and item.state=='awaiting_prerequisite'),None)
            if w is None:
                w = WorkItem(f'{original.request.request_id}:practice',original.request,'practice',theory.end,None,
                             eligible_at=theory.end+config.planning_delay)
                work_items.append(w)
            w.ready_at,w.eligible_at = theory.end,theory.end+config.planning_delay
            w.prerequisite_session_id = theory.session_id
            w.planned_start = slot.start
            follow_ups.append(commit((w,),'joined_follow_up',slot,blocked=True))
        log('joined_bundle_reserved',theory_session_id=theory.session_id,
            request_ids=tuple(w.request.request_id for w in practice_members),
            practice_session_ids=tuple(s.session_id for s in follow_ups),
            practice_starts={s.request_ids[0]:s.start for s in follow_ups},completion_limit=config.horizon)

    while True:
        session_members = {}
        for w in work_items:
            if w.session_id is not None:
                session_members.setdefault(w.session_id,[]).append(w)
        # Cancellations win ties with delivery start, then completions and arrivals.
        for index,session in enumerate(sessions):
            members = session_members.get(session.session_id,[])
            if not members:
                continue
            cancellation_times = []
            if workflow and workflow.cancellations and session.cancelled_at is None:
                for w in members:
                    for trigger in workflow.cancellations:
                        if (trigger.request_id,trigger.phase,trigger.attempt)==(w.request.request_id,w.phase,w.attempt):
                            cancellation_times.append(session.reservation_at+trigger.minutes_after_booking)
            if cancellation_times and min(cancellation_times)==now:
                session = replace(session,cancelled_at=now)
                sessions[index] = session
                for w in members:
                    blocked = w.state=='blocked'
                    w.state,w.session_id = ('awaiting_prerequisite' if blocked else 'waiting'),None
                    w.eligible_at = now+config.planning_delay
                    if not blocked:
                        lookup[w.request.request_id].state = 'waiting'
                log('cancelled',session_id=session.session_id,request_ids=session.request_ids,reason='scripted_session_cancellation')
                if config.joined_scheduling and session.phase=='theory':
                    dependents = [w for w in work_items if w.prerequisite_session_id==session.session_id]
                    for w in dependents:
                        if w.session_id is not None:
                            index_follow = next(i for i,s in enumerate(sessions) if s.session_id==w.session_id)
                            follow = sessions[index_follow]
                            if follow.cancelled_at is None:
                                if follow.start<now:
                                    raise AssertionError('Dependent practice started before theory completion')
                                sessions[index_follow] = replace(follow,cancelled_at=now)
                                log('cancelled',session_id=follow.session_id,request_ids=follow.request_ids,
                                    reason='joined_prerequisite_cancelled',prerequisite_session_id=session.session_id)
                        w.state,w.session_id,w.prerequisite_session_id = 'awaiting_prerequisite',None,None
                continue
            if session.cancelled_at is not None:
                continue
            for w in members:
                out = lookup[w.request.request_id]
                if w.state=='reserved' and session.start<=now:
                    start(w,session)
                if w.state=='training' and session.end<=now:
                    w.state,w.completed_at = 'complete',session.end
                    log('phase_complete',request_id=w.request.request_id,work_item_id=w.work_item_id,session_id=session.session_id,phase=w.phase)
                    if w.phase=='self_learning':
                        if learning.assessment_mode=='expert':
                            add_work(out,'assessment')
                            continue
                        passed = uniform(learning.seed,w.request.request_id,w.request.cycle_id,
                                         'automated-lms-v1',w.learning_attempt)<learning.pass_probability
                        retry = not passed and w.learning_attempt<=learning.max_self_retries
                        decision = ('equivalent_theory_accepted' if passed else
                                    ('self_learning_retry' if retry else 'instructor_theory_required'))
                        log('assessment_result',request_id=w.request.request_id,passed=passed,
                            mode='automated',learning_attempt=w.learning_attempt,decision=decision)
                        if not passed:
                            if retry:
                                add_work(out,'self_learning',w.learning_attempt+1)
                                log('self_learning_retry_ready',request_id=w.request.request_id,
                                    learning_attempt=w.learning_attempt+1,
                                    original_noticed_at=out.request.noticed_at,
                                    original_deadline_at=out.deadline_at)
                            else:
                                add_work(out,'theory')
                                work_items[-1].learning_fallback = True
                            continue
                    if w.phase=='assessment':
                        passed = uniform(learning.seed,w.request.request_id,w.request.cycle_id)<learning.pass_probability
                        log('assessment_result',request_id=w.request.request_id,passed=passed,
                            decision='equivalent_theory_accepted' if passed else 'instructor_theory_required')
                        if not passed:
                            add_work(out,'theory')
                            work_items[-1].learning_fallback = True
                            continue
                    if w.phase in ('theory','assessment','self_learning'):
                        out.phase_completed_at = session.end
                    if workflow is None:
                        out.state = 'phase_complete'
                    elif w.phase in ('theory','assessment','self_learning') and topics[w.request.topic_id].practice_required:
                        add_work(out,'practice')
                    else:
                        if w.phase!='proof':
                            out.training_completed_at = session.end
                        # Group follow-up includes administration; proof lag is passive.
                        required_work_end = max(s.work_end for s in sessions if out.request.request_id in s.request_ids and s.cancelled_at is None)
                        out.proof_due_at = required_work_end+workflow.proof_delay
                        out.state = 'proof_pending'
        for out in outcomes:
            if out.state=='not_arrived' and out.request.noticed_at<=now:
                log('arrival',request_id=out.request.request_id,batch_id=out.request.batch_id,deadline_at=out.deadline_at)
                available = learning and out.request.topic_id in learning.topic_ids and dict(learning.topic_ready_at).get(out.request.topic_id,0)<=now
                phase = 'proof' if out.request.case_kind=='proof_only' else ('self_learning' if available else 'theory')
                if learning and out.request.topic_id in learning.topic_ids and not available:
                    log('lms_course_not_ready',request_id=out.request.request_id,
                        course_ready_at=dict(learning.topic_ready_at)[out.request.topic_id],decision='retain_instructor_route_until_course_ready')
                add_work(out,phase)
            if out.proof_due_at is not None and out.proof_completed_at is None and out.proof_due_at<=now:
                out.proof_completed_at = now
                out.state = 'proof_complete'
                log('proof_complete',request_id=out.request.request_id,creates_competence=False)
        if learning and learning.topic_ready_at:
            ready=dict(learning.topic_ready_at)
            for w in work_items:
                if w.state=='waiting' and w.phase=='theory' and not w.learning_fallback and w.request.topic_id in ready and ready[w.request.topic_id]<=now:
                    original=w.work_item_id
                    w.phase='self_learning';w.work_item_id=f'{w.request.request_id}:self_learning'
                    w.eligible_at=max(w.eligible_at,ready[w.request.topic_id])
                    log('lms_course_ready_route_change',request_id=w.request.request_id,
                        original_work_item_id=original,work_item_id=w.work_item_id,
                        original_noticed_at=w.request.noticed_at,original_phase_ready_at=w.ready_at,
                        original_deadline_at=lookup[w.request.request_id].deadline_at,
                        course_ready_at=ready[w.request.topic_id])
        waiting = [w for w in work_items if w.state=='waiting']
        if config.urgency_review is not None:
            review = config.urgency_review
            for w in waiting:
                if needs_urgency_review(w) and w.request.noticed_at+(w.review_count+1)*review.interval_minutes<=now:
                    w.review_count = int((now-w.request.noticed_at)//review.interval_minutes)
                    w.urgent_release = uniform(review.seed,w.request.request_id,w.review_count)<review.urgent_probability
                    log('urgency_review',request_id=w.request.request_id,review_number=w.review_count,
                        urgent=w.urgent_release,decision='release_individual' if w.urgent_release else 'continue_waiting',
                        original_noticed_at=w.request.noticed_at)
        plans = plan([w for w in waiting if w.eligible_at<=now])
        for w in waiting:
            w.planned_start = None
        replan_after_join = False
        for members,reason,slot in plans:
            for w in members:
                w.planned_start = slot.start if slot else None
                if w.phase in ('theory','self_learning') and lookup[w.request.request_id].first_start is None:
                    lookup[w.request.request_id].planned_start = w.planned_start
            if slot and slot.preparation_start==now:
                session = commit(members,reason,slot)
                if config.joined_scheduling and session.phase=='theory':
                    join_follow_ups(session,members,plans)
                    # Future practice is now really occupied. Recompute every
                    # other choice rather than commit stale provisional slots.
                    replan_after_join = True
                    break
        for out in outcomes:
            if out.deadline_at is not None and out.deadline_at<=now and not out.escalated and (out.first_start is None or out.first_start>out.deadline_at):
                out.escalated = True
                breach = dict(request_id=out.request.request_id,deadline_at=out.deadline_at,escalation_at=now,
                              planned_start_at_escalation=out.planned_start,cause='no_timely_slot_in_greedy_resource_plan')
                breaches.append(breach)
                log('deadline_breach_escalation',**breach)
        if now==config.horizon:
            break
        if replan_after_join:
            continue
        future = [config.horizon]
        if learning and learning.topic_ready_at:
            ready=dict(learning.topic_ready_at)
            future.extend(ready[w.request.topic_id] for w in work_items
                          if w.state=='waiting' and w.phase=='theory' and not w.learning_fallback
                          and w.request.topic_id in ready and ready[w.request.topic_id]>now)
        future.extend(o.request.noticed_at for o in outcomes if o.state=='not_arrived' and o.request.noticed_at>now)
        future.extend(o.proof_due_at for o in outcomes if o.proof_due_at is not None and o.proof_completed_at is None and o.proof_due_at>now)
        for s in sessions:
            if s.cancelled_at is None:
                future.extend(t for t in (s.start,s.end,s.work_end) if t>now)
                if workflow and workflow.cancellations:
                    for w in work_items:
                        if w.session_id==s.session_id:
                            future.extend(s.reservation_at+t.minutes_after_booking for t in workflow.cancellations
                                          if (t.request_id,t.phase,t.attempt)==(w.request.request_id,w.phase,w.attempt)
                                          and s.reservation_at+t.minutes_after_booking>=now and w.state!='complete')
        future.extend(w.eligible_at for w in work_items if w.state=='waiting' and w.eligible_at>now)
        if config.priority is not None:
            future.extend(w.ready_at+config.priority.ageing_minutes for w in work_items
                          if w.state=='waiting' and w.ready_at+config.priority.ageing_minutes>now)
        if config.urgency_review is not None:
            future.extend(w.request.noticed_at+(w.review_count+1)*config.urgency_review.interval_minutes
                          for w in work_items if w.state=='waiting' and needs_urgency_review(w))
        future.extend(slot.preparation_start for _,_,slot in plans if slot and slot.preparation_start>now)
        future.extend(o.deadline_at for o in outcomes if o.deadline_at is not None and o.deadline_at>now and o.first_start is None)
        now = min(future)
    for breach in breaches:
        out = lookup[breach['request_id']]
        breach.update(actual_start=out.first_start,resolved_at=out.first_start)
    return Result(outcomes,sessions,events,breaches,config.horizon,work_items,workflow is not None)
