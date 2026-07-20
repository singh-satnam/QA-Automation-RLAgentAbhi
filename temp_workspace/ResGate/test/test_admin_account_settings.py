from pytest_bdd import scenarios

from step_defs.common_steps import *
from step_defs.researcher_login_steps import *
from step_defs.admin_login_steps import *
from step_defs.admin_account_settings_steps import *

scenarios("../feature/admin_account_settings.feature")
