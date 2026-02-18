from typing import List, Literal, Optional, Union, Dict

from .ai_module_class import AIModule


class MixedAIManager:
    """管理多个 `AIModule` 实例的调度器。

    参数:
      - type: 'chat' 或 'generate'
          - 'chat'：把同一条输入广播给所有模型（并返回所有模型的回答）
          - 'generate'：每次调用只对指定的模型生成回答
      - agents: AIModule 列表（AIModule 或其子类实例）

    __call__ 方法签名:
      - prompt: 要发送给模型的文本
      - agent: 当 type=='generate' 时，必须指定为 int(索引) 或 AIModule 实例；当 type=='chat' 时可省略
      - files: 可选，传递给 AIModule.answer 的文件列表
    返回值:
      - 当 type=='chat'：返回 Dict[int, str]，键为 agents 的索引，值为对应回答
      - 当 type=='generate'：返回单个模型的字符串回答
    """

    def __init__(self, type:Literal['chat', 'generate'], agents: List[AIModule]) -> None:
        if type not in ('chat', 'generate'):
            raise ValueError("type must be 'chat' or 'generate'")
        if not isinstance(agents, list) or not agents:
            raise ValueError('agents must be a non-empty list of AIModule instances')

        self.type = type
        self.agents = agents

    def __repr__(self) -> str:
        names = [getattr(a, 'model', a.__class__.__name__) for a in self.agents]
        return f"MixedAIManager(type={self.type!r}, agents={names!r})"

    def __call__(
        self,
        prompt: str,
        agent: Optional[Union[int, AIModule]] = None,
        files: Optional[list] = None,
        rounds: Optional[int] = None,
    ) -> Union[str, Dict[int, str]]:
        """调用混合管理器以获取模型回答。

        - 当 `self.type == 'chat'`：把 `prompt` 广播给所有 `agents`，并返回字典 {index: answer}
        - 当 `self.type == 'generate'`：需要指定 `agent`，可以是索引或实例，返回该模型的回答字符串
        """
        if not isinstance(prompt, str):
            raise TypeError('prompt must be a string')

        if self.type == 'chat':
            # AI-to-AI 讨论：把用户问题先加入每个 agent 的历史，
            # 然后按照顺序让每个 agent 回答并把回答同步到所有 agent 的历史中。
            n = len(self.agents)
            num_rounds = rounds if rounds is not None else n

            # 初始将用户问题加入所有 agent 历史
            for a in self.agents:
                a.history.append({'role': 'user', 'content': prompt})

            # 为每个 agent 保存其被要求回答的当前输入（初始均为用户问题）
            current_inputs = [prompt for _ in range(n)]
            logs = []  # list of (agent_index, reply)

            for r in range(num_rounds):
                for idx, a in enumerate(self.agents):
                    inp = current_inputs[idx]
                    try:
                        reply = a.answer(inp, files=files)
                    except TypeError:
                        reply = a.answer(inp)

                    logs.append((idx, reply))

                    # 下一个 agent 的索引（下一轮将由其回复）——不要把回答同步给它
                    next_idx = (idx + 1) % n

                    # 将该回答追加为除下一个 agent 外所有 agent 的 assistant 消息，使它成为共享上下文
                    for j, b in enumerate(self.agents):
                        if j == next_idx:
                            continue
                        b.history.append({'role': 'assistant', 'content': reply})

                    # 将刚才的回答设置为下一个 agent 的输入（环形）
                    current_inputs[next_idx] = reply

            # 汇总每个 agent 的所有回答并返回
            results: Dict[int, str] = {}
            for i in range(n):
                agent_replies = [r for (aid, r) in logs if aid == i]
                results[i] = '\n'.join(agent_replies)
            return results

        # generate 模式
        if self.type == 'generate':
            if agent is None:
                raise ValueError("In 'generate' mode you must specify the `agent` (index or AIModule instance)")

            # resolve agent index
            if isinstance(agent, int):
                if agent < 0 or agent >= len(self.agents):
                    raise IndexError('agent index out of range')
                target = self.agents[agent]
            elif isinstance(agent, AIModule):
                if agent not in self.agents:
                    raise ValueError('provided agent instance is not managed by this MixedAIManager')
                target = agent
            else:
                raise TypeError('agent must be int (index) or AIModule instance')

            try:
                return target.answer(prompt, files=files)
            except TypeError:
                return target.answer(prompt)

        # 不可达
        raise RuntimeError('unsupported manager type')
