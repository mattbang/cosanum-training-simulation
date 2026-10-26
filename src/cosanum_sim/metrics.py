"""Distinct phase, training and proof metrics, with censored work retained."""
from .scheduler import occupied_intervals
from .costs import elapsed


def summarize(result,topics):
    arrived = [o for o in result.outcomes if o.request.noticed_at<=result.horizon]
    complete = [o for o in arrived if o.phase_completed_at is not None]
    started = [o for o in arrived if o.first_start is not None]
    waiting = [o for o in arrived if o.first_start is None and o.request.case_kind!='proof_only']
    due = [o for o in arrived if o.deadline_at is not None and o.deadline_at<=result.horizon]
    timely = [o for o in due if o.first_start is not None and o.first_start<=o.deadline_at]
    priority1 = [o for o in arrived if topics[o.request.topic_id].priority==1 and o.request.case_kind!='proof_only']
    def clearance(cohort,field):
        return max(getattr(o,field) for o in cohort) if cohort and all(getattr(o,field) is not None for o in cohort) else None
    states = {state:sum(o.state==state for o in arrived) for state in sorted({o.state for o in arrived})}
    delivery = lambda s: elapsed(s.start,s.end,result.horizon,s.cancelled_at)
    return dict(scope='synthetic full training/proof workflow' if result.full_workflow else 'synthetic first theory phase only',
                arrived=len(arrived),phase_completed=len(complete),training=sum(o.state=='training' for o in arrived),
                waiting=sum(o.state=='waiting' for o in arrived),unstarted_training_requests=len(waiting),
                sessions=len(result.sessions),request_states=states,
                reconciliation_ok=sum(states.values())==len(arrived),
                training_completed=sum(o.training_completed_at is not None for o in arrived),
                proof_completed=sum(o.proof_completed_at is not None for o in arrived),
                proof_only_cases=sum(o.request.case_kind=='proof_only' for o in arrived),
                due_cases=len(due),on_time_due_starts=len(timely),deadline_service=len(timely)/len(due) if due else None,
                breach_count=len(result.breaches),
                mean_wait_started_minutes=sum(o.first_start-o.request.noticed_at for o in started)/len(started) if started else None,
                max_unstarted_age_minutes=max((result.horizon-o.request.noticed_at for o in waiting),default=None),
                priority1_phase_clearance_minutes=clearance(priority1,'phase_completed_at'),
                priority1_training_clearance_minutes=clearance(priority1,'training_completed_at'),
                priority1_proof_clearance_minutes=clearance(priority1,'proof_completed_at'),
                trainer_delivery_minutes=sum(delivery(s) for s in result.sessions if s.trainer_id and s.phase!='proof'),
                participant_delivery_minutes=sum(delivery(s)*len(s.person_ids) for s in result.sessions),
                trainer_total_work_minutes=sum(elapsed(s.preparation_start,s.work_end,result.horizon,s.cancelled_at) for s in result.sessions if s.trainer_id),
                lms_started=sum(s.phase=='self_learning' for s in result.sessions),
                lms_assessments_passed=sum(e['type']=='assessment_result' and e['passed'] for e in result.events),
                lms_instructor_fallbacks=sum(e['type']=='assessment_result' and
                                            e.get('decision')=='instructor_theory_required' for e in result.events),
                pq_group_work_minutes=sum(elapsed(s.preparation_start,s.work_end,result.horizon,s.cancelled_at) for s in result.sessions if s.phase=='theory' and len(s.request_ids)>1),
                cancelled_sessions=sum(s.cancelled_at is not None for s in result.sessions))


def assert_invariants(result,topics,config):
    busy = {}
    for s in result.sessions:
        assert 1<=len(s.request_ids)<=config.capacity
        assert len(set(s.person_ids))==len(s.person_ids)
        if len(s.request_ids)>1:
            assert s.phase=='theory' and topics[s.topic_id].theory_group_possible
        assert s.preparation_start<=s.start<s.end<=s.work_end
        if s.reason=='joined_follow_up':
            assert config.joined_scheduling and s.reservation_at<=s.release_at<=s.preparation_start
        else:
            assert s.reservation_at==s.preparation_start
        for identity,a,b in occupied_intervals(s):
            intervals = busy.setdefault(identity,[])
            assert all(b<=x or a>=y for x,y in intervals),identity
            intervals.append((a,b))
    assert summarize(result,topics)['reconciliation_ok']
    for w in result.work_items:
        successful = [s for s in result.sessions if w.work_item_id in s.work_item_ids and s.cancelled_at is None]
        assert len(successful)<=1
        if w.first_start is not None:
            assert w.first_start>=w.ready_at>=w.request.noticed_at
        if w.phase=='practice':
            out = next(o for o in result.outcomes if o.request.request_id==w.request.request_id)
            if w.state in ('blocked','awaiting_prerequisite'):
                assert config.joined_scheduling and w.first_start is None
            else:
                assert out.phase_completed_at is not None and w.ready_at>=out.phase_completed_at
            if w.prerequisite_session_id is not None:
                prerequisite = next(s for s in result.sessions if s.session_id==w.prerequisite_session_id)
                assert prerequisite.phase=='theory' and prerequisite.cancelled_at is None
                assert w.request.request_id in prerequisite.request_ids
                assert w.ready_at>=prerequisite.end
                if w.first_start is not None:
                    assert w.first_start>=prerequisite.end+config.planning_delay
    for out in result.outcomes:
        assert out.escalated==(out.deadline_at is not None and out.deadline_at<=result.horizon and (out.first_start is None or out.first_start>out.deadline_at))
        if out.request.case_kind=='proof_only':
            assert out.first_start is None and out.training_completed_at is None
        elif out.proof_completed_at is not None:
            assert out.training_completed_at is not None and out.proof_completed_at>=out.training_completed_at


