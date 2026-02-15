from .tool_manager import AIFunction
from typing import Union, Tuple
import re

class __VideoTime_hms:
    def __init__(self, h:int, m:int, s:float)->None:
        if s<0 or m<0 or h<0:
            raise ValueError(f'Invalid time, hour={h}, minute={m}, second={s}.')
        self.h, self.m, self.s = h, m, s
        self.flatten()
        return

    def flatten(self)->None:
        h, m, s = self.h, self.m, self.s
        if h%1!=0:
            hm = (h%1)*60
            m += hm
            h = int(h)
        if m%1!=0:
            ms = (m%1)*60
            s += ms
            m = int(m)

        if s>=60:
            sm = s//60
            s = s%60
            m += sm
        if m>=60:
            mh = m//60
            m = m%60
            h += mh
        self.h, self.m, self.s = h, m, s
        return
    
    def __str__(self)->str:
        return f'{self.h}:{self.m}:{self.s}'

    def __eq__(self, other):
        return self.h==other.h and self.m==other.m and abs(self.s-other.s)<=0.01
    
    def __ne__(self, other):
        return self.h!=other.h or self.m!=other.m or abs(self.s-other.s)>0.01
    
    def __lt__(self, other):
        if self.h>other.h:
            return False
        elif self.h<other.h:
            return True
        
        # self.h == other.h
        elif self.m>other.m:
            return False
        elif self.m<other.m:
            return True
        
        # self.m == other.m
        elif abs(self.s-other.s)>0.01:
            return self.s<other.s
        else:
            return False  # self==other

    def __le__(self, other):
        if self.h>other.h:
            return False
        elif self.h<other.h:
            return True
        
        # self.h == other.h
        elif self.m>other.m:
            return False
        elif self.m<other.m:
            return True
        
        # self.m == other.m
        elif abs(self.s-other.s)>0.01:
            return self.s<other.s
        else:
            return True  # self==other

    def __gt__(self, other):
        if self.h>other.h:
            return True
        elif self.h<other.h:
            return False
        
        # self.h == other.h
        elif self.m>other.m:
            return True
        elif self.m<other.m:
            return False
        
        # self.m == other.m
        elif abs(self.s-other.s)>0.01:
            return self.s>other.s
        else:
            return False  # self==other

    def __ge__(self, other):
        if self.h>other.h:
            return True
        elif self.h<other.h:
            return False
        
        # self.h == other.h
        elif self.m>other.m:
            return True
        elif self.m<other.m:
            return False
        
        # self.m == other.m
        elif abs(self.s-other.s)>0.01:
            return self.s>other.s
        else:
            return True  # self==other


class VideoTime(__VideoTime_hms):
    def __init__(
        self,
        time:Union[
            str,
            __VideoTime_hms, 'VideoTime'
            Tuple[int, int, float]
        ]
    )->None:
        if isinstance(time, tuple):
            if len(time)!=3:
                raise ValueError(f'Invalid tuple {time}.')
            h, m, s = time
            super().__init__(h, m, s)
            return
        elif isinstance(time, __VideoTime_hms) or isinstance(time, VideoTime):
            self.h, self.m, self.s = time.h, time.m, time.s
            self.flatten()
            return
        elif isinstance(time, str):
            # 使用正则提取所有数字（包括整数和小数）
            numbers = re.findall('\\d+\\.?\\d*', time)
            if len(numbers) < 3:
                raise ValueError(f"Could not find enough numbers in time string: '{time}'")
            
            # 只取前三个数字，按照出现的顺序分别作为时、分、秒
            try:
                # 尝试将数字转换为对应的类型
                # 前两个作为整数（分钟和小时通常是整数）
                h = float(numbers[0])
                m = float(numbers[1])
                # 最后一个可以是浮点数（秒可以有小数）
                s = float(numbers[2])
                
                # 如果有更多数字，可以发出警告
                if len(numbers) > 3:
                    import warnings
                    warnings.warn(f"Found more than 3 numbers in time string, only first 3 are used: '{time}'")
                
                super().__init__(h, m, s)
                return
            except:
                raise ValueError
            
class __OutlineBlock:
    def __init__(self, topic:str, begin:VideoTime, end:VideoTime)->None:
        if not isinstance(begin, VideoTime):
            begin = VideoTime(begin)
        if not isinstance(end, VideoTime):
            end = VideoTime(end)
        self.begin, self.end = begin, end
        self.topic = str(topic)
        self.block = {}
        return

    def write(self, time:Union[str, VideoTime], content:str)->None:
        if isinstance(time, str):
            time=VideoTime(time)
        if time < self.begin or time > self.end:
            raise ValueError('The corresponding time is not within the range of this block. ')
        content = str(content)
        if '|' in content:
            content = content.replace('|', '｜')
        self.block[time] = content
        return
    
    def encode(self)->str:
        res = f'\n{self.topic}\n'
        for time, content in self.block.items():
            res += f'{time}|{content}\n'
        res += '*****'
    
    def decode(self, block:str)->None:
        self.block = {}
        lines = block.splitlines()
        self.topic = lines.pop(0)
        times = []
        for line in lines:
            if '|' in line:
                time, content = line.strip().split('|', 1)
                time = VideoTime(time)
                self.block[time] = content
                times.append(time)
            elif '*****' in line:
                break
        self.begin = times[0]
        self.end = times[-1]
        return
    
    def __str__(self):
        res = f'{self.topic}({self.begin}~{self.end})\n'
        res += '|时间点|内容|\n|---|---|\n'
        for time, content in self.block.items():
            res += f'|{time}|{content}|\n'
        return res
    
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
    outline_manager.write_outline('00:00:00', '视频开场介绍')
    outline_manager.write_outline('00:01:30', '第一部分内容')
    outline_manager.write_outline('01:03:45', '第二部分内容')
    print(outline_manager.view_outline())
    outline_manager.save_outline()
    new_outline_manager = OutlineManager('outline.txt')
    print(new_outline_manager)