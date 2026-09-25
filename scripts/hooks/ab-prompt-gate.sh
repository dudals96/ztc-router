#!/bin/sh
# ZTC evaluation gate (UserPromptSubmit, Claude Code and Codex; registered globally).
# For a work-loop directive, asks the agent to put one question to the user first:
# should this loop join the ZTC evaluation (docs/harness/AB_EVAL_ztc.md)? Keeps asking
# until the user says "ZTC 평가 중지". Invariant: exit 0, stdout is "{}" or one JSON
# object carrying hookSpecificOutput.additionalContext; never blocks the prompt.
exec 2>/dev/null
dir=${0%/*}
[ "$dir" = "$0" ] && dir=.
out=
# The daemon only runs on the Mac; elsewhere (Git Bash on Windows, where python3 may be
# the Microsoft Store alias stub) answer "{}" without starting python. $OSTYPE is a
# shell variable, so the check costs no process (a fork is ~110 ms in Git Bash);
# PI_HOOK_OS overrides it for tests.
os=${PI_HOOK_OS:-${OSTYPE-}}
[ -n "$os" ] || os=$(uname -s 2>/dev/null)
case $os in darwin* | Darwin) ;; *) os= ;; esac
if [ -z "$os" ]; then
	cat >/dev/null 2>&1
elif [ -f "$dir/ab_prompt_gate.py" ] && command -v python3 >/dev/null 2>&1; then
	out=$(python3 -S "$dir/ab_prompt_gate.py" 2>/dev/null)
else
	cat >/dev/null 2>&1
fi
# UserPromptSubmit adds plain stdout to Claude's context: pass on only a JSON object.
case $out in
'{'*'}') printf '%s' "$out" ;;
*) printf '{}' ;;
esac
exit 0
