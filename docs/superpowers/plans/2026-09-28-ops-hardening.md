# Ops hardening (open-items §G) — runbook

**Date:** 2026-09-28 · **Decision:** ADR-067 · **PR:** `ops-hardening`

Six gaps members never see, closed in one PR:

| # | Gap | What shipped | Locked by |
|---|---|---|---|
| 1 | A job that exits 1 emails nobody | `OnFailure=job-alert@%N.service` + `OnSuccess=job-ping@%N.service` on every timer-fired unit (worldcup excepted); `utils/job_alert.py` | `tests/test_job_alerts.py` |
| 2 | `flask db upgrade` runs with no backup | `deploy.sh` takes a `pg_dump` into `~/backups` first; a failed dump stops the deploy | `tests/test-deploy-guards.sh` cases BA–BE |
| 3 | A 500 reports nothing | Sentry (`sentry-sdk[flask]`), off while `SENTRY_DSN` is blank | `tests/test_observability.py` |
| 4 | A password change leaves other sessions signed in | `User.rotate_auth_id()` on change, reset and admin reset; remember cookie `Secure`/`HttpOnly`/`SameSite=Lax` | `tests/test_auth_session_rotation.py` |
| 5 | Production would boot on the public dev `SECRET_KEY` | `create_app` refuses a blank or default key in production | same |
| 6 | Logout is a GET | `/logout` is POST-only; "Step Out" is a CSRF form | same |

Nothing here needs a migration. Items 3–6 take effect on deploy. Items 1 and 2
need the steps below: two free accounts, two `.env` lines, one test alert, one
restore rehearsal.

---

## Brad's steps after merge

### 1. healthchecks.io (the dead-man)

1. Sign up at <https://healthchecks.io> (free: 20 checks, email alerts).
2. Project **Settings → API Access → Ping key → Create**. Copy the key.
3. On the droplet, add it to `.env` (your editor, not `echo >>`, so it never
   lands in shell history twice):
   ```bash
   ssh deploy@104.131.28.136
   nano ~/fantasy-platform/.env
   # add:  HEALTHCHECKS_PING_KEY=<the key>
   ```
   The job units read `.env` at every firing, so no restart is needed for the
   key itself.

### 2. Sentry (error tracking)

1. Sign up at <https://sentry.io> (free Developer plan), create a **Flask**
   project, and copy its DSN (`https://…@o….ingest.sentry.io/…`).
2. Add to the same `.env`: `SENTRY_DSN=<the DSN>`.
3. Sentry is read at app start, so it takes effect with the deploy below.

### 3. Deploy

```bash
cd ~/fantasy-platform && ./deploy.sh
```

Expect a new step before migrations:

```
==> Backing up the database before migrating...
    /home/deploy/backups/pre-migrate-20260929T….dump
```

Then run the usual post-deploy verification (ADR-040; `CLAUDE.md` → Production
Deployment), and additionally:

```bash
systemctl cat club-remind.service | grep -E 'OnFailure|OnSuccess'   # both lines
systemctl cat job-alert@club-remind.service | grep ExecStart          # the template resolves
ls -l ~/backups/                                                     # drwx------, one -rw------- dump
```

### 4. Fire one alert for real

```bash
sudo systemctl start job-alert@club-remind.service
journalctl -u job-alert@club-remind.service -n 20 --no-pager
```

- An email `[CCC ops] club-remind failed` reaches `ADMIN_EMAIL`, carrying
  club-remind's last 40 journal lines.
- healthchecks.io now shows a `club-remind` check, **down** (the `/fail`
  ping auto-created it).
- The next hourly `club-remind` run (or `sudo systemctl start club-remind.service`)
  pings success and turns it green.

### 5. Set each check's schedule in healthchecks.io

Each check is created by its job's first ping, with a default one-day period.
Or create them ahead of time: a check whose **slug** is the job's name (e.g.
`docket-scores`) is the one that job's pings land on, and a new check stays
quiet until its first ping.
Give each one its real schedule: **Schedule → Cron**, timezone
`America/Chicago`. Extra pings (the December/January extra firings, a
hand-fire) are harmless; a *missing* expected ping is what alerts.

| Check | Cron (America/Chicago) | Grace |
|---|---|---|
| `club-remind` | `0 * * * *` | 30 min |
| `club-paper` | `15 6 * * 2` | 1 h |
| `scores-gameday` | `30 13,15,17,19,21,23 * * *` (the odd hours: December fires only every other hour, so an hourly cron would alert all month) | 1 h |
| `cfb-setup` | `0 9 * * 1` | 1 h |
| `cfb-spreads` | `0 6 * * 5` | 1 h |
| `cfb-scores` | `0 8 * * 0-4` | 1 h |
| `cfb-autopick` | `5,35 11 * * 6` | 1 h |
| `docket-lines` | `0 7 * * 2-5` | 1 h |
| `docket-scores` | `0 8 * * 0,1,3-6` | 1 h |
| `docket-deadline` | `2,32 12 * * 0` | 1 h |

Timers keep firing (and pinging) out of season. `--scheduled` exits 0, which
counts as a success. When a timer is **disabled** (Survivor after its last CFP
week in late January), **pause** its check in healthchecks.io in the same
sitting, or it will alert. The golf-* units carry the same lines and create
their checks on their first run at Phase L.

