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
    user_input = input("请输入你的问题（输入'退出'结束对话）：")
    if user_input.lower() == '退出':
        print("对话结束。")
        break
    ai.answer(user_input)