"""Explicit author workload calendars; budgets already contain its labour cost."""
import math
from dataclasses import replace


def subtract(intervals, bookings):
    free=list(intervals)
    for a,b in sorted(bookings):
        revised=[]
        for x,y in free:
            if b<=x or a>=y:revised.append((x,y));continue
            if x<a:revised.append((x,a))
            if b<y:revised.append((b,y))
        free=revised
    return tuple(free)


def allocate(free, minutes, identity, component, actor, topic=None):
    if minutes<0:raise ValueError('Negative author workload')
    bookings=[]
    for a,b in free:
        if minutes<=1e-8:break
        end=min(b,a+minutes)
        bookings.append(dict(task_id=identity,component=component,actor=actor,topic_id=topic,start=a,end=end))
        minutes-=end-a
    if minutes>1e-8:raise ValueError('Insufficient author calendar for declared workload')
    return bookings,subtract(free,[(x['start'],x['end']) for x in bookings])


def resolve_effort(resolved, source_values, settings):
    options={x['input_id']:x['value'] for x in settings['inputs']}
    source={x['input_id']:x['value'] for x in source_values['values']}
    rate=source[options['authoring_rate_binding']]
    if not isinstance(rate,(int,float)) or isinstance(rate,bool) or not math.isfinite(rate) or rate<=0:
        raise ValueError('Positive finite authoring valuation required')
    batch=options['maintenance_batch_days']
    if type(batch) is not int or batch<1:raise ValueError('Positive maintenance batch required')
    if options['course_order']!='priority_then_topic_id':raise ValueError('Unsupported course ordering')
    return dict(authoring_rate_chf=rate,setup_hours=resolved['internal_setup_chf']/rate,
        course_hours_each=resolved['content_chf_per_topic']/rate,
        content_hours=len(resolved['selected_topic_ids'])*resolved['content_chf_per_topic']/rate,
        maintenance_hours_per_day=resolved['maintenance_chf_per_day']/rate,
        maintenance_batch_days=batch,source_status='assumption',
        rationale='Budget divided by P&Q task valuation; same labour already included in portfolio costs')


def apply_workload(cfg,topics,profile,effort,actor):
    if actor not in ('prelaunch_team','daniel_calendar'):raise ValueError('Unknown author allocation')
    trainer=next(r for r in cfg.resources if r.role=='trainer')
    original_trainer_hours=sum(b-a for r in cfg.resources if r.role=='trainer' for a,b in r.intervals)/60
    v=profile.values;day_minutes=1440
    def calendar(days,weekdays):
        return tuple((d*day_minutes+v['resource_calendar_start_minute'],
                      d*day_minutes+v['resource_calendar_end_minute']) for d in days if d%7 in weekdays)
    year_days=cfg.horizon/day_minutes
    if year_days<365:raise ValueError('This workload comparison requires at least one full model year')
    team_calendar=calendar(range(math.ceil(year_days)),v['participant_calendar_weekdays'])
    maintenance_free=trainer.intervals if actor=='daniel_calendar' else team_calendar
    maintenance=[]
    periods=[(day,min(day+effort['maintenance_batch_days'],year_days))
             for day in range(0,math.ceil(year_days),effort['maintenance_batch_days'])]
    # A final short week can contain no training day. Reserve its prorated work
    # together with the preceding week, without changing annual effort or cost.
    if len(periods)>1:
        day,stop=periods[-1]
        if not any(b>day*day_minutes and a<stop*day_minutes for a,b in maintenance_free):
            periods[-2]=(periods[-2][0],stop);periods.pop()
    for day,stop in periods:
        windows=tuple((max(a,day*day_minutes),min(b,stop*day_minutes)) for a,b in maintenance_free
                      if b>day*day_minutes and a<stop*day_minutes)
        rows,_=allocate(windows,(stop-day)*effort['maintenance_hours_per_day']*60,
                        f'maintenance-{day}','lms_maintenance',actor)
        maintenance.extend(rows)
    needed=(effort['setup_hours']+effort['content_hours'])*60
    if actor=='prelaunch_team':
        daily=v['resource_calendar_end_minute']-v['resource_calendar_start_minute']
        weeks=math.ceil(needed/(daily*len(v['participant_calendar_weekdays'])))+1
        possible=calendar(range(-weeks*7,0),v['participant_calendar_weekdays'])
        remaining=needed;last=[]
        for a,b in reversed(possible):
            if remaining<=1e-8:break
            begin=max(a,b-remaining);last.append((begin,b));remaining-=b-begin
        free=tuple(sorted(last))
    else:
        free=subtract(trainer.intervals,[(x['start'],x['end']) for x in maintenance])
    preparation,free=allocate(free,effort['setup_hours']*60,'implementation','lms_implementation',actor)
    ready=[]
    for topic in sorted(cfg.workflow.learning.topic_ids,key=lambda t:(topics[t].priority,t)):
        rows,free=allocate(free,effort['course_hours_each']*60,f'content-{topic}','lms_content',actor,topic)
        preparation.extend(rows)
        ready.append((topic,max(0,max((x['end'] for x in rows),default=0))))
    bookings=sorted(preparation+maintenance,key=lambda x:(x['start'],x['task_id']))
    assert all(a['end']<=b['start']+1e-8 for a,b in zip(bookings,bookings[1:]))
    internal_hours=sum(x['end']-x['start'] for x in bookings)/60
    expected=effort['setup_hours']+effort['content_hours']+year_days*effort['maintenance_hours_per_day']
    assert math.isclose(internal_hours,expected,abs_tol=1e-8)
    remaining_resources=cfg.resources
    if actor=='daniel_calendar':
        intervals=subtract(trainer.intervals,[(x['start'],x['end']) for x in bookings])
        remaining_resources=tuple(replace(r,intervals=intervals) if r.resource_id==trainer.resource_id else r for r in cfg.resources)
    cfg=replace(cfg,resources=remaining_resources,workflow=replace(cfg.workflow,
        learning=replace(cfg.workflow.learning,topic_ready_at=tuple(ready))))
    return cfg.validate(topics),dict(actor=actor,bookings=bookings,topic_ready_at=ready,
        internal_hours=internal_hours,trainer_overhead_hours=internal_hours if actor=='daniel_calendar' else 0,
        setup_hours=effort['setup_hours'],content_hours=effort['content_hours'],
        maintenance_hours=year_days*effort['maintenance_hours_per_day'],
        original_trainer_hours=original_trainer_hours,
        preparation_start=min((x['start'] for x in preparation),default=0),preparation_end=max((x['end'] for x in preparation),default=0),
        internal_valued_cost_chf=internal_hours*effort['authoring_rate_chf'],
        accounting='Already charged in LMS implementation/content/maintenance; never added again as coach labour')
