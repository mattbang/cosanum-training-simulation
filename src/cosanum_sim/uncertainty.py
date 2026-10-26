"""Fixed-n paired summaries. Simulation uncertainty is not input uncertainty."""
from collections import defaultdict
from math import sqrt, isfinite, ceil
from statistics import mean, stdev

# NIST two-sided 95% Student-t table, df 1..30 (0.975 column).
# https://itl.nist.gov/div898/handbook/eda/section3/eda3672.htm
# Half a last-place unit guards rounding; df >30 uses conservative df=30.
T975 = (12.706,4.303,3.182,2.776,2.571,2.447,2.365,2.306,2.262,2.228,
        2.201,2.179,2.160,2.145,2.131,2.120,2.110,2.101,2.093,2.086,
        2.080,2.074,2.069,2.064,2.060,2.056,2.052,2.048,2.045,2.042)


def interval(values, target=None, minimum_n=20):
    """Pointwise approximate t interval, no optional stopping or rank inference."""
    total=len(values)
    data=[x for x in values if x is not None]
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not isfinite(x) for x in data):
        raise ValueError('Finite numeric observations required')
    if type(minimum_n) is not int or minimum_n<2:
        raise ValueError('Precision minimum must be at least two')
    if target is not None and (isinstance(target,bool) or not isinstance(target,(int,float)) or not isfinite(target) or target<=0):
        raise ValueError('Precision target must be positive')
    n=len(data); avg=mean(data) if n else None
    spread=stdev(data) if n>1 else None
    half=(T975[min(n-1,30)-1]+.0005)*spread/sqrt(n) if n>1 else None
    status=('not_targeted' if target is None else 'missing_observations' if n<total else
            'insufficient_replications' if n<minimum_n else 'met' if half<=target else 'unmet')
    return dict(n=n,planned_n=total,missing=total-n,mean=avg,sample_sd=spread,half_width=half,
                lower=avg-half if half is not None else None,upper=avg+half if half is not None else None,
                precision_target=target,precision_status=status,zero_observed_spread=spread==0,
                suggested_total_n=max(minimum_n,ceil(n*(half/target)**2)) if target and half is not None else None)


def summarise(rows, metrics, precision_targets, minimum_n, contrasts=None):
    groups=defaultdict(list)
    for row in rows:
        groups[(row['case_id'],row['mode'])].append(row)
    absolute,paired,clearance=[],[],[]
    for (case,mode),records in sorted(groups.items()):
        indexed={}
        for row in records:
            key=(row['replication'],row['scenario'])
            if key in indexed: raise ValueError('Duplicate scenario/replication')
            indexed[key]=row
        reps=sorted({r['replication'] for r in records})
        scenarios=sorted({r['scenario'] for r in records})
        if 'S0' not in scenarios: raise ValueError('S0 pairing baseline missing')
        for rep in reps:
            if any((rep,s) not in indexed for s in scenarios): raise ValueError('Unbalanced paired experiment')
            base=indexed[(rep,'S0')]
            for s in scenarios:
                other=indexed[(rep,s)]
                if any(other[k]!=base[k] for k in ('fixture_hash','underlying_needs','common_due_needs')):
                    raise ValueError('Paired fixture or denominator mismatch')
        for scenario in scenarios:
            for metric in metrics:
                values=[indexed[(rep,scenario)][metric] for rep in reps]
                absolute.append(dict(case_id=case,mode=mode,scenario=scenario,metric=metric,
                                     **interval(values,minimum_n=minimum_n)))
                references = ['S0','S7'] if scenario=='S7_PLUS_LMS' and 'S7' in scenarios else ['S0']
                references += [c['reference'] for c in contrasts or ()
                               if c['scenario']==scenario and c['reference'] in scenarios]
                for reference in dict.fromkeys(references):
                    if reference==scenario: continue
                    pairs=[(indexed[(rep,scenario)][metric],indexed[(rep,reference)][metric]) for rep in reps]
                    differences=[a-b if a is not None and b is not None else None for a,b in pairs]
                    paired.append(dict(case_id=case,mode=mode,scenario=scenario,reference=reference,metric=metric,
                                       **interval(differences,precision_targets.get(metric),minimum_n)))
            flags=[indexed[(rep,scenario)]['priority1_clearance_observed'] for rep in reps]
            eligible=[flag for flag in flags if flag is not None]
            times=[indexed[(rep,scenario)]['priority1_clearance_minutes'] for rep in reps]
            clearance.append(dict(case_id=case,mode=mode,scenario=scenario,replications=len(reps),
                eligible_initial_cohorts=len(eligible),cleared_replications=sum(eligible),
                empirical_clearance_fraction=sum(eligible)/len(eligible) if eligible else None,
                censored_replications=sum(flag==0 for flag in eligible),
                mean_clearance_minutes=mean(times) if times and all(t is not None for t in times) else None,
                interpretation='Unreached clearance stays unavailable; empirical fraction is not guaranteed probability'))
    return absolute,paired,clearance


def revalue_overhead(rows, chf_per_supervised_session):
    """Price-only scope sensitivity; no new scheduling or labour claims."""
    if isinstance(chf_per_supervised_session,bool) or not isinstance(chf_per_supervised_session,(int,float)) or not isfinite(chf_per_supervised_session) or chf_per_supervised_session<0:
        raise ValueError('Nonnegative finite overhead required')
    return [dict(row,net_chf=row['net_chf']+row['supervised_sessions_started']*chf_per_supervised_session) for row in rows]
