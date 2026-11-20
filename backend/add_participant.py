"""Add a participant: create their access key and print their personal links.

    python backend/add_participant.py C01 [--url https://<address>]
    python backend/add_participant.py T01 --trial     # a dry-run round (see app.py)
    python backend/add_participant.py DEV_me --dev    # the prototype (free mode) for us
    python backend/add_participant.py C02 --drop      # C02 quit: a new key takes over their schedule

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
    ap.add_argument('--drop', action='store_true',
                    help='mark an existing clinician as dropped out: their schedule is reused')
    ap.add_argument('--dev', action='store_true',
                    help='a dev key: its link opens the Prototype (free mode), everything visible')
    args = ap.parse_args()
    args.trial |= args.dev

    f = Config.PARTICIPANTS_FILE
    people = json.loads(f.read_text()) if f.exists() else {}
    before = json.loads(json.dumps(people))
    key = next((k for k, p in people.items() if p['pid'] == args.pid), None)
    if args.drop:
        if key is None:
            raise SystemExit(f'no participant {args.pid}')
        if not people[key].get('dropped'):
            people[key]['dropped'] = True
            f.write_text(json.dumps(people, indent=1))
            f.chmod(0o600)
        print(f'{args.pid} marked dropped (schedule {people[key].get("schedule")} is free for the next new key; '
              'their answers are kept)')
        return
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
    if args.dev and not people[key].get('dev'):
        people[key]['dev'] = True
        print(f'{args.pid} is a dev key: its link opens the Prototype (free mode)')
    if people != before:  # only write on a change: the running app may be assigning schedules
        f.write_text(json.dumps(people, indent=1))
        f.chmod(0o600)
    kind = 'prototype' if people[key].get('dev') else 'study'
    print(f'  {kind + ":":<10} {args.url}/?k={key}')
    print(f'  tutorial:  {args.url}/?mode=tutorial&k={key}')


if __name__ == '__main__':
    main()
