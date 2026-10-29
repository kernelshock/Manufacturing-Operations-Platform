from pydantic import ValidationError
import pytest

from mop.core.schemas import OrganizationCreate, ResourceCreate


def test_business_codes_are_normalized() -> None:
    payload = OrganizationCreate(code=" faic ", name="FAIC S.A.")

    assert payload.code == "FAIC"


def test_blank_business_code_is_rejected() -> None:
    with pytest.raises(ValidationError):
        OrganizationCreate(code="   ", name="Invalid")


def test_resource_type_defaults_to_generic() -> None:
    from uuid import uuid4

    payload = ResourceCreate(
        code="R1",
        name="Robot 1",
        work_center_id=uuid4(),
    )

    assert payload.resource_type == "generic"
