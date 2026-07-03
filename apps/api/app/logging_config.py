from __future__ import annotations

import logging
import os
import sys


LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 这些第三方库默认 DEBUG/INFO 太吵，统一压到 WARNING；
# uvicorn.access 维持 INFO 以保留访问日志。
NOISY_LOGGER_LEVELS = {
    "httpx": logging.WARNING,
    "httpcore": logging.WARNING,
}

_HANDLER_MARKER = "_mock_interview_logging"


def _resolve_level() -> int:
    configured = os.getenv("MOCK_INTERVIEW_LOG_LEVEL", "INFO").strip().upper()
    return getattr(logging, configured, logging.INFO)


def configure_logging() -> None:
    """配置应用日志：输出到 stderr、含模块名、级别可由环境变量调节。

    幂等：重复调用（如 reload 或多次导入）不会叠加 handler。
    """
    root = logging.getLogger()

    if not any(getattr(handler, _HANDLER_MARKER, False) for handler in root.handlers):
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
        setattr(handler, _HANDLER_MARKER, True)
        root.addHandler(handler)

    root.setLevel(_resolve_level())
    for logger_name, level in NOISY_LOGGER_LEVELS.items():
        logging.getLogger(logger_name).setLevel(level)
