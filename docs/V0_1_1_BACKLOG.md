# v0.1.1 backlog

Target: first post-`v0.1.0` stabilization release with no scope expansion.

Status: closed (completed in `v0.1.1`).

## Priorities

1. **Release/CI hygiene**
   - Upgrade GitHub Actions versions in workflows to current supported releases.
   - Remove Node runtime deprecation warning from the publish workflow.
   - Keep `build` + `twine check` in CI green on every push.

2. **Developer experience polish**
   - Add a concise changelog entry format for future releases.
   - Ensure `docs/PUBLISH_PYPI.md` reflects the exact current release steps.
   - Add a short troubleshooting section for common trusted-publisher failures.

3. **README and package surface polish**
   - Keep `README.md` status/current commands aligned with shipped behavior.
   - Add a minimal install + SDK quickstart path near the top.
   - Verify PyPI project links and description remain accurate as repo visibility changes.

4. **Flow reliability cleanup**
   - Review recent acceptance artifacts for flaky waits/recognition steps.
   - Tighten default wait/verify guidance in flow docs based on observed runs.
   - Add at least one regression test for any bug found during this review.

## Out of scope for v0.1.1

- New recognizer families (Phase 7+)
- Windows backend implementation (Phase 9)
- Ecosystem expansion items (Phase 10)
