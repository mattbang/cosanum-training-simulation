"""Interval scheduling: trainer preparation/follow-up excludes room and attendees."""
from dataclasses import dataclass
from functools import lru_cache
from itertools import product


@dataclass(frozen=True)
class Slot:
    start: float
    end: float
    trainer_id: str
    room_id: str
    people: tuple
    preparation_start: float
    work_end: float


def intersect(left, right):
    # Calendar subtraction and duration conversion produce sorted disjoint
    # ranges. Preserve closed, exact-start points without a Cartesian scan.
    result = []
    i = j = 0
    while i<len(left) and j<len(right):
        a,b = left[i]
        c,d = right[j]
        low,high = max(a,c),min(b,d)
        if low<=high:
            result.append((low,high))
        if b<d:
            i+=1
        elif d<b:
            j+=1
        else:
            i+=1
            j+=1
    return result


def subtract(windows, busy):
    # Real calendars and occupied intervals have positive length. Preserve
    # original splitting semantics for nonpositive spans used directly here.
    if any(start>=end for start,end in busy) or any(a>=b for a,b in windows):
        for start,end in busy:
            remaining = []
            for a,b in windows:
                if end <= a or start >= b:
                    remaining.append((a,b))
                else:
                    if a < start:
                        remaining.append((a,start))
                    if end < b:
                        remaining.append((end,b))
            windows = remaining
        return windows
    merged = []
    for start,end in sorted(busy):
        if merged and start<=merged[-1][1]:
            merged[-1] = (merged[-1][0],max(end,merged[-1][1]))
        else:
            merged.append((start,end))
    # Calendars are validated in order and disjoint. Retain their boundaries
    # while walking the occupied union, including spans crossing calendar gaps.
    remaining = []
    i = 0
    for a,b in windows:
        while i<len(merged) and merged[i][1]<=a:
            i += 1
        cursor,j = a,i
        while j<len(merged) and merged[j][0]<b:
            start,end = merged[j]
            if start>cursor:
                remaining.append((cursor,start))
            cursor = max(cursor,end)
            if cursor>=b:
                break
            j += 1
        if cursor<b:
            remaining.append((cursor,b))
        i = j
    return remaining


def occupied_intervals(session):
    begin = session.preparation_start if session.preparation_start is not None else session.start
    end = session.work_end if session.work_end is not None else session.end
    stop = session.cancelled_at
    trainer_end = min(end,stop) if stop is not None else end
    delivery_end = min(session.end,stop) if stop is not None else session.end
    result = [(session.trainer_id,begin,trainer_end)] if session.trainer_id and trainer_end > begin else []
    if delivery_end > session.start:
        result.extend((identity,session.start,delivery_end) for identity in (session.room_id,*session.person_ids) if identity)
    return result


def subtract_booking(windows, start, end):
    """Subtract one positive booking from sorted disjoint free intervals.

    Locate the affected range by its end, then copy untouched spans in C.
    Calendar boundaries and exact touching endpoints retain subtract semantics.
    """
    if start>=end:
        return subtract(windows,[(start,end)])
    lo,hi=0,len(windows)
    while lo<hi:
        mid=(lo+hi)//2
        if windows[mid][1]<=start:lo=mid+1
        else:hi=mid
    first=lo;pieces=[]
    while lo<len(windows) and windows[lo][0]<end:
        a,b=windows[lo]
        if a<start:pieces.append((a,start))
        if end<b:pieces.append((end,b))
        lo+=1
    return windows[:first]+pieces+windows[lo:]


class StartRanges:
    """Seek over ordered free calendars while preserving closed delivery starts."""
    def __init__(self, windows, now, duration, before, after, deadline, latest):
        self.windows=windows;self.now=now;self.duration=duration;self.before=before;self.after=after;self.deadline=deadline;self.latest=latest
        self.index=len(windows)-1 if latest else 0
        self._jump(deadline if latest and deadline is not None else float('inf') if latest else now+before)
    def __iter__(self):return self
    def _jump(self,target):
        lo,hi=(0,self.index+1) if self.latest else (self.index,len(self.windows))
        threshold=target-self.before if self.latest else target+self.duration+self.after
        while lo<hi:
            mid=(lo+hi)//2
            if (self.windows[mid][0]<=threshold if self.latest else self.windows[mid][1]<threshold):lo=mid+1
            else:hi=mid
        self.index=lo-1 if self.latest else lo
    def seek_point(self,target):
        self._jump(target)
        return next(self,None)
    def __next__(self):
        while 0<=self.index<len(self.windows):
            a,b=self.windows[self.index];self.index+=-1 if self.latest else 1
            low,high=max(a,self.now)+self.before,b-self.duration-self.after
            if self.deadline is not None:
                if low>self.deadline:
                    if not self.latest:raise StopIteration
                    continue
                high=min(high,self.deadline)
            if low<=high:return low,high
        raise StopIteration


