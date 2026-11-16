from pathlib import Path

HTML = (Path(__file__).resolve().parents[2] / "index.html").read_text(encoding="utf-8")


def test_login_uses_api_and_jwt_session():
    assert 'sskattApi("/auth/login"' in HTML
    assert 'sessionStorage.setItem("sskatt_access_token"' in HTML
    assert 'sskattApi("/auth/me"' in HTML


def test_employee_leave_support_attendance_and_provisioning_use_api():
    assert '/resources/leaveRequests' in HTML
    assert '/resources/supportQueries' in HTML
    assert '/attendance/punch' in HTML
    assert '/employees' in HTML
    assert 'type="password" minlength="12"' in HTML


def test_tasks_shifts_messages_and_workload_use_api():
    for route in ('/resources/tasks', '/resources/shifts', '/resources/messages',
                  '/resources/workloadRequests', '/resources/resignations'):
        assert route in HTML
    assert 'Transferred to Super Admin' in HTML


def test_leave_decisions_and_payslips_use_api():
    assert '/leave-requests/' in HTML
    assert 'resources/payslips' in HTML
    assert 'function issuePayslip' in HTML


def test_no_browser_local_storage_or_plaintext_password_display():
    assert 'localStorage.' not in HTML
    assert "e.password || 'password123'" not in HTML
    assert 'Pass: ${pass}' not in HTML


def test_admin_chat_persists_to_api():
    assert 'persistEmployeeMessage' in HTML
    assert '/resources/messages' in HTML
