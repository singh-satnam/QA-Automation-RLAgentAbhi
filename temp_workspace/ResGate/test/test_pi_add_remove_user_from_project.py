from pytest_bdd import scenarios

from step_defs.common_steps import *
from step_defs.researcher_login_steps import *
from step_defs.pi_login_steps import *
from step_defs.pi_project_details_active_project_steps import *
from step_defs.pi_admin_user_cannot_be_added_to_project_steps import *
from step_defs.pi_add_remove_user_from_project_steps import *

scenarios("../feature/pi_add_remove_user_from_project.feature")
