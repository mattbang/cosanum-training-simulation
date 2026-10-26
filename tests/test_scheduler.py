"""Scheduling optimizations preserve calendars and actual start deadlines."""
import random
import unittest

from cosanum_sim.domain import Resource
from cosanum_sim.scheduler import Scheduler, Slot, subtract


def sequential_subtract(windows, busy):
    """Historical interval difference, including unusual nonpositive spans."""
    for start, end in busy:
        remaining = []
        for a, b in windows:
            if end <= a or start >= b:
                remaining.append((a, b))
            else:
                if a < start:
                    remaining.append((a, start))
                if end < b:
                    remaining.append((end, b))
        windows = remaining
    return windows


def random_calendar(rng):
    """Positive, sorted disjoint intervals, including adjacent boundaries."""
    result = []
    cursor = rng.randrange(-20, 10)
    for _ in range(rng.randrange(8)):
        start = cursor + rng.randrange(8)
        cursor = start + rng.randrange(1, 25)
        result.append((start, cursor))
    return result


def scan_find(scheduler, topic, people, now, duration, deadline, latest,
              phase, preparation, follow_up):
    """Independent integer-time oracle for finite synthetic calendars.

    Every boundary in these fixtures is integral, so a feasible optimum is
    integral too. Check occupied time directly rather than subtracting or
    intersecting feasible-start windows.
    """
    resources = scheduler.resources
    qualification = 'theory' if phase == 'assessment' else phase
    trainers = ([r for r in resources if r.role == 'trainer'
                 and topic in r.topic_ids and qualification in r.phases]
                if phase != 'self_learning' else [None])
    rooms = ([r for r in resources if r.role == 'room'
              and topic in r.topic_ids and phase in r.phases]
             if phase not in ('proof', 'self_learning', 'assessment') else [None])
    participants = {r.resource_id: r for r in resources if r.role == 'participant'}

    def available(resource, identity, begin, end):
        if resource is not None and not any(a <= begin and end <= b
                                            for a, b in resource.intervals):
            return False
        return all(stop <= begin or start >= end
                   for start, stop in scheduler.busy.get(identity, []))

    horizon = max((b for r in resources for _, b in r.intervals), default=0)
    upper = min(horizon, deadline) if deadline is not None else horizon
    choices = []
    for start in range(now + preparation, upper + 1):
        end = start + duration
        for trainer in trainers:
            if trainer and not available(trainer, trainer.resource_id,
                                         start - preparation, end + follow_up):
                continue
            for room in rooms:
                if room and not available(room, room.resource_id, start, end):
                    continue
                if not all(available(participants.get(person), person, start, end)
                           for person in people):
                    continue
                choices.append(Slot(start, end,
                                    trainer.resource_id if trainer else '',
                                    room.resource_id if room else '', tuple(people),
                                    start - preparation, end + follow_up))
    return min(choices, key=lambda s: (-s.start if latest else s.start,
                                      s.trainer_id, s.room_id)) if choices else None


class IntervalDifference(unittest.TestCase):
    def test_hand_calculated_boundaries_and_legacy_nonpositive_spans(self):
        cases = [
            ([], [(0, 10)], []),
            ([(0, 10)], [], [(0, 10)]),
            ([(0, 10)], [(-5, 15)], []),
            ([(0, 10)], [(3, 7)], [(0, 3), (7, 10)]),
            ([(0, 10)], [(-5, 3), (7, 15)], [(3, 7)]),
            ([(0, 10)], [(-5, 0), (10, 15)], [(0, 10)]),
            ([(0, 10)], [(3, 5), (5, 7)], [(0, 3), (7, 10)]),
            ([(0, 10), (10, 20)], [(5, 15)], [(0, 5), (15, 20)]),
            ([(0, 10), (20, 30)], [(5, 25)], [(0, 5), (25, 30)]),
            ([(0, 10)], [(5, 5)], [(0, 5), (5, 10)]),
            ([(0, 10)], [(7, 3)], [(0, 7), (3, 10)]),
            ([(5, 5)], [], [(5, 5)]),
            ([(5, 5)], [(0, 10)], []),
            ([(5, 5)], [(5, 10)], [(5, 5)]),
            ([(10, 0)], [], [(10, 0)]),
            ([(10, 0)], [(2, 8)], [(10, 0)]),
            ([(10, 0)], [(-1, 11)], []),
            ([(0, float('inf'))], [(10, 20)],
             [(0, 10), (20, float('inf'))]),
            ([(0, float('inf'))], [(20, float('inf'))], [(0, 20)]),
            ([(float('-inf'), float('inf'))], [(0, 10)],
             [(float('-inf'), 0), (10, float('inf'))]),
            ([(float('-inf'), float('inf'))],
             [(10, float('inf')), (float('-inf'), -10)], [(-10, 10)]),
            ([(0, float('inf'))], [(float('-inf'), float('inf'))], []),
        ]
        for windows, busy, expected in cases:
            with self.subTest(windows=windows, busy=busy):
                self.assertEqual(subtract(windows, busy), expected)

    def test_unsorted_overlapping_occupancy_matches_sequential_difference(self):
        rng = random.Random(7103)
        for case in range(2000):
            windows = random_calendar(rng)
            if case % 13 == 0:
                point = rng.randrange(-20, 100)
                windows.insert(rng.randrange(len(windows) + 1), (point, point))
            if case % 17 == 0:
                point = rng.randrange(-20, 100)
                windows.insert(rng.randrange(len(windows) + 1), (point + 5, point))
            busy = []
            for _ in range(rng.randrange(20)):
                start = rng.randrange(-40, 180)
                end = start + rng.randrange(1, 50)
                busy.append((start, end))
            if windows and case % 3 == 0:
                a, b = rng.choice(windows)
                busy.extend([(a - 5, a), (b, b + 5), (a, b)])
            if case % 7 == 0:
                point = rng.randrange(-20, 100)
                busy.append((point, point))
            if case % 11 == 0:
                point = rng.randrange(-20, 100)
                busy.append((point + 5, point))
            rng.shuffle(busy)
            original_windows, original_busy = list(windows), list(busy)
            with self.subTest(case=case):
                self.assertEqual(subtract(windows, busy),
                                 sequential_subtract(windows, busy))
                self.assertEqual(windows, original_windows)
                self.assertEqual(busy, original_busy)


