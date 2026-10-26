"""Pool shortcuts preserve the ordinary solver's resource constraints."""
import copy
import random
import unittest

from cosanum_sim.domain import Resource, Session
from cosanum_sim.scheduler import Scheduler, Slot, covers_calendar
from test_scheduler import scan_find


PHASES = ('theory', 'practice', 'proof', 'assessment', 'self_learning')


class StandardScheduler(Scheduler):
    def __init__(self, resources, sessions=()):
        super().__init__(resources, sessions, event_history_only=False)


def session(identity, start=20, end=40, trainer='trainer', room='room',
            people=('person', 'unknown'), phase='theory', prep=10, work=50,
            cancelled=None):
    return Session(identity, 'A', phase, (identity,), people, 'test', 0, 0,
                   start, end, trainer, room, prep, work, cancelled_at=cancelled)


def simple_resources(room_calendar=((0, 100),), person_calendar=((0, 100),)):
    return (Resource('trainer', 'trainer', ('A',), ((0, 100),)),
            Resource('room', 'room', ('A',), room_calendar),
            Resource('person', 'participant', (), person_calendar))


class PoolScheduling(unittest.TestCase):
    def pair(self, resources, history=()):
        return (StandardScheduler(resources, history),
                Scheduler(resources, history, event_history_only=True))

    def check_query(self, ordinary, pool, **arguments):
        expected = ordinary.find(**arguments)
        actual = pool.find(**arguments)
        self.assertEqual(actual, expected)
        self.assertEqual(actual, scan_find(ordinary, **arguments))
        self.assertEqual(ordinary.busy, pool.busy)
        return actual

    def reserve_both(self, ordinary, pool, slot):
        ordinary.reserve(slot)
        pool.reserve(slot)
        self.assertEqual(ordinary.busy, pool.busy)
        for resource in ordinary.resources:
            self.assertEqual(ordinary.free(resource), pool.free(resource))

    def test_coverage_preserves_separate_calendar_boundaries(self):
        cases = [(((0, 100),), ((0, 100),), True),
                 (((0, 100),), ((0, 50), (50, 100)), True),
                 (((0, 50), (50, 100)), ((0, 50), (50, 100)), True),
                 (((0, 50), (50, 100)), ((0, 100),), False),
                 (((0, 49), (50, 100)), ((0, 100),), False)]
        for cover, required, expected in cases:
            with self.subTest(cover=cover, required=required):
                self.assertEqual(covers_calendar(cover, required), expected)
        for calendar, expected_start in [(((0, 100),), 40),
                                          (((0, 50), (50, 100)), 50),
                                          (((0, 49), (50, 100)), 50),
                                          (((0, 45), (60, 100)), 60)]:
            with self.subTest(calendar=calendar):
                ordinary, pool = self.pair(simple_resources(room_calendar=calendar))
                slot = self.check_query(ordinary, pool, topic='A',
                                        people=('person', 'unknown'), now=40,
                                        duration=20, deadline=80, latest=False,
                                        phase='theory', preparation=0, follow_up=0)
                self.assertEqual(slot.start, expected_start)

    def test_trust_boundaries_history_cancellations_and_reservations(self):
        resources = simple_resources()
        # Public generic use permits direct occupancy mutation and must retain
        # every room/participant constraint even with one covered trainer.
        for identity in ('room', 'person', 'unknown'):
            with self.subTest(manual_busy=identity):
                ordinary, generic = StandardScheduler(resources), Scheduler(resources)
                self.assertFalse(generic._pool_safe)
                ordinary.busy[identity] = [(40, 60)]
                generic.busy[identity] = [(40, 60)]
                slot = self.check_query(ordinary, generic, topic='A',
                                        people=('person', 'unknown'), now=40,
                                        duration=10, deadline=90, latest=False,
                                        phase='theory', preparation=0, follow_up=0)
                self.assertEqual(slot.start, 60)

        # Unprotected delivery occupancy must permanently disable the pool
        # shortcut, including delivery starting before trainer preparation.
        for trainer_id, prep, work in (('', 40, 60), ('foreign', 40, 60),
                                       ('trainer', 45, 60)):
            ordinary, pool = self.pair(resources)
            self.reserve_both(ordinary, pool, Slot(40, 60, trainer_id, '',
                                                  ('person', 'unknown'), prep, work))
            self.assertFalse(pool._pool_safe)
            for phase in ('assessment', 'self_learning'):
                with self.subTest(trainer=trainer_id, phase=phase, prep=prep):
                    slot = self.check_query(ordinary, pool, topic='A',
                                            people=('person', 'unknown'), now=40,
                                            duration=5, deadline=90, latest=False,
                                            phase=phase, preparation=0, follow_up=0)
                    self.assertEqual(slot.start, 60)

        for cancelled in (5, 15, 25, 55, None):
            ordinary, pool = self.pair(resources,
                                       (session('cancel', cancelled=cancelled),))
            for phase in PHASES:
                with self.subTest(cancelled=cancelled, phase=phase):
                    self.check_query(ordinary, pool, topic='A',
                                     people=('person', 'unknown'), now=10,
                                     duration=10, deadline=80, latest=False,
                                     phase=phase, preparation=5, follow_up=5)

        ordinary, pool = self.pair(resources)
        self.assertTrue(pool._pool_safe)
        self.reserve_both(ordinary, pool, Slot(40, 60, 'trainer', 'room',
                                              ('person', 'unknown'), 30, 70))
        self.assertTrue(pool._pool_safe)
        for phase in PHASES:
            with self.subTest(protected_phase=phase):
                self.check_query(ordinary, pool, topic='A',
                                 people=('person', 'unknown'), now=40,
                                 duration=10, deadline=90, latest=False,
                                 phase=phase, preparation=0, follow_up=0)

    def test_random_pool_queries_match_ordinary_solver_and_independent_scan(self):
        rng = random.Random(51003)
        feasible = 0
        for case in range(400):
            mode = case % 8
            trainer_calendar = ((0, 120), (150, 300))
            covered = ((0, 300),)
            adjacent = ((0, 60), (60, 120), (150, 220), (220, 300))
            gapped = ((0, 59), (60, 120), (150, 219), (220, 300))
            partial = ((20, 100), (175, 260))
            room_calendar = gapped if mode == 2 else adjacent if mode == 3 else covered
            resources = [Resource('trainer', 'trainer', ('A', 'B'), trainer_calendar),
                         Resource('room', 'room', ('A', 'B'), room_calendar),
                         Resource('room-second', 'room', ('A',), covered),
                         Resource('person', 'participant', (),
                                  partial if mode == 1 else covered),
                         Resource('second-person', 'participant', (),
                                  adjacent if mode == 3 else covered)]
            if mode == 4:
                resources.append(Resource('second-trainer', 'trainer', ('A',), covered))
            rng.shuffle(resources)
            history = []
            for index in range(rng.randrange(1, 7)):
                start = rng.randrange(10, 250)
                end = start + rng.randrange(1, 25)
                phase = PHASES[index % len(PHASES)]
                trainer_id = ('' if mode == 5 and index == 0 else
                              'foreign' if mode == 6 and index == 0 else 'trainer')
                room_id = 'room' if phase in ('theory', 'practice') else ''
                prep, work = start - rng.randrange(9), end + rng.randrange(9)
                cancelled = (rng.choice((None, prep - 1, prep + 1, start,
                                         start + 1, end + 1)) if mode == 7 else None)
                history.append(session(str(index), start, end, trainer_id, room_id,
                                       ('person', 'unknown') if index % 2 else ('second-person',),
                                       phase, prep, work, cancelled))
            resources = tuple(resources)
            ordinary, pool = self.pair(resources, history)
            original_calendars = tuple(r.intervals for r in resources)
            for index in range(5):
                if index == 2:
                    start = rng.randrange(20, 200)
                    end = start + rng.randrange(1, 25)
                    trainer_id = rng.choice(('trainer', '', 'foreign'))
                    prep, work = start - rng.randrange(9), end + rng.randrange(9)
                    if case % 5 == 0:
                        trainer_id, prep, work = 'trainer', start + 1, end
                    self.reserve_both(ordinary, pool,
                                      Slot(start, end, trainer_id, rng.choice(('room', '')),
                                           ('person', 'unknown'), prep, work))
                now, prep = rng.randrange(200), rng.randrange(16)
                arguments = dict(topic='A', people=rng.choice((('person',),
                                                               ('person', 'unknown'),
                                                               ('person', 'second-person'))),
                                 now=now, duration=rng.randrange(1, 26),
                                 deadline=rng.choice((None, now + prep,
                                                      now + prep - 1, now - 1, 285)),
                                 latest=bool(rng.randrange(2)), phase=PHASES[index],
                                 preparation=prep, follow_up=rng.randrange(16))
                with self.subTest(case=case, arguments=arguments):
                    feasible += self.check_query(ordinary, pool, **arguments) is not None
                    self.assertEqual(tuple(r.intervals for r in resources), original_calendars)
        # The fixed fixtures exercise successful schedules as well as failures.
        self.assertGreater(feasible, 500)

    def test_metadata_uses_calendar_values_and_accepts_unhashable_fields(self):
        # Equal calendar values in fresh Resource objects give the same result;
        # reusing IDs with different values must not reuse the old coverage.
        calendars = [((0, 100),), ((0, 100),), ((60, 100),)]
        starts = []
        for calendar in calendars:
            resources = simple_resources(person_calendar=calendar)
            ordinary, pool = self.pair(resources)
            slot = self.check_query(ordinary, pool, topic='A', people=('person',),
                                    now=40, duration=10, deadline=90,
                                    latest=False, phase='theory',
                                    preparation=0, follow_up=0)
            starts.append(slot.start)
        self.assertEqual(starts, [40, 40, 60])

        # Resource accepts list fields from a caller; trust-mode construction
        # must calculate uncached metadata when those fields cannot be hashed.
        resources = [Resource('trainer', 'trainer', ['A'], [[0, 100]], ['theory']),
                     Resource('room', 'room', ['A'], [[0, 100]], ['theory']),
                     Resource('person', 'participant', [], [[0, 100]], ['theory'])]
        original = copy.deepcopy(resources)
        ordinary, pool = self.pair(resources)
        self.reserve_both(ordinary, pool, Slot(40, 60, 'trainer', 'room',
                                              ('person',), 30, 70))
        slot = self.check_query(ordinary, pool, topic='A', people=('person',),
                                now=40, duration=10, deadline=90,
                                latest=False, phase='theory',
                                preparation=0, follow_up=0)
        self.assertEqual(slot.start, 70)
        self.assertEqual(resources, original)


if __name__ == '__main__':
    unittest.main()
