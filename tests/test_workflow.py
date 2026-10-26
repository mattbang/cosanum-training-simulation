"""Independent full-workflow arithmetic and event-boundary acceptance tests."""
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from cosanum_sim.config import Workflow, Cancellation
from cosanum_sim.costs import reconcile
from cosanum_sim.domain import Resource
from cosanum_sim.engine import simulate
from cosanum_sim.experiments import run
from cosanum_sim.metrics import assert_invariants, summarize
from test_slice import TOPICS, config, batch, resources, ROOT

W = Workflow(180,90,90,30,12,65,65,100,400,4,0.5,('unmeasured overhead',))
T = dict(TOPICS,B=replace(TOPICS['B'],practice_required=True))


def full(demand,**changes):
    cfg = config(threshold=3,max_wait=1000,horizon=2000,workflow=W,**changes)
    result = simulate(demand,T,cfg)
    assert_invariants(result,T,cfg)
    return result,reconcile(result,cfg.workflow)


class WorkflowAcceptance(unittest.TestCase):
    def test_three_person_allowance_and_workload(self):
        r,c = full(batch('a',0,3))
        self.assertEqual([(s.preparation_start,s.start,s.end,s.work_end) for s in r.sessions],[(0,90,150,240)])
        self.assertEqual(c['totals'],dict(gross_chf=595,credit_chf=0,net_chf=595))
        self.assertEqual(sum(i['gross_chf'] for i in c['items'] if i['component']=='included_pq_allowance'),400)
        self.assertFalse(any(i['component']=='coach_labour' for i in c['items']))
        self.assertEqual(summarize(r,T)['pq_group_work_minutes'],240)
        self.assertEqual([o.training_completed_at for o in r.outcomes],[150]*3)
        self.assertEqual([o.proof_completed_at for o in r.outcomes],[270]*3)

    def test_practice_duration_cost_credit_and_phase_order(self):
        r,c = full(batch('a',0,1,'B'),group_preferred=False)
        self.assertEqual([(s.phase,s.start,s.end) for s in r.sessions],[('theory',0,60),('practice',60,240)])
        self.assertEqual(r.outcomes[0].deadline_at,1000)
        self.assertEqual(r.outcomes[0].training_completed_at,240)
        self.assertEqual(r.outcomes[0].proof_completed_at,270)
        practice = r.sessions[1].session_id
        items = [i for i in c['items'] if i['session_id']==practice]
        self.assertEqual(sum(i['gross_chf'] for i in items),390)
        self.assertEqual(sum(i['credit_chf'] for i in items),97.5)
        self.assertEqual(sum(i['net_chf'] for i in items),292.5)
        self.assertEqual(summarize(r,T)['participant_delivery_minutes'],240)
        self.assertEqual(c['totals'],dict(gross_chf=520,credit_chf=97.5,net_chf=422.5))

    def test_practice_is_individual_even_when_eligible(self):
        topics = dict(T,B=replace(T['B'],practice_group_possible=True))
        cfg = config(threshold=3,max_wait=1000,horizon=2000,workflow=W)
        r = simulate(batch('a',0,3,'B'),topics,cfg)
        assert_invariants(r,topics,cfg)
        self.assertEqual([(s.phase,len(s.request_ids),s.start) for s in r.sessions],
                         [('theory',3,90),('practice',1,240),('practice',1,420),('practice',1,600)])
        self.assertEqual([w.ready_at for w in r.work_items if w.phase=='practice'],[150]*3)

    def test_proof_only_does_not_create_competence_or_participant_time(self):
        request = replace(batch('p',0,1)[0],case_kind='proof_only')
        r,c = full([request])
        out = r.outcomes[0]
        self.assertIsNone(out.first_start)
        self.assertIsNone(out.training_completed_at)
        self.assertIsNone(out.deadline_at)
        self.assertEqual(out.proof_completed_at,42)
        self.assertEqual((r.sessions[0].phase,r.sessions[0].person_ids,r.sessions[0].room_id),('proof',(),''))
        self.assertEqual(c['totals'],dict(gross_chf=20,credit_chf=0,net_chf=20))
        self.assertEqual(summarize(r,T)['participant_delivery_minutes'],0)

    def test_cancellation_preserves_preparation_and_retries_original_cases(self):
        wf = replace(W,cancellations=(Cancellation('a-0','theory',1,30),))
        cfg = config(threshold=3,max_wait=1000,horizon=2000,workflow=wf)
        r = simulate(batch('a',0,3),T,cfg)
        assert_invariants(r,T,cfg)
        c = reconcile(r,wf)
        self.assertEqual(len(r.outcomes),3)
        self.assertEqual([(s.preparation_start,s.start,s.cancelled_at) for s in r.sessions],[(0,90,30),(30,120,None)])
        self.assertEqual([w.attempt for w in r.work_items],[2]*3)
        self.assertEqual([w.ready_at for w in r.work_items],[0]*3)
        self.assertEqual([o.deadline_at for o in r.outcomes],[1000]*3)
        self.assertEqual(c['totals'],dict(gross_chf=645,credit_chf=0,net_chf=645))
        self.assertEqual(summarize(r,T)['trainer_total_work_minutes'],270)

    def test_partial_delivery_cancel_consumes_participant_time(self):
        wf = replace(W,cancellations=(Cancellation('a-0','theory',1,120),))
        cfg = config(threshold=3,max_wait=1000,horizon=2000,workflow=wf)
        r = simulate(batch('a',0,3),T,cfg)
        assert_invariants(r,T,cfg)
        c = reconcile(r,wf)
        self.assertEqual(c['totals']['gross_chf'],892.5) # 200 P&Q + 97.5 attendance + 595 retry
        self.assertEqual(r.outcomes[0].first_start,90)
        self.assertEqual(r.outcomes[0].training_completed_at,270)

    def test_cancel_at_start_does_not_count_training_or_competence(self):
        wf = replace(W,cancellations=(Cancellation('a-0','theory',1,90),))
        cfg = config(threshold=3,max_wait=1000,horizon=2000,workflow=wf)
        r = simulate(batch('a',0,3),T,cfg)
        self.assertEqual(r.outcomes[0].first_start,180)
        self.assertEqual(reconcile(r,wf)['totals']['gross_chf'],745)

    def test_horizon_partial_work_and_pending_proof(self):
        cfg = config(threshold=3,max_wait=1000,horizon=120,workflow=W)
        r = simulate(batch('a',0,3),T,cfg)
        assert_invariants(r,T,cfg)
        self.assertEqual(reconcile(r,W)['totals']['gross_chf'],297.5)
        self.assertTrue(all(o.training_completed_at is None for o in r.outcomes))
        cfg = replace(cfg,horizon=200)
        r = simulate(batch('a',0,3),T,cfg)
        self.assertEqual(summarize(r,T)['training_completed'],3)
        self.assertEqual(summarize(r,T)['proof_completed'],0)
        self.assertIsNone(summarize(r,T)['priority1_proof_clearance_minutes'])

    def test_deadline_lookahead_includes_preparation_and_room_only_delivery(self):
        rs = (Resource('t','trainer',('A',),((0,240),)),Resource('r','room',('A',),((90,150),)))
        cfg = config(threshold=5,max_wait=100,horizon=300,workflow=W,resources=rs)
        r = simulate(batch('a',0,3),T,cfg)
        assert_invariants(r,T,cfg)
        self.assertEqual((r.sessions[0].preparation_start,r.sessions[0].start),(0,90))
        self.assertFalse(r.breaches)

    def test_phase_qualification_scarcity_and_proof_censoring(self):
        rs = tuple(replace(x,phases=('theory',)) for x in resources())
        r,c = full(batch('a',0,1,'B'),group_preferred=False,resources=rs)
        self.assertEqual(r.outcomes[0].phase_completed_at,60)
        self.assertIsNone(r.outcomes[0].training_completed_at)
        self.assertIsNone(r.outcomes[0].proof_completed_at)
        self.assertEqual(c['totals']['gross_chf'],130)
        self.assertEqual([w.state for w in r.work_items],['complete','waiting'])

    def test_credit_changes_cost_not_resource_intervals(self):
        request = batch('a',0,1,'B')
        cfg = config(group_preferred=False,workflow=W)
        a = simulate(request,T,cfg)
        b = simulate(request,T,replace(cfg,workflow=replace(W,practice_credit=0)))
        self.assertEqual(a.sessions,b.sessions)
        self.assertEqual(reconcile(a,W)['totals']['net_chf'],422.5)
        self.assertEqual(reconcile(b,replace(W,practice_credit=0))['totals']['net_chf'],520)

    def test_cost_break_even_is_conditional_seven_not_five(self):
        for count,group_cost,individual_cost in ((6,790,780),(7,855,910)):
            cfg = config(threshold=count,capacity=count,max_wait=1000,horizon=2000,workflow=W)
            demand = batch('a',0,count)
            grouped = simulate(demand,T,cfg)
            individual = simulate(demand,T,replace(cfg,group_preferred=False))
            self.assertEqual(reconcile(grouped,W)['totals']['gross_chf'],group_cost)
            self.assertEqual(reconcile(individual,W)['totals']['gross_chf'],individual_cost)

    def test_workflow_validation(self):
        for wf in (replace(W,practice_credit=1.1),replace(W,coach_rate=-1),replace(W,preparation=0),
                   replace(W,proof_delay=float('nan')),replace(W,cancellations=(Cancellation('missing','theory',1,10),))):
            with self.assertRaises(ValueError):
                simulate(batch('a',0,1),T,config(workflow=wf))

    def test_export_reproducibility_and_demo_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory:
            a,b = Path(directory)/'a',Path(directory)/'b'
            first,m = run(ROOT,a,True)
            second,_ = run(ROOT,b,True)
            self.assertEqual(first,second)
            self.assertEqual((m['arrived'],m['training_completed'],m['proof_completed']),(9,8,9))
            self.assertEqual(m['costs'],dict(gross_chf=1795,credit_chf=97.5,net_chf=1697.5))
            self.assertEqual((m['trainer_total_work_minutes'],m['participant_delivery_minutes']),(732,660))
            for name in ('costs.json','cost_allocations.csv','work_items.json','requests.csv','events.json'):
                self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())


if __name__=='__main__':
    unittest.main()
