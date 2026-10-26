import json,unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from cosanum_sim.operating import load_operating,validate_operating,configure_operating,resolve_learning
from cosanum_sim.annual_demand import load_profile,annual_fixture
from cosanum_sim.inputs import load_topics
from cosanum_sim.randomness import seed_map
from cosanum_sim.scenarios import compose_scenario
ROOT=Path(__file__).resolve().parents[1]
class OperatingBoundaries(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.op=load_operating(ROOT/'config/operating_configuration.json');cls.v={r['input_id']:r['value'] for r in cls.op['inputs']}
  cls.topics=load_topics(ROOT/'data/processed/topic_catalog.csv');cls.profile=load_profile(ROOT/'config/annual_profile.json')
  cls.controls=json.loads((ROOT/'config/prototype_controls.json').read_text());cls.sources=json.loads((ROOT/'config/source_values.json').read_text())
  cls.seeds=seed_map(123,600);cls.fixture,cls.demand=annual_fixture(cls.topics,cls.seeds,cls.profile,False,True)
  cls.recipe,_=compose_scenario('S7_RECOVERY',cls.controls,cls.sources,cls.topics,cls.seeds,'ongoing_stochastic_demand',cls.profile.values['recovery_aged_every'])
 def cfg(self,**kw):
  op=deepcopy(self.v);op.update(kw.pop('overrides',{}))
  return configure_operating(replace(self.recipe.config,horizon=365*1440),self.topics,self.profile,{r.person_id for r in self.demand},op,self.seeds,self.controls,self.sources,**kw)
 def test_staffing_guard_is_independent_of_preferred_size(self):
  for g in (5,10,20,30):
   cfg,_,_=self.cfg(overrides={'preferred_group':g});self.assertEqual((cfg.target,cfg.capacity,cfg.participant_absence_limit),(g,30,30))
  with self.assertRaises(ValueError):self.cfg(overrides={'preferred_group':45})
  cfg,_,_=self.cfg(overrides={'preferred_group':45,'minimum_logistics_working':0});self.assertEqual(cfg.capacity,45)
 def test_group_capacity_does_not_change_arrival_fixture(self):
  before=self.demand
  self.cfg(overrides={'preferred_group':45,'minimum_logistics_working':0})
  self.assertEqual(before,self.demand);self.assertEqual(len(before),350)
 def test_weekly_calendar_hours_and_phase_specialization(self):
  for d in (1,2,3,4):
   cfg,_,_=self.cfg(overrides={'training_days':d})
   trainers=[r for r in cfg.resources if r.role=='trainer'];self.assertEqual(len(trainers),2)
   self.assertNotIn('practice',trainers[0].phases);self.assertEqual(trainers[1].phases,('practice',))
   self.assertTrue(all(b-a==480 for r in trainers for a,b in r.intervals))
   self.assertEqual(set(int(a)//1440%7 for a,b in trainers[0].intervals),set(self.v['weekday_patterns'][str(d)]))
 def test_unselected_lms_and_planning_restore_zero_overhead_and_ist_coordination(self):
  cfg,_,work=self.cfg(learning=False,planning_improved=False)
  self.assertIsNone(cfg.workflow.learning);self.assertIsNone(work);self.assertEqual(cfg.workflow.coordination_minutes,15)
  cfg,_,_=self.cfg(planning_improved=True);self.assertEqual(cfg.workflow.coordination_minutes,5)
  for ist in (False,True):
   for planning in (False,True):
    cfg,_,_=self.cfg(ist=ist,planning_improved=planning)
    self.assertEqual(cfg.workflow.coordination_minutes,5 if planning else 15)
    self.assertEqual(cfg.target,20 if ist else 30)
 def test_both_author_cases_have_same_cost_but_different_calendar_effect(self):
  team,_,t=self.cfg(learning=True,actor='prelaunch_team');daniel,_,d=self.cfg(learning=True,actor='daniel_calendar')
  self.assertAlmostEqual(t['internal_hours'],353.25);self.assertAlmostEqual(d['trainer_overhead_hours'],353.25)
  self.assertEqual(t['trainer_overhead_hours'],0);self.assertEqual(set(x for k,x in team.workflow.learning.topic_ready_at),{0})
  self.assertGreater(max(x for k,x in daniel.workflow.learning.topic_ready_at),0)
  self.assertEqual(team.workflow.learning.implementation_chf,daniel.workflow.learning.implementation_chf)
 def test_crossqualification_and_extra_coach_add_only_declared_capacity(self):
  q,_,_=self.cfg(overrides={'pq_practice_qualified':True});self.assertIn('practice',q.resources[0].phases)
  c,_,_=self.cfg(overrides={'practice_coach_count':2});self.assertEqual(sum(r.role=='trainer' for r in c.resources),3)
 def test_invalid_operating_inputs_rejected(self):
  for k,v in [('physical_group_capacity',50),('annual_cases',True),('training_days',5),('minimum_logistics_working',45),('pass_probability',1.1),('course_order','random'),('pq_practice_qualified',1)]:
   changed=deepcopy(self.v);changed[k]=v
   with self.subTest(k=k),self.assertRaises(ValueError):validate_operating(changed)
