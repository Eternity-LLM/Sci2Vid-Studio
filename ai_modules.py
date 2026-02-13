from typing import Optional, List
import re

import openai
from openai import OpenAI

class TextFileContent(str):
    def __init__(self, file_name: str, file_content: str) -> None:
        self.fname, self.fcont = file_name, file_content
        self.template = f'[file name]: {file_name}\n[file content begin]{file_content}[file content end]\n'
        super().__init__(self.template)
    def save(self, encoding:str='utf-8')->None:
        with open(self.fname, mode='w', encoding=encoding) as f:
            f.write(self.fcont)
        return

class TODOListManager(list):
    def __init__(self, todo_list:list)->None:
        super().__init__(todo_list)
        self.nsteps = len(self)
        self.progress = [False for i in range(self.nsteps)]
        self.cur_step = 1

    def __str__(self)->str:
        res = '\n```TODO\n'
        for idx, step in enumerate(self, start=1):
            if idx < self.cur_step:
                res += '[+] '
            elif idx == self.cur_step:
                res += '[*] '
            else:
                res += '[-] '
            res += f'{step}\n'
        res += f'```\n'
        if self.cur_step > self.nsteps:
            res += '当前所有任务均已完成！'
        else:
            res += '标注[+][*][-]分别表示已完成、当前步骤、未完成步骤。\n当前正在处理的步骤为第{self.cur_step}步：\n```text\n{self[self.cur_step-1]}\n```'
        return res

    def clear(self)->None:
        self.cur_step = 1
        self.nsteps = 0
        self.progress = []
        super().__init__([])

    def complete_step(self)->None:
        self.progress[self.cur_step-1] = True
        self.cur_step += 1
        return

    def complete_all(self)->None:
        self.progress = [True for i in range(self.nsteps)]
        self.cur_step = self.nsteps + 1
        return

    def append(self, step:str)->None:
        self.nsteps += 1
        self.progress += [False]

class AIModule:
    def __init__(self, api_key: str, model: str, url: Optional[str] = None, system_prompt: str = '你是一个AI助手。') -> None:
        self.model, self.url, self.system_prompt = model, url, system_prompt
        self.history = [{'role': 'system', 'content': system_prompt}]
        self.client = OpenAI(api_key=api_key) if url is None else OpenAI(api_key=api_key, base_url=url)
        self.todos = []

    def __answer(self, prompt: str, show: bool = True) -> str:
        response = self.client.chat.completions.create(
            model=self.model, 
            messages=self.history + [{'role': 'user', 'content': prompt}],
            stream=show
        )
        if show:
            result = ''
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content is not None:
                    print(chunk.choices[0].delta.content, end='')
                    result += chunk.choices[0].delta.content
            print('')
            return result
        else:
            return response.choices[0].message.content

    def answer(self, prompt: str, files: Optional[List[TextFileContent]] = None) -> str:
        if files is not None:
            file_prompt = '以下内容是用户提供的文件，供你参考。文件以此格式提供：\n```text\n[file name]: 文件名\n[file content begin]文件内容[file content end]\n```\n。文件：\n'
            for file in files:
                file_prompt += str(file)
            file_prompt += '\n\n用户的问题如下：\n'
            prompt = file_prompt + prompt

        # Generate TODO list
        todo_res = self.__answer(
            prompt=prompt + '\n现在，请你将任务拆解成多个步骤，生成一个TODO列表。回答格式：\n```TODO\n1. ...\n2. ...\n...\n```\n编号遵循Markdown语法。回答时只需按照格式生成TODO列表即可，不要添加任何其他内容。',
            show=False
        )
        match = re.search(r'```TODO\s*\n(.*?)```', todo_res, re.DOTALL)
        if match:
            todo_text = match.group(1)
            steps = []
            for line in todo_text.splitlines():
                line = line.strip()
                if line and (re.match(r'^\d+\.\s+', line) or line.startswith('-')):
                    steps.append(line)
            self.todos = steps
        else:
            self.todos = [line.strip() for line in todo_res.splitlines() if line.strip()]

        # Complete each step in TODO list