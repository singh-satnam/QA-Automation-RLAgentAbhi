from pytest_bdd import scenarios

from step_defs.common_steps import *
from step_defs.researcher_login_steps import *
from step_defs.pi_login_steps import *
from step_defs.create_delete_key_pair_steps import *

scenarios("../feature/create_delete_key_pair.feature")
