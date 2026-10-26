"""Independent previous-selection oracle, including stable fairness ties."""
import random
import unittest
from dataclasses import replace

from cosanum_sim.config import PriorityPolicy
from cosanum_sim.domain import WorkItem
from cosanum_sim.policies import Candidate, RecoveryQueue, recovery_order
from test_slice import TOPICS, batch, config


class PreviousSelection:
    def __init__(self, choices, topics, cfg, now):
        self.pending = sorted(choices,key=lambda c:recovery_order(c,topics,cfg,now))
        self.topics,self.cfg,self.now = topics,cfg,now

    def pop(self, bookings):
        aged = [c for c in self.pending if min(self.topics[w.request.topic_id].priority for w in c.members)>1
                and any(self.now-w.ready_at>=self.cfg.priority.ageing_minutes for w in c.members)]
        if (bookings+1)%self.cfg.recovery_aged_every==0 and aged:
            chosen = min(aged,key=lambda c:(min(w.ready_at for w in c.members),
                                            min(w.request.request_id for w in c.members)))
            allocation = 'recovery_aged:'
        else:
            chosen,allocation = self.pending[0],'recovery_priority:'
        self.pending.remove(chosen)
        return chosen,allocation


class RecoveryQueueEquivalence(unittest.TestCase):
    def test_identical_fairness_keys_keep_original_sorted_phase_tie_order(self):
        request = batch('shared',0,1,'I')[0]
        theory = Candidate((WorkItem('theory',request,'theory',0,None),),'theory',False)
        practice = Candidate((WorkItem('practice',request,'practice',0,None),),'practice',False)
        cfg = config(priority=PriorityPolicy(0,60),recovery_aged_every=1)
        queue = RecoveryQueue([theory,practice],TOPICS,cfg,100)
        self.assertEqual(queue.pop(0),(practice,'recovery_aged:'))
        self.assertEqual(queue.pop(0),(theory,'recovery_aged:'))
        self.assertFalse(queue)
        with self.assertRaises(IndexError):
            queue.pop(0)

    def test_lazy_removal_preserves_priority_after_out_of_order_fairness_choices(self):
        cfg = config(priority=PriorityPolicy(0,60),recovery_aged_every=2)
        choices = [Candidate((WorkItem(str(i),batch(str(i),0,1,topic)[0],'theory',ready,None),),str(i),False)
                   for i,(topic,ready) in enumerate((('A',0),('A',20),('I',0),('B',80)))]
        oracle = PreviousSelection(choices,TOPICS,cfg,100)
        queue = RecoveryQueue(choices,TOPICS,cfg,100)
        for bookings in (1,1,2,3):
            self.assertEqual(queue.pop(bookings),oracle.pop(bookings))

    def test_1000_randomized_candidate_sets_match_previous_oracle(self):
        rng = random.Random(20261004)
        cfg = config(priority=PriorityPolicy(0,60),recovery_aged_every=4)
        for case in range(1000):
            now = rng.choice((0,60,100,240))
            cfg_case = replace(cfg,recovery_aged_every=rng.choice((1,2,4,8)))
            choices = []
            for index in range(rng.randrange(1,31)):
                topic = rng.choice(tuple(TOPICS))
                phase = rng.choice(('proof','practice','assessment','theory','self_learning'))
                members = tuple(WorkItem(f'{case}-{index}-{i}',request,phase,rng.randrange(now+1),None)
                                for i,request in enumerate(batch(f'{case}-{index}',0,rng.randrange(1,5),topic)))
                choices.append(Candidate(members,str(index),False))
            rng.shuffle(choices)
            oracle = PreviousSelection(choices,TOPICS,cfg_case,now)
            queue = RecoveryQueue(choices,TOPICS,cfg_case,now)
            bookings = rng.randrange(8)
            while oracle.pending:
                self.assertTrue(queue)
                self.assertEqual(queue.pop(bookings),oracle.pop(bookings),case)
                # 0 covers future/failed tentative plans; 1..3 covers real
                # current-time appointments, including group-to-single fallbacks.
                bookings += rng.randrange(4)
            self.assertFalse(queue)


if __name__=='__main__':
    unittest.main()
