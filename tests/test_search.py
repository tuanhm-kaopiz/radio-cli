from __future__ import annotations

import pytest

from radio_cli import search


def test_search_vpop_quiet_raises_without_console(monkeypatch):
    monkeypatch.setattr(search, "_ytdlp_argv", lambda quiet=False: (_ for _ in ()).throw(search.YtdlpError("missing")))

    with pytest.raises(search.SearchError, match="missing"):
        search.search_vpop("demo", limit=3, quiet=True)


def test_search_vpop_rejects_invalid_limit():
    with pytest.raises(ValueError, match="between 1 and 50"):
        search.search_vpop("demo", limit=0, quiet=True)
