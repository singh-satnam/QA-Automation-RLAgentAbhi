import pytest
from pytest_bdd import scenario

from step_defs.login_and_launch_machine_steps import *


@scenario(
    "../feature/login_and_launch_machine.feature",
    "Login navigate to project product and launch remote desktop",
)
def test_login_navigate_to_project_product_and_launch_remote_desktop():
    pass
