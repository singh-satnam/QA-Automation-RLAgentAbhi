from pytest_bdd import scenarios

from step_defs.common_steps import *
from step_defs.researcher_login_steps import *
from step_defs.pi_login_steps import *
from step_defs.pi_product_details_for_project_steps import *

scenarios("../feature/pi_product_details_for_project.feature")
