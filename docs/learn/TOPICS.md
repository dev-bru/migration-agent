# Topics: concept map

Each topic: what it is, why industry uses it, where it lives here, what we did not pick, mistakes, two interview questions.
Test counts are MEASURED: 167 tests passed on 2026-11-02 (`pytest -q -p no:cacheprovider`, 79 s).

---

## 1. LLM proposes, deterministic code moves data

**What (eli5).** A model is good at guessing "this field looks like a title". It is bad at being exactly right every time.
So the model only writes a *proposal*. Plain code does every write, the same way each time.

**Why industry.** Data migrations must be repeatable, testable and auditable. A model call is none of these.

**Where.**
- Only two model calls exist: `src/migration_agent/mapping.py:163` and `src/migration_agent/report.py:39`.
- Model class has no target client: `src/migration_agent/model.py:35` returns text only.
- Writes happen in `src/migration_agent/migrate.py:85`.
- Rule text: `AGENTS.md` rule 1, `docs/DECISIONS.md` D-002.

**Not picked.** An agent with write tools ("let the model call upsert_page"). It would be faster to build and impossible to replay or audit.

**Common mistakes.** Letting the model fill `signed_off`. Trusting a model's counts. Giving the model a tool "just for reads" and later adding a write.

**Interview.**
1. *Where does the LLM sit?* Two places: proposing a mapping, and writing summary prose. Both outputs are checked by code before use.
2. *What stops it writing data?* It never gets a client. Writes come only from `migrate()` after a sign-off hash check.

---

## 2. Mapping plan with confidence and questions

**What.** The plan lists, per source entity, `source_field -> target_property`, a type, a `confidence` from 0 to 1 and a reason.
Fields with confidence under 0.7 become questions for the human.

**Why.** Customers own the meaning of their data. A confident wrong guess is worse than a question.

**Where.**
- Models: `mapping.py:27` (`FieldMapping`), `mapping.py:46` (`Question`), `mapping.py:55` (`MappingPlan`).
- Static checks: `mapping.py:108` (`check_plan`).
- Confidence to question: `mapping.py:178-187`. Threshold is a literal `0.7` (decision A-2).
- Tests: `tests/test_mapping.py:85` (low confidence adds question), `:95` (new property must be marked `create`).

**Not picked.** A free-form text proposal. It cannot be parsed or hashed in a stable way.

