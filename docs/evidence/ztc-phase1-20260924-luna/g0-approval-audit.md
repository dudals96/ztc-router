# ZTC Phase 1 Luna — G0 approval audit

Date: 2026-09-24  
Track: B — Luna / GPT-6  
Worktree: `/Users/richardkim-macpro/Pi-wt/ztc-luna`  
Branch: `ztc/phase1-luna`  
HEAD: `dcd00b7e206cc05fbb98a3209cf91a979993c0b2`  
Status: initial audit stopped at G0; see the decision-resolution addendum below for the current state.

## Approval record

| Decision | Record and evidence | State at this turn | Boundary |
|---|---|---|---|
| Phase 1 start and priority for this bounded Luna task | Current user instruction archived as `learning/user-prompts/2026-09-24_Thu/12_luna-phase1-execution.md`; task scope is `tasks/codex-to-gpt6-luna__ztc-phase1-impl.md` | Approved to enter the task and perform G0. This does not waive the task's item-level gates. | No implied approval for settings, services, or unresolved policy. |
| Plan §10-1, local worker direction | `docs/PLAN_ZTC_topology_optimization.md` §10-1 | Pending; Phase 2 direction, outside this G0 implementation step. | No worker or Windows changes. |
| Plan §10-2, LaunchAgent registration | Plan §10-2 | Pending; requires a later, separate approval after daemon safety work. | No service registration. |
| Plan §10-3, shadow hook registration | Plan §10-3; implementation task §5–6 | Pending at separate G3. | No settings or hook edits. |
| Plan §10-4, Laya installation | Plan §10-4 says withdrawn | Withdrawn; no approval needed or inferred. | No Laya install. |
| Plan §10-5, L1/L2 gate criteria | Plan §10-5 | Pending for a later phase after gold evaluation. | No L1/L2 work. |
| Plan §10-6, Site 1 exclusion / i7 candidate | Plan §10-6 | Pending for later target selection. | No other-node changes. |
| Plan §10-7, council disagreement about “ZTC 100% 준수” | `docs/UNIFIED_TURN_REPORT.md`; `docs/evidence/ztc-plan-review-20260924/claude-code-verification-A1-A12.md`; `astra-review-2.md` | No user verdict found. | Do not edit UTR or present the disagreement as user-resolved. |
| Plan §10-8, priority versus Remote Vibe Hub | Current user instruction explicitly requests this bounded Phase 1 task. | Approved only for the current task. | No broader reprioritization inferred. |
| Plan §10-9, Phase 1 start | Current user instruction explicitly requests execution of the Luna task. | Approved to start, subject to G0–G3. | Does not approve unresolved entries below. |
| v0.3 contract corrections and v0.3 file | User's reply `1` to the clarification prompt selected “1번만 진행,” whose option text was approval of the v0.3 correction set only. | Approved for the listed documentary corrections; reflected in the v0.3 plan and contract/evaluation files. | No code, hook registration, or service/settings change is covered by this approval. |
| Luna raw-data root | User's parallel-draft header sets `~/.pi-router/luna/`, with `PI_ROUTER_HOME` and the merge default `~/.pi-router`. | Approved for this isolated track by the current task directive. | No raw-data write performed. |
| Mac Tier-2 security-hook failure policy | Handoff §3 and prompt 07 list OS guard plus explicit failure handling versus removal from Mac. | Pending; no choice found. | No Tier-2 hook or approval-file edits. |
| `biome.json` `.codegraph` exclusion | Task §3 and handoff §3 list this as an unresolved exact-diff decision. | Pending. | No Biome config or gate changes. |

## v0.3 proposal content (approved after this audit)

The task requests that v0.3 include: retracting the v0.2 claim that output replacement is impossible and marking installed behavior unverified; a per-agent/version/hook/event input-output-timeout-exit contract table; separate shadow conformance and actual resolution/reoccurrence metrics; session/signature-group splits with separate tuning and final holdout sets; frozen write-through during evaluation; an explicit limit on what samples of 300/1,000 can establish; HEAD and relevant-file hashes attached to the council correction proposal; and raw-data minimization, retention, capacity, permissions, and deletion procedure. The user later approved this correction set only; implementation is recorded in `docs/PLAN_ZTC_topology_optimization.md` and `docs/harness/{HOOK_CONTRACT_ztc,EVAL_PROTOCOL_ztc}.md`.

