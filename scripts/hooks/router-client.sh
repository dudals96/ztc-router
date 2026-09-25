#!/bin/sh
# ZTC Phase 1 shadow hook client (Claude Code PreToolUse / PostToolUse).
# Invariant: stdout is exactly "{}" and the exit code is 0, whatever the helper does
# (python3 missing, daemon down, timeout, bad input, cancellation). See
# docs/harness/HOOK_CONTRACT_ztc.md section 2.
exec 2>/dev/null
dir=${0%/*}
[ "$dir" = "$0" ] && dir=.
# The daemon only runs on the Mac. Elsewhere (Git Bash on Windows, where python3 may be
# the Microsoft Store alias stub, ~300 ms per call) skip python entirely. $OSTYPE costs
# no process; PI_HOOK_OS overrides it for tests.
os=${PI_HOOK_OS:-${OSTYPE-}}
[ -n "$os" ] || os=$(uname -s 2>/dev/null)
case $os in darwin* | Darwin) ;; *) os= ;; esac
if [ -z "$os" ]; then
	cat >/dev/null 2>&1
elif [ -f "$dir/router_client.py" ] && command -v python3 >/dev/null 2>&1; then
	python3 -S "$dir/router_client.py" >/dev/null 2>&1
else
	cat >/dev/null 2>&1
fi
printf '{}'
exit 0
