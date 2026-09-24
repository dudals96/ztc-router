# ZTC Luna W4 gate and G1 fixture evidence

Date: 2026-09-24
Track: B — Luna
Worktree: `/Users/richardkim-macpro/Pi-wt/ztc-luna`
Branch: `ztc/phase1-luna`
W4 implementation commit: `fd5fc51010d8cc5046cda975a01ed999a3d9ea90`
Tier-2 commit: `f129c3e4e58f3f5cfa55cf0b452a414e97e0e912`

## Quality gates

The worktree had no `node_modules` at first. Locked packages were restored offline with `npm ci --offline --ignore-scripts` (389 packages; audit reported 0 vulnerabilities; package lock unchanged). The first command attempts could not find the local tools. After install and the narrowly scoped style/fixture corrections, all original gates passed:

| Command | Result |
|---|---|
| `npm run check` | PASS — Biome checked 73 files; no fixes applied. |
| `npm run secretlint` | PASS — exit 0, no findings. |
| `npm run typecheck` | PASS — exit 0. |
| `npm run typecheck:scripts` | PASS — exit 0. |
| `npm test` | PASS — 17 suites, 99 tests. |

Gate command: `npm run check && npm run secretlint && npm run typecheck && npm run typecheck:scripts && npm test`

The test-only Stripe-shaped fixture is assembled from fragments at runtime. Its runtime value and privacy assertion remain unchanged; this avoids a false-positive secret scan without weakening the test.

## Tier-2 platform checks

- `python3 -B tests/test_tier2_gate_hook.py`: PASS, 26/26.
- Existing one-shot allow was simulated with in-memory mocks; the deny path used `bypassPermissions`; no `.approve` file or approval hash was created, read, or changed.
- Malformed hook input on macOS returned `ask`.
- The actual `.claude/settings.json` command was invoked on this Mac with a benign Bash event: exit 0, no exit 127.
- Missing dispatcher, gate script, and Python interpreter simulations each returned `ask` and exit 0.
- The Tier-2 log remains at the repository-relative `learning/remote-approvals/tier2-gate-log.jsonl`; it is not coupled to `PI_ROUTER_HOME`.
- Windows execution is unverified. The shared `.codex/hooks.json` command path was not exercised through Codex; Codex hook execution remains unverified.

## G1 shadow fixtures

- `python3 -B engines/hybrid_router/tests/test_shadow_hook.py -v`: PASS, 11/11.
- Coverage includes normal paired Pre/Post events, daemon absence, timeout, malformed/oversized requests and responses, request cancellation/deduplication, overload, queue shutdown, loopback health, allowlisted telemetry, sensitive-value masking, neutral output, and preservation of undecided permission flow.
- The fixture server used ephemeral loopback resources and shut down in the test process. No production daemon, launchd entry, or shadow hook registration was started or changed by this fixture run.
- The fixture pass qualifies preparation of the separately gated shadow settings diff; it does not establish live registration or real-agent operation.
