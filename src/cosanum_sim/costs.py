"""Accrued work valuation, including interrupted attempts; no extra allowance charge."""
from dataclasses import dataclass, asdict
from decimal import Decimal
from math import isclose


def dec(value):
    return Decimal(str(value))


@dataclass(frozen=True)
class CostItem:
    session_id: str
    request_id: str
    component: str
    quantity: float
    unit: str
    rate_chf: float
    gross_chf: float
    credit_chf: float
    net_chf: float
    source_status: str
    input_reference: str
    inclusion_rule: str


def elapsed(start,end,horizon,cancelled_at=None):
    stop = min(end,horizon,cancelled_at if cancelled_at is not None else end)
    return max(0,stop-start)


def reconcile(result,workflow):
    if workflow is None:
        return None
    items,allocations = [],[]
    def add(session,request,component,quantity,unit,rate,credit_fraction,reference,rule):
        gross = dec(quantity)*dec(rate)
        credit = gross*dec(credit_fraction)
        item = CostItem(session.session_id,request,component,float(quantity),unit,float(rate),
                        float(gross),float(credit),float(gross-credit),'derived',reference,rule)
        items.append(item)
        members = [request] if request else list(session.request_ids)
        for member in members:
            allocations.append(dict(session_id=session.session_id,request_id=member,component=component,
                                    gross_chf=float(gross/len(members)),credit_chf=float(credit/len(members)),net_chf=float((gross-credit)/len(members))))
    for s in result.sessions:
        labour = elapsed(s.preparation_start,s.work_end,result.horizon,s.cancelled_at)
        delivery = elapsed(s.start,s.end,result.horizon,s.cancelled_at)
        if s.phase=='theory' and len(s.request_ids)>1:
            add(s,'','included_pq_allowance',dec(labour)/(dec(workflow.included_pq_hours)*60),
                'session_equivalent',workflow.group_allowance,0,
                'theory_group_pq_allowance_chf; theory_group_included_pq_hours',
                'Replaces all P&Q preparation/delivery/follow-up/admin labour; accrued proportionally to consumed work')
        elif s.phase=='assessment':
            support = elapsed(s.start,s.start+workflow.learning.support_minutes,result.horizon,s.cancelled_at)
            assessment = elapsed(s.start+workflow.learning.support_minutes,s.end,result.horizon,s.cancelled_at)
            for component,minutes in (('lms_support_labour',support),('lms_assessment_labour',assessment)):
                add(s,'',component,dec(minutes)/60,'hours',workflow.coach_rate,0,'coach_hourly_chf',
                    'Qualified theory expert; support then assessment; participant present throughout')
        elif s.trainer_id:
            proof = s.phase=='proof'
            coordination=elapsed(s.preparation_start,s.start,result.horizon,s.cancelled_at) if s.phase in ('theory','practice') else 0
            if coordination:
                add(s,'','coordination_labour',dec(coordination)/60,'hours',workflow.coach_rate,0,'coordination_minutes; coach_hourly_chf',
                    'Unincluded individual-session preparation only; group coordination is inside its allowance')
            add(s,'','proof_recovery_labour' if proof else 'coach_labour',dec(labour-coordination)/60,'hours',
                workflow.pq_rate if proof else workflow.coach_rate,0,'pq_hourly_chf' if proof else 'coach_hourly_chf',
                'Actual consumed labour; no group allowance added')
        if s.phase!='proof':
            for request in s.request_ids:
                add(s,request,'participant_labour',dec(delivery)/60,'hours',workflow.participant_rate,
                    workflow.practice_credit if s.phase=='practice' else 0,
                    'participant_hourly_chf; participant_practice_credit_fraction' if s.phase=='practice' else 'participant_hourly_chf',
                    'Practice credit changes valuation only; full attendance remains occupied')
    learning = workflow.learning
    if learning is not None:
        # Portfolio costs are explicit unallocated rows, not fictitious request labour.
        for component,quantity,unit,rate in (
            ('lms_implementation',1,'deployment',learning.implementation_chf),
            ('lms_content',len(learning.topic_ids),'topic',learning.content_chf_per_topic),
            ('lms_licence',result.horizon/1440,'calendar_day',learning.licence_chf_per_day),
            ('lms_maintenance',result.horizon/1440,'calendar_day',learning.maintenance_chf_per_day)):
            amount = float(dec(quantity)*dec(rate))
            items.append(CostItem('','',component,quantity,unit,rate,amount,0,amount,'assumption',component,
                         'Setup/content charged at time zero; recurring costs accrued over horizon; portfolio level, no per-completer dilution'))
            allocations.append(dict(session_id='',request_id='',component=component,gross_chf=amount,credit_chf=0,net_chf=amount))
    totals = {field:sum(getattr(i,field) for i in items) for field in ('gross_chf','credit_chf','net_chf')}
    assert isclose(totals['gross_chf']-totals['credit_chf'],totals['net_chf'],abs_tol=1e-8)
    for field in totals:
        assert isclose(totals[field],sum(a[field] for a in allocations),abs_tol=1e-8)
    return dict(items=[asdict(i) for i in items],allocations=allocations,totals=totals,
                exclusions=list(workflow.exclusions),basis='Accrued work through horizon; not invoiced cash; cancelled allowance prorated by consumed P&Q time')
