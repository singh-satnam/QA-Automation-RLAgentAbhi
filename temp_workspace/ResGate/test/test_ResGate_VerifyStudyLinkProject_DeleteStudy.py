from pytest_bdd import scenario

from step_defs.common_steps import *
from step_defs.admin_users_filter_search_steps import *
from step_defs.pi_login_steps import *
from step_defs.researcher_login_steps import *
from step_defs.create_internal_study_steps import *
from step_defs.study_details_and_delete_steps import *


@scenario(
    '../feature/study_details_and_delete.feature',
    'PI verifies study details and assigned project then deletes the study',
)
def test_pi_verifies_study_details_and_deletes():
    pass