**Mistakes.** Treating confidence as a probability (it is the model's own guess, not calibrated: UNVERIFIED how well it tracks truth). Skipping the schema check because "the JSON parsed".

**Interview.**
1. *Why a threshold?* It limits human load to the uncertain fields. Tune it from real review data.
2. *Is model confidence reliable?* No. Treat it as a routing hint only; the human and the validator are the real controls.

---

## 3. Human-in-the-loop sign-off

**What.** The human answers every question, then `signoff` stores `sha256(plan.json)`, the reviewer name and a time.
`run` re-hashes the plan and refuses if it differs.

**Why.** Approval must cover the exact thing that will run. Approving "a plan" and running an edited one is a classic audit failure.

**Where.** `src/migration_agent/signoff.py:22` (sign), `:41` (check), `migrate.py:32` (guard), `cli.py:86` (CLI guard). Tests: `tests/test_signoff.py:37`, `:67`.

**Not picked.** A boolean flag in the plan (editable with no trace). A timestamp compare (edit and touch).

**Mistakes.** Hashing a parsed object instead of the bytes. Letting a demo's canned approval stand in for a real review (the README warns).

**Interview.**
1. *What invalidates approval?* Any change to the plan bytes.
2. *Who can approve?* A human by CLI. A model reply cannot set it (`mapping.py:166`).

---

## 4. Dry run

**What.** Run the real transform, print counts, empty fields, first 3 records and warnings. Make zero writes.

**Why.** The customer sees the result before it exists. It finds surprises (an unknown member) cheaply.

**Where.** `src/migration_agent/dryrun.py:11`. It shares `transform.py:10` with `migrate` and `validate`. Tests: `tests/test_dryrun.py:13` (reads only, prints preview), `tests/test_signoff.py:82` (no sign-off needed).

**Not picked.** A separate "preview" code path. It would drift from the real one.

**Mistakes.** A preview that uses different rules from the run. A dry run that creates the schema "to look at it" (here it never creates databases).

**Interview.**
1. *Why share the transform?* Preview, run and validation then agree by construction.
2. *How do you prove zero writes?* `FakeTarget.write_calls` stays 0 (`fakes.py:61`, `:76-77`).

---

## 5. Idempotent upserts

**What.** Writing the same record twice gives the same state. The key is the source system's id (`external_id`).

**Why.** Networks fail. Retries and replays must not duplicate data.

**Where.** `store.py:50-54` (UNIQUE (db, external_id)), `store.py:148` (people), `store.py:229` (page values). Decision: D-005. Tests: `tests/test_target_store.py:69`, `tests/test_target_server.py:60`.

**Not picked.** Exactly-once with a transaction log (more code, not needed). Auto-increment ids (a replay would duplicate).

**Mistakes.** Keying on name or title. Letting a replay *reset* data the user edited in the target (upserts overwrite; see deep-02).

**Interview.**
1. *Why source ids?* They are stable, unique per source, and let relations be sent before database ids exist.
2. *Idempotent versus exactly-once?* Idempotent makes at-least-once delivery safe. Exactly-once needs coordination.

---

## 6. Checkpointed, resumable batches

**What.** Records go in batches of 50. After a whole batch succeeds, a checkpoint file records progress. A crash restarts at the first unsaved batch.

**Why.** Large migrations take long and fail midway. You must resume, not restart.

**Where.** `migrate.py:20-26` (atomic write), `:59-69` (load and check), `:70-76` (validate shape), `:77-94` (loop). Checkpoint holds the plan hash (D-009). Tests: `tests/test_migrate.py:29`, `:54`, `:81`, `:129`.

**Not picked.** Checkpoint per record (write amplification). One transaction for everything (no partial progress, locks the DB).

**Mistakes.** Writing the checkpoint *before* the data. Non-atomic checkpoint file. Reusing a checkpoint after the plan changed.

**Interview.**
1. *What if it crashes between the write and the checkpoint?* The batch replays; upserts make that harmless.
2. *Why store the plan hash?* A changed plan must not reuse old progress (`migrate.py:64`).

---

## 7. MCP server design with FastMCP

**What.** MCP (Model Context Protocol) lets a client call named tools on a server. FastMCP builds the tool schemas from typed Python signatures. Here the server is the "customer workspace".

**Why.** The target is a real product boundary: its own validation, its own tests, replaceable by a real API.

**Where.** `target_server/server.py:29` (seven tools), `:22` (store errors become `ToolError`), `target_server/__main__.py:15` (stdio entry), `target.py:63` (client). Walkthrough: `lessons/07_mcp_target_server.md`. Tests: `tests/test_target_server.py:47`, `:135`, `:151`.

**Not picked.** Hand-written JSON-RPC (docs/ARCHITECTURE.md: easy to get wrong). Calling SQLite directly (skips the boundary). A TypeScript server (D-014, owner rule: Python for backend).

**Mistakes.** Letting an exception kill the server. Returning raw tracebacks. Tools with loose `dict` params and no checks (here checks live in the store, `store.py:153`).

**Interview.**
1. *What happens on a bad write?* The store raises `StoreError`; the server turns it into `ToolError`; the client sees `isError` and raises `TargetError`; the server keeps running (`tests/test_target_server.py:135`).
2. *Why stdio?* No port, no auth, the child dies with the parent. Good for local tools. A hosted target would need HTTP and auth (UNVERIFIED here).

---

## 8. Contract tests with fakes

**What.** One test body runs against the fake and the real implementation. If both pass, the fake is faithful.

**Why.** Fakes make tests fast and offline. Without a contract test they drift and lie.

**Where.** `tests/test_target_contract.py:14` (parametrized `fake`/`mcp`), `fakes.py:53`, `fakes.py:24` (scripted model). D-011. Socket guard: `tests/conftest.py:1`.

**Not picked.** Mocking with `unittest.mock` call assertions (tests the mock). Hitting a live model in every test (slow, flaky).

**Mistakes.** A fake that skips validation. A fake with a different error type. Fakes that accept anything.

**Interview.**
1. *How do you stop a fake drifting?* Run the same assertions on both, in CI.
2. *Why is `FakeTarget` built on the real `Store`?* It reuses the real value checks, so only the transport differs.

---

## 9. Validation strategy

**What.** After the move, read the target back and check: counts, required values, relation targets, and a seeded random content sample.

**Why.** "No errors" does not mean "correct". Counts alone miss a changed title.

**Where.** `validate.py:13`. Checks: counts `:49-53`, required `:59-60`, relations `:61-68`, sample `:70-80`. Tests: `tests/test_validate.py:26`, `:49` (four kinds of damage), `:76` (pagination).

**Not picked.** Hash of whole tables (cannot name the bad record). Full compare of every field of every record (slow for big data; sample size is a setting, tests use all).

**Mistakes.** Comparing target to source rather than to the *transformed* source. Sampling without a seed (you cannot reproduce the check).

**Interview.**
1. *Why a seeded sample?* Reproducible: the customer can re-run the same check.
2. *What does `warn` mean?* `member` has no read tool, so people cannot be verified; it is shown, not hidden (`validate.py:32-37`).

---

## 10. Customer-facing report with grounded numbers

**What.** A report whose counts come from saved files. The model may write summary prose, but numbers and ids in it must appear in the facts.

**Why.** A customer will quote the report. One invented number destroys trust.

**Where.** `report.py:15`. Grounding: `:29-33`, `:45-48`. Fallback text: `:12`. Tests: `tests/test_report.py:27`, `:43` (`--no-llm` makes no call), `:52` (unsupported claim replaced).

**Not picked.** Letting the model write the whole report. Asking it to "double-check" its own numbers.

**Mistakes.** Number matching that is too loose (see limits in deep-04). Forgetting the "what did NOT move" section.

**Interview.**
1. *How do you stop hallucinated numbers?* Code writes every table; prose is filtered by a numeric-token check against the evidence.
2. *What is the weakness?* The check is token-level: "2 tasks failed" passes if the number 2 appears anywhere in the facts. It catches inventions, not misuse.
