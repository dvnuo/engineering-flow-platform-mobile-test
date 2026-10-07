"""The session link in the evidence opens on BrowserStack's current dashboard."""
from mobiletest.session import dashboard_url


def test_retired_links_move_to_the_current_dashboard():
    current = "https://app-automate.browserstack.com/dashboard/v2/builds/b1/sessions/s1"
    assert dashboard_url("https://app-automate.browserstack.com/builds/b1/sessions/s1") == current
    assert dashboard_url("https://app-automate.browserstack.com/builds/b1/sessions/s1?auth_token=t0k") == current
    assert dashboard_url(current) == current
    assert dashboard_url("https://dashboard.example/s1") == "https://dashboard.example/s1"
    assert dashboard_url("", "s1") == "https://app-automate.browserstack.com/dashboard/v2/sessions/s1"
    assert dashboard_url("", "") == ""
