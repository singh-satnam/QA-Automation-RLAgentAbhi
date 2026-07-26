from pytest_bdd import scenarios

from step_defs.common_steps import *
from step_defs.admin_users_filter_search_steps import *
from step_defs.admin_add_search_delete_user_steps import *

scenarios("../feature/admin_add_search_delete_user.feature")
