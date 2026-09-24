# ZTC Phase 1 — Agent Hook Contract Matrix v0.3

- Status: Approved correction set; documentary contract only.
- Document snapshot date: 2026-09-24.
- Runtime verification: **not performed**. No hook settings were changed or exercised.
- Purpose: keep each agent's event schema and process result separate. A documented contract is not proof that the installed process behaves the same.

## Contract matrix

| Agent / version | Hook and event | Input on stdin | Neutral shadow output on stdout | Timeout | Exit and failure behavior | Verification state |
|---|---|---|---|---|---|---|
| Claude Code CLI 2.1.281 observed; official docs read 2026-09-24 | Command `PreToolUse` | JSON common fields plus `hook_event_name`, `tool_name`, `tool_input`, and `tool_use_id` | `{}` then exit `0`; leaves the normal permission flow undecided. Do not return `permissionDecision`, `updatedInput`, or `additionalContext`. | `timeout` is seconds; event default documented as 30 seconds. | Exit `2` blocks the tool call. A timed-out command hook does not block; normal permission flow continues. Other nonzero codes usually do not block by themselves; event-specific JSON rules still apply. | Local version observed; no installed-hook fixture. |
| Claude Code CLI 2.1.281 observed; official docs read 2026-09-24 | Command `PostToolUse` | Common fields plus `tool_input`, `tool_response`, `tool_use_id`, and optional `duration_ms`; tool has already completed. | `{}` then exit `0`; adds no context or decision. | `timeout` is seconds; command default is 600 seconds on this event. | Exit `2` can send feedback after execution; it cannot undo the completed tool. Current docs describe `updatedToolOutput` for replacing the result, but Phase 1 does not use it and installed behavior is unverified. | Local version observed; no installed-hook fixture. |
| Codex CLI 0.156.1 observed; official docs read 2026-09-24 | Command `PreToolUse` | JSON common fields plus `hook_event_name`, `tool_name`, `tool_input`, and `tool_use_id`; common fields include `session_id`, `cwd`, `transcript_path`, and `model`. | `{}` then exit `0`; Codex continues with its regular permission flow. | `timeout` is seconds; default 600 seconds for command hooks. | Exit `2` with a reason on stderr blocks supported tool calls. Do not depend on undocumented handling of a killed process or other nonzero exits; exercise those in an installed fixture before registration. | Local CLI version observed; no hook fixture. |
| Codex CLI 0.156.1 observed; official docs read 2026-09-24 | Command `PostToolUse` | Common fields plus `tool_name`, `tool_input`, `tool_response`, and `tool_use_id`; tool has already run. | `{}` then exit `0`; no informational feedback or result changes. | `timeout` is seconds; default 600 seconds for command hooks. | Current docs describe post-tool feedback/result handling, including replacing the tool result with feedback for some responses. It cannot undo tool side effects. No such output is used in Phase 1. | Local CLI version observed; no hook fixture. |
| Antigravity IDE/CLI; installed build not observed; official docs snapshot 2026-09-24 | Command `PreToolUse` | CamelCase JSON with `toolCall.name`, `toolCall.args`, `stepIdx`, and common fields such as `conversationId`, `workspacePaths`, `transcriptPath`, `artifactDirectoryPath`, and `modelName`. | **No neutral `{}` contract documented.** Current docs require a `decision`; this event is excluded from the Phase 1 neutral client. | `timeout` is integer seconds; default 30 seconds. | Current page does not specify process exit-code behavior. Do not infer allow/fail-open or register this event. | Neither build nor runtime behavior verified. |
| Antigravity IDE/CLI; installed build not observed; official docs snapshot 2026-09-24 | Command `PostToolUse` | CamelCase JSON with `toolCall`, `stepIdx`, optional `error`, and the common fields above. | `{}` is the documented response. | `timeout` is integer seconds; default 30 seconds. | Current page does not specify process exit-code behavior. Do not rely on it until the installed build is fixture-tested. | Neither build nor runtime behavior verified. |

## Boundaries

- A 30 ms client-side budget is an internal target; it is not a harness timeout. Harness values in this table are in seconds.
- The official Claude Code documentation describes `updatedToolOutput` on `PostToolUse`; the Codex documentation describes post-tool result feedback/replacement behavior. The v0.2 blanket claim that output replacement is impossible is withdrawn. No result-replacement behavior is enabled or accepted as verified in this phase.
- `PreToolUse` and `PostToolUse` do not share one schema across agents. Antigravity `PreToolUse` currently has no documented neutral output, so it cannot be treated as equivalent to the `{}`/exit-0 shadow contract.
- On daemon absence, timeout, malformed response, overload, or client error, use `{}`/exit `0` only for an event whose installed neutral contract has passed fixture tests. Never turn a performance hook into an allow/deny/input-rewrite/context-injection path.
- Hook registration, candidate-agent choice, and live shadow execution require the separate G3 approval in the task directive.

## Official references

- Claude Code [Hooks reference](https://code.claude.com/docs/en/hooks) — command input, event schemas, timeout and exit behavior, `PostToolUse.updatedToolOutput`; accessed 2026-09-24.
- OpenAI Codex [Hooks reference](https://developers.openai.com/codex/hooks) — command hook schemas, event outputs, timeout and exit behavior; accessed 2026-09-24.
- Google Antigravity [Hooks](https://antigravity.google/docs/hooks?tab=ide) — IDE hook event schemas and handler timeout; accessed 2026-09-24.

Official documentation is the source for the “documented” column. Local version strings only identify installed binaries; they do not certify hook behavior. No experimental claims are made here.
