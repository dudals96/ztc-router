# ZTC Phase 1 — Shadow and Gold Evaluation Protocol v0.3

- Status: Approved correction set; protocol only.
- No raw events or gold samples were collected in this turn.
- G3 registration and live shadow evaluation remain separately gated.

## 1. Separate what is measured

| Measure | What it answers | Numerator / denominator | Shadow status |
|---|---|---|---|
| Hook conformance (K0) | Did the event follow the selected agent/version/event contract and return a neutral response? | Eligible events that produced the documented neutral JSON, exited `0`, and had no permission/input/context/output side effect / all eligible events. Separately report attempted RPC correlation (matched, unmatched, duplicate), malformed, timeout, and neutral-fallback counts. | Measurable only after G3 approval and installed-contract verification. It says nothing about whether an error was solved. |
| Routing/classification quality (K3) | Did a candidate label match a reviewed gold label? | Correct candidate classifications / adjudicated holdout cases; report class-wise counts and 95% confidence intervals. | Fixture results are not user-reviewed gold performance. |
| Actual resolution (K2) | Did the first comparable retry succeed after an approved repair? | Approved interventions followed by a successful first comparable retry / approved interventions followed by an eligible retry. | **N/A**: a shadow hook makes no repair. |
| Recurrence (K4) | Did the same normalized signature return after an initially successful approved repair? | Initial-success repairs followed by the same signature during the next 3 comparable calls or 24 hours, whichever ends first / initial-success repairs with a complete window. | **N/A**: no intervention occurs in shadow. Report censored/incomplete windows separately. |
| Latency (K1) | What cost did observation add? | Full process and internal RPC durations as separate distributions. | Report cold/warm, concurrency, p50/p95/p99, timeout and neutral-fallback rates. Do not substitute simulated values. |

Hook conformance, classification accuracy, actual resolution, recurrence, and latency are separate results. Do not label a neutral or matched response as a fix, and do not report shadow K2/K4 as zero-percent failure.

## 2. Gold grouping and holdout

1. Give each source session and normalized error-signature group a local pseudonymous identifier. Keep any key or mapping outside the repository; do not commit stable per-session identifiers.
2. Build connected groups from the relation “same source session” or “same normalized error-signature group.” Assign each connected component wholly to one partition. No session or error-signature group may cross partitions.
3. Use the tuning partition for rule and threshold selection. Freeze the rule/policy snapshot, schema, evaluation code, and partition manifest before opening the final holdout.
4. Evaluate the final holdout once for the predeclared candidate release. Repeated inspection retires that holdout and requires a new independently collected holdout. If a component is too large or a class is missing, preserve the boundary and report the resulting class coverage/precision limit. Do not split a group to improve balance.
5. Keep separate tuning and final-holdout manifests with hashes and the evaluated HEAD. Report exclusions and duplicate/collision handling. A holdout inspected during tuning is no longer a final holdout.

## 3. Freeze learning during evaluation

- Evaluation reads a pinned, read-only candidate/rule snapshot. Disable write-through, signature promotion, threshold updates, cache learning, and automatic outcome ingestion for the entire run.
- Record the candidate and policy hashes before evaluation and verify them afterward. If they differ, discard the run as contaminated and start a new versioned evaluation.
- Review and adjudication occur outside the final scoring pass. Any accepted feedback creates a new candidate/dataset version; it cannot update the active holdout while that candidate is being scored.

## 4. What sample counts can establish

For a simple random binary proportion near 50%, the approximate worst-case 95% margin of error is `1.96 × sqrt(0.25/n)`: about **±5.7 percentage points at n=300** and **±3.1 points at n=1,000**. An idealized ±1 point margin needs roughly **9,604 independent cases**. These are idealized precision estimates, not power guarantees.

Session/signature clustering reduces effective sample size when cases are correlated, and rare classes or rare harmful outcomes need substantially more observations. Therefore:

- n=300 alone does not establish 3-percentage-point noninferiority.
- n=1,000 alone does not establish one-percentage-point precision or a one-point performance improvement.
- Neither count guarantees coverage of every class or rare failure mode.
- A confirmatory noninferiority claim needs a pre-registered margin, baseline, one-sided error/power, class and cluster assumptions, and a prospective power calculation. Report the actual confidence interval and effective grouping; if precision is inadequate, label the result inconclusive.

## 5. Data minimization and local storage

### Collection and fields

- Collect nothing until the relevant live-test/gold-data approvals exist. Fixtures use synthetic input only.
- Before queueing, transmitting, or logging, allow-list only what evaluation needs: event type, tool family, coarse outcome code, elapsed time, bounded request ID, and local keyed pseudonyms for grouping.
- Do not persist or transmit raw command text, file contents, stdout/stderr, full tool responses, absolute paths, transcript paths, usernames, tokens, or credential-shaped values. Treat normalized signatures and pseudonyms as sensitive local data.
- The only permitted future raw-data location for the Luna draft is `PI_ROUTER_HOME/raw/`, with `PI_ROUTER_HOME=~/.pi-router/luna/` for this worktree. The merged default remains `~/.pi-router/`. Raw material never goes under Git-tracked `learning/`, `docs/`, or repository logs. Repository metrics may contain anonymized aggregates only.

### Capacity, permissions, and retention

- POSIX directory permissions: `0700`; data and manifest files: `0600`; create under `umask 077`. No Windows collection until a separate ACL design is reviewed.
- Hard raw-storage limits: **256 MiB total**, at most **4,096 records**, and **64 KiB per record**. On a limit, stop collection and report quota exhaustion; do not silently evict records or expand the cap.
- Raw scratch data expires after **7 days**. A sanitized, user-approved gold corpus expires **90 days after the evaluation phase closes**, unless the user approves a new retention decision. Aggregates must contain no path, transcript, stable session ID, or reversible pseudonym.
- Record the chosen data version, count, byte size, creation time, expiry, and deletion result in a local manifest. Store any pseudonymization key outside the repository with `0600` permissions. Do not put the manifest, key, or keyed pseudonyms in Git.

### Deletion procedure

1. Stop the manually started Luna process and verify that it has exited; do not register or stop any unrelated service.
2. Resolve and inspect the exact `PI_ROUTER_HOME/raw/` path, confirm it is the intended Luna data directory, and list the target corpus/date and manifest before deletion.
3. Delete only the selected raw corpus or expired files. If deleting the complete raw directory, verify the canonical path and directory basename first, then recreate an empty `0700` directory only if a later approved run needs it.
4. Verify the selected files are absent and record the logical deletion. APFS/SSD snapshots and backups may retain physical copies; this procedure does not claim secure erasure. Review those retention surfaces separately if they contain the corpus.

No collection, storage setup, expiry job, or deletion was performed as part of this documentation change.
