"""Versioned, identity-keyed streams independent of policy branch draw order."""
import hashlib
import json
import random
from functools import lru_cache

STREAMS = ('detection','batch_size','topic_assignment','person_assignment','case_kind',
           'routing','urgency_review','duration','disruption','selection_order','assessment')


def seed_map(master_seed,replication):
    if type(master_seed) is not int or type(replication) is not int or master_seed<0 or replication<0:
        raise ValueError('Seed and replication must be nonnegative integers')
    return {name:_hash(master_seed,['streams-v1',replication,name]) for name in STREAMS}


def _hash(seed,identity):
    payload = json.dumps([seed,identity],sort_keys=True,separators=(',',':')).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:16],'big')


@lru_cache(maxsize=65536)
def uniform(seed,*identity):
    return random.Random(_hash(seed,identity)).random()


def categorical(seed,identity,values,probabilities):
    u = uniform(seed,*identity)
    cumulative = 0
    for value,p in zip(values,probabilities):
        cumulative += p
        if u<cumulative:
            return value
    return values[-1] # floating-point sum tolerance; probabilities validated upstream
