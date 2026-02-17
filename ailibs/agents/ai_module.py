from typing import Optional, List
import re

import json
from openai import OpenAI
from ..tools import TextFileContent, TODOListManager
from ..tools import AIFunction

class AIModule:
    def __init__(self, api_key: str, model: str, url: Optional[str] = None, system_prompt: str = '你是一个AI助手。', tools:Optional[AIFunction]=None) -> None:
        self.model, self.url, self.system_prompt = model, url, system_prompt
        self.history = [{'role': 'system', 'content': system_prompt}]
        self.client = OpenAI(api_key=api_key) if url is None else OpenAI(api_key=api_key, base_url=url)
        self.todos = TODOListManager()
        self.tools = tools
        self.use_tools = tools is not None
        if self.use_tools:
            self.tool_functions = tools.functions

    def __answer_show(self, prompt: str) -> str:
        messages = self.history
        messages.append({'role':'user', 'content':prompt})
        stop = False
        while not stop:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tool_functions,
                tool_choice='auto',
                stream=True
            ) if self.use_tools else self.client.chat.completions.create(
                model=self.model,
                messages=messages,
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
        return msg
    
    def __answer_hide(self, prompt: str) -> str:
        messages = self.history
        messages.append({'role':'user', 'content':prompt})
        stop = False
        while not stop:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tool_functions,
                tool_choice='auto'
            ) if self.use_tools else self.client.chat.completions.create(
                model=self.model,
                messages=messages
            )

            if response.choices[0].finish_reason == 'stop':
                stop = True
            msg = response.choices[0].message
            messages.append(msg)
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    kwargs = json.loads(tc.function.arguments)
                    fname = tc.function.name
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
        return msg['content']
    
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
        todo_res = self.__answer(
            prompt=prompt + '\n现在，请你将任务拆解成多个步骤，生成一个TODO列表。回答格式：\n```TODO\n1. ...\n2. ...\n...\n```\n编号遵循Markdown语法。回答时必须严格按照格式生成TODO列表，不要添加任何其他内容。',
            show=False
        )
        match = re.search('```TODO\\s*\n(.*?)```', todo_res, re.DOTALL)
        if match:
            todo_text = match.group(1)
            for line in todo_text.splitlines():
                line = line.strip()
                self.todos.append(line[1:] if line.startswith('-') else line)
        else:
            for line in todo_res.splitlines():
                self.todos.append(line.strip())
        self.todos.print()

        # Complete each step in TODO list
        for idx, step in enumerate(self.todos.todo, start=1):
            cur_res = self.__answer(f'{prompt}你需要按照下面的TODO列表推进任务。\n{self.todos}\n现在请你完成第{idx}步', show=True)
