* A local platform to support debugging/testing notifications
* I'd like to build a notifier platform supporting webhooks, emails (unauth SMTP) & syslog - find a catchy name for it
* Authentication should happen via webhook URL path, via email subject (prefix it with auth key) and via SYSLOG (use CEF standard format, find out if we can use CEF and insert an auth key somewhere). All input not matching a key should be silently discarded asap
* Web UI with backend in python. All 3 methods of input should lead to the same notifications in the same window. Dofferent tabs for differnet API keys.