from pytest_bdd import scenario

from step_defs.create_new_instance_steps import *  # noqa: F401,F403


@scenario(
    "../feature/create_new_instance.feature",
    "Launch a Standard Linux Remote Desktop instance with project configuration",
)
def test_launch_standard_linux_remote_desktop():
    pass