### 6. Rehearse a restore (together, once)

This proves the dump is restorable. It restores into a scratch database on the
same managed cluster and never touches `defaultdb`.

```bash
ssh deploy@104.131.28.136
cd ~/fantasy-platform
# The same reading deploy.sh uses: the password goes in PGPASSWORD, never argv.
export PGPASSWORD="$(venv/bin/python -m utils.backup_target password)"
url="$(venv/bin/python -m utils.backup_target url)"
scratch="${url/\/defaultdb/\/restore_rehearsal}"      # same cluster, another database
latest=$(ls -1 ~/backups/pre-migrate-*.dump | tail -1)

psql "$url" -c 'CREATE DATABASE restore_rehearsal'
pg_restore --exit-on-error --no-owner --no-acl --dbname "$scratch" "$latest"; echo "rc=$?"

q="select (select count(*) from users), (select version_num from alembic_version),
          (select count(*) from docket_pick), (select count(*) from cfb_pick)"
psql "$url"     -Atc "$q"      # live
psql "$scratch" -Atc "$q"      # restored: must match, or differ only by picks made since the dump

psql "$url" -c 'DROP DATABASE restore_rehearsal'
unset PGPASSWORD
```

Record the result here:

| Date | Dump | rc | users / alembic / docket_pick / cfb_pick (live → restored) |
|---|---|---|---|
| 2026-09-28 (local, `ccc_local`) | same flags, Postgres 18.6 | 0 | 61 / b7c4e2a91d05 / 110 / 27 → identical |
| _prod, pending_ | | | |

---

## A real restore (if a migration ever destroys data)

Restore to a **fresh** database and repoint the app, never `--clean` over the
live one. The broken database stays intact for comparison.

1. Stop writes: `sudo systemctl stop fantasy-platform` and every enabled game
   timer (`systemctl list-timers --no-pager`, then
   `sudo systemctl stop <name>.timer …`).
2. Take the bad migration out of `main` **first**, from your Mac, never on the
   droplet: `git revert <the PR's squash commit>`, push, and merge it the usual
   way. `deploy.sh` always `git pull`s the current branch, so checking out an
   older commit on the box would either be undone by that pull or, on a
   detached HEAD, stop the deploy.
3. Restore into a fresh database on the cluster, with `url` and `PGPASSWORD`
   set as in the rehearsal above. Use the dump the bad deploy itself took: its
   name carries that deploy's UTC time and short SHA, and it was taken seconds
   before the migration ran.
   ```bash
   psql "$url" -c 'CREATE DATABASE restored_<date>'
   restored="${url/\/defaultdb/\/restored_<date>}"
   pg_restore --exit-on-error --no-owner --no-acl --dbname "$restored" ~/backups/<that dump>
   echo "rc=$?"
   ```
4. **Only with `rc=0`,** run the rehearsal's count query against `$restored`
   and check it reads as the club did before the bad deploy (members, the
   alembic revision before the bad migration, picks). A non-zero rc or a
   count that looks wrong means stop: drop `restored_<date>` and try the
   previous dump or DO's daily backup instead.
5. In `.env`, point `DATABASE_URL` at `restored_<date>`, then `./deploy.sh`.
   It pulls the revert, dumps the restored database, and `flask db upgrade`
   finds nothing to apply: the restored database is at the pre-migration
   revision, and the revert removed the migration.
6. Start the timers again. Once you are satisfied, drop the broken database.

DigitalOcean's managed cluster also keeps its own daily backups (dashboard →
Databases → Backups); those are the fallback when `~/backups` is gone.

---

## How each piece behaves

- **job-alert@** pings healthchecks `/fail` *first*, then mails. Pinging first
  means a failure caused by our mail being down (Brevo) still reaches you
  through healthchecks' own email. It imports only `config`, Flask and
  `utils.email`, so a deploy that breaks the app's import (every job fails)
  still produces the alert. Neither template carries `OnFailure=`/`OnSuccess=`
  itself, so an alert can never trigger another.
- **`systemd-analyze verify`** (which gates every unit install in `deploy.sh`)
  accepts an `OnFailure=` naming a template that does not exist (checked on the
  droplet 2026-09-28), so `tests/test_job_alerts.py` locks the names instead.
- **The backup** runs on every deploy, even when nothing is pending, so a
  broken `pg_dump` (a client/server major-version mismatch after a cluster
  upgrade is the likely one) surfaces on a quiet deploy. The droplet's
  `pg_dump` is 18.6 from PGDG; the cluster is Postgres 18. It keeps the newest 10
  (check the size of the first one; the disk had 43 GB free on 2026-09-28).
  `SKIP_DB_BACKUP=1 ./deploy.sh` is the override.
- **Sentry** sends errors only: no cookies, IPs, user or request bodies
  (`send_default_pii=False`, `max_request_body_size='never'`,
  `traces_sample_rate=0`). Release = the deployed git SHA. It covers Gunicorn
  requests and every `flask …` job.

## Noticed, not done

- Password-reset tokens are signed over the email only, so a link can be
  reused within its hour. Binding the token to `auth_id` would make it
  single-use now that a reset rotates it.
- The admin password reset hands out the fixed `changeme123`.
