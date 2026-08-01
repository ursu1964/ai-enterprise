# Extension Standard

Each extension supplies a signed manifest with identity, version, capabilities, permissions,
dependencies, compatibility matrix, lifecycle hooks, configuration schema, isolation class, and
publisher. The kernel verifies signature, compatibility, dependency closure, authority ceiling, and
configuration before activation. Extensions cannot grant themselves capabilities, bypass gateways,
modify approval state, or run lifecycle hooks outside declared limits. Disable and uninstall paths
are tested and auditable.

