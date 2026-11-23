# Required reading

Read these in order before changing alt-claude.

1. [README](../README.md) for installation, the public CLI, recovery, and design principles.
2. [Software overview](software-overview.md) for entry points and the launch sequence.
3. [Limits](limits.md) and [Project rules](project-rules.md) for operational boundaries and maintenance expectations.

Read the matching reference before changing a subsystem.

| Work | Reference | Implementation or check |
| --- | --- | --- |
| Profiles, context, and free-route fallback | [Model profiles](profiles.md) | [Profile dispatcher](../alt-claude-profile), [catalog check](../tools/check-profiles.sh) |
| Provider routing, authentication, and usage | [Providers](providers.md), [Credentials](credentials.md), [Usage](usage.md) | [Provider core](../alt-claude-core), [usage report](../tools/usage-report.py) |
| Project policy | [README policy section](../README.md#project-policy) | [CLI dispatcher](../alt-claude), [policy helper](../tools/project-policy.py) |
| Local model state and free-profile benchmarks | [CLI help](../alt-claude) | [Model state](../tools/model-state.py), [performance helper](../tools/performance.py) |
| Session recovery | [README session recovery section](../README.md#offline-session-compact--recovery) | [Session compactor](../tools/session-compact.py) |
| Delegation to the T610 | [Local worker capacity](local-worker-capacity.md) | Worker scope, benchmark conditions, and resource policy |

Use the [structural test suite](../tests/test-profiles.sh) to see how installation, dispatch, policy, fallback, and session recovery are exercised.
