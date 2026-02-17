import os
from typing import Optional, List

import json
from openai import OpenAI
from ..tools import TextFileContent, TODOListManager
from ..tools import AIFunction

class AIModule:
    def __init__(self, api_key: str, model: str, url: Optional[str] = None, system_prompt: str = '你是一个AI助手。', tools:Optional[AIFunction]=None, max_attempts_per_step: int = 10) -> None:
        self.model, self.url, self.system_prompt = model, url, system_prompt
        self.history = [{'role': 'system', 'content': system_prompt}]
        self.client = OpenAI(api_key=api_key) if url is None else OpenAI(api_key=api_key, base_url=url)
        self.todos = TODOListManager()
        self.tools = self.todos.function
        if tools is not None:
            self.tools.include(tools)
        # Ensure tool_functions is always defined; prefer functions from self.tools if available
        try:
            self.tool_functions = self.tools.functions
        except Exception:
            self.tool_functions = []
        self.max_attempts_per_step = max_attempts_per_step

    def __answer_show(self, prompt: str, messages:Optional[list]=None) -> str:
        if messages is None:
            messages = list(self.history)
        messages.append({'role':'user', 'content':prompt})
        stop = False
        called_tools = []
        while not stop:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tool_functions,
                tool_choice='auto',
                stream=True
            )

            tool_calls = {}
            msg = ''
            for chunk in response:
                if chunk.choices[0].finish_reason == 'stop':
                    stop = True
                delta = chunk.choices[0].delta

                if delta.content:
                    print(delta.content, end='', flush=True)
                    msg += delta.content
                
                if delta.tool_calls:
                    for tcd in delta.tool_calls:
                        idx = tcd.index
                        if idx not in tool_calls:
                            tool_calls[idx] = tcd
                        else:
                            if tcd.id:
                                tool_calls[idx].id = tcd.id
                            if tcd.function.name:
                                tool_calls[idx].function.name = tcd.function.name
                            if tcd.function.arguments:
                                tool_calls[idx].function.arguments += tcd.function.arguments
            messages.append({'role':'assistant', 'content':msg})
            if tool_calls:
                for tc in tool_calls.values():
                    kwargs = json.loads(tc.function.arguments)
                    fname = tc.function.name
                    called_tools.append(fname)
                    print(f'\n\033[36m调用工具 {fname}\033[0m')
                    res = self.tools(fname, **kwargs)
                    messages.append({
                        'role':'assistant',
                        'tool_calls':[{
                            'id':tc.id,
                            'type':'function',
                            'function':{
                                'name':fname,
                                'arguments':tc.function.arguments
                            }
                        }]
                    })
                    messages.append({
                        'role':'tool',
                        'tool_call_id':tc.id,
                        'content':res
                    })
        return msg, called_tools
    
    def __answer_hide(self, prompt: str, messages:Optional[list]=None) -> str:
        if messages is None:
            messages = list(self.history)
        messages.append({'role':'user', 'content':prompt})
        stop = False
        called_tools = []
        while not stop:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tool_functions,
                tool_choice='auto'
            )

            if response.choices[0].finish_reason == 'stop':
                stop = True
            msg = response.choices[0].message
            messages.append({
                'role':'assistant',
                'content':msg.content
            })
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    kwargs = json.loads(tc.function.arguments)
                    fname = tc.function.name
                    called_tools.append(fname)
                    res = self.tools(fname, **kwargs)
                    messages.append({
                        'role':'assistant',
                        'tool_calls':[{
                            'id':tc.id,
                            'type':'function',
                            'function':{
                                'name':fname,
                                'arguments':tc.function.arguments
                            }
                        }]
                    })
                    messages.append({
                        'role':'tool',
                        'tool_call_id':tc.id,
                        'content':res
                    })
        return msg.content, called_tools
    
    def __answer(self, prompt: str, show: bool = True) -> str:
        if show:
            return self.__answer_show(prompt)
        else:
            return self.__answer_hide(prompt)
        
    def answer(self, prompt: str, files: Optional[List[TextFileContent]] = None) -> str:
        if files is not None:
            file_prompt = '以下内容是用户提供的文件，供你参考。文件以此格式提供：\n```text\n[file name]: 文件名\n[file content begin]文件内容[file content end]\n```\n。文件：\n'
            for file in files:
                file_prompt += str(file)
            file_prompt += '\n\n用户的问题如下：\n'
            prompt = file_prompt + prompt

        # Generate TODO list
        self.__answer(
            prompt=prompt + '\n现在，请你将任务拆解成多个步骤，调用工具制定一个TODO列表，每个步骤标上序号，从1开始。注意：只要你调用工具制定TODO列表，不需要执行任务！',
            show=False
        )
        
        self.todos.print()
        results = [str(self.todos)]

        # Complete each step in TODO list
        while not self.todos.pause and not self.todos.all_completed:
            # 注意：TODO 列表的 cur_step 从 1 开始，因此取列表元素时需要减 1
            cur_step = self.todos.todo[self.todos.cur_step - 1]
            idx = self.todos.cur_step
            attempts = 0
            retry_messages = None  
            original_prompt = prompt
            # 对当前 step 重试直到复盘合格或达到最大尝试次数
            while not self.todos.pause and not self.todos.all_completed:
                attempts += 1
                if retry_messages is None:
                    cur_ans, called_tools = self.__answer(
                        f'{original_prompt}\n你必须严格按照TODO清单完成任务。（可调用工具查看）\n现在请你只完成第{idx}步：\n{cur_step}\n不要完成后面的步骤，但可以修改TODO列表。',
                        show=True
                    )
                else:
                    redo_instruction = f'请基于下面的历史回答和复盘反馈，重新完成第{idx}步：\n{cur_step}'
                    cur_ans, called_tools = self.__answer_show(redo_instruction, messages=retry_messages)

                # 如果模型在生成回答过程中调用了工具，检测特定工具并调整流程
                if called_tools:
                    # 把当前回答记录并追加到 results/history
                    results.append(cur_ans)
                    self.history.append({'role': 'assistant', 'content': cur_ans})
                    # 如果调用了 complete_all 或者整个 TODO 已完成，则结束所有循环
                    if 'complete_all' in called_tools or self.todos.all_completed:
                        break
                    # 如果调用了 complete_step 或者当前步骤已变更，则跳过复盘，进入下一步
                    if 'complete_step' in called_tools:
                        self.todos.redo()
                    
                    if self.todos.cur_step != idx:
                        break

                # 调用 AI 进行复盘（显示模式）
                review_prompt = (
                    f'请先检查TODO清单和文件内容（如果有），再复盘回答内容并判断是否合格。\n步骤内容：\n{cur_step}\n\n'
                    f'你的完成内容：\n{cur_ans}\n\n'
                    '如果合格，只回复“合格”。'
                    '如果不合格，回复“不合格”，并简要列出不足与需要重做的改进要点。'
                )
                review, review_tools = self.__answer(review_prompt, show=True)

                # 简单判定是否合格（只要包含“合格”字样即通过）
                if isinstance(review, str) and '合格' in review and '不合格' not in review:
                    self.todos.complete_step()
                    results.append(cur_ans)
                    # 仅把当前步的回答追加到 history（assistant），避免把整个累计结果覆盖到 history
                    self.history.append({'role': 'assistant', 'content': cur_ans})
                    break

                # 未合格处理：若超过最大重试次数则强制完成以避免死循环
                if attempts >= self.max_attempts_per_step:
                    self.todos.complete_step()
                    break

                # 要求重做：以字典消息形式传回（assistant 的之前回答，user 的复盘反馈），供模型参考
                retry_messages = list(self.history)
                retry_messages.append({'role': 'assistant', 'content': cur_ans})
                retry_messages.append({'role': 'user', 'content': review})
                # 重试循环会使用更新后的 original_prompt
            # 内层循环结束，继续外层循环直到所有步骤完成
            continue

        return '\n'.join(results)

if __name__ == '__main__':
    from ..tools.file_manager import FileManager
    fm = FileManager(os.path.curdir)
    agent = AIModule(
        api_key=input('请输入您的DeepSeek API KEY\n> '),
        model='deepseek-chat',
        url='https://api.deepseek.com/',
        system_prompt='你是AI助手DeepSeek。在完成复杂任务时，你应先检查TODO清单是否已有内容，再决定是否继续制定TODO待办清单，并严格按照清单推进。',
        tools=fm.function
    )
    agent.answer('请帮我分析位于test_files/report.txt的工作报告并提供改进建议。你可以帮我直接改文件。')
