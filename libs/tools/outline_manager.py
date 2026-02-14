from .tool_manager import AIFunction

class OutlineManager:
    def __init__(self, path:str) -> None:
        self.path = path
        self.outline = {} # time : content
        self.load_outline()
        self.build_function()
    
    def write_outline(self, time:str, content:str) -> None:
        if '|' in time:
            raise ValueError('时间点不能包含竖线字符 "|".')
        if '|' in content:
            # 替换内容中的竖线字符为全角竖线，以避免表格格式问题
            content = content.replace('|', '｜')
        self.outline[time] = content    
    
    def view_outline(self) -> str:
        outline_str = '视频大纲：\n| 时间点 | 大纲内容 |\n| --- | --- |\n'
        for time, content in self.outline.items():
            outline_str += f'| {time} | {content} |\n'
        return outline_str
    
    def __str__(self) -> str:
        return self.view_outline()
    
    def save_outline(self) -> None:
        with open(self.path, 'w', encoding='utf-8') as f:
            for time, content in self.outline.items():
                f.write(f'{time}|{content}\n')
    
    def load_outline(self) -> None:
        self.outline = {}
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                for line in f:
                    if '|' in line:
                        time, content = line.strip().split('|', 1)
                        self.outline[time] = content
        except FileNotFoundError:
            # 如果文件不存在，则保持大纲为空
            pass

    def build_function(self):
        self.function = AIFunction([], [])
        self.function.add_function(
            name='write_outline',
            description='添加或更新视频大纲中的一个时间点和对应内容。时间点和内容都必须是字符串，且不能包含竖线字符 "|".',
            parameters={
                'time': '要添加或更新的大纲时间点，必须是字符串，且不能包含竖线字符 "|".',
                'content': '要添加或更新的大纲内容，必须是字符串，且不能包含竖线字符 "|".'
            },
            required=['time', 'content'],
            function=self.write_outline
        )
        self.function.add_function(
            name='view_outline',
            description='以Markdown表格格式查看当前视频大纲的内容。',
            parameters={},
            required=[],
            function=self.view_outline
        )
        return

    def __call__(self, __func_name:str, *args, **kwargs):
        return self.function(__func_name, *args, **kwargs)

OutlineManager.write_outline.__doc__ = '''write_outline方法用于添加或更新视频大纲中的一个时间点和对应内容。它接受两个参数：
- time: 要添加或更新的大纲时间点，必须是字符串，且不能包含竖线字符 "|".
- content: 要添加或更新的大纲内容，必须是字符串，且不能包含竖线字符 "|".
该方法会将给定的时间点和内容添加到大纲字典中，如果时间点已经存在，则会更新对应的内容。该方法不返回任何值。'''
OutlineManager.view_outline.__doc__ = '''view_outline方法用于以Markdown表格格式查看当前视频大纲的内容。该方法不需要参数。
该方法会将当前大纲字典中的时间点和内容格式化为一个Markdown表格字符串，并返回该字符串。表格的第一行是表头，包含“时间点”和“大纲内容”两列，第二行是分隔符，后续每一行对应一个时间点和内容的条目。'''
OutlineManager.__str__.__doc__ = '''__str__方法用于返回当前视频大纲的字符串表示。该方法不需要参数。
该方法会调用view_outline方法来获取大纲的Markdown表格字符串，并返回该字符串作为当前对象的字符串表示。'''
OutlineManager.__call__.__doc__ = '''__call__方法用于调用当前对象的函数定义列表中的函数。它接受以下参数：
- __func_name: 要调用的函数的名称，必须是之前通过build_function方法添加的函数名称。
- *args: 可选的位置参数，将被传递给函数实现。
- **kwargs: 可选的关键字参数，将被传递给函数实现。
该方法会在函数定义列表中查找与给定名称匹配的函数，如果找到，则调用对应的函数实现并传递参数。如果没有找到匹配的函数，则会抛出一个ValueError异常。'''

if __name__ == '__main__':
    outline_manager = OutlineManager('outline.txt')
    outline_manager.write_outline('00:00', '视频开场介绍')
    outline_manager.write_outline('01:30', '第一部分内容')
    outline_manager.write_outline('03:45', '第二部分内容')
    print(outline_manager.view_outline())
    outline_manager.save_outline()
    new_outline_manager = OutlineManager('outline.txt')
    print(new_outline_manager)