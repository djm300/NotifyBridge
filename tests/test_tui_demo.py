from notifybridge.config import load_settings
from notifybridge.tui import demo


def test_generate_demo_keys_count_and_prefix():
    keys = demo.generate_demo_keys(5)
    assert len(keys) == 5
    assert all(len(key) == 20 for key in keys)
    assert all(key.isalnum() for key in keys)
    assert len(set(keys)) == 5


async def test_seed_random_demo_uses_all_channels(monkeypatch):
    calls = []
    settings = load_settings()

    monkeypatch.setattr(demo, "generate_demo_keys", lambda count=5: [f"A{i:019d}"[:20] for i in range(count)])
    monkeypatch.setattr(demo, "post_key", lambda settings: calls.append(("key",)) or f"K{len(calls):019d}"[:20])
    monkeypatch.setattr(demo, "send_webhook", lambda settings, api_key, index: calls.append(("webhook", api_key, index)))
    monkeypatch.setattr(demo, "send_email", lambda settings, api_key, index: calls.append(("email", api_key, index)))
    monkeypatch.setattr(demo, "send_syslog", lambda settings, api_key, index: calls.append(("syslog", api_key, index)))

    keys = await demo.seed_random_demo(settings, 5)

    assert len(keys) == 5
    assert all(len(key) == 20 for key in keys)
    assert len([call for call in calls if call[0] == "key"]) == 5
    assert len([call for call in calls if call[0] == "webhook"]) == 5
    assert len([call for call in calls if call[0] == "email"]) == 5
    assert len([call for call in calls if call[0] == "syslog"]) == 5
