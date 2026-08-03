from pytest_bdd import scenarios

from step_defs.common_steps import *
from step_defs.admin_users_filter_search_steps import *
from step_defs.researcher_login_steps import *
from step_defs.admin_user_catalog_steps import *
from step_defs.pi_catalog_e2e_steps import *

scenarios("../feature/pi_catalog_e2e.feature")
