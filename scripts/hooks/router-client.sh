#!/bin/sh
# ZTC Phase 1 shadow hook client (Claude Code PreToolUse / PostToolUse).
# Invariant: stdout is exactly "{}" and the exit code is 0, whatever the helper does
# (python3 missing, daemon down, timeout, bad input, cancellation). See
# docs/harness/HOOK_CONTRACT_ztc.md section 2.
exec 2>/dev/null
dir=${0%/*}
[ "$dir" = "$0" ] && dir=.
if [ -f "$dir/router_client.py" ] && command -v python3 >/dev/null 2>&1; then
	python3 -S "$dir/router_client.py" >/dev/null 2>&1
else
	cat >/dev/null 2>&1
fi
printf '{}'
exit 0
