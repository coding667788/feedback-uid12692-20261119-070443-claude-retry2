"""UTC 整日秒数运算。

全部时间以自 Unix 纪元起的 UTC 整数秒表示；所有比较与窗口运算先向下
对齐到 UTC 整日（86400 秒），再做整数除法。本模块不依赖任何本地时区。
"""

from __future__ import annotations

from datetime import datetime, timezone

from .errors import E_TIMESTAMP, PlannerError

DAY_SECONDS = 86_400


def parse_timestamp(value: object, *, field: str = "timestamp") -> int:
    """解析 ISO-8601 时间字符串为 UTC 整数秒。

    要求：显式带时区（Z 或偏移量）、秒为整数（拒绝小数秒）。
    纳秒级字符串也会被拒绝，避免静默截断。
    """
    if not isinstance(value, str) or not value:
        raise PlannerError(E_TIMESTAMP, f"{field} 必须是非空 ISO-8601 字符串")
    text = value.strip()
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PlannerError(E_TIMESTAMP, f"{field} 无法解析: {value!r}") from exc
    if dt.tzinfo is None:
        raise PlannerError(E_TIMESTAMP, f"{field} 必须显式带时区: {value!r}")
    if dt.microsecond != 0:
        raise PlannerError(E_TIMESTAMP, f"{field} 不允许小数秒: {value!r}")
    return int(dt.astimezone(timezone.utc).timestamp())


def day_floor(ts: int) -> int:
    """向下对齐到 UTC 整日起点。"""
    return ts - (ts % DAY_SECONDS)


def day_index(ts: int, anchor_day: int) -> int:
    """ts 所在 UTC 日相对锚定日（已对齐整日）的日序号，可为负。"""
    return (day_floor(ts) - anchor_day) // DAY_SECONDS


def to_iso(ts: int) -> str:
    """UTC 整数秒转回 ...Z 形式，仅用于输出。"""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
