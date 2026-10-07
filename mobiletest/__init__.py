"""Helpers the generated tests call: finding elements with fallbacks, actions,
checks, screenshots, and the BrowserStack session behind behave's hooks.

Plain Python on top of the Appium Python client. Nothing here depends on EFP;
the generated tests and this package run wherever Python, behave, and a
BrowserStack account are.
"""
from mobiletest.actions import (
    accept_permission,
    activate_app,
    back,
    clear,
    close_app,
    deny_permission,
    double_tap,
    hide_keyboard,
    launch_app,
    long_press,
    open_deep_link,
    press_enter,
    press_keycode,
    reset_app,
    scroll_to,
    scroll_to_end,
    swipe,
    tap,
    tap_point,
    terminate_app,
    type_text,
)
from mobiletest.checks import (
    assert_count,
    assert_enabled,
    assert_not_visible,
    assert_selected,
    assert_text,
    assert_visible,
    visible,
    wait_enabled,
    wait_gone,
    wait_stable,
    wait_text,
    wait_visible,
)
from mobiletest.elements import ElementNotFound, by_name, by_role, by_text, find, optional
from mobiletest.evidence import screenshot
from mobiletest.secrets import MissingSecret, profile, secret, user_value

__all__ = [
    "ElementNotFound", "MissingSecret",
    "accept_permission", "activate_app", "assert_count", "assert_enabled", "assert_not_visible", "assert_selected",
    "assert_text", "assert_visible", "back", "by_name", "by_role", "by_text", "clear", "close_app", "deny_permission",
    "double_tap", "find", "hide_keyboard", "launch_app", "long_press", "open_deep_link", "optional", "press_enter",
    "press_keycode", "reset_app", "screenshot", "scroll_to", "scroll_to_end", "secret", "profile", "user_value", "swipe", "tap", "tap_point", "terminate_app",
    "type_text", "visible", "wait_enabled", "wait_gone", "wait_stable", "wait_text", "wait_visible",
]
