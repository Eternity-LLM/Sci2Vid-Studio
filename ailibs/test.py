import os
from .agents.ai_modules import DeepSeekModule
from .tools.file_manager import FileManager

fm = FileManager(os.path.curdir)

ai = DeepSeekModule(
    api_key=input("Enter your DeepSeek API key: "),
    system_prompt='你是AI助手DeepSeek。在解决复杂任务时，你可以调用工具、制定TODO清单辅助。',
    tools=fm.function,
    reasoning=False,
    max_attempts_per_step=5
)

while True:
    ai.load(os.path.join(os.path.curdir, 'agent_state.json'))
    ai.answer(ai.initial_prompt)