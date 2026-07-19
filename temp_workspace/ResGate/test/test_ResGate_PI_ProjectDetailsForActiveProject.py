from pytest_bdd import scenarios

from step_defs.common_steps import *
from step_defs.researcher_login_steps import *
from step_defs.pi_login_steps import *
from step_defs.pi_project_details_active_project_steps import *

scenarios("../feature/pi_project_details_active_project.feature")
