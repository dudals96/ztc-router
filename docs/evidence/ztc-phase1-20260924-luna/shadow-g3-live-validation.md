# Luna G3 live shadow validation and D2 freeze

Date: 2026-09-24
Track: B — Luna
Worktree: `~/Pi-wt/ztc-luna`
Branch: `ztc/phase1-luna`
Implementation freeze commit: `2e43c35a9f0c29290e6fc9002a232f53f5389a49`
Target: Claude Code CLI `2.1.281`, Bash `PreToolUse` and `PostToolUse` only. No Codex or Antigravity registration.
Daemon: manually started on loopback port `9878`; no launchd registration.

## Live 100-call conformance run

A single Claude Code CLI session issued 100 distinct, harmless `printf ZTC_LUNA_SHADOW_NNN` Bash tool calls under the normal `default` permission mode. The test-only allow rule covered only `Bash(printf *)`; session persistence was disabled. Each call returned its exact expected marker.

- Claude tool calls/results: 100 / 100; IDs unique: 100.
- Registered PreToolUse and PostToolUse callbacks: 100 each; all completed with exit 0.
- Shadow wrapper stdout: exact `{}` for all 200 callbacks; no permission decision, input rewrite, context injection, or output replacement was emitted.
- Raw shadow events: 200; each Claude tool-use ID had exactly one PreToolUse and one PostToolUse event. Missing, duplicate, and unmatched IDs: 0.
- Unexpected/injected tool output: 0; all 100 observed results equaled their requested marker.
- Queue delta for this run: 200 processed, 0 dropped, 0 write errors.
- Claude CLI-reported run cost: `$0.1901724`; elapsed process wall time: `87.967 s` (includes model/tool orchestration and is not the hook-latency sample).

## Permission-flow preservation

A separate Claude CLI run attempted only local `curl --help`, which matches the existing ask rule and makes no network request. The Tier-2 PreToolUse hook returned `permissionDecision=ask`; the adjacent shadow hook returned exact `{}`. With `--permission-prompts none`, Claude reported one permission denial and did not run the command; no PostToolUse callback followed. CLI mode was `default`. The normal user approval mechanism was not replaced by the shadow hook.

## Latency distributions

Measurements use the actual registered Node wrapper command and `shadow_hook_client.py`, with synthetic non-sensitive event IDs. Percentiles use nearest-rank. “Cold” is one first invocation; warm samples are new per-hook processes after the first invocation, not a persistent Python process.

| Layer / condition | n | p50 ms | p95 ms | p99 ms | max ms | Outcome |
|---|---:|---:|---:|---:|---:|---|
| Node wrapper + Python client, first invocation | 1 | 53.023 | 53.023 | 53.023 | 53.023 | exact `{}`, exit 0 |
| Node wrapper + Python client, warm, concurrency 1 | 100 | 54.876 | 60.388 | 61.231 | 61.514 | 100/100 exact `{}`, exit 0 |
| Node wrapper + Python client, warm, concurrency 3 | 100 | 60.428 | 62.577 | 63.134 | 63.679 | 100/100 exact `{}`, exit 0 |
| Internal HTTP RPC, first invocation | 1 | 1.626 | 1.626 | 1.626 | 1.626 | response validated |
| Internal HTTP RPC, warm, concurrency 1 | 100 | 0.181 | 0.247 | 0.277 | 0.301 | 100 responses; no client exception |
| Internal HTTP RPC, warm, concurrency 3 | 100 | 0.360 | 0.522 | 0.683 | 0.768 | 84 enqueued; 16 queue-overload drops; no client exception |

The concurrency-3 overload result was independently reproduced in two 100-event RPC bursts: 81/100 then 84/100 events were recorded, while the daemon dropped 19 then 16. The missing event IDs matched each `dropped_count` delta. In the measured burst the client received bounded overload responses, kept its neutral output contract, and the queue drained to depth 0 with the daemon ready and zero write errors. A separate 128-call registered-wrapper burst at concurrency 24 produced 128 exact `{}` outputs, exit 0, empty wrapper stderr, 128 records, and no additional drop.

No timeout or client exception occurred in the measured RPC or wrapper latency samples. The hook wrapper remained neutral through both daemon-unavailable and bounded-load cases. Fixture overload/timeout tests are recorded in `w4-g1-validation.md`.

## Daemon stop and data boundary

The foreground daemon was stopped with Ctrl-C after the trial. Verification found no listener on `127.0.0.1:9878` and no remaining `hybrid-router-daemon.py` or `shadow_hook_client.py` process. A post-stop invocation of the registered wrapper returned exit 0 and exactly `{}` on stdout, emitted no wrapper stderr, and did not change the event log.

The Luna event log remained outside the repository at `~/.pi-router/luna/interventions.jsonl`; metadata after the run: 1,100 rows, 425,397 bytes, directory mode `0700`, file mode `0600`. No raw shadow records were committed. The tracked Tier-2 audit log remains at its original repository path; it has one local added line from live gate execution and is intentionally excluded from the evidence commit.

## Quality gates and limits

The final freeze verification command and results are recorded in the D2 council entry. Windows runtime remains unverified; Codex hook execution remains unverified. No gold corpus or resolution/recurrence claim was produced. The existing Claude `Stop` hook still reports exit 127 on this Mac because its configured `py c:/Pi/scripts/remote-relay.py` command is Windows-specific; the Claude tool run itself completed, and this unrelated hook was not changed.

A preliminary Fable CLI smoke hit `error_max_budget_usd` before executing its Bash tool and reported `$0.43458` despite a `$0.30` CLI budget setting. Subsequent smoke, 100-call, and permission runs used Haiku; their CLI-reported costs were `$0.0355601`, `$0.1901724`, and `$0.0186305`. CLI-reported total across these invocations was approximately `$0.678943`; account billing was not independently checked. No further model calls were made.
