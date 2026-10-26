"""Thin CLI; configurations and fixtures hold all model numbers."""
import argparse
import json
from pathlib import Path
from .experiments import run, run_ist


def main():
    parser = argparse.ArgumentParser(description='Run synthetic deterministic first theory phase')
    parser.add_argument('--ist-mode', choices=['initial_backlog_clearance','ongoing_stochastic_demand'])
    parser.add_argument('--replication', type=int, default=0)
    parser.add_argument('--full-workflow', action='store_true', help='Include required practice, proof and accrued cost reconciliation')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path, required=True, help='New immutable run directory')
    args = parser.parse_args()
    if args.ist_mode:
        result,metrics = run_ist(args.root.resolve(),args.output.resolve(),args.ist_mode,args.replication)
    else:
        result,metrics = run(args.root.resolve(),args.output.resolve(),args.full_workflow)
    for session in result.sessions[:12]:
        print(f'{session.start/1440:g} days: {session.topic_id} {session.phase}, {len(session.request_ids)} requests, {session.reason}; {", ".join(session.request_ids)}')
    print(json.dumps(metrics, indent=2))


if __name__ == '__main__':
    main()
