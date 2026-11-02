# Interview kit: the migration agent story

Numbers below are MEASURED on 2026-11-02 in this repo unless marked otherwise.

## STAR

**Situation.** I practised the core Forward Deployed Engineer routine: a customer team keeps its work in a Trello-like board
and needs it in a Notion-like workspace. The data has mess (an unknown member id on a card, duplicate label names, attachment links, an empty due date).
I built the tool and the test target myself because I had not yet shipped a migration end to end.

**Task.** Move the data so that: (1) the customer approves what will happen before it happens, (2) a crash or retry never duplicates or loses data,
(3) the result is checked, not assumed, and (4) the customer gets a report with numbers they can trust.
Use a model where it helps, but keep it away from writes.

**Action.**
- Split the system by trust. The model proposes a mapping (`mapping.py:151`) and writes summary prose (`report.py:39`). Plain code does the rest.
- Checked the model's JSON with strict pydantic and a semantic check against both schemas, allowed one repair, and turned any field under 0.7 confidence into a question for the human (`mapping.py:108`, `:162`, `:178`).
- Bound approval to the sha256 of the exact plan bytes. The run re-checks it (`signoff.py:41`, `migrate.py:32`).
- Used one `transform()` for preview, run and validation, so all three agree (`transform.py:10`).
- Made writes idempotent by source id in a FastMCP server over SQLite (`store.py:54`, `store.py:229`), batched them, and wrote an atomic checkpoint after each full batch (`migrate.py:20`, `:94`).
- Tested with a scripted fake model, a fake target built on the real store, and one contract test run on both fake and real MCP target (`tests/test_target_contract.py:14`). A socket guard keeps offline tests offline (`tests/conftest.py:8`).
- Validated by id-set counts, required values, relation targets and a seeded content sample, and wrote a report whose numbers come from files and whose model prose is filtered (`validate.py:13`, `report.py:15`).

**Result.**
- 12 of 12 planned features passing; 167 offline tests pass in 79 s with no model, no key and no remote network.
- The demo migrates 1 board, 2 cards, 3 checklist items and 2 comments, plus 2 people per person-bearing database; all four validation checks pass; it surfaces 1 source warning instead of dropping the card.
- A forced crash after the target write but before the checkpoint resumes to the exact page count with no duplicates (`tests/test_migrate.py:81`: 120 pages after a crash at batch 2).
- Damage tests show the validator catches a deleted page, a changed title, an emptied relation and a nulled required value, and names the record (`tests/test_validate.py:49`).
- Honest scale note: the fixture is tiny and made up. I have not run this on real customer data or at large scale (UNVERIFIED).

## Tradeoffs I can defend

| Choice | Why | Cost |
|---|---|---|
| Model proposes, code writes | Repeatable, testable, auditable | Less "magic"; mapping quality limits the plan |
| One repair, then fail | Bounded cost and time | A small local model may need a human to fix the plan |
| Plan hash sign-off | Exact approval, tamper evident | Any edit, even a typo fix, needs re-approval |
| Upsert by source id (D-005) | Replay-safe, no log needed | Replay overwrites target edits; no delete sync |
| Checkpoint per batch | Simple resume | A crash repeats up to one batch |
| Same transform everywhere | No drift between preview, run, check | A bug in the transform is invisible to validation (both use it) |
| FastMCP stdio target | Real boundary, tested like a product | A local process is not a hosted API with auth |
| Fake target on the real store | Fast, same rules | Transport differences need the contract test |
| Seeded sample | Reproducible | A sample can miss a rare bad record |
| Token-level number grounding | Cheap, catches invention | Does not catch a real number used wrongly |
| Python for the target (D-014) | Owner rule: one backend language | Rewrote the original TypeScript plan |

## Questions to expect (short answers)

1. **Why not let the model call the write tools?** The run must be repeatable and reviewable. The model's output is a guess; a signed plan plus deterministic code is evidence.
2. **What if the customer edits the plan after approval?** The hash differs; `run` refuses until they sign again.
3. **What if it crashes mid-run?** The checkpoint says which batches finished; the next run starts at the first unsaved batch; upserts make the repeated batch safe.
4. **How do you know the data is right?** Four checks and a human-read dry run. Counts alone are not enough; the sample catches changed values.
5. **How do you handle a messy source value?** Warn and keep. The unknown member becomes a warning and an empty owner list, not a dropped card (`source.py:148-160`).
6. **How do you keep model keys safe?** Env vars only, never in files; errors never print provider text (`model.py:39-60`).
7. **How would a customer's secret data be protected?** The prompt holds counts and 3 samples per field. For real data I would add redaction and a data-handling agreement first (not built).

## What I would do in production

1. Target a real API (Notion or the customer's system) behind the same `Target` interface; add auth, rate limits and backoff with jitter (retry today has none, `migrate.py:81`).
2. Handle concurrent edits: compare an `updated_at` or version before overwriting, or freeze the target during the move.
3. Sync deletes and renames with a tombstone list, or declare them out of scope in writing.
4. Make the created/updated split exact across retries (`counts` resets per attempt, `migrate.py:82`) or report only page totals from validation.
5. Add `fsync` to the checkpoint, a lock file so two runs cannot overlap, and a run id in every log line.
6. Read people back (the target has no read tool for them, `validate.py:36`) so they get a real check.
7. Batch relation lookups in validation instead of one `get_page` per link (`validate.py:66`).
8. Add PII redaction before any hosted model call, and log what left the machine.
9. Evaluate the mapper on a labeled set of real boards; track how often humans override it; recalibrate the 0.7 threshold from that data.
10. Add a rollback or "undo run" using the run's list of created ids.
11. Raise the sample size with table size, and stratify it per entity.
12. Test with a model that attacks: put an instruction in a card title and confirm the plan and report are unaffected.

## One-minute pitch

"I built a migration agent for a customer's board data. A model proposes how fields map and asks questions where it is unsure.
A human answers and signs the exact plan. Then plain code previews, moves records in resumable idempotent batches through an MCP server,
validates what landed, and writes a report whose numbers come from code. The model never writes data.
Offline, 167 tests pass with no network. I know where it breaks: concurrent edits, deletes, scale, and PII, and I have a list for production."
