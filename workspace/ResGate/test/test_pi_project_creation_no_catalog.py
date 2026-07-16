from pytest_bdd import scenarios

from step_defs.common_steps import *
from step_defs.pi_project_creation_no_catalog_steps import *

scenarios("../feature/pi_project_creation_no_catalog.feature")
