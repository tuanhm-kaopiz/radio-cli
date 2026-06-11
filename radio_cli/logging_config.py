from __future__ import annotations

import logging
import os


def setup_logging(*, verbose: bool = False) -> None:
    enabled = verbose or os.environ.get("RADIO_CLI_DEBUG") in {"1", "true", "TRUE", "yes", "YES"}
    if not enabled:
        logging.getLogger("radio_cli").addHandler(logging.NullHandler())
        return

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
