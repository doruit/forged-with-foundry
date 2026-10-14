import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "AUT-002_irreversible_action_attempted/infra"))
spec = importlib.util.spec_from_file_location("mandate_oidc_setup", Path(__file__).resolve().parents[1] / "infra/setup_oidc.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def test_legacy_default_subject():
    assert setup.environment_subject("contoso/synthetic-agent", {"use_default": True}) == "repo:contoso/synthetic-agent:environment:autonomy-mandate-demo"


def test_immutable_default_subject_uses_reported_prefix():
    configuration = {"use_default": True, "use_immutable_subject": True,
                     "sub_claim_prefix": "repo:contoso@123456/synthetic-agent@654321"}
    assert setup.environment_subject("contoso/synthetic-agent", configuration) == "repo:contoso@123456/synthetic-agent@654321:environment:autonomy-mandate-demo"


@pytest.mark.parametrize("configuration", [
    {"use_default": False}, {"use_default": True, "use_immutable_subject": True},
    {"use_default": True, "use_immutable_subject": True, "sub_claim_prefix": "repo:contoso/synthetic-agent"},
])
def test_unknown_subject_shape_fails_closed(configuration):
    with pytest.raises(ValueError):
        setup.environment_subject("contoso/synthetic-agent", configuration)