"""Acceptance fixtures have explicit hand-calculated expectations (minutes)."""
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from cosanum_sim.config import Config, resolve
from cosanum_sim.domain import Topic, Request, Resource
from cosanum_sim.demand import expand_batches
from cosanum_sim.engine import simulate
from cosanum_sim.inputs import load_topics, verify_sources
from cosanum_sim.metrics import summarize, assert_invariants
from cosanum_sim.experiments import run

ROOT = Path(__file__).resolve().parents[1]
DAY = 1440
TOPICS = {'A':Topic('A',1,True,False,True,False,0),
          'B':Topic('B',2,True,False,True,False,0),
          'I':Topic('I',3,True,False,False,False,0)}


def resources(intervals=((0,100000),), count=1):
    return tuple(Resource(f'{role}-{i}',role,tuple(TOPICS),intervals) for role in ('trainer','room') for i in range(count))


def config(**changes):
    base = Config(5,None,5,20*DAY,40*DAY,60,True,True,resources())
    return replace(base,**changes)


def batch(identity,time,size,topic='A',person=None):
    return [Request(f'{identity}-{i}',person or f'synthetic-{identity}-{i}',topic,time,identity,identity) for i in range(size)]


class Behaviour(unittest.TestCase):
    def check_run(self, requests, cfg=None):
        cfg = cfg or config()
        result = simulate(requests, TOPICS, cfg)
        assert_invariants(result,TOPICS,cfg)
        return result

    def test_threshold_leftovers_and_selection(self):
        demand = batch('a',0,1)+batch('b',4*DAY,2)+batch('c',11*DAY,1)+batch('d',15*DAY,3)
        result = self.check_run(demand)
        self.assertEqual([(s.start,len(s.request_ids)) for s in result.sessions],[(15*DAY,5),(35*DAY,2)])
        self.assertEqual(result.sessions[0].request_ids,('a-0','b-0','b-1','c-0','d-0'))
        leftovers = [o for o in result.outcomes if o.request.request_id in ('d-1','d-2')]
        self.assertEqual([o.deadline_at for o in leftovers],[35*DAY]*2)
        self.assertEqual([o.first_start-o.request.noticed_at for o in leftovers],[20*DAY]*2)
        full = self.check_run(demand,config(capacity=10))
        self.assertEqual([(s.start,len(s.request_ids)) for s in full.sessions],[(15*DAY,7)])
        target = self.check_run(demand,config(capacity=10,target=5))
        self.assertEqual([len(s.request_ids) for s in target.sessions],[5,2])

    def test_small_group_and_single_fallback_without_later_arrivals(self):
        r = self.check_run(batch('a',0,2)+batch('b',7*DAY,1))
        self.assertEqual([(s.start,len(s.request_ids),s.reason) for s in r.sessions],[(20*DAY,3,'deadline_fallback')])
        single = self.check_run(batch('a',0,1))
        self.assertEqual(single.sessions[0].start,20*DAY)
        self.assertFalse(single.breaches)

    def test_individual_only_and_separate_topics(self):
        r = self.check_run(batch('i',0,5,'I'))
        self.assertEqual([s.start for s in r.sessions],[0,60,120,180,240])
        self.assertTrue(all(len(s.request_ids)==1 for s in r.sessions))
        separated = self.check_run(batch('a',0,2)+batch('b',0,3,'B'))
        self.assertEqual(sorted(len(s.request_ids) for s in separated.sessions),[2,3])
        self.assertTrue(all(s.reason=='deadline_fallback' for s in separated.sessions))
        self.assertFalse(separated.breaches)

    def test_same_time_arrival_timer_and_release(self):
        r = self.check_run(batch('a',0,1)+batch('b',100,4),config(max_wait=100,horizon=200))
        self.assertEqual(len(r.sessions),1)
        self.assertEqual((r.sessions[0].start,r.sessions[0].reason,len(r.sessions[0].request_ids)),(100,'threshold',5))
        self.assertFalse(r.breaches)
        released = self.check_run(batch('i',0,1,'I')+batch('a',0,1)+batch('b',60,4),config(max_wait=60,horizon=200))
        self.assertEqual([s.start for s in released.sessions],[0,60])
        self.assertFalse(released.breaches)

    def test_lookahead_uses_last_slot_before_deadline(self):
        r = self.check_run(batch('a',0,1),config(max_wait=100,horizon=300,resources=resources(((0,80),(200,500)))))
        self.assertEqual(r.sessions[0].start,20)
        self.assertFalse(r.breaches)

    def test_resource_infeasibility_escalates_at_original_deadline(self):
        r = self.check_run(batch('a',0,1),config(max_wait=100,horizon=300,resources=resources(((200,500),))))
        self.assertEqual(r.sessions[0].start,200)
        self.assertEqual(len(r.breaches),1)
        self.assertEqual((r.breaches[0]['deadline_at'],r.breaches[0]['escalation_at'],r.breaches[0]['actual_start']),(100,100,200))
        no_slots = self.check_run(batch('a',0,1),config(max_wait=100,horizon=300,resources=resources(())))
        self.assertEqual(len(no_slots.breaches),1)
        self.assertFalse(no_slots.sessions)
        self.assertEqual(summarize(no_slots,TOPICS)['max_unstarted_age_minutes'],300)
        self.assertIsNone(no_slots.breaches[0]['actual_start'])

    def test_late_compatible_group_stays_together(self):
        r = self.check_run(batch('a',0,3),config(max_wait=100,horizon=300,resources=resources(((200,500),))))
        self.assertEqual([(s.start,len(s.request_ids)) for s in r.sessions],[(200,3)])
        self.assertEqual(len(r.breaches),3)

    def test_participant_conflicts_with_two_free_trainers(self):
        demand = batch('a',0,1,person='shared')+batch('b',0,1,'B',person='shared')
        r = self.check_run(demand,config(group_preferred=False,resources=resources(count=2)))
        self.assertEqual([s.start for s in r.sessions],[0,60])

    def test_younger_person_calendar_does_not_block_oldest_deadline(self):
        demand = batch('a',0,1,person='old')+batch('b',0,1,person='young')
        rs = resources()+ (Resource('young','participant',(),((200,500),)),)
        r = self.check_run(demand,config(max_wait=100,horizon=500,resources=rs))
        self.assertEqual([(s.start,s.person_ids) for s in r.sessions],[(100,('old',)),(200,('young',))])
        self.assertEqual([b['request_id'] for b in r.breaches],['b-0'])

    def test_censoring_and_future_arrivals(self):
        r = self.check_run(batch('a',0,1)+batch('b',400,1),config(horizon=100,max_wait=200))
        m = summarize(r,TOPICS)
        self.assertEqual((m['arrived'],m['waiting'],m['phase_completed']),(1,1,0))
        self.assertIsNone(m['deadline_service'])
        self.assertIsNone(m['priority1_phase_clearance_minutes'])
        partial = self.check_run(batch('i',0,1,'I'),config(horizon=30))
        m = summarize(partial,TOPICS)
        self.assertEqual((m['training'],m['phase_completed'],m['trainer_delivery_minutes']),(1,0,30))

    def test_disabled_deadline_does_not_become_ist_timeout(self):
        r = self.check_run(batch('a',0,1),config(deadline_enabled=False))
        self.assertFalse(r.sessions)
        self.assertFalse(r.breaches)
        self.assertIsNone(r.outcomes[0].deadline_at)

    def test_zero_wait_is_deliberate_and_capacity_breach_visible(self):
        r = self.check_run(batch('i',0,2,'I'),config(max_wait=0,horizon=100))
        self.assertEqual([s.start for s in r.sessions],[0,60])
        self.assertEqual(len(r.breaches),1)

    def test_validation_rejects_contradictions_and_unknowns(self):
        for change in ({'threshold':0},{'threshold':6},{'capacity':1.5},{'target':3},{'target':6},{'duration':-1},{'duration':0},{'horizon':float('nan')},{'max_wait':None},{'group_preferred':1}):
            with self.subTest(change=change),self.assertRaises((ValueError,TypeError)):
                self.check_run(batch('a',0,1),config(**change))
        for demand in (batch('a',0,1,'unknown'), batch('a',0,1)*2, batch('a',-1,1)):
            with self.assertRaises(ValueError):
                self.check_run(demand)
        bad = (Resource('t','trainer',('unknown',),((0,10),)),)
        with self.assertRaises(ValueError):
            self.check_run([],config(resources=bad))
        bad = resources(((0,100),(90,200)))
        with self.assertRaises(ValueError):
            self.check_run([],config(resources=bad))
        fixture = dict(synthetic=True,cohort_id='test',batches=[dict(batch_id='a',size=1.5,noticed_at=0,topic_id='A')])
        with self.assertRaises(ValueError):
            expand_batches(fixture)

    def test_sensitivity_capacity_threshold_deadline(self):
        demand = batch('a',0,3)
        fast = self.check_run(demand,config(threshold=2,max_wait=120,horizon=300))
        slow = self.check_run(demand,config(threshold=4,max_wait=120,horizon=300))
        short = self.check_run(demand,config(threshold=4,max_wait=60,horizon=300))
        self.assertEqual([r.sessions[0].start for r in (fast,slow,short)],[0,120,60])
        self.assertEqual(len(self.check_run(demand,config(threshold=2,capacity=2,max_wait=120,horizon=300)).sessions),2)


