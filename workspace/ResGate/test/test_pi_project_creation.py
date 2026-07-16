from pytest_bdd import scenarios

from step_defs.common_steps import *
from step_defs.pi_login_to_research_gateway_steps import *
from step_defs.pi_project_creation_steps import *

scenarios("../feature/pi_project_creation.feature")
