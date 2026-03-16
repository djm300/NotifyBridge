from notifybridge import cli


def test_cli_dispatches_dev(monkeypatch):
    called = {"value": False}

    def fake_dev():
        called["value"] = True
        return 0

    monkeypatch.setattr(cli, "dev_command", fake_dev)
    result = cli.main(["dev"])
    assert result == 0
    assert called["value"] is True