def add_attendance(segments, start, end, count, prior_peak=None):
    """Add a half-open weighted booking to an ordered sparse occupancy map.

    An optional prior peak updates the exact maximum for nonnegative bookings
    without rescanning unaffected intervals. Scheduler attendance uses such
    bookings exclusively. Public callers may omit it to obtain only segments.
    """
    if end<=start or count==0:return segments if prior_peak is None else (segments,prior_peak)
    lo,hi=0,len(segments)
    while lo<hi:
        mid=(lo+hi)//2
        if segments[mid][1]<=start:lo=mid+1
        else:hi=mid
    first=lo;changed=[];cursor=start;peak=max(prior_peak or 0,count)
    while lo<len(segments) and segments[lo][0]<end:
        a,b,n=segments[lo]
        if a<start:changed.append((a,start,n))
        if cursor<a:changed.append((cursor,a,count))
        low,high=max(a,start),min(b,end)
        changed.append((low,high,n+count));cursor=high;peak=max(peak,n+count)
        if b>end:changed.append((end,b,n))
        lo+=1
    if cursor<end:changed.append((cursor,end,count))
    # Adjacent equal loads need not be merged: boundaries preserve exact starts.
    result=segments[:first]+changed+segments[lo:]
    return result if prior_peak is None else (result,peak)


def common_start(iterators, latest=False):
    """Find the first/last common closed point without building intersections."""
    current=[next(it,None) for it in iterators]
    while all(window is not None for window in current):
        low=max(window[0] for window in current)
        high=min(window[1] for window in current)
        if low<=high:return high if latest else low
        for i,window in enumerate(current):
            if (window[0]>high if latest else window[1]<low):
                current[i]=iterators[i].seek_point(high if latest else low) if hasattr(iterators[i],'seek_point') else next(iterators[i],None)
    return None


def covers_calendar(cover, required):
    """Each required window fits inside one covering calendar window.

    Adjacent covering windows are kept separate: the ordinary solver cannot
    place a delivery across their shared calendar boundary.
    """
    i = 0
    for a,b in required:
        while i<len(cover) and cover[i][1]<=a:
            i += 1
        if i==len(cover) or cover[i][0]>a or cover[i][1]<b:
            return False
    return True


def _pool_calendar_metadata(resources):
    trainers = [r for r in resources if r.role=='trainer']
    pool_id = trainers[0].resource_id if len(trainers)==1 else None
    covered = {r.resource_id:covers_calendar(r.intervals,trainers[0].intervals)
               for r in resources if r.role in ('room','participant')} if pool_id else {}
    return pool_id,covered,{r.resource_id:r for r in resources if r.role=='participant'}


@lru_cache(maxsize=1)
def _cached_pool_calendar_metadata(resources):
    # Provisional schedulers share immutable calendars throughout a run.
    # Retain only the latest configuration; eviction has no model effect.
    return _pool_calendar_metadata(resources)


