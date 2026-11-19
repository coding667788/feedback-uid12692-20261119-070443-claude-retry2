"""稳定错误码。

所有错误均为整份请求级别致命错误；单个对象的规则矛盾不致命，
以 status="RULE_CONFLICT" 在报告中逐对象展示。
"""

from __future__ import annotations


class PlannerError(Exception):
    """带稳定错误码的领域异常。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message}


# 输入结构或引用关系不合法（缺字段、未知 ID、悬空引用等）
E_MALFORMED = "E_MALFORMED"
# 同一版本键下出现不同载荷（同版异值拒绝）
E_VERSION_CONFLICT = "E_VERSION_CONFLICT"
# 保全解除引用了在截点不可见的保全 ID
E_HOLD_RELEASE_UNKNOWN = "E_HOLD_RELEASE_UNKNOWN"
# 派生引用形成环，依赖 DAG 无法拓扑化
E_CYCLE = "E_CYCLE"
# 时间戳无法解析或不满足 UTC 整日秒数对齐要求
E_TIMESTAMP = "E_TIMESTAMP"
# 规划窗口超过 7 个 UTC 日
E_HORIZON = "E_HORIZON"
# 待删对象超过 16 个
E_TOO_MANY_OBJECTS = "E_TOO_MANY_OBJECTS"
# 规则自相矛盾：最早可删晚于最晚必须删
E_RULE_CONTRADICTION = "E_RULE_CONTRADICTION"
# 搜索节点超过安全预算（理论上 16 对象/7 日规模不应触发，触发即暴露问题）
E_SEARCH_BUDGET = "E_SEARCH_BUDGET"
