from pytest_bdd import scenarios

from step_defs.common_steps import *
from step_defs.researcher_login_steps import *

scenarios("../feature/researcher_login.feature")
