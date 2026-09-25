#!/bin/sh
# ZTC A/B prompt gate (Claude Code UserPromptSubmit).
# While the router daemon reports ready, asks Claude to put one AskUserQuestion to the
# user: should this directive's loop / work turn join the A/B evaluation
# (docs/harness/AB_EVAL_ztc.md)? Invariant: exit 0, stdout is "{}" or one JSON object
# carrying hookSpecificOutput.additionalContext; never blocks the prompt.
exec 2>/dev/null
dir=${0%/*}
[ "$dir" = "$0" ] && dir=.
out=
# The daemon only runs on the Mac; elsewhere (Git Bash on Windows, where python3 may be
# the Microsoft Store alias stub) answer "{}" without starting python.
if [ "$(uname -s 2>/dev/null)" != Darwin ]; then
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
