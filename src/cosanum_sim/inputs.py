"""Read-only catalogue and snapshot integrity checks."""
import csv
import hashlib
import json
from .domain import Topic


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_sources(root):
    manifest = json.loads((root / 'SOURCE_MANIFEST.json').read_text())
    hashes = {}
    for entry in manifest['files']:
        path = root / entry['snapshot_path']
        if sha(path) != entry['sha256'] or path.stat().st_size != entry['bytes']:
            raise ValueError(f"Source snapshot changed: {entry['snapshot_path']}")
        hashes[entry['snapshot_path']] = entry['sha256']
    derived = json.loads((root / 'DERIVED_DATA_MANIFEST.json').read_text())
    if sha(root / derived['dataset_path']) != derived['dataset_sha256']:
        raise ValueError('Derived catalogue changed')
    hashes[derived['dataset_path']] = derived['dataset_sha256']
    return hashes


def load_topics(path):
    topics = {}
    with path.open(newline='', encoding='utf-8') as stream:
        for row in csv.DictReader(stream):
            flags = []
            for key in ('theory_required', 'practice_required', 'theory_group_possible', 'practice_group_possible'):
                if row[key] not in ('true', 'false'):
                    raise ValueError(f'Invalid boolean: {key}')
                flags.append(row[key] == 'true')
            t = Topic(row['topic_id'], int(row['revenue_priority']), *flags, int(row['open_person_topic_records']))
            if not t.topic_id or t.topic_id in topics or t.priority not in (1, 2, 3) or t.open_records < 0:
                raise ValueError('Invalid topic identity, priority or count')
            if (t.practice_group_possible and not t.practice_required) or (t.theory_group_possible and not t.theory_required):
                raise ValueError('Group flag without required phase')
            topics[t.topic_id] = t
    return topics
