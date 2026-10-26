"""Annual interpretation is explicit; synthetic fixtures reconcile by cohort."""
import json
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace

from cosanum_sim.annual_demand import load_profile, annual_fixture
from cosanum_sim.demand import expand_batches, validate_requests
from cosanum_sim.domain import Topic
from cosanum_sim.inputs import load_topics
from cosanum_sim.randomness import seed_map

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'config/annual_profile.json'


class AnnualDemand(unittest.TestCase):
    def setUp(self):
        self.profile = load_profile(PROFILE)
        self.topics = load_topics(ROOT / 'data/processed/topic_catalog.csv')
        self.seeds = seed_map(20261003, 100)

    def test_fixed_occurrences_reconcile_as_participations_not_people(self):
        fixture, requests = annual_fixture(self.topics, self.seeds, self.profile)
        self.assertEqual(len(fixture['batches']), 65)
        self.assertEqual(len(requests), 350)
        group = [b for b in fixture['batches'] if b['baseline_delivery'] == 'group']
        single = [b for b in fixture['batches'] if b['baseline_delivery'] == 'individual']
        self.assertEqual((len(group), len(single)), (15, 50))
        self.assertTrue(all(b['size'] == 20 for b in group))
        self.assertTrue(all(b['size'] == 1 for b in single))
        self.assertTrue(all(self.topics[b['topic_id']].theory_group_possible for b in group))
        self.assertEqual(len({r.person_id for r in requests}), 45)
        self.assertTrue(all(r.person_id.startswith('synthetic-internal-') for r in requests))
        self.assertTrue(all(len(b['person_ids']) == len(set(b['person_ids'])) for b in fixture['batches']))
        self.assertEqual(fixture['annual_summary']['annual_person_topic_participations'], 350)
        unknown = self.profile.provenance['unresolved_source_fields']
        self.assertTrue(any(x['input_id'] == 'actual_annual_training_volume' and x['value'] is None for x in unknown))

    def test_reproducibility_and_independent_group_size_sensitivity(self):
        first, requests = annual_fixture(self.topics, self.seeds, self.profile)
        self.assertEqual((first, requests), annual_fixture(self.topics, self.seeds, self.profile))
        other, _ = annual_fixture(self.topics, seed_map(20261003, 101), self.profile)
        self.assertNotEqual(first['batches'], other['batches'])
        larger, larger_requests = annual_fixture(self.topics, self.seeds, self.profile.with_overrides({'group_size': 25}))
        projection = lambda f: [(b['batch_id'], b['noticed_at'], b['topic_id']) for b in f['batches']]
        self.assertEqual(projection(first), projection(larger))
        self.assertEqual(len(larger_requests), 425)
        self.assertEqual(self.profile.values['group_size'], 20)

    def test_detection_tail_is_explicit_and_does_not_guarantee_clearance(self):
        first, requests = annual_fixture(self.topics, self.seeds, self.profile)
        self.assertEqual(first['horizon_minutes'], 525600)
        self.assertEqual(first['annual_profile']['derived_closeout_days'], 35)
        self.assertTrue(all(0 <= r.noticed_at < 330*1440 for r in requests))
        full, full_requests = annual_fixture(self.topics, self.seeds, self.profile.with_overrides({'arrival_window_days': 365}))
        self.assertEqual(full['annual_profile']['derived_closeout_days'], 0)
        self.assertTrue(all(0 <= r.noticed_at < 365*1440 for r in full_requests))
        self.assertEqual([b['topic_id'] for b in first['batches']], [b['topic_id'] for b in full['batches']])

    def test_optional_stock_remains_a_separate_exact_cohort(self):
        first, ongoing = annual_fixture(self.topics, self.seeds, self.profile)
        combined, requests = annual_fixture(self.topics, self.seeds, self.profile, include_backlog=True)
        self.assertEqual([r for r in requests if r.cohort_id == 'ongoing'], ongoing)
        initial = [r for r in requests if r.cohort_id == 'initial']
        self.assertEqual(len(initial), 1305)
        self.assertEqual([sum(self.topics[r.topic_id].priority == p for r in initial) for p in (1,2,3)], [191,333,781])
        self.assertEqual(len(requests), 1655)
        self.assertTrue(all(r.baseline_delivery is None and r.noticed_at == 0 for r in initial))
        self.assertEqual(len({(r.person_id,r.topic_id,r.cycle_id) for r in requests}), 1655)
        validate_requests(requests, self.topics, full_workflow=True)
        self.assertEqual(combined['annual_summary']['initial_priority_counts'], {'1':191,'2':333,'3':781})
        for key in ('annual_person_topic_participations','rough_baseline_annual_trainer_minutes'):
            self.assertEqual(first['annual_summary'][key], combined['annual_summary'][key])

    def test_hand_calculated_required_practice_workload(self):
        topics = {'A': Topic('A',1,True,True,True,False,0)}
        profile = self.profile.with_overrides({'group_training_count':2,'individual_training_count':3,'group_size':2,'synthetic_internal_pool_size':4})
        f, requests = annual_fixture(topics,self.seeds,profile)
        s=f['annual_summary']
        self.assertEqual(len(requests),7)
        self.assertEqual(s['practice_required_count'],7)
        self.assertEqual(s['rough_baseline_theory_trainer_minutes'],660) # 2x240 + 3x60
        self.assertEqual(s['rough_annual_individual_practice_trainer_minutes'],1260)
        self.assertEqual(s['rough_baseline_annual_trainer_minutes'],1920)
        self.assertEqual(s['rough_annual_participant_minutes'],1680) # 7x(60+180)

    def test_source_eligibility_and_hint_validation(self):
        ineligible = {'I': Topic('I',1,True,False,False,False,0)}
        with self.assertRaisesRegex(ValueError, 'source-eligible'):
            annual_fixture(ineligible,self.seeds,self.profile)
        only_single = self.profile.with_overrides({'group_training_count':0})
        f, requests = annual_fixture(ineligible,self.seeds,only_single)
        self.assertEqual(len(requests),50)
        bad = dict(f)
        bad['batches'] = [dict(f['batches'][0],baseline_delivery='group')]
        with self.assertRaisesRegex(ValueError, 'source topic eligibility'):
            validate_requests(expand_batches(bad), ineligible, True)
        with self.assertRaisesRegex(ValueError, 'Unknown baseline delivery'):
            validate_requests([replace(requests[0],baseline_delivery='invented')], ineligible, True)

    def test_contradictory_or_unsupported_profile_inputs_fail(self):
        cases = [{'group_training_count':True}, {'individual_training_count':-1}, {'group_size':46},
                 {'arrival_window_days':366}, {'resource_calendar_weekdays':[1,1]},
                 {'resource_days_per_week':3}, {'resource_calendar_end_minute':540},
                 {'reported_count_phase_interpretation':'full_workflows'},
                 {'initial_backlog_age_minutes':1}, {'recovery_aged_every':0},
                 {'participant_calendar_weekdays':[7]}]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.profile.with_overrides(changes)
        with self.assertRaisesRegex(ValueError,'Unknown annual'):
            self.profile.with_overrides({'actual_annual_cost':0})
        with self.assertRaisesRegex(ValueError,'Synthetic pool too small'):
            annual_fixture(self.topics,self.seeds,self.profile.with_overrides({'synthetic_internal_pool_size':30}),True)

    def test_profile_provenance_and_source_bindings_are_required(self):
        raw=json.loads(PROFILE.read_text())
        self.assertEqual(self.profile.bound_source_values['theory_minutes']['value'],60)
        self.assertEqual(self.profile.bound_source_values['practice_minutes']['value'],180)
        self.assertEqual(self.profile.bound_source_values['group_pq_hours']['value'],4)
        changed=self.profile.with_overrides({'group_size':25}).resolved()
        self.assertEqual(changed['provenance']['overrides']['group_size']['original'],20)
        self.assertEqual(changed['values']['group_size'],25)
        self.assertEqual(next(x for x in changed['provenance']['inputs'] if x['input_id']=='group_size')['value'],20)
        raw['inputs'][0].pop('limitation')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'annual_profile.json'
            p.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError,'provenance'):
                load_profile(p)


if __name__ == '__main__':
    unittest.main()
