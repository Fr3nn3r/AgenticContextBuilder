"""Unit tests for compliance endpoint role-based access control.

Tests that compliance endpoints properly enforce admin/auditor role requirements.
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


@pytest.fixture
def test_app(tmp_path: Path):
    """Create a test FastAPI app with isolated auth services."""
    from context_builder.api.services.users import UsersService
    from context_builder.api.services.auth import AuthService

    # Create test services with temp directory
    users_service = UsersService(tmp_path)
    auth_service = AuthService(tmp_path, users_service)

    # Patch in both dependencies (for get_current_user) and main (for endpoints)
    with patch("context_builder.api.dependencies.get_users_service", return_value=users_service), \
         patch("context_builder.api.dependencies.get_auth_service", return_value=auth_service), \
         patch("context_builder.api.main.get_users_service", return_value=users_service), \
         patch("context_builder.api.main.get_auth_service", return_value=auth_service):
        from context_builder.api.main import app
        yield TestClient(app), users_service, auth_service


def get_token(client, username: str, password: str) -> str:
    """Helper to login and get token."""
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    return response.json()["token"]


class TestRequireRoleFunction:
    """Tests for the require_role dependency factory."""

    def test_require_role_returns_callable(self):
        """require_role returns a callable dependency."""
        from context_builder.api.main import require_role

        checker = require_role(["admin"])
        assert callable(checker)

    def test_require_role_with_multiple_roles(self):
        """require_role accepts multiple roles."""
        from context_builder.api.main import require_role

        checker = require_role(["admin", "auditor", "reviewer"])
        assert callable(checker)


class TestComplianceEndpointAccessControl:
    """Tests for compliance endpoint role-based access."""

    # Compliance endpoints that require admin/auditor role
    COMPLIANCE_ENDPOINTS = [
        ("/api/compliance/ledger/verify", "GET"),
        ("/api/compliance/ledger/decisions", "GET"),
        ("/api/compliance/version-bundles", "GET"),
        ("/api/compliance/config-history", "GET"),
    ]

    def test_admin_can_access_compliance_endpoints(self, test_app):
        """Admin role can access all compliance endpoints."""
        client, users_service, auth_service = test_app

        # Login as admin (su user)
        token = get_token(client, "su", "su")
        headers = {"Authorization": f"Bearer {token}"}

        for endpoint, method in self.COMPLIANCE_ENDPOINTS:
            if method == "GET":
                response = client.get(endpoint, headers=headers)
            else:
                response = client.post(endpoint, headers=headers)

            # Should not get 403 Forbidden
            assert response.status_code != 403, f"Admin should access {endpoint}"

    def test_auditor_can_access_compliance_endpoints(self, test_app):
        """Auditor role can access all compliance endpoints."""
        client, users_service, auth_service = test_app

        # Create auditor user (default password is "su" for tod user)
        # Use the default auditor user "tod"
        token = get_token(client, "tod", "su")
        headers = {"Authorization": f"Bearer {token}"}

        for endpoint, method in self.COMPLIANCE_ENDPOINTS:
            if method == "GET":
                response = client.get(endpoint, headers=headers)
            else:
                response = client.post(endpoint, headers=headers)

            # Should not get 403 Forbidden
            assert response.status_code != 403, f"Auditor should access {endpoint}"

    def test_reviewer_cannot_access_compliance_endpoints(self, test_app):
        """Reviewer role is denied access to compliance endpoints."""
        client, users_service, auth_service = test_app

        # Use the default reviewer user "ted"
        token = get_token(client, "ted", "su")
        headers = {"Authorization": f"Bearer {token}"}

        for endpoint, method in self.COMPLIANCE_ENDPOINTS:
            if method == "GET":
                response = client.get(endpoint, headers=headers)
            else:
                response = client.post(endpoint, headers=headers)

            assert response.status_code == 403, f"Reviewer should not access {endpoint}"

    def test_operator_cannot_access_compliance_endpoints(self, test_app):
        """Operator role is denied access to compliance endpoints."""
        client, users_service, auth_service = test_app

        # Use the default operator user "seb"
        token = get_token(client, "seb", "su")
        headers = {"Authorization": f"Bearer {token}"}

        for endpoint, method in self.COMPLIANCE_ENDPOINTS:
            if method == "GET":
                response = client.get(endpoint, headers=headers)
            else:
                response = client.post(endpoint, headers=headers)

            assert response.status_code == 403, f"Operator should not access {endpoint}"

    def test_unauthenticated_cannot_access_compliance_endpoints(self, test_app):
        """Unauthenticated requests are denied."""
        client, users_service, auth_service = test_app

        for endpoint, method in self.COMPLIANCE_ENDPOINTS:
            if method == "GET":
                response = client.get(endpoint)
            else:
                response = client.post(endpoint)

            assert response.status_code == 401, f"Unauthenticated should get 401 for {endpoint}"


class TestComplianceLedgerVerifyEndpoint:
    """Tests for /api/compliance/ledger/verify endpoint access."""

    def test_verify_returns_integrity_report(self, test_app):
        """Verify endpoint returns integrity report structure."""
        client, users_service, auth_service = test_app

        token = get_token(client, "su", "su")
        response = client.get(
            "/api/compliance/ledger/verify",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "valid" in data
        assert "total_records" in data


class TestComplianceLedgerDecisionsEndpoint:
    """Tests for /api/compliance/ledger/decisions endpoint access."""

    def test_decisions_returns_list(self, test_app):
        """Decisions endpoint returns a list."""
        client, users_service, auth_service = test_app

        token = get_token(client, "su", "su")
        response = client.get(
            "/api/compliance/ledger/decisions",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_decisions_accepts_filters(self, test_app):
        """Decisions endpoint accepts filter parameters."""
        client, users_service, auth_service = test_app

        token = get_token(client, "su", "su")

        # Test with type filter
        response = client.get(
            "/api/compliance/ledger/decisions?decision_type=classification",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        # Test with claim_id filter
        response = client.get(
            "/api/compliance/ledger/decisions?claim_id=CLM-001",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        # Test with limit
        response = client.get(
            "/api/compliance/ledger/decisions?limit=10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200


class TestComplianceVersionBundlesEndpoint:
    """Tests for /api/compliance/version-bundles endpoint access."""

    def test_version_bundles_returns_list(self, test_app):
        """Version bundles endpoint returns a list."""
        client, users_service, auth_service = test_app

        token = get_token(client, "su", "su")
        response = client.get(
            "/api/compliance/version-bundles",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestComplianceConfigHistoryEndpoint:
    """Tests for /api/compliance/config-history endpoint access."""

    def test_config_history_returns_list(self, test_app):
        """Config history endpoint returns a list."""
        client, users_service, auth_service = test_app

        token = get_token(client, "su", "su")
        response = client.get(
            "/api/compliance/config-history",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_config_history_accepts_limit(self, test_app):
        """Config history endpoint accepts limit parameter."""
        client, users_service, auth_service = test_app

        token = get_token(client, "su", "su")
        response = client.get(
            "/api/compliance/config-history?limit=50",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200


class TestComplianceTruthHistoryEndpoint:
    """Tests for /api/compliance/truth-history/{file_md5} endpoint access."""

    def test_truth_history_requires_auth(self, test_app):
        """Truth history endpoint requires authentication."""
        client, users_service, auth_service = test_app

        response = client.get("/api/compliance/truth-history/abc123")
        assert response.status_code == 401

    def test_truth_history_requires_admin_or_auditor(self, test_app):
        """Truth history endpoint requires admin or auditor role."""
        client, users_service, auth_service = test_app

        # Reviewer should be denied
        token = get_token(client, "ted", "su")
        response = client.get(
            "/api/compliance/truth-history/abc123",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

        # Admin should be allowed
        token = get_token(client, "su", "su")
        response = client.get(
            "/api/compliance/truth-history/abc123",
            headers={"Authorization": f"Bearer {token}"},
        )
        # May return 200 with empty or data, but not 403
        assert response.status_code != 403


class TestComplianceLabelHistoryEndpoint:
    """Tests for /api/compliance/label-history/{doc_id} endpoint access."""

    def test_label_history_requires_auth(self, test_app):
        """Label history endpoint requires authentication."""
        client, users_service, auth_service = test_app

        response = client.get("/api/compliance/label-history/DOC-001")
        assert response.status_code == 401

    def test_label_history_requires_admin_or_auditor(self, test_app):
        """Label history endpoint requires admin or auditor role."""
        client, users_service, auth_service = test_app

        # Operator should be denied
        token = get_token(client, "seb", "su")
        response = client.get(
            "/api/compliance/label-history/DOC-001",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

        # Auditor should be allowed
        token = get_token(client, "tod", "su")
        response = client.get(
            "/api/compliance/label-history/DOC-001",
            headers={"Authorization": f"Bearer {token}"},
        )
        # May return various status codes, but not 403
        assert response.status_code != 403


class TestAccessDeniedResponse:
    """Tests for access denied response format."""

    def test_access_denied_returns_403(self, test_app):
        """Access denied returns 403 status code."""
        client, users_service, auth_service = test_app

        token = get_token(client, "ted", "su")  # reviewer
        response = client.get(
            "/api/compliance/ledger/verify",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403

    def test_access_denied_has_detail_message(self, test_app):
        """Access denied response includes detail message."""
        client, users_service, auth_service = test_app

        token = get_token(client, "ted", "su")  # reviewer
        response = client.get(
            "/api/compliance/ledger/verify",
            headers={"Authorization": f"Bearer {token}"},
        )

        data = response.json()
        assert "detail" in data
        assert "Access denied" in data["detail"] or "Required role" in data["detail"]