## Evidence anchors

- Task directive: `tasks/codex-to-gpt6-luna__ztc-phase1-impl.md`.
- Parallel isolation and separate gates: `tasks/ztc-phase1-dual-draft__merge-protocol.md`.
- Plan decisions: `docs/PLAN_ZTC_topology_optimization.md` §10.
- Handoff status: `docs/turn-reports/2026-09-24_Thu/2026-09-24_claude-code_session-handoff.md` §§3–4.
- Current UTR SHA-256: `d290b718c445f35b2c4d0384f11b753ebcbb8483e89ee69e49f1eac05608d219`.
- Plan SHA-256: `5c32f8bcfad5d586c02dab7b608173e73486639adba45992a3a6b75d39a92cd8`.
- A1–A12 verification SHA-256: `15b57060749dee46a7666bf887f2ae7cf80a295ed6e853bcba3203b919943248`.
- Astra second-reply SHA-256: `f928a6e965b2f08b06f551d8e4cf6bd1876c287f63522ac311b62e3bd4335b36`.

## Read-only checks

- `git status --short --branch`: clean at start; branch `ztc/phase1-luna`.
- `git rev-parse --show-toplevel`: `/Users/richardkim-macpro/Pi-wt/ztc-luna`.
- `git remote -v`: origin is Pi; branch has no upstream.
- `pwsh -File scripts/session-recover.ps1`: exit 0, no `-Pull`; surfaced an Astra-addressed pending INBOX without consuming it. Its MCP self-heal prelude reported “success” after noting the Windows extensions directory was absent; this is not evidence that an MCP failure was present or independently repaired.
- At this initial audit, no tests were run because G0 had not yet authorized v0.3 edits or offline implementation.
- `scripts/rebuild-user-prompts.ps1` was not run: it is hard-coded to `C:\Pi` and warns that `pwsh` 7 is unsafe; it cannot safely rebuild this Mac worktree. The user prompt was archived directly. DIGEST/INDEX regeneration remains outstanding.

## G0 stop point before clarification

At the time of the initial audit, the track was stopped before v0.3 edits. See the decision-resolution addendum below for the later scoped approval and current stop point.

## Integrity-check addendum

- The newly appended intervention row parses as valid JSON.
- Line-by-line validation of the existing `learning/interventions.jsonl` found pre-existing malformed rows at 30, 36, 38, 39, 43, 46, 50, 106, 109, 181, and 293. These rows were not edited because this log is append-only.
- Current `biome.json` uses `files.includes` patterns and currently omits the root `.codegraph` symlink. The exact proposed change is one line, inserted before `!dist`: add `"!.codegraph",`. This change was not applied and remains pending user approval.
- `.codegraph` currently points to `/Users/richardkim-macpro/.omo/codegraph/projects/ztc-luna-e11663cf8fa58b52`.

## Weighted SWOT comparison guide

Purpose at comparison time: let the user compare four pending decisions while rewarding stronger S/O and lower W/T. These are preliminary judgment scores from the recorded task and review evidence; they are not measured outcomes or probabilities. The later decision is in the addendum below.

### Rating and scoring

Rate each option from 1 to 5:

- **S — Strength:** 1 = little benefit; 5 = directly strengthens correctness, safety, or control.
- **O — Opportunity:** 1 = little future value; 5 = opens a substantial, evidence-backed next step.
- **W — Weakness:** 1 = low cost/limitation; 5 = high cost/limitation.
- **T — Threat:** 1 = low residual risk; 5 = high residual risk.

S and O together carry 60% of the score; reducing W and T carries 40%:

Score = 100 × [0.30×(S−1)/4 + 0.30×(O−1)/4 + 0.20×(5−W)/4 + 0.20×(5−T)/4]

Read scores as: 75–100 = favorable candidate; 50–74 = conditional; 0–49 = defer or redesign. Evidence confidence is shown separately so a high estimate does not imply strong evidence. Compare alternatives within each decision first; do not add scores across independent approval gates.

