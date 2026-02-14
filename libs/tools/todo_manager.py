class TODOListManager:
    def __init__(self, todo_list:list=[])->None:
        self.todo = todo_list
        self.nsteps = len(self)
        self.progress = [False for i in range(self.nsteps)]
        self.cur_step = 1

    def __str__(self)->str:
        res = '\n```TODO\n'
        for idx, step in enumerate(self.todo, start=1):
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
        self.todo = []
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
        self.todo.append(step)

    def print(self, color:bool=True)->None:
        if not color:
            print(self)
            return
        res = '\033[33m\nTODO\n\033[0m'
        for idx, step in enumerate(self.todo, start=1):
            if idx < self.cur_step:
                res += '\033[32m√\033[0m '   # Green check mark for completed steps
            elif idx == self.cur_step:
                res += '\033[36m→ '   # Cyan arrow for the current step
            else:
                res += '\033[31m×\033[0m '   # Red cross for incomplete steps
            res += f'{step}\n'
        res += '\n'
        if self.cur_step > self.nsteps:
            res += '\033[32m当前所有任务均已完成！\033[0m'
        else:
            res += '\033[33m标注[+][*][-]分别表示已完成、当前步骤、未完成步骤。\n当前正在处理的步骤为第{self.cur_step}步：\n\033[36m{self[self.cur_step-1]}\n\033[0m'
        print(res)
        return

if __name__ == '__main__':
    todo_manager = TODOListManager(['Step 1: Do something', 'Step 2: Do something else', 'Step 3: Finish up'])
    todo_manager.append('Step 4: Extra step')
    print(todo_manager)
    todo_manager.complete_step()
    print(todo_manager)
    todo_manager.complete_all()
    print(todo_manager)
