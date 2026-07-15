from pytest_bdd import scenarios

from step_defs.common_steps import *
from step_defs.admin_login_to_research_gateway_steps import *

scenarios("../feature/admin_login_to_research_gateway.feature")
