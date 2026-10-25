import json

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction


@AgentServer.custom_action("sweep_until_exhausted")
class SweepUntilExhaustedAction(CustomAction):
    """蔚蓝档案扫荡示例：循环执行扫荡节点，直到识别到终止条件（体力不足等）。

    在 pipeline 中的用法（需先在 interface.json 中启用 agent）：

    ```jsonc
    "日程_循环扫荡": {
        "recognition": "OCR",
        "expected": "扫荡",
        "action": "Custom",
        "custom_action": "sweep_until_exhausted",
        "custom_action_param": {
            "sweep_node": "日程_执行扫荡",    // 单次扫荡链的入口节点
            "exhausted_node": "日程_体力不足"  // 终止判定节点（OCR 识别"体力不足"等文本）
        }
    }
    ```

    注意：exhausted_node 指向的节点需要你在 pipeline 中定义，例如：

    ```jsonc
    "日程_体力不足": {
        "recognition": "OCR",
        "expected": ["体力不足", "无法扫荡"],
        "action": "DoNothing"
    }
    ```
    """

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:

        param = json.loads(argv.custom_action_param or "{}") or {}
        sweep_node = param.get("sweep_node")
        exhausted_node = param.get("exhausted_node")
        if not sweep_node:
            print("[sweep_until_exhausted] 缺少 sweep_node 参数")
            return False

        count = 0
        while True:
            # 判断是否已经无法继续扫荡（体力不足 / 次数用尽）
            if exhausted_node:
                detail = context.run_recognition(exhausted_node, argv.image)
                if detail and detail.hit:
                    print(f"[sweep_until_exhausted] 已完成 {count} 次扫荡，命中终止条件")
                    return True

            # 执行一次单次扫荡链（识别 + 动作），未命中说明没有可扫荡的关卡了
            task_detail = context.run_task(sweep_node)
            if not task_detail or not task_detail.nodes:
                print(f"[sweep_until_exhausted] 节点 {sweep_node} 未命中，共扫荡 {count} 次")
                return True

            count += 1
            if count >= 50:
                print("[sweep_until_exhausted] 达到安全上限 50 次，强制结束")
                return False
