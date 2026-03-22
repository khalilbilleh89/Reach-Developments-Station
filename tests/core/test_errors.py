"""
tests.core.test_errors

Validates the global error handling framework:
  - exception class hierarchy and serialisation
  - HTTP status code mapping
  - API response structure produced by the global handler
  - detail propagation
  - error codes constants
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.constants.error_codes import (
    CONFLICT,
    INTERNAL_ERROR,
    PERMISSION_DENIED,
    RESOURCE_NOT_FOUND,
    VALIDATION_ERROR,
)
from app.core.error_handlers import _error_body, _status_for, register_error_handlers
from app.core.errors import (
    AppError,
    ConflictError,
    PermissionDeniedError,
    ResourceNotFoundError,
    ValidationError,
)


# ---------------------------------------------------------------------------
# Error code constants
# ---------------------------------------------------------------------------


class TestErrorCodes:
    def test_resource_not_found_code(self):
        assert RESOURCE_NOT_FOUND == "RESOURCE_NOT_FOUND"

    def test_validation_error_code(self):
        assert VALIDATION_ERROR == "VALIDATION_ERROR"

    def test_permission_denied_code(self):
        assert PERMISSION_DENIED == "PERMISSION_DENIED"

    def test_conflict_code(self):
        assert CONFLICT == "CONFLICT"

    def test_internal_error_code(self):
        assert INTERNAL_ERROR == "INTERNAL_ERROR"


# ---------------------------------------------------------------------------
# Exception class hierarchy
# ---------------------------------------------------------------------------


class TestExceptionHierarchy:
    def test_app_error_is_exception(self):
        assert issubclass(AppError, Exception)

    def test_resource_not_found_inherits_app_error(self):
        assert issubclass(ResourceNotFoundError, AppError)

    def test_validation_error_inherits_app_error(self):
        assert issubclass(ValidationError, AppError)

    def test_permission_denied_inherits_app_error(self):
        assert issubclass(PermissionDeniedError, AppError)

    def test_conflict_error_inherits_app_error(self):
        assert issubclass(ConflictError, AppError)


# ---------------------------------------------------------------------------
# Exception instantiation and attribute access
# ---------------------------------------------------------------------------


class TestAppError:
    def test_default_message(self):
        err = AppError()
        assert err.message == "An unexpected application error occurred."

    def test_custom_message(self):
        err = AppError("something broke")
        assert err.message == "something broke"
        assert str(err) == "something broke"

    def test_default_details_none(self):
        err = AppError()
        assert err.details is None

    def test_custom_details(self):
        err = AppError("err", details={"key": "value"})
        assert err.details == {"key": "value"}

    def test_code_attribute(self):
        assert AppError.code == INTERNAL_ERROR


class TestResourceNotFoundError:
    def test_default_code(self):
        assert ResourceNotFoundError.code == RESOURCE_NOT_FOUND

    def test_custom_message_and_details(self):
        err = ResourceNotFoundError(
            "Scenario 'abc' not found.",
            details={"scenario_id": "abc"},
        )
        assert err.message == "Scenario 'abc' not found."
        assert err.details == {"scenario_id": "abc"}

    def test_is_catchable_as_app_error(self):
        with pytest.raises(AppError):
            raise ResourceNotFoundError("not found")


class TestValidationError:
    def test_default_code(self):
        assert ValidationError.code == VALIDATION_ERROR

    def test_custom_message(self):
        err = ValidationError("source_type must be one of: ['feasibility'].")
        assert "source_type" in err.message


class TestPermissionDeniedError:
    def test_default_code(self):
        assert PermissionDeniedError.code == PERMISSION_DENIED

    def test_default_message(self):
        err = PermissionDeniedError()
        assert err.message == "Permission denied."


class TestConflictError:
    def test_default_code(self):
        assert ConflictError.code == CONFLICT

    def test_custom_message_and_details(self):
        err = ConflictError(
            "Parcel 'P-001' already exists.",
            details={"parcel_code": "P-001"},
        )
        assert err.message == "Parcel 'P-001' already exists."
        assert err.details["parcel_code"] == "P-001"


# ---------------------------------------------------------------------------
# HTTP status mapping
# ---------------------------------------------------------------------------


class TestStatusMapping:
    def test_resource_not_found_maps_to_404(self):
        assert _status_for(ResourceNotFoundError()) == 404

    def test_validation_error_maps_to_422(self):
        assert _status_for(ValidationError()) == 422

    def test_permission_denied_maps_to_403(self):
        assert _status_for(PermissionDeniedError()) == 403

    def test_conflict_maps_to_409(self):
        assert _status_for(ConflictError()) == 409

    def test_generic_app_error_maps_to_500(self):
        assert _status_for(AppError()) == 500

    def test_subclass_inherits_parent_mapping(self):
        """A subclass not in the map inherits its parent's HTTP status."""

        class CustomNotFound(ResourceNotFoundError):
            code = "CUSTOM_NOT_FOUND"

        assert _status_for(CustomNotFound()) == 404


