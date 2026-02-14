from typing import Optional, List
import re

import openai
from openai import OpenAI
from ..tools import TextFileContent, TODOListManager

class AIModule:
    def __init__(self, api_key: str, model: str, url: Optional[str] = None, system_prompt: str = '你是一个AI助手。') -> None:
        self.model, self.url, self.system_prompt = model, url, system_prompt
        self.history = [{'role': 'system', 'content': system_prompt}]
        self.client = OpenAI(api_key=api_key) if url is None else OpenAI(api_key=api_key, base_url=url)
        self.todos = TODOListManager()

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