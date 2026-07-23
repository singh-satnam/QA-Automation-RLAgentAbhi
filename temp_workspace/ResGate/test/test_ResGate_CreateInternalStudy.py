from pytest_bdd import scenario

from step_defs.common_steps import *
from step_defs.admin_users_filter_search_steps import *
from step_defs.researcher_login_steps import *
from step_defs.pi_login_steps import *
from step_defs.create_internal_study_steps import *


@scenario('../feature/create_internal_study.feature', 'PI creates an internal study')
def test_pi_creates_internal_study():
    pass
