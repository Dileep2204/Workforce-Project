from pathlib import Path

HTML = (Path(__file__).resolve().parents[2] / "index.html").read_text(encoding="utf-8")


def test_login_uses_api_and_jwt_session():
    assert 'sskattApi("/auth/login"' in HTML
    assert 'sessionStorage.setItem("sskatt_access_token"' in HTML
    assert 'sskattApi("/auth/me"' in HTML


def test_employee_leave_and_support_submissions_use_api():
    assert '/resources/leaveRequests' in HTML
    assert '/resources/supportQueries' in HTML


def test_ticket_resolution_and_escalation_use_api():
    assert 'method: "PATCH", body: JSON.stringify({ payload: updated })' in HTML
    assert 'Transferred to Super Admin' in HTML