class FeasibleSlots(unittest.TestCase):
    @staticmethod
    def resources():
        return (Resource('trainer', 'trainer', ('A',), ((0, 200),)),
                Resource('room', 'room', ('A',), ((0, 200),)),
                Resource('person', 'participant', (), ((0, 200),)))

    def test_deadline_before_preparation_finishes_skips_calendar_scan(self):
        class NoCalendarScan(Scheduler):
            def free(self, resource):
                raise AssertionError('infeasible deadline must skip calendar scans')

        scheduler = NoCalendarScan(self.resources())
        for latest in (False, True):
            with self.subTest(latest=latest):
                self.assertIsNone(scheduler.find('A', ('person',), now=10,
                                                duration=20, deadline=24,
                                                latest=latest, preparation=15))

    def test_exact_preparation_boundary_is_a_feasible_delivery_start(self):
        scheduler = Scheduler(self.resources())
        for latest in (False, True):
            with self.subTest(latest=latest):
                slot = scheduler.find('A', ('person',), now=10, duration=20,
                                      deadline=25, latest=latest,
                                      preparation=15, follow_up=5)
                self.assertEqual(slot, Slot(25, 45, 'trainer', 'room',
                                            ('person',), 10, 50))

    def test_latest_and_earliest_respect_preparation_and_delivery_resources(self):
        resources = (Resource('trainer', 'trainer', ('A',), ((0, 100),)),
                     Resource('room', 'room', ('A',), ((30, 80),)),
                     Resource('person', 'participant', (), ((35, 90),)))
        scheduler = Scheduler(resources)
        earliest = scheduler.find('A', ('person',), now=25, duration=20,
                                  deadline=55, preparation=10, follow_up=15)
        latest = scheduler.find('A', ('person',), now=25, duration=20,
                                deadline=55, latest=True,
                                preparation=10, follow_up=15)
        self.assertEqual(earliest, Slot(35, 55, 'trainer', 'room',
                                       ('person',), 25, 70))
        self.assertEqual(latest, Slot(55, 75, 'trainer', 'room',
                                     ('person',), 45, 90))
        scheduler.reserve(earliest)
        self.assertIsNone(scheduler.find('A', ('person',), now=25, duration=20,
                                        deadline=55, preparation=10,
                                        follow_up=15))

    def test_finds_match_independent_integer_time_feasibility_scan(self):
        rng = random.Random(17003)
        phases = ('theory', 'practice', 'proof', 'assessment', 'self_learning')
        for case in range(250):
            resources = tuple(Resource(f'{role}-{i}', role,
                                       ('A',) if role != 'participant' else (),
                                       tuple(random_calendar(rng)))
                              for role in ('trainer', 'room', 'participant')
                              for i in range(2))
            scheduler = Scheduler(resources)
            for identity in [r.resource_id for r in resources] + ['unknown']:
                busy = []
                for _ in range(rng.randrange(6)):
                    start = rng.randrange(120)
                    busy.append((start, start + rng.randrange(1, 20)))
                rng.shuffle(busy)
                scheduler.busy[identity] = busy
            people = rng.choice([('participant-0',),
                                 ('participant-0', 'participant-1'),
                                 ('participant-0', 'unknown')])
            arguments = dict(topic='A', people=people, now=rng.randrange(50),
                             duration=rng.randrange(1, 21),
                             deadline=rng.choice([None, rng.randrange(160)]),
                             latest=bool(rng.randrange(2)), phase=rng.choice(phases),
                             preparation=rng.randrange(16),
                             follow_up=rng.randrange(11))
            with self.subTest(case=case, arguments=arguments):
                self.assertEqual(scheduler.find(**arguments),
                                 scan_find(scheduler, **arguments))


if __name__ == '__main__':
    unittest.main()
