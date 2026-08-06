# Decision: Two SQLAlchemy Engines Are a Deliberate Transitional State

**Date:** 2026-08-06
**Status:** Accepted (transitional — resolved by slice 2)
**Context:** Adopting `cosmo_suite.pages.logs` pulled `cosmo_suite.db_manager` into the
process, while `cosmonaut_app/db_manager.py` stayed (it is slice-2 work). The app now
runs **two SQLAlchemy engines against the same Postgres**, with **two separate
`DeclarativeBase` registries** that both map `jobs` and `logs`.

| | app | framework |
|---|---|---|
| Engine | `cosmonaut_app/db_manager.py:128` | `cosmo_suite/db_manager.py:98` |
| `Base` | `cosmonaut_app/db_manager.py:90` | `cosmo_suite/db_manager.py:34` |
| `jobs` / `logs` | mapped | mapped |

## Decision

**Leave it.** Do not merge the registries, do not shim one onto the other, do not
give the framework page a different data source. Slice 2 resolves it by moving the
app's tables onto the framework `Base`. COSMOPOLITAN reaches the same state with its
own slice 1b, so the fix belongs there once, not twice here.

## Why it is safe today

Verified, not assumed:

- **Neither tree ever calls `Base.metadata.create_all()` or `drop_all()`** — grepped
  across `cosmonaut_app/`, `test/` and the installed `cosmo_suite/`. The schema comes
  solely from `docker/init.sql`, so the duplicated mappings can never race to emit
  DDL or disagree about what the table should look like. **This is the load-bearing
  fact.** If either package ever adds `create_all`, this decision expires
  immediately.
- **The two `logs` mappings are column-identical** to each other and to `init.sql`
  (`id`, `timestamp`, `pid`, `level`, `module`, `message`).
- **The framework engine has exactly two callers**, both read-only on `logs`:
  `DbManager.query_distinct_modules()` and `DbManager.query_logs()` from
  `cosmo_suite/pages/logs.py`. Nothing framework-side writes, and nothing
  framework-side touches `jobs` — `cosmo_suite.job.Job` is never instantiated,
  because the reset callbacks that would do so are not registered (v0.4.0 put them
  behind `app_layout(with_reset=True)`, which this app does not call).
- Confirmed on a running app: the Logs page renders real records written by the
  framework's `PostgreSQLHandler` through cosmonaut's own logging config.

## Consequences

- Two connection pools instead of one. Bounded and small — the framework pool only
  serves the Logs page.
- **Do not add framework-side writers** before slice 2. A second writer against
  `jobs` through a second identity map is where this stops being harmless.
- Slice 2 acceptance: one `Base`, one engine, `cosmonaut_app/db_manager.py` gone or
  reduced to the domain queries.
