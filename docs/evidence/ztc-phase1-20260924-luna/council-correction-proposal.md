# Council correction proposal — ZTC deployment claim

- Status: Evidence-bound proposal only; **user verdict remains pending**.
- Captured: 2026-09-24.
- Worktree: `/Users/richardkim-macpro/Pi-wt/ztc-luna`, branch `ztc/phase1-luna`.
- Source HEAD: `dcd00b7e206cc05fbb98a3209cf91a979993c0b2`.
- The recorded source files below were not edited in this turn. Their hashes bind this proposal to the repository evidence snapshot, not to an observed deployed system.

## Statement under review

The 2026-09-24 UTR reports “ZTC 100% 준수: 로짓 기반 확신도 게이팅·forward-pass 분류 확인.” The Phase 1 source/review evidence does not support treating that statement as proof of deployed routing. The worktree does not establish current deployment, daemon registration, or live hook behavior.

## Proposed correction for user adjudication

> The cited repository snapshot uses heuristic/simulated routing metadata, and the inspected HYBRID-ROUTER interceptor was not wired as a usable agent hook. These artifacts do not verify deployed routing or live model inference; current deployment state remains unverified.

This text is not yet a UTR change and is not a user verdict. The UTR remains untouched until the user decides the disagreement.

## Evidence snapshot

| Artifact | SHA-256 |
|---|---|
| `docs/UNIFIED_TURN_REPORT.md` | `d290b718c445f35b2c4d0384f11b753ebcbb8483e89ee69e49f1eac05608d219` |
| `engines/hybrid_router/router_core.py` | `6a5522c79d79a5410e349e42018f8e84a5e6c2c75c762cce12e363d8fec165fb` |
| `engines/hybrid_router/hierarchical_routing/hierarchical_engine.py` | `1938ea86decaee3d5a19019c56fb29de2ac4bfd4ca7e10755fdb39c250200f21` |
| `engines/hybrid_router/gateway/jev_client.py` | `6ea5ec0e263441715b089c0d9bf9009bfb0a52cd117a8fafc648a37b01aae8df` |
| `scripts/hybrid-router-daemon.py` | `aa32fb73150e9d537b589e75602784fb6e2a5faaf7bfb09b7fbf48e6c8d043a0` |
| `scripts/decision-gate-interceptor.py` | `3bbe46ebd5e03e283d3721528827effcb1cb1ed216842a9d68397ec064f22fa7` |
| `docs/evidence/ztc-plan-review-20260924/claude-code-verification-A1-A12.md` | `15b57060749dee46a7666bf887f2ae7cf80a295ed6e853bcba3203b919943248` |
| `docs/evidence/ztc-plan-review-20260924/astra-review-2.md` | `f928a6e965b2f08b06f551d8e4cf6bd1876c287f63522ac311b62e3bd4335b36` |

The claim and correction candidate should be judged against this pinned snapshot. A new checkout, changed source hash, or live-system observation requires a new evidence record.
