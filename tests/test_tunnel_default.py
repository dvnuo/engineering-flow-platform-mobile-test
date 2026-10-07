"""Every session goes through the BrowserStack Local tunnel unless its
config says network: public, and the tunnel is the one named by
BROWSERSTACK_LOCAL_IDENTIFIER (the pipeline's run label)."""
from mobiletest import session


def bstack(monkeypatch, config, identifier="build-7"):
    monkeypatch.setenv("BROWSERSTACK_USERNAME", "user")
    monkeypatch.setenv("BROWSERSTACK_ACCESS_KEY", "not-a-real-key")
    if identifier is None:
        monkeypatch.delenv("BROWSERSTACK_LOCAL_IDENTIFIER", raising=False)
    else:
        monkeypatch.setenv("BROWSERSTACK_LOCAL_IDENTIFIER", identifier)
    options = session.capabilities(dict({"platform": "android"}, **config), "row 1", build_name="build-7")
    return options.to_capabilities()["bstack:options"]


def test_the_tunnel_is_the_default_and_public_opts_out(monkeypatch):
    assert session.uses_tunnel({"app": "bs://x"}) and not session.uses_tunnel({"app": "bs://x", "network": "public"})
    default = bstack(monkeypatch, {"app": "bs://x"})
    assert default["local"] is True and default["localIdentifier"] == "build-7"
    assert bstack(monkeypatch, {"app": "bs://x", "network": "private-managed"})["localIdentifier"] == "build-7"
    assert bstack(monkeypatch, {"app": "bs://x", "network": "private-external"})["local"] is True
    public = bstack(monkeypatch, {"app": "bs://x", "network": "public"})
    assert "local" not in public and "localIdentifier" not in public


def test_an_unnamed_tunnel_is_still_asked_for(monkeypatch, capsys):
    unnamed = bstack(monkeypatch, {"app": "bs://x", "issue": "FX-12"}, identifier=None)
    assert unnamed["local"] is True and "localIdentifier" not in unnamed
    assert "BROWSERSTACK_LOCAL_IDENTIFIER is not set" in capsys.readouterr().out
