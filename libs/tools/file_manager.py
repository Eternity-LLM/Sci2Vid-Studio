class TextFileContent(str):
    def __init__(self, file_name: str, file_content: str) -> None:
        self.fname, self.fcont = file_name, file_content
        self.template = f'[file name]: {file_name}\n[file content begin]{file_content}[file content end]\n'
        super().__init__(self.template)
    def save(self, encoding:str='utf-8')->None:
        with open(self.fname, mode='w', encoding=encoding) as f:
            f.write(self.fcont)
        return
