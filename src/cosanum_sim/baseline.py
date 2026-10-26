"""Source-informed assumed IST recipe; all policies use the same engine."""
from dataclasses import replace
from .config import resolve, UrgencyReview, number
from .domain import Resource
from .demand import DemandSpec
from .randomness import uniform


def compose_ist(controls,source_values,topics,seeds,mode):
    c = {x['input_id']:x['value'] for x in controls['controls']}
    s = {x['input_id']:x['value'] for x in source_values['values']}
    if c['phase_duration_variability'] != 'constant_source_allowances' or c['stochastic_disruption_probability'] != 0 or c['initial_backlog_age_minutes'] != 0:
        raise ValueError('This IST increment requires constant durations, disabled random disruptions and zero initial age')
    base = resolve(controls,source_values,topics,True)
    fraction = c['ist_group_topic_fraction']
    number(fraction,'IST group-topic fraction')
    if fraction>1:
        raise ValueError('IST group-topic fraction outside [0,1]')
    horizon = c['stochastic_horizon_minutes']
    calendar = c['ist_calendar']
    if type(horizon) is not int or horizon<1:
        raise ValueError('Stochastic horizon must be positive integer minutes')
    if not calendar['weekdays'] or len(set(calendar['weekdays']))!=len(calendar['weekdays']) or any(type(day) is not int or not 0<=day<7 for day in calendar['weekdays']):
        raise ValueError('Calendar weekdays must be unique integers 0..6')
    start,end = calendar['start_minute'],calendar['end_minute']
    if type(start) is not int or type(end) is not int or not 0<=start<end<=1440:
        raise ValueError('Invalid daily calendar')
    intervals = tuple((day*1440+start,min(day*1440+end,horizon)) for day in range(horizon//1440+1)
                      if day%7 in calendar['weekdays'] and day*1440+start<horizon)
    resources = []
    for role,key in (('trainer','ist_trainer_count'),('room','ist_room_count')):
        count = c[key]
        if type(count) is not int or count<1:
            raise ValueError('Resource counts must be positive integers')
        resources.extend(Resource(f'assumed-{role}-{i+1}',role,tuple(sorted(topics)),intervals) for i in range(count))
    grouping = tuple(t for t in sorted(topics) if topics[t].theory_group_possible and uniform(seeds['routing'],t)<fraction)
    config = replace(base,horizon=horizon,deadline_enabled=False,resources=tuple(resources),grouping_topics=grouping,selection_seed=seeds['selection_order'],
                     urgency_review=UrgencyReview(s['ist_urgency_review_calendar_weeks']*7*1440,
                                                  c['ist_urgent_review_probability'],seeds['urgency_review'])).validate(topics)
    probabilities = tuple((key,float(value)) for key,value in c['topic_demand_distribution'].items())
    # Explicit uniform choice expands over the catalogue; never silently stock-weighted.
    if c['topic_demand_distribution']=={'uniform_catalogue':1}:
        probabilities = tuple((key,1/len(topics)) for key in sorted(topics))
    spec = DemandSpec(mode,horizon,c['detection_intensity'],
                      tuple((int(size),p) for size,p in c['batch_size_distribution'].items()),probabilities,
                      s['reference_population'],c['synthetic_external_pool_size'],c['proof_only_fraction']).validate(topics)
    return config,spec
