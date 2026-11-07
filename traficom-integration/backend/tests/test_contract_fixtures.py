"""Shared fixtures are the contract's exit test: the UI type-checks the same valid set."""

import inspect
import json
from pathlib import Path

import pytest
from conftest import FIXTURES_DIR
from pydantic import BaseModel, ValidationError

from astrasync_api.contract import models
from astrasync_api.contract.models import ContractModel, Envelope


def _fixtures(kind: str) -> list[Path]:
    return sorted((FIXTURES_DIR / kind).glob("*.json"))


def _model_for(path: Path) -> type[BaseModel]:
    return getattr(models, path.name.split(".")[0])


@pytest.mark.parametrize("path", _fixtures("valid"), ids=lambda path: path.stem)
def test_valid_fixture_is_accepted_and_round_trips(path: Path) -> None:
    payload = json.loads(path.read_text("utf-8"))
    parsed = _model_for(path).model_validate(payload)
    assert parsed.model_dump(mode="json", exclude_unset=True).keys() == payload.keys()


@pytest.mark.parametrize("path", _fixtures("invalid"), ids=lambda path: path.stem)
def test_invalid_fixture_is_rejected(path: Path) -> None:
    payload = json.loads(path.read_text("utf-8"))
    with pytest.raises(ValidationError) as rejected:
        _model_for(path).model_validate(payload)
    # Exactly one defect, so a fixture cannot pass by being wrong in some unrelated way.
    assert rejected.value.error_count() == 1


def test_fixture_sets_are_not_empty() -> None:
    assert _fixtures("valid")
    assert _fixtures("invalid")


@pytest.mark.parametrize("path", _fixtures("valid"), ids=lambda path: path.stem)
def test_valid_fixtures_are_visibly_synthetic(path: Path) -> None:
    text = path.read_text("utf-8")
    payload = json.loads(text)
    if "is_synthetic" in _model_for(path).model_fields:
        assert payload["is_synthetic"] is True
    assert "/ITU" not in text


def test_response_models_have_no_implicit_defaults() -> None:
    """Every response field is always present, so null can never be confused with absent."""
    offenders = [
        f"{model.__name__}.{field}"
        for _, model in inspect.getmembers(models, inspect.isclass)
        if issubclass(model, ContractModel)
        and not model.__name__.endswith(("Request", "Update", "Upsert"))
        and model is not ContractModel
        for field, info in model.model_fields.items()
        if not info.is_required()
    ]
    assert offenders == []


def test_envelope_is_on_every_top_level_list() -> None:
    assert issubclass(models.CaseList, Envelope)
    fields = models.CaseList.model_fields.keys()
    assert {"items", "limit", "next_cursor", "total_if_known"} <= fields
