import os
from typing import Optional, List

import json
import ast
from openai import OpenAI
from ..tools import TextFileContent, TODOListManager, FileManager
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
        # state file path for saving/loading agent state
        self._state_file = os.path.join(os.getcwd(), 'agent_state.json')
        # initial user prompt for this run (set in answer)
        self.initial_prompt = None
        # file-based state directory and manager (用于在步骤间保存关键内容，避免超出上下文长度)
        try:
            self._file_dir = os.path.join(os.getcwd(), '.agent_files')
            os.makedirs(self._file_dir, exist_ok=True)
            self._file_manager = FileManager(self._file_dir)
            # expose file manager functions to the agent tools so model can call read_file/write_file
            try:
                self.tools.include(self._file_manager.function)
            except Exception:
                pass
        except Exception:
            self._file_dir = None
            self._file_manager = None

    def _save_step_file(self, step_idx: int, content: str) -> Optional[str]:
        """将当前步骤的回答写入文件，并在 history 中添加提示，返回写入的相对文件名。"""
        if not self._file_manager or not self._file_dir:
            return None
        fname = f'step_{step_idx}_summary.txt'
        try:
            # 直接写入完整回答；若需精简，可改为让模型生成摘要后写入
            self._file_manager.write_file(fname, content)
            # 将提示添加到 conversation history，提醒模型可用文件读取
            note = (f'注意：第{step_idx}步的关键内容已保存为文件 {fname}。'
                    ' 若需要历史关键信息以避免重复上下文长度，请使用工具 `read_file` 读取该文件的内容。')
            self.history.append({'role': 'system', 'content': note})
            return fname
        except Exception:
            return None

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
                    arg_str = tc.function.arguments
                    try:
                        kwargs = json.loads(arg_str) if isinstance(arg_str, str) and arg_str.strip() else {}
                    except Exception:
                        try:
                            kwargs = ast.literal_eval(arg_str) if isinstance(arg_str, str) and arg_str.strip() else {}
                        except Exception:
                            kwargs = {}
                    if not isinstance(kwargs, dict):
                        kwargs = {}
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
            messages.append(msg)
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    arg_str = tc.function.arguments
                    try:
                        kwargs = json.loads(arg_str) if isinstance(arg_str, str) and arg_str.strip() else {}
                    except Exception:
                        try:
                            kwargs = ast.literal_eval(arg_str) if isinstance(arg_str, str) and arg_str.strip() else {}
                        except Exception:
                            kwargs = {}
                    if not isinstance(kwargs, dict):
                        kwargs = {}
                    fname = tc.function.name
                    called_tools.append(fname)
                    res = self.tools(fname, **kwargs)
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

    def save_state(self, path: Optional[str] = None) -> str:
        """Save agent state (system prompt, initial prompt, history, todos) to JSON."""
        p = path or self._state_file
        data = {
            'system_prompt': self.system_prompt,
            'initial_prompt': self.initial_prompt,
            'model': self.model,
            'history': self.history,
            'todos': {
                'todo': self.todos.todo,
                'nsteps': self.todos.nsteps,
                'progress': self.todos.progress,
                'cur_step': self.todos.cur_step,
                'pause': self.todos.pause
            }
        }
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return p

    def load(self, path: Optional[str] = None) -> bool:
        """Load agent state from JSON and restore history and TODO list."""
        p = path or self._state_file
        if not os.path.exists(p):
            return False
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # restore simple fields
        self.system_prompt = data.get('system_prompt', self.system_prompt)
        self.initial_prompt = data.get('initial_prompt', self.initial_prompt)
        self.model = data.get('model', self.model)
        self.history = data.get('history', self.history)

        # restore todos
        todos_data = data.get('todos', {})
        todo_list = todos_data.get('todo', [])
        self.todos = TODOListManager(todo_list)
        # override attributes if provided
        self.todos.nsteps = todos_data.get('nsteps', len(todo_list))
        self.todos.progress = todos_data.get('progress', [False] * self.todos.nsteps)
        self.todos.cur_step = todos_data.get('cur_step', 1)
        self.todos.pause = todos_data.get('pause', False)

        # restore tool references
        self.tools = self.todos.function
        try:
            self.tool_functions = self.tools.functions
        except Exception:
            self.tool_functions = []

        return True
        
    def answer(self, prompt: str, files: Optional[List[TextFileContent]] = None) -> str:
        # record initial prompt for saving/loading
        self.initial_prompt = prompt
        if files is not None:
            file_prompt = '以下内容是用户提供的文件，供你参考。文件以此格式提供：\n```text\n[file name]: 文件名\n[file content begin]文件内容[file content end]\n```\n。文件：\n'
            for file in files:
                file_prompt += str(file)
            file_prompt += '\n\n用户的问题如下：\n'
            prompt = file_prompt + prompt

        # Generate TODO list
        self.__answer(
            prompt=prompt + '\n现在，请你将任务拆解成多个步骤，调用工具制定一个TODO列表，每个步骤标上序号，从1开始。注意：只要你调用工具制定TODO列表，不需要执行任务！',
            show=True
        )

        results = [str(self.todos)]
        # save initial state after generating TODOs
        try:
            self.save_state()
        except Exception:
            pass

        # Complete each step in TODO list
        while not self.todos.pause and not self.todos.all_completed:
            print()
            self.todos.print()
            print()
            # 注意：TODO 列表的 cur_step 从 1 开始，因此取列表元素时需要减 1
            cur_step = self.todos.todo[self.todos.cur_step - 1]
            idx = self.todos.cur_step
            attempts = 0
            retry_messages = None  
            original_prompt = prompt
            # 对当前 step 重试直到复盘合格或达到最大尝试次数
            while not self.todos.pause and not self.todos.all_completed:
                attempts += 1
                print()
                if retry_messages is None:
                    step_save_fname = os.path.join('.agent_files', f'step_{idx}_summary.txt')
                    write_instr = (
                        "\n\n注意：如果本步骤产生可持久化的关键结果，" 
                        "请调用工具 `write_file` 将精炼后的关键要点写入文件 '" + step_save_fname + "'。"
                        " 文件内容应只包含要点与必要数据，不要重复大量上下文；最多 8 行或 300 字；使用项目符号或短句呈现。"
                        " 写入后在回答中仅给一行极简说明（最多一句），不要把完整结果粘贴进回答。"
                    )
                    cur_ans, called_tools = self.__answer(
                        f'{original_prompt}\n你必须严格按照TODO清单完成任务。（可调用工具查看）\n现在请你只完成第{idx}步：\n{cur_step}\n不要完成后面的步骤，不要调用complete_step标记步骤（因为系统会自动处理），但可以修改TODO列表。'
                        + write_instr,
                        show=True
                    )
                else:
                    step_save_fname = os.path.join('.agent_files', f'step_{idx}_summary.txt')
                    write_instr = (
                        "\n\n注意：如果本步骤产生可持久化的关键结果，" 
                        "请调用工具 `write_file` 将精炼后的关键要点写入文件 '" + step_save_fname + "'。"
                        " 文件内容应只包含要点与必要数据，不要重复大量上下文；最多 8 行或 300 字；使用项目符号或短句呈现。"
                        " 写入后在回答中仅给一行极简说明（最多一句），不要把完整结果粘贴进回答。"
                    )
                    redo_instruction = (
                        f'请基于下面的历史回答和复盘反馈，重新完成第{idx}步：\n{cur_step}\n请不要完成后面的步骤。系统会自动标记TODO列表状态，因此请不要调用complete_step。'
                        + write_instr
                    )
                    cur_ans, called_tools = self.__answer_show(redo_instruction, messages=retry_messages)

                # 如果模型在生成回答过程中调用了工具，检测特定工具并调整流程
                if called_tools:
                    # 把当前回答记录并追加到 results/history
                    results.append(cur_ans)
                    self.history.append({'role': 'assistant', 'content': cur_ans})
                    # persist state after tool-invoked changes
                    try:
                        self.save_state()
                    except Exception:
                        pass
                    # 如果调用了 complete_all 或者整个 TODO 已完成，则结束所有循环
                    if 'complete_all' in called_tools or self.todos.all_completed:
                        break
                    # 如果调用了 complete_step 或者当前步骤已变更，则跳过复盘，进入下一步
                    if 'complete_step' in called_tools:
                        self.todos.redo()
                    
                    if self.todos.cur_step != idx:
                        break

                print()
                # 调用 AI 进行复盘（显示模式）
                review_prompt = (
                    f'请先检查TODO清单和文件内容（如果有），再复盘回答内容并判断是否合格。\n步骤内容：\n{cur_step}\n\n'
                    f'你的完成内容：\n{cur_ans}\n\n'
                    '如果合格，只回复“合格”。'
                    '如果不合格，回复“不合格”，并简要列出不足与需要重做的改进要点。'
                )
                review, review_tools = self.__answer(review_prompt, show=True)
                print()

                # 简单判定是否合格（只要包含“合格”字样即通过）
                if isinstance(review, str) and '合格' in review and '不合格' not in review:
                    self.todos.complete_step()
                    results.append(cur_ans)
                    # 仅把当前步的回答追加到 history（assistant），避免把整个累计结果覆盖到 history
                    self.history.append({'role': 'assistant', 'content': cur_ans})
                    # 优先由模型主动调用 write_file 保存关键信息；若模型未调用，则在 history 中加入提示，提醒后续步骤可读取文件
                    if 'write_file' not in called_tools:
                        note = (f'注意：第{idx}步的关键结果尚未保存为文件。如需持久化，请调用工具 `write_file` 将精要写入 .agent_files/step_{idx}_summary.txt，'
                                ' 文件内容最多 8 行或 300 字，只包含要点。')
                        self.history.append({'role': 'system', 'content': note})
                    # persist state after completing a step
                    try:
                        self.save_state()
                    except Exception:
                        pass
                    break

                # 未合格处理：若超过最大重试次数则强制完成以避免死循环
                if attempts >= self.max_attempts_per_step:
                    self.todos.complete_step()
                    # 达到最大重试次数时做最小回退保存（截断），以免丢失重要工作成果
                    if 'write_file' not in called_tools:
                        try:
                            lines = cur_ans.splitlines()
                            short = '\n'.join(lines[:8])
                            short = short[:1000]
                            self._save_step_file(idx, short)
                            self.history.append({'role':'system', 'content': f'已为第{idx}步写入回退摘要文件 step_{idx}_summary.txt（内容已截断）。'})
                        except Exception:
                            pass
                    try:
                        self.save_state()
                    except Exception:
                        pass
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
