"""输入数据模型与结构校验。

只负责形状与引用关系校验；双时间版本选择、保全生效判定等时间逻辑
位于 bitemporal 模块。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import E_HOLD_RELEASE_UNKNOWN, E_HORIZON, E_MALFORMED, E_TOO_MANY_OBJECTS, PlannerError
from .timeutil import parse_timestamp

MAX_OBJECTS = 16
MAX_HORIZON_DAYS = 7
MAX_CAPACITY = 16


@dataclass(frozen=True)
class RuleVersion:
    rule_id: str
    jurisdiction: str
    valid_from: int          # UTC 整数秒
    ingest_seq: int
    min_retention_days: int
    max_lifetime_days: int


@dataclass(frozen=True)
class RecordFact:
    record_id: str
    jurisdiction: str
    created_at: int          # 记录事实发生时间（创建时刻）
    ingest_seq: int
    valid_from: int          # 该版本生效时间
    payload: str
    derived_from: str | None  # 上游原件 ID；派生副本指向上游


@dataclass(frozen=True)
class Hold:
    hold_id: str
    target_record: str       # 具体记录 ID 或 "*" 表示全域保全
    valid_from: int
    ingest_seq: int
    note: str = ""


@dataclass(frozen=True)
class HoldRelease:
    release_id: str
    hold_id: str
    valid_from: int          # 解除生效时间，可早于录入时间（追溯解除）
    ingest_seq: int


@dataclass
class Request:
    request_id: str
    occurred_at: int
    cutoff_seq: int
    horizon_days: int
    capacities: tuple[int, ...]   # 第 k 项 = 窗口第 k+1 个 UTC 日的容量
    rules: list[RuleVersion] = field(default_factory=list)
    records: list[RecordFact] = field(default_factory=list)
    holds: list[Hold] = field(default_factory=list)
    releases: list[HoldRelease] = field(default_factory=list)


def _require_mapping(obj: object, where: str) -> dict:
    if not isinstance(obj, dict):
        raise PlannerError(E_MALFORMED, f"{where} 必须是对象")
    return obj


def _require_int(value: object, field_name: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PlannerError(E_MALFORMED, f"{field_name} 必须是整数")
    if minimum is not None and value < minimum:
        raise PlannerError(E_MALFORMED, f"{field_name} 不能小于 {minimum}")
    return value


def _require_str(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise PlannerError(E_MALFORMED, f"{field_name} 必须是非空字符串")
    return value


def _opt_str(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_str(value, field_name)


def load_request(raw: object) -> Request:
    """把未受信的 JSON 结构校验并转换为 Request。"""
    data = _require_mapping(raw, "请求根对象")

    request_id = _require_str(data.get("request_id"), "request_id")
    occurred_at = parse_timestamp(data.get("occurred_at"), field="occurred_at")
    cutoff_seq = _require_int(data.get("cutoff_seq"), "cutoff_seq", minimum=0)
    horizon_days = _require_int(data.get("horizon_days"), "horizon_days", minimum=1)
    if horizon_days > MAX_HORIZON_DAYS:
        raise PlannerError(E_HORIZON, f"horizon_days 最大为 {MAX_HORIZON_DAYS}，实际 {horizon_days}")

    capacities_raw = data.get("capacities")
    if not isinstance(capacities_raw, list) or len(capacities_raw) != horizon_days:
        raise PlannerError(E_MALFORMED, "capacities 必须是长度等于 horizon_days 的整数数组")
    capacities = tuple(_require_int(c, f"capacities[{i}]", minimum=0) for i, c in enumerate(capacities_raw))
    if any(c > MAX_CAPACITY for c in capacities):
        raise PlannerError(E_MALFORMED, f"单日容量不能超过 {MAX_CAPACITY}")

    rules: list[RuleVersion] = []
    for i, item in enumerate(data.get("rules", [])):
        m = _require_mapping(item, f"rules[{i}]")
        rules.append(
            RuleVersion(
                rule_id=_require_str(m.get("rule_id"), f"rules[{i}].rule_id"),
                jurisdiction=_require_str(m.get("jurisdiction"), f"rules[{i}].jurisdiction"),
                valid_from=parse_timestamp(m.get("valid_from"), field=f"rules[{i}].valid_from"),
                ingest_seq=_require_int(m.get("ingest_seq"), f"rules[{i}].ingest_seq", minimum=0),
                min_retention_days=_require_int(
                    m.get("min_retention_days"), f"rules[{i}].min_retention_days", minimum=0
                ),
                max_lifetime_days=_require_int(
                    m.get("max_lifetime_days"), f"rules[{i}].max_lifetime_days", minimum=0
                ),
            )
        )

    records: list[RecordFact] = []
    record_ids: set[str] = set()
    for i, item in enumerate(data.get("records", [])):
        m = _require_mapping(item, f"records[{i}]")
        rid = _require_str(m.get("record_id"), f"records[{i}].record_id")
        if rid in record_ids:
            raise PlannerError(E_MALFORMED, f"record_id 重复: {rid}")
        record_ids.add(rid)
        records.append(
            RecordFact(
                record_id=rid,
                jurisdiction=_require_str(m.get("jurisdiction"), f"records[{i}].jurisdiction"),
                created_at=parse_timestamp(m.get("created_at"), field=f"records[{i}].created_at"),
                ingest_seq=_require_int(m.get("ingest_seq"), f"records[{i}].ingest_seq", minimum=0),
                valid_from=parse_timestamp(m.get("valid_from"), field=f"records[{i}].valid_from"),
                payload=_require_str(m.get("payload"), f"records[{i}].payload"),
                derived_from=_opt_str(m.get("derived_from"), f"records[{i}].derived_from"),
            )
        )
    if len(records) > MAX_OBJECTS:
        raise PlannerError(E_TOO_MANY_OBJECTS, f"待删对象上限 {MAX_OBJECTS}，实际 {len(records)}")

    holds: list[Hold] = []
    hold_ids: set[str] = set()
    for i, item in enumerate(data.get("holds", [])):
        m = _require_mapping(item, f"holds[{i}]")
        hid = _require_str(m.get("hold_id"), f"holds[{i}].hold_id")
        if hid in hold_ids:
            raise PlannerError(E_MALFORMED, f"hold_id 重复: {hid}")
        hold_ids.add(hid)
        holds.append(
            Hold(
                hold_id=hid,
                target_record=_require_str(m.get("target_record"), f"holds[{i}].target_record"),
                valid_from=parse_timestamp(m.get("valid_from"), field=f"holds[{i}].valid_from"),
                ingest_seq=_require_int(m.get("ingest_seq"), f"holds[{i}].ingest_seq", minimum=0),
                note=str(m.get("note", "")),
            )
        )

    releases: list[HoldRelease] = []
    for i, item in enumerate(data.get("hold_releases", [])):
        m = _require_mapping(item, f"hold_releases[{i}]")
        rid = _require_str(m.get("release_id"), f"hold_releases[{i}].release_id")
        hid = _require_str(m.get("hold_id"), f"hold_releases[{i}].hold_id")
        if hid not in hold_ids:
            raise PlannerError(E_HOLD_RELEASE_UNKNOWN, f"解除引用了未知保全: {hid}（release {rid}）")
        releases.append(
            HoldRelease(
                release_id=rid,
                hold_id=hid,
                valid_from=parse_timestamp(m.get("valid_from"), field=f"hold_releases[{i}].valid_from"),
                ingest_seq=_require_int(m.get("ingest_seq"), f"hold_releases[{i}].ingest_seq", minimum=0),
            )
        )

    req = Request(
        request_id=request_id,
        occurred_at=occurred_at,
        cutoff_seq=cutoff_seq,
        horizon_days=horizon_days,
        capacities=capacities,
        rules=rules,
        records=records,
        holds=holds,
        releases=releases,
    )
    _validate_references(req)
    return req


def _validate_references(req: Request) -> None:
    """派生引用必须指向已声明记录（可见性在双时间阶段再过滤）。"""
    ids = {r.record_id for r in req.records}
    for rec in req.records:
        if rec.derived_from is not None and rec.derived_from not in ids:
            raise PlannerError(E_MALFORMED, f"记录 {rec.record_id} 的 derived_from 指向未知记录 {rec.derived_from}")
    # 保全目标：具体 ID 必须存在；"*" 为全域保全
    for hold in req.holds:
        if hold.target_record != "*" and hold.target_record not in ids:
            raise PlannerError(E_MALFORMED, f"保全 {hold.hold_id} 指向未知记录 {hold.target_record}")
