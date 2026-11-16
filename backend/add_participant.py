"""Add a participant: create their access key and print their personal links.

    python backend/add_participant.py C01 [--url https://<address>]
    python backend/add_participant.py T01 --trial     # a dry-run round (see app.py)

Clinician keys: the schedule is left empty; app.py assigns the least-used one on the key's
first visit. Trial keys get no schedule (fixed model order, condition picked in the page),
do not count toward the clinicians' schedule balance, and also get a prototype link.
Running it again for an existing pid reprints that pid's links (lost-link recovery);
adding --trial then turns the existing key into a trial key.
"""
import argparse
import json
import secrets

from config import Config


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pid')
    ap.add_argument('--url', default='http://localhost:5055', help='the study address')
    ap.add_argument('--trial', action='store_true', help='a trial (dry-run) key, not a clinician')
    args = ap.parse_args()

    f = Config.PARTICIPANTS_FILE
    people = json.loads(f.read_text()) if f.exists() else {}
    before = json.loads(json.dumps(people))
    key = next((k for k, p in people.items() if p['pid'] == args.pid), None)
    if key is None:
        key = secrets.token_urlsafe(16)
        people[key] = {'pid': args.pid, 'schedule': None, **({'trial': True} if args.trial else {})}
        print(f'added {args.pid}' + (' (trial)' if args.trial else ''))
    elif args.trial and not people[key].get('trial'):
        people[key] = {'pid': args.pid, 'schedule': None, 'trial': True}
        print(f'{args.pid} is now a trial key')
    else:
        p = people[key]
        print(f'{args.pid} already exists ' + ('(trial)' if p.get('trial') else f'(schedule: {p.get("schedule")})'))
    if people != before:  # only write on a change: the running app may be assigning schedules
        f.write_text(json.dumps(people, indent=1))
        f.chmod(0o600)
    print(f'  study:     {args.url}/?k={key}')
    if people[key].get('trial'):
        print(f'  prototype: {args.url}/?k={key}&mode=free')


if __name__ == '__main__':
    main()
