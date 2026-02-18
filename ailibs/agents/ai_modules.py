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