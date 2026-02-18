import base64
import os
from pathlib import Path
from .ai_module_class import AIModule
from openai import OpenAI
from typing import Optional
import json
from ..tools import AIFunction

class DeepSeekModule(AIModule):
    def __init__(self, api_key:str, reasoning:bool=True, system_prompt:str='你是一个AI助手。', tools:Optional[AIFunction]=None, max_attempts_per_step: int = 10)->None:
        super().__init__(
            api_key, 
            'deepseek-chat' if not reasoning else 'deepseek-reasoner',
            url='https://api.deepseek.com/',
            system_prompt=system_prompt,
            tools=tools,
            max_attempts_per_step=max_attempts_per_step
        )
        self.reasoning = reasoning
    
    def set_mode(self, reasoning:bool)->None:
        self.reasoning = reasoning
        self.model = 'deepseek-chat' if not reasoning else 'deepseek-reasoner'
        return
    
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
            messages.append(msg)
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    kwargs = json.loads(tc.function.arguments)
                    fname = tc.function.name
                    called_tools.append(fname)
                    res = self.tools(fname, **kwargs)
                    messages.append({
                        'role':'tool',
                        'tool_call_id':tc.id,
                        'content':res
                    })
        return msg.content, called_tools
    
    def __answer_show(self, prompt, messages:Optional[list]=None)->str:
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
            rsn = ''
            for chunk in response:
                if chunk.choices[0].finish_reason == 'stop':
                    stop = True
                delta = chunk.choices[0].delta

                if self.reasoning:
                    if delta.reasoning_content:
                        print(f'\033[90m{delta.reasoning_content}\033[0m', end='', flush=True)
                        rsn += delta.reasoning_content
                        
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
            messages.append({'role':'assistant', 'content':msg, 'reasoning_content':rsn})
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

class KimiModule(AIModule):
    def __init__(self, api_key:str, reasoning:bool=True, system_prompt:str='你是一个AI助手。', tools:Optional[AIFunction]=None, max_attempts_per_step: int = 10)->None:
        super().__init__(
            api_key, 
            'kimi-k2.5',
            url='https://api.moonshot.cn/v1',
            system_prompt=system_prompt,
            tools=tools,
            max_attempts_per_step=max_attempts_per_step
        )
        self.reasoning = reasoning
        self.file_ids = []
    
    def upload_file(self, fpath:str, purpose:str)->None:
        if purpose == 'file-extract' or purpose == 'video':
            file_obj = self.client.files.create(file=Path(fpath), purpose=purpose)
            self.file_ids.append(file_obj.id)
            if purpose == 'file-extract':
                content = self.client.files.content(file_id=file_obj.id).text
                self.history.append({'role':'system', 'content':content})
            else:
                self.history.append({'role':'user', 'content':[{'type':'video_url','video_url':{'url':f'ms://{file_obj.id}'}}]})
        elif purpose == 'image':
            if os.path.exists(fpath) and os.path.isfile(fpath):
                with open(fpath, 'rb') as f:
                    img_content = f.read()
                img_url = f'data:image/{os.path.splitext(fpath)[1]};base64,{base64.b64encode(img_content).decode("utf-8")}'
                self.history.append({'role':'user', 'content':{'type':'image_url', 'image_url':{'url':img_url}}})
    
    def clear_files(self)->None:
        for f_id in self.file_ids:
            self.client.files.delete(file_id=f_id)
        self.file_ids = []
        return
    
    def __del__(self):
        self.clear_files()

class DoubaoModule(AIModule):
    pass

