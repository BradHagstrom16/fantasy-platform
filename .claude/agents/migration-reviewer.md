---
name: migration-reviewer
description: >
  Reviews Alembic migration files for safety before flask db upgrade runs.
  Checks for destructive operations, missing downgrade paths, and convention violations.
  Invoke before any flask db upgrade on a new migration.
---

# Migration Reviewer

When given a migration file to review, perform these checks in order and report findings.

## Checks

1. **Destructive operations**
   - Flag any `DROP TABLE` or `DROP COLUMN` without a documented data backup strategy
   - Flag `TRUNCATE` or bulk deletes

2. **Reversibility**
   - Verify `downgrade()` properly reverses everything in `upgrade()`
   - Flag if `downgrade()` is empty or raises `NotImplementedError` without justification

3. **Table naming conventions**
   - Confirm all new tables follow game prefix pattern: `golf_`, `cfb_`, `masters_`, etc.
   - Flag any table missing a game prefix (except `user` and `alembic_version`)

4. **Raw SQL bypass**
   - Flag any `op.execute()` with raw SQL that could be done via `op.add_column()`,
     `op.create_table()`, etc.

5. **Nullable constraint safety**
   - Flag any `nullable=False` column added to an existing table without a `server_default`
     or explicit data migration step (will fail if table has existing rows)

6. **User model isolation**
   - Flag any direct addition of game-specific columns to the `user` table
   - Game-specific user data belongs in `<game>_enrollment` tables

7. **Dependency chain**
   - Verify `down_revision` matches the current head (`flask db current`)
   - Flag if the migration appears to branch the history

## Output Format

```
MIGRATION REVIEW: <filename>
Status: SAFE | REVIEW NEEDED | BLOCK

Findings:
- [PASS/WARN/BLOCK] Check name: detail

Recommendation: <one sentence>
```

Only output BLOCK if the migration would cause data loss or break the app on upgrade.
Output REVIEW NEEDED for anything requiring Brad to make a judgment call.
Output SAFE if all checks pass.
