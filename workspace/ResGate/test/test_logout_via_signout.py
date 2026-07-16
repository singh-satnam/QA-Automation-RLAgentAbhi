from pytest_bdd import scenarios

from step_defs.common_steps import *
from step_defs.logout_via_signout_steps import *

scenarios("../feature/logout_via_signout.feature")