class Integration(unittest.TestCase):
    def test_source_controls(self):
        self.assertEqual(len(verify_sources(ROOT)),16)
        topics = load_topics(ROOT/'data/processed/topic_catalog.csv')
        self.assertEqual(len(topics),90)
        self.assertEqual([sum(t.open_records for t in topics.values() if t.priority==p) for p in (1,2,3)],[191,333,781])
        self.assertEqual(sum(t.theory_group_possible for t in topics.values()),85)
        self.assertEqual(sum(t.practice_required for t in topics.values()),55)
        self.assertEqual(sum(t.practice_group_possible for t in topics.values()),44)

    def test_immutable_reproducible_run_and_hand_totals(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b = Path(temp)/'a',Path(temp)/'b'
            first,m = run(ROOT,a)
            second,_ = run(ROOT,b)
            self.assertEqual(first,second)
            self.assertEqual(json.loads((a/'run_manifest.json').read_text())['engine_source_root'], 'src')
            self.assertEqual((m['arrived'],m['phase_completed'],m['waiting'],m['sessions']),(8,8,0,3))
            self.assertEqual((m['trainer_delivery_minutes'],m['participant_delivery_minutes']),(180,480))
            self.assertEqual([s.start for s in first.sessions],[15840,20160,41760])
            for filename in ('events.json','metrics.json','sessions.csv','requests.csv','resolved_config.json'):
                self.assertEqual((a/filename).read_bytes(),(b/filename).read_bytes())
            with self.assertRaises(FileExistsError):
                run(ROOT,a)


if __name__ == '__main__':
    unittest.main()
