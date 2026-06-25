from pytest_bdd import scenario

from step_defs.login_and_stop_instance_steps import *  # noqa: F401,F403


@scenario(
    "../feature/login_and_stop_instance.feature",
    "Login and stop the instance",
)
def test_login_and_stop_instance():
    pass
