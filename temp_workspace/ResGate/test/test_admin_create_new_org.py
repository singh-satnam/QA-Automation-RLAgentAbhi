from pytest_bdd import scenarios

from step_defs.common_steps import *
from step_defs.researcher_login_steps import *
from step_defs.admin_login_steps import *
from step_defs.pi_project_creation_steps import *
from step_defs.admin_create_new_org_steps import *

scenarios("../feature/admin_create_new_org.feature")
