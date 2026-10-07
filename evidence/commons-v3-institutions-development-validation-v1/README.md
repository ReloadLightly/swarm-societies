# Institutional development validation and publication

These receipts are outside the completed frozen bank. The
[study report](../../docs/commons-v3-institutions-development-v1.md) gives the
scientific results and limitations; none of these checks qualifies institutional
benefit.

- [Preparation](preparation.json) and [seed disjointness](seed-disjointness.json)
  precede the bank. [Freeze](freeze.json) verifies remote source/design commit
  `a4c84e67cc7d6d05ef4d05c13e75c7fafe90e6c2` with zero panel episodes.
- [Execution](execution.json) completes all 144 episodes in 192.95 seconds.
  [Replay](replay.json) verifies every episode, exact summary and midpoint
  policy-memory continuation in 244.83 seconds. Complete logs remain alongside.
- [Recorded diagnostics](recorded-diagnostics.json) bind the read-only script,
  completed manifest, summary and all raw hashes. They are retrospective counts
  of saved decisions/outcomes, not additional simulations or causal evidence.
- [Local archive verification](archive-local.json) checks all 144 raw files,
  original total 17,133,617 bytes, archive size 15,473,215 bytes.
- [Results synchronization](results-sync.json) records remote main at
  `2c59d9e90e616a4e62c7c31b77e841986053c491` before release creation.
  [Release metadata](release.json) and [remote tag verification](release-sync.json)
  confirm that same target for the new separately identified public release.
- [Public metadata](public-metadata.json) verifies unauthenticated catalog and
  manifest downloads against local bytes. [Public restoration](public-restore.json)
  starts with an empty destination and cache; [offline restoration](offline-restore.json)
  uses the verified cache and a second empty destination. Each restores all
  144 files with zero pre-existing files and exact path/size/SHA-256 checks.

The [first public restoration attempt](public-restore-initial-attempt.json)
downloaded the archive but failed because its destination root did not exist;
the existing helper requires that root to be created first. The successful
retry explicitly created an empty destination and used a different empty
cache. No bank, archive asset or restoration helper was changed.

No ecology replay, figure or publication layer was added. Earlier bank sources,
verdicts and archive identities remain unchanged. Hashes detect changed assets;
GitHub hosting is not administratively immutable.