def need_time(request):
    return request.need_arises_at if request.need_arises_at is not None else request.noticed_at


def cohort_metrics(result,topics):
    """Common true-need denominators, including cases not yet recognised."""
    cohorts = {}
    for cohort in sorted({o.request.cohort_id for o in result.outcomes}):
        underlying = [o for o in result.outcomes if o.request.cohort_id==cohort and need_time(o.request)<=result.horizon]
        needed = [o for o in underlying if o.request.case_kind=='training_needed']
        p1 = [o for o in needed if topics[o.request.topic_id].priority==1]
        def clear(rows):
            return max(o.training_completed_at for o in rows) if rows and all(o.training_completed_at is not None for o in rows) else None
        cohorts[cohort] = dict(underlying_needs=len(underlying),arrived=sum(o.request.noticed_at<=result.horizon for o in underlying),
                              unrecognised=sum(o.request.noticed_at>result.horizon for o in underlying),training_needed=len(needed),
                              training_completed=sum(o.training_completed_at is not None for o in needed),
                              training_unfinished=sum(o.training_completed_at is None for o in needed),
                              priority1_training_needed=len(p1),priority1_training_completed=sum(o.training_completed_at is not None for o in p1),
                              training_clearance_minutes=clear(needed),priority1_training_clearance_minutes=clear(p1),
                              training_backlog_request_days=sum((o.training_completed_at if o.training_completed_at is not None else result.horizon)-need_time(o.request) for o in needed)/1440)
    return cohorts


def backlog_series(result,topics):
    """Event-exact underlying training stock, including unrecognised needs."""
    from collections import defaultdict
    changes = defaultdict(lambda:defaultdict(lambda:[0,0]))
    cohorts = sorted({o.request.cohort_id for o in result.outcomes})
    for out in result.outcomes:
        if out.request.case_kind!='training_needed' or need_time(out.request)>result.horizon:
            continue
        cohort = out.request.cohort_id
        priority1 = int(topics[out.request.topic_id].priority==1)
        changes[need_time(out.request)][cohort][0] += 1
        changes[need_time(out.request)][cohort][1] += priority1
        if out.training_completed_at is not None:
            changes[out.training_completed_at][cohort][0] -= 1
            changes[out.training_completed_at][cohort][1] -= priority1
    changes[0]
    changes[result.horizon]
    stock = {cohort:[0,0] for cohort in cohorts}
    rows = []
    for time in sorted(changes):
        for cohort,delta in changes[time].items():
            stock[cohort] = [a+b for a,b in zip(stock[cohort],delta)]
        for cohort,(total,p1) in stock.items():
            assert 0<=p1<=total
            rows.append(dict(time_minutes=time,cohort_id=cohort,training_backlog=total,priority1_training_backlog=p1))
    return rows


def comparison_metrics(result,topics,target_wait,ageing_limit):
    """An analytical common target is not an IST hard-wait requirement."""
    needed = [o for o in result.outcomes if o.request.case_kind=='training_needed' and need_time(o.request)<=result.horizon]
    due = [o for o in needed if need_time(o.request)+target_wait<=result.horizon]
    timely = [o for o in due if o.first_start is not None and o.first_start<=need_time(o.request)+target_wait]
    by_priority = {}
    for priority in (1,2,3):
        rows = [o for o in needed if topics[o.request.topic_id].priority==priority]
        started = [o for o in rows if o.first_start is not None]
        by_priority[str(priority)] = dict(needs=len(rows),completed=sum(o.training_completed_at is not None for o in rows),
            max_unstarted_need_age_minutes=max((result.horizon-need_time(o.request) for o in rows if o.first_start is None),default=None),
            mean_need_to_start_minutes=sum(o.first_start-need_time(o.request) for o in started)/len(started) if started else None,
            backlog_request_days=sum((o.training_completed_at if o.training_completed_at is not None else result.horizon)-need_time(o.request) for o in rows)/1440)
    return dict(common_target_minutes=target_wait,common_due_needs=len(due),common_timely_starts=len(timely),
                common_target_service=len(timely)/len(due) if due else None,
                unrecognised_needs=sum(o.request.noticed_at>result.horizon for o in needed),
                by_priority=by_priority,
                phase_waiters_over_ageing_limit=sum(w.state in ('waiting','reserved') and result.horizon-w.ready_at>=ageing_limit for w in result.work_items))
