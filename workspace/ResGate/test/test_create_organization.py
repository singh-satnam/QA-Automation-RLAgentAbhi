"""pytest-bdd entrypoint for feature/create_organization.feature.

Binds the feature's scenarios. Step definitions are imported from the
per-feature step module so they are registered even before the harness wires
them into pytest_plugins.
"""

from pytest_bdd import scenarios

# Register the step definitions for this feature.
from step_defs.create_organization_steps import *  # noqa: F401,F403

scenarios("../feature/create_organization.feature")