# ---------------------------------------------------------------------------
# Error body serialisation
# ---------------------------------------------------------------------------


class TestErrorBody:
    def test_body_structure(self):
        err = ResourceNotFoundError("Run not found.", details={"run_id": "x"})
        body = _error_body(err)
        assert set(body.keys()) == {"code", "message", "details"}

    def test_body_code(self):
        body = _error_body(ResourceNotFoundError())
        assert body["code"] == RESOURCE_NOT_FOUND

    def test_body_message(self):
        body = _error_body(ResourceNotFoundError("Custom message."))
        assert body["message"] == "Custom message."

    def test_body_details_present(self):
        body = _error_body(ConflictError("conflict", details={"parcel_code": "P-1"}))
        assert body["details"] == {"parcel_code": "P-1"}

    def test_body_details_none_when_absent(self):
        body = _error_body(AppError())
        assert body["details"] is None


# ---------------------------------------------------------------------------
# FastAPI integration — end-to-end response shape
# ---------------------------------------------------------------------------


def _build_test_app() -> FastAPI:
    """Create a minimal FastAPI app with the error handlers registered."""
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/not-found")
    def raise_not_found():
        raise ResourceNotFoundError("Thing not found.", details={"thing_id": "42"})

    @app.get("/validation")
    def raise_validation():
        raise ValidationError("Invalid input.", details={"field": "name"})

    @app.get("/permission")
    def raise_permission():
        raise PermissionDeniedError()

    @app.get("/conflict")
    def raise_conflict():
        raise ConflictError("Already exists.", details={"code": "X-1"})

    @app.get("/internal")
    def raise_internal():
        raise AppError()

    return app


@pytest.fixture(scope="module")
def error_client():
    return TestClient(_build_test_app())


class TestFastAPIIntegration:
    def test_resource_not_found_status(self, error_client):
        resp = error_client.get("/not-found")
        assert resp.status_code == 404

    def test_resource_not_found_body(self, error_client):
        resp = error_client.get("/not-found")
        body = resp.json()
        assert body["code"] == RESOURCE_NOT_FOUND
        assert body["message"] == "Thing not found."
        assert body["details"] == {"thing_id": "42"}

    def test_validation_error_status(self, error_client):
        resp = error_client.get("/validation")
        assert resp.status_code == 422

    def test_validation_error_body(self, error_client):
        resp = error_client.get("/validation")
        body = resp.json()
        assert body["code"] == VALIDATION_ERROR
        assert "Invalid input" in body["message"]
        assert body["details"] == {"field": "name"}

    def test_permission_denied_status(self, error_client):
        resp = error_client.get("/permission")
        assert resp.status_code == 403

    def test_permission_denied_body(self, error_client):
        body = error_client.get("/permission").json()
        assert body["code"] == PERMISSION_DENIED

    def test_conflict_status(self, error_client):
        resp = error_client.get("/conflict")
        assert resp.status_code == 409

    def test_conflict_body(self, error_client):
        body = error_client.get("/conflict").json()
        assert body["code"] == CONFLICT
        assert "Already exists" in body["message"]
        assert body["details"]["code"] == "X-1"

    def test_internal_error_status(self, error_client):
        resp = error_client.get("/internal")
        assert resp.status_code == 500

    def test_internal_error_body(self, error_client):
        body = error_client.get("/internal").json()
        assert body["code"] == INTERNAL_ERROR

    def test_response_always_has_three_keys(self, error_client):
        """All error responses must contain exactly code, message, details."""
        for path in ["/not-found", "/validation", "/permission", "/conflict", "/internal"]:
            body = error_client.get(path).json()
            assert set(body.keys()) == {"code", "message", "details"}, f"Failed for {path}"