| Decision option | S/O/W/T | Score | Confidence | Basis |
|---|---:|---:|---|---|
| 1. Approve the task's v0.3 correction set | 5/5/2/2 | **90** | Medium | At scoring time the v0.3 had not yet been drafted or reviewed; the approved documentary draft is now recorded below, while runtime behavior remains unverified. |
| 1. Defer v0.3 approval | 2/2/4/4 | **25** | Medium | Avoids fixing unsettled assumptions, while blocking implementation and leaving v0.2 gaps open. |
| 2A. Approve OS-specific Mac handling with explicit failure behavior | 5/5/3/3 | **80** | Medium | Addresses the reported Mac exit 127; platform behavior and per-failure policy still need definition and verification. |
| 2B. Approve removing this hook on Mac | 3/3/2/4 | **50** | Medium | Avoids the incompatible invocation, but leaves this Mac path without the hook's protection. |
| 2. Defer the Mac policy | 1/1/4/5 | **5** | Medium | Makes no unsupported policy choice; the known failure state remains unresolved. |
| 3. Approve only the one-line !.codegraph Biome exclusion | 4/4/1/2 | **80** | Medium | Narrowly removes the root CodeGraph symlink from lint scope; exact behavior has not been rerun. |
| 3. Defer the exclusion and keep current scan | 2/2/3/4 | **30** | Medium | Preserves current scan intent; the reported CodeGraph-related gate problem remains. |
| 4. Correct the UTR claim to heuristic/simulated; deployed routing unverified | 5/5/2/2 | **90** | Medium-high | Aligns the record with code/review evidence; actual deployment state remains a separate unknown. |
| 4. Defer the council verdict | 2/2/4/4 | **25** | Medium-high | Preserves the user's authority to adjudicate; the unsupported claim remains visible meanwhile. |

### User comparison procedure

1. Review each option's S/O/W/T ratings and its evidence-confidence label; change any rating that does not match the user's priorities.
2. Prefer the higher-scoring option within each item, unless its stated threat or a hard project gate is unacceptable.
3. For 2A, specify Mac behavior for daemon absence, timeout, and permission failure; the score does not select those policies.
4. Record four independent decisions. A score never authorizes code/config edits by itself; G0 still governs v0.3 and offline work, and shadow registration remains a separate G3 approval.

## Decision-resolution addendum — 2026-09-24

The user first replied “4항목 다 승인 결정,” then sent `1`. To resolve the conflict without inferring intent, the assistant offered three choices: (1) approve only v0.3 and defer the other three, (2) keep all four approvals, or (3) another meaning. The user's raw reply was `1`, so only choice 1 is recorded as the current decision.

### Approved

- The v0.3 correction set listed in task §3, limited to documentation: event/version-specific hook contract table; withdraw the universal PostToolUse-output-replacement claim and record installed behavior as unverified; separate shadow conformance from actual resolution/reoccurrence; session/signature-grouped tuning and holdout; freeze write-through during evaluation; document limits of n=300/n=1,000; attach current HEAD and relevant source hashes to the council correction proposal; and specify raw-data minimization, retention, capacity, permissions, and deletion.
- The approval was applied to `docs/PLAN_ZTC_topology_optimization.md`, `docs/harness/HOOK_CONTRACT_ztc.md`, and `docs/harness/EVAL_PROTOCOL_ztc.md`. The UTR disagreement document is only a hash-bound proposal; the UTR was not edited.

### Still pending

- Mac Tier-2 hook failure policy.
- Exact `.codegraph` Biome exclusion.
- User verdict on the UTR “ZTC 100% 준수” claim.
- Shadow registration at G3, including agent choice and exact settings diff.

No source code, hook/settings/configuration, daemon, LaunchAgent, or service was changed. No test, installed hook fixture, live shadow, data collection, or deletion was performed. The latest documented stop is after v0.3 documentation and before W1–W4 code/config implementation. The prompt index/digest remains stale because the existing rebuild script targets `C:\Pi` and rejects the current PowerShell 7/Mac worktree workflow.
