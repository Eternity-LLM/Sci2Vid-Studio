from typing import List

class AIFunction:
    def __init__(self, functions_dict:List[dict], functions:list)->None:
        self.functions = functions
        self.__f = functions
        if len(self.functions) != len(self.__f):
            raise ValueError
        return
    
    def add_function(
        self,
        name:str,
        description:str,
        parameters:dict,
        required:List[str],
        function
    )->None:
        self.functions.append