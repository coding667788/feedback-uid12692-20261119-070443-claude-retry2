"""离线合规删除计划器。

模块划分：
- errors:     稳定错误码与领域异常
- timeutil:   UTC 整日秒数运算与 ISO-8601 解析
- model:      输入数据校验与领域对象
- bitemporal:双时间（生效时间/录入序号）版本选择、同版异值拒绝、保全可见性
- engine:     逐对象保留期计算、阻断路径、状态判定
- planner:    DAG 约束 + 逐日容量下的三级目标精确优化器
- cli:        命令行入口与 JSON 装配
"""

__all__ = ["errors", "timeutil", "model", "bitemporal", "engine", "planner", "cli"]
