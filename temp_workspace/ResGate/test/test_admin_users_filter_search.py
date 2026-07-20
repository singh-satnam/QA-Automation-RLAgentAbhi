from pytest_bdd import scenarios

from step_defs.common_steps import *
from step_defs.admin_users_filter_search_steps import *

scenarios("../feature/admin_users_filter_search.feature")
