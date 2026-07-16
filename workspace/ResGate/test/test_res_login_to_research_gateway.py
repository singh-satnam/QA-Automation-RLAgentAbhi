from pytest_bdd import scenarios

from step_defs.common_steps import *
from step_defs.pi_login_to_research_gateway_steps import *
from step_defs.res_login_to_research_gateway_steps import *

scenarios("../feature/res_login_to_research_gateway.feature")