class Scheduler:
    def __init__(self, resources, sessions=(), event_history_only=False,absence_limit=None):
        # The engine owns its occupancy through session records and reserve().
        # Public callers that edit busy directly retain the ordinary solver.
        sessions = tuple(sessions)
        self.absence_limit=absence_limit
        self.attendance=[(s.start,min(s.end,s.cancelled_at) if s.cancelled_at is not None else s.end,len(s.person_ids)) for s in sessions]
        self._attendance_cache={}
        self._attendance_segments=None
        self._attendance_peak=None
        self.resources = resources
        self._participants = {r.resource_id:r for r in resources if r.role=='participant'}
        self.busy = {}
        self._free_cache = {}
        for s in sessions:
            for identity,a,b in occupied_intervals(s):
                self.busy.setdefault(identity,[]).append((a,b))
        self._pool_id,self._covered,self._pool_participants = None,{},{}
        self._pool_safe = False
        if event_history_only and sum(r.role=='trainer' for r in resources)==1:
            try:
                metadata = _cached_pool_calendar_metadata(tuple(resources))
            except TypeError:
                # List-valued calendar records remain supported without caching.
                metadata = _pool_calendar_metadata(resources)
            self._pool_id,self._covered,self._pool_participants = metadata
            self._pool_safe = bool(self._pool_id) and all(self._pool_session(s) for s in sessions)

    def fork(self):
        """Independent tentative reservations against the same real calendars."""
        other = object.__new__(Scheduler)
        other.resources = self.resources
        other._participants = self._participants
        other.busy = {identity:list(spans) for identity,spans in self.busy.items()}
        other._free_cache = {identity:list(spans) for identity,spans in self._free_cache.items()}
        other._pool_id,other._covered,other._pool_participants = self._pool_id,self._covered,self._pool_participants
        other._pool_safe = self._pool_safe
        other.absence_limit=self.absence_limit;other.attendance=list(self.attendance);other._attendance_cache=dict(self._attendance_cache)
        other._attendance_segments=None if self._attendance_segments is None else list(self._attendance_segments);other._attendance_peak=self._attendance_peak
        return other

    def find_follow_ups(self, topic, people, earliest, duration, completion_limit,
                       preparation=0):
        """All individual practices, or none; never modify this scheduler.

        Caller has held theory and other protected first starts. Stable person
        order is a heuristic, not an optimal packing or a future-capacity claim.
        The existing observation horizon bounds the entire delivered practice.
        """
        trial = self.fork()
        result = []
        for person in people:
            slot = trial.find(topic,(person,),earliest,duration,
                              deadline=completion_limit-duration,phase='practice',
                              preparation=preparation)
            if slot is None or slot.work_end>completion_limit:
                return None
            trial.reserve(slot)
            result.append(slot)
        return tuple(result)

    def _pool_session(self, session):
        begin = session.preparation_start if session.preparation_start is not None else session.start
        end = session.work_end if session.work_end is not None else session.end
        return session.trainer_id==self._pool_id and begin<=session.start<session.end<=end

    def reserve(self, slot):
        self.attendance.append((slot.start,slot.end,len(slot.people)));self._attendance_cache.clear()
        if self._attendance_segments is not None:
            self._attendance_segments,self._attendance_peak=add_attendance(self._attendance_segments,slot.start,slot.end,len(slot.people),self._attendance_peak)
        self._pool_safe = (self._pool_safe and slot.trainer_id==self._pool_id
                           and slot.preparation_start<=slot.start<slot.end<=slot.work_end)
        if slot.trainer_id:
            if slot.trainer_id in self._free_cache:
                self._free_cache[slot.trainer_id] = subtract_booking(self._free_cache[slot.trainer_id],
                                                                   slot.preparation_start,slot.work_end)
            else:
                self._free_cache.pop(slot.trainer_id,None)
            self.busy.setdefault(slot.trainer_id,[]).append((slot.preparation_start,slot.work_end))
        for identity in (slot.room_id,*slot.people):
            if identity:
                if identity in self._free_cache:
                    self._free_cache[identity] = subtract_booking(self._free_cache[identity],slot.start,slot.end)
                self.busy.setdefault(identity,[]).append((slot.start,slot.end))

    def free(self, resource):
        if resource.resource_id not in self._free_cache:
            self._free_cache[resource.resource_id] = subtract(list(resource.intervals),self.busy.get(resource.resource_id,[]))
        return self._free_cache[resource.resource_id]

    def find(self, topic, people, now, duration, deadline=None, latest=False,
             phase='theory', preparation=0, follow_up=0):
        def ordinary():
            return self._ordinary_find(topic,people,now,duration,deadline,latest,phase,preparation,follow_up)
        if self.absence_limit is not None or not self._pool_safe or phase=='self_learning':
            return ordinary()
        if deadline is not None and deadline<now+preparation:
            return None
        qualification = 'theory' if phase=='assessment' else phase
        trainers = [r for r in self.resources if r.role=='trainer' and topic in r.topic_ids and qualification in r.phases]
        rooms = [r for r in self.resources if r.role=='room' and topic in r.topic_ids and phase in r.phases] if phase not in ('proof','assessment') else [None]
        if len(trainers)!=1 or trainers[0].resource_id!=self._pool_id or not rooms:
            return ordinary()
        if any(room is not None and not self._covered.get(room.resource_id,False) for room in rooms) or not all(
                self._covered.get(person,person not in self._pool_participants) for person in people):
            return ordinary()
        # Every delivery constraint covers the entire trainer calendar, and
        # all its occupied time lies inside this single trainer's occupied time.
        # A free trainer slot therefore also satisfies room/participant time.
        trainer = trainers[0]
        room_id = min(room.resource_id if room is not None else '' for room in rooms)
        free = self.free(trainer)
        for a,b in reversed(free) if latest else free:
            low,high = max(a,now)+preparation,b-duration-follow_up
            if deadline is not None:
                high = min(high,deadline)
            if low<=high:
                start = high if latest else low
                return Slot(start,start+duration,trainer.resource_id,room_id,tuple(people),
                            start-preparation,start+duration+follow_up)
        return None

    def _ordinary_find(self, topic, people, now, duration, deadline=None, latest=False,
                       phase='theory', preparation=0, follow_up=0):
        if self.absence_limit is not None and len(people)>self.absence_limit:return None
        # Preparation cannot begin before now, so an earlier delivery deadline
        # is impossible regardless of availability. Equality remains feasible.
        if deadline is not None and deadline<now+preparation:
            return None
        qualification = 'theory' if phase=='assessment' else phase
        trainers = [r for r in self.resources if r.role=='trainer' and topic in r.topic_ids and qualification in r.phases] if phase!='self_learning' else [None]
        rooms = [r for r in self.resources if r.role=='room' and topic in r.topic_ids and phase in r.phases] if phase not in ('proof','self_learning','assessment') else [None]
        participants = self._participants
        choices = []
        def starts(free, before=0, after=0):
            return StartRanges(free,now,duration,before,after,deadline,latest)
        for trainer,room in product(trainers,rooms):
            # Convert free busy-time intervals into feasible DELIVERY-start intervals.
            trainer_windows = self.free(trainer) if trainer else [(now,float('inf'))]
            trainer_starts=starts(trainer_windows,preparation,follow_up)
            initial_index=trainer_starts.index
            if next(trainer_starts,None) is None:continue
            trainer_starts.index=initial_index
            constraints = [trainer_starts]
            if room:
                constraints.append(starts(self.free(room)))
            for person in people:
                if person in participants:
                    free = self.free(participants[person])
                else:
                    free = subtract([(now,float('inf'))],self.busy.get(person,[]))
                constraints.append(starts(free))
            if self.absence_limit is not None:
                count=len(people)
                if count not in self._attendance_cache:
                    if self._attendance_segments is None:
                        events={}
                        for a,b,n in self.attendance:
                            if b>a:
                                events[a]=events.get(a,0)+n;events[b]=events.get(b,0)-n
                        active=0;prior=0;self._attendance_segments=[];self._attendance_peak=0
                        for t,change in sorted(events.items()):
                            if active and prior<t:self._attendance_segments.append((prior,t,active))
                            active+=change;prior=t;self._attendance_peak=max(self._attendance_peak,active)
                    if self._attendance_peak+count<=self.absence_limit:
                        self._attendance_cache[count]=[(0,float('inf'))]
                    else:
                        blocked=[(a,b) for a,b,n in self._attendance_segments if n+count>self.absence_limit]
                        self._attendance_cache[count]=subtract([(0,float('inf'))],blocked)
                constraints.append(starts(self._attendance_cache[count]))
            start=common_start(constraints,latest)
            if start is not None:
                choices.append(Slot(start,start+duration,trainer.resource_id if trainer else '',room.resource_id if room else '',
                                    tuple(people),start-preparation,start+duration+follow_up))
        return min(choices,key=lambda s:(-s.start if latest else s.start,s.trainer_id,s.room_id)) if choices else None
