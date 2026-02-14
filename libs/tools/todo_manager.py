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
