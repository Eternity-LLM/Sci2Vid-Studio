from .tool_manager import AIFunction
from typing import Union, Tuple
import re
import bisect

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
        res = f'\n{self.topic}({self.begin}~{self.end})\n'
        res += '|时间点|内容|\n|---|---|\n'
        for time, content in self.block.items():
            res += f'|{time}|{content}|\n'
        return res
    
class OutlineManager:
    def __init__(self, path:str) -> None:
        self.path = path
        self.outline = {}  # topic(str) : block(__OutlineBlock)
        return
    
    def 