# Claude Code hooks 레퍼런스 재조회 (2026-09-24, 유저 결정 4)

- 원문: https://code.claude.com/docs/en/hooks.md, HTTP 200, 331285 bytes, sha256 dc59d7c4fb28b246…, curl 로 직접 받음.
- WebFetch 요약은 두 번 서로 모순됐고 두 번째는 원문에 없는 `tool_output` 필드를 지어냈다(원문 grep 0건). 아래는 원문 줄 그대로다.

## 1. timeout 기본값 (원문 430행)
```
| `timeout`       | no       | Seconds before canceling. Claude Code doesn't enforce it on a command hook you run with [`async: true`](#run-hooks-in-the-background). Defaults: 600 for `command`, `http`, and `mcp_tool`; 30 for `prompt`; 60 for `agent`. Claude Code lowers the `command`, `http`, and `mcp_tool` default to 30 on [`UserPromptSubmit`](#userpromptsubmit), [`PreModelSwitch`](#premodelswitch), and [`PostModelSwitch`](#postmodelswitch), and to 10 on [`MessageDisplay`](#messagedisplay). [`SessionEnd`](#sessionend) hooks share a 1.5-second budget; if your settings set a longer per-hook `timeout`, Claude Code raises the budget to match, up to 60 seconds |
```
→ PreToolUse 별도 기본값 없음. command 600 s. 트랙 B 의 'PreToolUse 30 s' 는 틀림.

## 2. updatedToolOutput
```
* `PostToolUse`: `updatedToolOutput` replaces the tool's result. See [PostToolUse decision control](#posttooluse-decision-control)
| `decision`             | `"block"` adds the `reason` next to the tool result. Claude still sees the original output; to replace it, use `updatedToolOutput`                                                                                                                                               
| `updatedToolOutput`    | Replaces the tool's output with the provided value before it is sent to Claude. The value must match the tool's output shape                                                                                                                                                     
| `updatedMCPToolOutput` | Replaces the output for [MCP tools](#match-mcp-tools) only. Prefer `updatedToolOutput`, which works for all tools                                                                                                                                                                
  `updatedToolOutput` only changes what Claude sees. The tool has already run by the time the hook fires, so any files written, commands executed, or network requests sent have already taken effect. Telemetry such as OpenTelemetry tool spans and analytics events also captures the original output before the hook runs. To prevent or modify a tool call before it runs, use a [PreToolUse](#pretooluse) hook instead.
```
→ PostToolUse 결정 필드로 문서화됨. 트랙 A 의 '레퍼런스 표에 없음' 은 옛 판독. 설치판 동작은 미검증이며 shadow 에서는 계속 금지.

## 3. PostToolUseFailure 입력·결정 (원문 2108행~)
```
#### PostToolUseFailure input

PostToolUseFailure hooks receive the same `tool_name` and `tool_input` fields as PostToolUse, along with error information as top-level fields. For an MCP tool, they also receive the [`mcp_server`](#pretooluse-input) object. For example, a failed `npm test` command might deliver:

```json theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "PostToolUseFailure",
  "tool_name": "Bash",
  "tool_input": {
    "command": "npm test",
    "description": "Run test suite"
  },
  "tool_use_id": "toolu_01ABC123...",
  "error": "Exit code 1\nError: Cannot find module 'express'",
  "is_interrupt": false,
  "duration_ms": 4187
}
```

| Field          | Description                                                                                                                                                                                                                    |
| :------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `error`        | String describing what went wrong. The format depends on the tool that failed                                                                                                                                                  |
| `is_interrupt` | Optional boolean. True when the failure reached Claude Code as an abort rather than as an error the tool reported. Cancelling a running tool does not fire this hook; the tool result carries the interruption message instead |
| `duration_ms`  | Optional. Tool execution time in milliseconds. Excludes time spent in permission prompts and PreToolUse hooks                                                                                                                  |

The `error` string is generally the same text Claude receives as the failed tool's result. Its format varies by tool and failure. Key your hook on `tool_name`, `is_interrupt`, and the `Exit code N` first line; treat the rest of the string as display text, not a stable format.

* For Bash and PowerShell, a command that ran and exited produces a first line `Exit code N`, then any output the command produced as one block with stdout and stderr interleaved
* A payload may also carry a bare failure message with no exit-code line, when Claude Code could not start the shell process itself
* Claude Code middle-truncates long strings around a `... [N characters truncated] ...` marker, and can insert lines of its own, such as `Command timed out after 2m 0s`

#### PostToolUseFailure decision control

`PostToolUseFailure` hooks can provide context to Claude after a tool failure. In addition to the [JSON output fields](#json-output) available to all hooks, your hook script can return these event-specific fields:

| Field               | Description                                                                                                 |
| :------------------ | :---------------------------------------------------------------------------------------------------------- |
| `additionalContext` | String added to Claude's context alongside the error. See [Add context for Claude](#add-context-for-claude) |

```json theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUseFailure",
    "additionalContext": "Additional information about the failure for Claude"
  }
}
```

### PostToolBatch

Runs once after every tool call in a batch has resolved, before Claude Code sends the next request to the model. `PostToolUse` fires once per tool, which means it fires concurrently when Claude makes parallel tool calls. `PostToolBatch` fires exactly once with the full batch, so it is the right place to inject context that depen
```
