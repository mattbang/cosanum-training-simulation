"""Independent arithmetic and calendar boundaries for joined appointments."""
import json
import unittest
from dataclasses import asdict, replace

from cosanum_sim.config import Cancellation, PriorityPolicy
from cosanum_sim.costs import reconcile
from cosanum_sim.domain import Resource
from cosanum_sim.engine import simulate
from cosanum_sim.inputs import load_topics
from cosanum_sim.metrics import assert_invariants, summarize
from cosanum_sim.randomness import seed_map
from cosanum_sim.scenarios import compose_scenario
from cosanum_sim.scheduler import Scheduler
from test_slice import TOPICS, ROOT, batch, config, resources
from test_workflow import W


T = dict(TOPICS,B=replace(TOPICS['B'],practice_required=True))


class JoinedAppointments(unittest.TestCase):
    def run_case(self,demand,**changes):
        cfg = config(workflow=W,joined_scheduling=True,group_preferred=False,
                     max_wait=1000,horizon=2000)
        cfg = replace(cfg,**changes)
        result = simulate(demand,T,cfg)
        assert_invariants(result,T,cfg)
        return result,reconcile(result,cfg.workflow)

    def test_one_case_reserves_required_practice_without_duplicate_cost_or_learning(self):
        r,c = self.run_case(batch('case',0,1,'B'),resources=resources(((0,300),)),horizon=300)
        self.assertEqual([(s.phase,s.reservation_at,s.start,s.end) for s in r.sessions],
                         [('theory',0,0,60),('practice',0,60,240)])
        self.assertEqual((r.outcomes[0].training_completed_at,r.outcomes[0].proof_completed_at),(240,270))
        self.assertEqual(c['totals'],dict(gross_chf=520,credit_chf=97.5,net_chf=422.5))
        self.assertEqual(len(r.work_items),2)
        practice = r.work_items[1]
        self.assertEqual((practice.ready_at,practice.first_start,practice.prerequisite_session_id),(60,60,'session-0001'))
        bundle = next(e for e in r.events if e['type']=='joined_bundle_reserved')
        self.assertEqual((bundle['time'],bundle['practice_session_ids']),(0,('session-0002',)))
        self.assertLess(next(e['sequence'] for e in r.events if e['type']=='phase_complete' and e['phase']=='theory'),
                        next(e['sequence'] for e in r.events if e['type']=='start' and e['phase']=='practice'))

    def test_prebooked_practice_includes_coordination_time_and_cost(self):
        r,c = self.run_case(batch('case',0,1,'B'),
                            workflow=replace(W,coordination_minutes=5),
                            resources=resources(((0,320),)),horizon=320)
        self.assertEqual([(s.phase,s.preparation_start,s.start,s.end) for s in r.sessions],
                         [('theory',0,5,65),('practice',65,70,250)])
        self.assertEqual(r.outcomes[0].training_completed_at,250)
        # Two five-minute trainer coordination blocks at CHF65/h, once each.
        self.assertAlmostEqual(c['totals']['net_chf'],422.5+65/6)
        self.assertAlmostEqual(c['totals']['gross_chf'],520+65/6)
        self.assertEqual(c['totals']['credit_chf'],97.5)

    def test_prebooked_chain_cannot_ignore_coordination_to_fit_a_short_window(self):
        rs=(Resource('theory','trainer',('B',),((0,65),),('theory',)),
            Resource('coach','trainer',('B',),((100,280),),('practice',)),
            Resource('place','room',('B',),((0,300),)),
            Resource('synthetic-case-0','participant',('B',),((0,300),)))
        r,_ = self.run_case(batch('case',0,1,'B'),
                            workflow=replace(W,coordination_minutes=5),
                            resources=rs,horizon=300)
        self.assertEqual([s.phase for s in r.sessions],['theory'])
        self.assertIsNone(r.outcomes[0].training_completed_at)
        self.assertTrue(any(e['type']=='joined_follow_up_escalation' for e in r.events))
        self.assertFalse(any(e['type']=='joined_bundle_reserved' for e in r.events))

    def test_group_follow_up_is_individual_and_respects_pq_follow_up(self):
        r,c = self.run_case(batch('group',0,2,'B'),group_preferred=True,threshold=2,
                            resources=resources(((0,600),)),horizon=600)
        self.assertEqual([(s.phase,len(s.request_ids),s.start,s.end) for s in r.sessions],
                         [('theory',2,90,150),('practice',1,240,420),('practice',1,420,600)])
        self.assertEqual([s.reservation_at for s in r.sessions],[0,0,0])
        self.assertEqual(c['totals'],dict(gross_chf=1310,credit_chf=195,net_chf=1115))
        self.assertEqual([w.ready_at for w in r.work_items if w.phase=='practice'],[150,150])

    def test_partial_chain_failure_rolls_back_all_follow_ups_and_keeps_timely_theory(self):
        r,c = self.run_case(batch('group',0,2,'B'),group_preferred=True,threshold=2,
                            resources=resources(((0,420),)),horizon=420,max_wait=100)
        self.assertEqual([(s.phase,s.reservation_at,s.start) for s in r.sessions],
                         [('theory',0,90),('practice',240,240)])
        self.assertFalse(r.breaches)
        self.assertFalse([e for e in r.events if e['type']=='joined_bundle_reserved'])
        failure = next(e for e in r.events if e['type']=='joined_follow_up_escalation')
        self.assertEqual((failure['time'],failure['partial_reservations_committed']),(0,0))
        self.assertEqual(failure['decision'],'retain_first_start_and_use_normal_follow_up_queue')
        self.assertEqual(sum(o.training_completed_at is not None for o in r.outcomes),1)
        self.assertEqual(c['totals']['net_chf'],822.5)

    def test_other_known_feasible_start_deadline_is_protected_before_practice(self):
        r,_ = self.run_case(batch('high',0,1,'B')+batch('low',0,1,'I'),max_wait=60,horizon=400,
                            resources=resources(((0,400),)))
        self.assertEqual([(s.phase,s.topic_id,s.start) for s in r.sessions],
                         [('theory','B',0),('practice','B',120),('theory','I',60)])
        self.assertFalse(r.breaches)
        self.assertEqual([o.deadline_at for o in r.outcomes],[60,60])

    def test_participant_and_phase_qualified_calendars_are_real_constraints(self):
        person = 'synthetic-case-0'
        rs = (Resource('theory-expert','trainer',('B',),((0,60),),('theory',)),
              Resource('practice-expert','trainer',('B',),((100,500),),('practice',)),
              Resource('room','room',('B',),((0,500),)),
              Resource(person,'participant',('B',),((0,60),(220,500))))
        r,_ = self.run_case(batch('case',0,1,'B'),resources=rs,horizon=500)
        self.assertEqual([(s.trainer_id,s.phase,s.start) for s in r.sessions],
                         [('theory-expert','theory',0),('practice-expert','practice',220)])
        self.assertEqual(r.outcomes[0].training_completed_at,400)

    def test_same_person_other_topic_cannot_overlap_future_practice(self):
        demand = batch('first',0,1,'B',person='same')+batch('other',100,1,'I',person='same')
        r,_ = self.run_case(demand,resources=resources(((0,500),),count=2),horizon=500)
        self.assertEqual([(s.phase,s.topic_id,s.start) for s in r.sessions],
                         [('theory','B',0),('practice','B',60),('theory','I',240)])
        self.assertEqual(len({s.trainer_id for s in r.sessions}),1)

    def test_booking_never_creates_competence_or_cost_before_consumed_work(self):
        # A future complete bundle is outside the horizon, so the standard
        # queue runs a censored practice instead. Only 120 minutes are valued.
        r,c = self.run_case(batch('case',0,1,'B'),resources=resources(((0,300),)),horizon=180)
        self.assertEqual([(s.phase,s.start,s.end) for s in r.sessions],
                         [('theory',0,60),('practice',60,240)])
        self.assertIsNone(r.outcomes[0].training_completed_at)
        self.assertEqual(c['totals'],dict(gross_chf=390,credit_chf=65,net_chf=325))
        self.assertEqual(summarize(r,T)['training_completed'],0)
        self.assertTrue([e for e in r.events if e['type']=='joined_follow_up_escalation'])

    def test_observation_before_theory_completion_retains_blocked_practice(self):
        # Resources are available, but no entire practice fits this horizon.
        # No synthetic practice WorkItem is created on unsuccessful trial.
        r,_ = self.run_case(batch('group',0,2,'B'),group_preferred=True,threshold=2,
                            resources=resources(((0,1000),)),horizon=100)
        self.assertEqual([w.phase for w in r.work_items],['theory','theory'])
        self.assertTrue(all(o.phase_completed_at is None for o in r.outcomes))

    def test_theory_cancellation_releases_all_dependents_and_preserves_incurred_pq_cost(self):
        wf = replace(W,cancellations=(Cancellation('group-0','theory',1,30),))
        r,c = self.run_case(batch('group',0,2,'B'),workflow=wf,group_preferred=True,threshold=2,
                            resources=resources(((0,700),)),horizon=700)
        self.assertEqual([(s.phase,s.start,s.cancelled_at) for s in r.sessions],
                         [('theory',90,30),('practice',240,30),('practice',420,30),
                          ('theory',120,None),('practice',270,None),('practice',450,None)])
        self.assertEqual(c['totals']['net_chf'],1165)
        self.assertEqual([o.training_completed_at for o in r.outcomes],[450,630])
        self.assertEqual([o.deadline_at for o in r.outcomes],[1000,1000])
        self.assertEqual(len([w for w in r.work_items if w.phase=='practice']),2)
        self.assertEqual(sum(i['net_chf'] for i in c['items'] if i['session_id'] in ('session-0002','session-0003')),0)

    def test_practice_cancelled_before_theory_ends_waits_for_actual_prerequisite(self):
        wf = replace(W,cancellations=(Cancellation('group-0','practice',1,30),))
        r,c = self.run_case(batch('group',0,2,'B'),workflow=wf,group_preferred=True,threshold=2,
                            resources=resources(((0,700),)),horizon=700)
        first = next(w for w in r.work_items if w.work_item_id=='group-0:practice')
        self.assertEqual((first.ready_at,first.first_start,first.attempt),(150,240,2))
        self.assertEqual([o.training_completed_at for o in r.outcomes],[420,600])
        self.assertEqual(c['totals']['net_chf'],1115)

    def test_follow_up_eligibility_retains_existing_planning_delay(self):
        r,_ = self.run_case(batch('case',0,1,'B'),planning_delay=30,
                            resources=resources(((0,500),)),horizon=500)
        self.assertEqual([(s.phase,s.start) for s in r.sessions],[('theory',30),('practice',120)])
        practice = next(w for w in r.work_items if w.phase=='practice')
        self.assertEqual((practice.ready_at,practice.eligible_at),(90,120))

    def test_theory_only_and_proof_only_never_acquire_practice(self):
        proof = replace(batch('proof',0,1,'B')[0],case_kind='proof_only')
        r,_ = self.run_case(batch('theory',0,1,'I')+[proof],horizon=500)
        self.assertEqual({s.phase for s in r.sessions},{'theory','proof'})
        self.assertFalse([e for e in r.events if e['type'].startswith('joined_')])

    def test_off_switch_preserves_complete_event_and_session_behavior(self):
        cfg = config(workflow=W,group_preferred=False,horizon=500)
        demand = batch('case',0,1,'B')+batch('later',70,1,'I')
        default = simulate(demand,T,cfg)
        off = simulate(demand,T,replace(cfg,joined_scheduling=False))
        self.assertEqual(asdict(default),asdict(off))
        self.assertEqual([(s.phase,s.start) for s in off.sessions],
                         [('theory',0),('practice',60),('theory',240)])

    def test_invalid_switch_and_missing_full_workflow_are_rejected(self):
        for cfg in (config(joined_scheduling=True),config(workflow=W,joined_scheduling=1)):
            with self.assertRaises(ValueError):
                simulate([],T,cfg)


