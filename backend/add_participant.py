"""Add a participant: create their access key and print their personal links.

    python backend/add_participant.py C01 [--url https://<address>]

The schedule is left empty; app.py assigns the least-used one on the key's first visit.
Running it again for an existing pid just reprints that pid's links (lost-link recovery).
"""
import argparse
import json
import secrets

from config import Config


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pid')
    ap.add_argument('--url', default='http://localhost:5055', help='the study address')
    args = ap.parse_args()

    f = Config.PARTICIPANTS_FILE
    people = json.loads(f.read_text()) if f.exists() else {}
    key = next((k for k, p in people.items() if p['pid'] == args.pid), None)
    if key is None:
        key = secrets.token_urlsafe(16)
        people[key] = {'pid': args.pid, 'schedule': None}
        f.write_text(json.dumps(people, indent=1))
        f.chmod(0o600)
        print(f'added {args.pid}')
    else:
        print(f'{args.pid} already exists (schedule: {people[key].get("schedule")})')
    print(f'  study:     {args.url}/?k={key}')
    print(f'  prototype: {args.url}/?k={key}&mode=free')


if __name__ == '__main__':
    main()
