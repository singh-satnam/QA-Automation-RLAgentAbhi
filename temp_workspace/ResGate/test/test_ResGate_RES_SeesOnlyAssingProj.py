from pytest_bdd import scenarios

from step_defs.common_steps import *
from step_defs.researcher_login_steps import *
from step_defs.researcher_sees_only_assigned_projects_steps import *

scenarios("../feature/researcher_sees_only_assigned_projects.feature")
