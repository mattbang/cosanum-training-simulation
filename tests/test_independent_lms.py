"""Independent hand calculations and clock/resource/learning boundaries."""
import json
import unittest
from dataclasses import replace
from pathlib import Path
from cosanum_sim.config import LearningPolicy
from cosanum_sim.domain import Resource
from cosanum_sim.engine import simulate
from cosanum_sim.costs import reconcile
from cosanum_sim.metrics import assert_invariants,summarize
from cosanum_sim.randomness import uniform
from test_slice import batch,config
from test_workflow import W,T
from cosanum_sim.operating import load_operating,resolve_learning
ROOT=Path(__file__).resolve().parents[1]
def resolve_inputs(topics,profile,controls):
    return resolve_learning(topics,profile,controls,json.loads((ROOT/"config/source_values.json").read_text()),load_operating(ROOT/"config/operating_configuration.json"))
from cosanum_sim.annual_demand import load_profile
from cosanum_sim.inputs import load_topics

L=LearningPolicy(('A','B'),60,0,0,.9,123,0,0,0,0,
                 assessment_mode='automated',max_self_retries=1)


def example(requests,learning=L,**changes):
    cfg=config(**{'workflow':replace(W,learning=learning),'horizon':1440,**changes})
    result=simulate(requests,T,cfg);assert_invariants(result,T,cfg)
    return result,reconcile(result,cfg.workflow)


def fixture_for(pattern):
    for i in range(10000):
        r=batch(f'quiz-{i}',0,1)[0]
        outcomes=[uniform(L.seed,r.request_id,r.cycle_id,'automated-lms-v1',a)<.9 for a in (1,2)]
        if outcomes==pattern:return r
    raise AssertionError('No deterministic boundary fixture')


class IndependentLearning(unittest.TestCase):
    def test_success_needs_no_trainer_or_room_and_reconciles_learner_time(self):
        r,c=example(batch('pass',0,1),replace(L,pass_probability=1),resources=())
        self.assertEqual([(s.phase,s.start,s.end,s.trainer_id,s.room_id) for s in r.sessions],
                         [('self_learning',0,60,'','')])
        self.assertEqual((r.outcomes[0].phase_completed_at,r.outcomes[0].training_completed_at), (60,60))
        self.assertEqual(c['totals']['net_chf'],65)
        self.assertEqual(summarize(r,T)['trainer_total_work_minutes'],0)

    def test_retry_pass_keeps_notice_deadline_and_doubles_consumed_study_time(self):
        request=fixture_for([False,True])
        r,c=example([request],max_wait=30)
        self.assertEqual([(s.phase,s.start,s.end) for s in r.sessions],
                         [('self_learning',0,60),('self_learning',60,120)])
        out=r.outcomes[0]
        self.assertEqual((out.request.noticed_at,out.deadline_at,out.first_start,out.training_completed_at),(0,30,0,120))
        self.assertEqual(c['totals']['net_chf'],130)
        self.assertEqual(summarize(r,T)['lms_instructor_fallbacks'],0)
        self.assertEqual(len({w.work_item_id for w in r.work_items}),2)

    def test_two_failures_require_individual_human_fallback_once(self):
        r,c=example([fixture_for([False,False])])
        self.assertEqual([(s.phase,s.start,s.end) for s in r.sessions],
                         [('self_learning',0,60),('self_learning',60,120),('theory',120,180)])
        self.assertEqual(r.sessions[-1].reason,'instructor_theory_fallback')
        self.assertEqual(c['totals']['net_chf'],260)
        self.assertEqual(summarize(r,T)['lms_instructor_fallbacks'],1)

    def test_required_practice_follows_accepted_theory_and_consumes_full_capacity(self):
        r,c=example(batch('practice',0,1,'B'),replace(L,pass_probability=1))
        self.assertEqual([(s.phase,s.start,s.end) for s in r.sessions],
                         [('self_learning',0,60),('practice',60,240)])
        self.assertEqual((r.outcomes[0].training_completed_at,r.outcomes[0].proof_completed_at),(240,270))
        self.assertEqual(summarize(r,T)['trainer_total_work_minutes'],180)
        self.assertEqual(c['totals']['net_chf'],357.5)

    def test_partial_retry_accrues_time_without_acceptance_or_reset(self):
        r,c=example([fixture_for([False,True])],horizon=90,max_wait=30)
        self.assertIsNone(r.outcomes[0].training_completed_at)
        self.assertIsNone(r.outcomes[0].phase_completed_at)
        self.assertEqual(r.outcomes[0].first_start,0)
        self.assertEqual(c['totals']['net_chf'],97.5)

    def test_shared_person_serializes_independent_courses_and_calendar_breaches(self):
        calendar=Resource('synthetic-shared','participant',('A','B'),((100,500),))
        demand=batch('a',0,1,person=calendar.resource_id)+batch('b',0,1,'B',calendar.resource_id)
        r,_=example(demand,replace(L,pass_probability=1),resources=config().resources+(calendar,),max_wait=50)
        study=sorted((s.start,s.end) for s in r.sessions if s.phase=='self_learning')
        self.assertEqual(study,[(100,160),(160,220)])
        self.assertEqual(len(r.breaches),2)

    def test_assessment_attempts_are_stable_under_input_order_and_unrelated_demand(self):
        wanted=[fixture_for([False,True]),fixture_for([False,False])]
        first,_=example(wanted)
        second,_=example(batch('unrelated',0,1,'B')+list(reversed(wanted)))
        ids={r.request_id for r in wanted}
        events=lambda r:sorted((e['request_id'],e['learning_attempt'],e['passed']) for e in r.events
                              if e['type']=='assessment_result' and e['request_id'] in ids)
        self.assertEqual(events(first),events(second))

    def test_invalid_retry_and_mode_inputs_fail(self):
        for bad in (replace(L,max_self_retries=True),replace(L,max_self_retries=-1),
                    replace(L,assessment_mode='unknown'),replace(L,support_minutes=15),
                    replace(L,assessment_mode='expert'),replace(L,pass_probability=1.1)):
            with self.assertRaises(ValueError):example([],bad)

    def test_topic_scope_and_published_licence_arithmetic_are_separate_from_demand(self):
        topics=load_topics(ROOT/'data/processed/topic_catalog.csv')
        profile=load_profile(ROOT/'config/annual_profile.json')
        controls=json.loads((ROOT/'config/prototype_controls.json').read_text())
        resolved=resolve_inputs(topics,profile,controls)
        self.assertEqual(len(resolved['theory_only_topic_ids']),35)
        self.assertEqual((resolved['all_mixed_topic_count'],len(resolved['selected_mixed_topic_ids'])),(55,28))
        self.assertEqual(len(resolved['selected_topic_ids']),63)
        self.assertEqual(resolved['accounts'],47)
        self.assertEqual(resolved['annual_licence_usd'],4512)
        self.assertAlmostEqual(resolved['annual_licence_chf'],3737.2896)
        self.assertAlmostEqual(resolved['first_year_portfolio_chf'],39062.2896)
        self.assertEqual(profile.values['group_size'],20)


if __name__=='__main__':unittest.main()