class AtomicScheduler(unittest.TestCase):
    def test_failed_bundle_leaves_busy_and_free_cache_unchanged(self):
        for pooled in (False,True):
            scheduler = Scheduler(resources(((0,300),)),event_history_only=pooled)
            theory = scheduler.find('B',('one','two'),0,60)
            scheduler.reserve(theory)
            before = {key:list(value) for key,value in scheduler.busy.items()}
            self.assertIsNone(scheduler.find_follow_ups('B',('one','two'),60,180,300))
            self.assertEqual(scheduler.busy,before)
            self.assertEqual(scheduler.find('B',('one',),60,180,phase='practice').start,60)


class JoinedComposition(unittest.TestCase):
    def test_component_variants_change_only_the_named_switch(self):
        controls = json.loads((ROOT/'config/prototype_controls.json').read_text())
        sources = json.loads((ROOT/'config/source_values.json').read_text())
        topics = load_topics(ROOT/'data/processed/topic_catalog.csv')
        seeds = seed_map(20261003,0)
        for before,after in (('S0','S0_JOINED'),('S7_RECOVERY','S7_RECOVERY_JOINED')):
            kwargs = {'recovery_aged_every':4} if 'RECOVERY' in before else {}
            base = compose_scenario(before,controls,sources,topics,seeds,'ongoing_stochastic_demand',**kwargs)[0]
            joined = compose_scenario(after,controls,sources,topics,seeds,'ongoing_stochastic_demand',**kwargs)[0]
            self.assertEqual(joined.config,replace(base.config,joined_scheduling=True))
            self.assertEqual(joined.components,base.components+('joined_scheduling',))
            self.assertEqual(joined.recognition_delay,base.recognition_delay)


if __name__=='__main__':
    unittest.main()
