import unittest
from copy import deepcopy
from pathlib import Path
from cosanum_dashboard.experiments import bootstrap,validate,prepare
HERE=Path(__file__).resolve().parents[1]
class LMSControls(unittest.TestCase):
 def setUp(self):
  self.s=bootstrap(HERE.parent,HERE);self.p=dict(values=deepcopy(self.s['defaults']),solutions=[True]*6+[False,True],options=deepcopy(self.s['option_defaults']),mode='annual_same_volume',seed=600,replications=1)
 def test_off_bypasses_portfolio_and_calendar(self):
  self.p['solutions'][7]=False;x=prepare(HERE.parent,validate(self.p,self.s),self.s,600)
  self.assertIsNone(x['chosen'].workflow.learning);self.assertIsNone(x['workload'])
 def test_both_author_cases_are_selectable(self):
  for actor,hours in [('prelaunch_team',0),('daniel_calendar',353.25)]:
   self.p['options']['actor']=actor;x=prepare(HERE.parent,validate(self.p,self.s),self.s,600)
   self.assertAlmostEqual(x['workload']['trainer_overhead_hours'],hours);self.assertEqual(x['chosen'].workflow.learning.max_self_retries,1)
 def test_45_requires_explicit_staffing_relaxation(self):
  self.p['values']['group']=45
  with self.assertRaisesRegex(ValueError,'Freistellung'):validate(self.p,self.s)
  self.p['options']['minimum_working']=0;x=prepare(HERE.parent,validate(self.p,self.s),self.s,600);self.assertEqual(x['chosen'].capacity,45)
 def test_unchecked_planning_restores15min(self):
  self.p['solutions'][3]=False;x=prepare(HERE.parent,validate(self.p,self.s),self.s,600)
  self.assertEqual(x['chosen'].workflow.coordination_minutes,15)
 def test_internal_budget_changes_have_time_and_cost_effect_once(self):
  self.p['options']['course_chf']=100;x=prepare(HERE.parent,validate(self.p,self.s),self.s,600)
  self.assertEqual(x['learning']['effort']['content_hours'],63)
  self.assertAlmostEqual(x['learning']['first_year_portfolio_chf'],13862.2896)
 def test_invalid_options_do_not_execute(self):
  for k,v in [('minimum_working',True),('practice_coaches',3),('setup_chf',-1),('actor','unknown'),('pq_practice_qualified',1)]:
   p=deepcopy(self.p);p['options'][k]=v
   with self.subTest(k=k),self.assertRaises(ValueError):validate(p,self.s)
