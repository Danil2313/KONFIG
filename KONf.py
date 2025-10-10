import os
import socket
import getpass
import shlex
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
import base64
import xml.etree.ElementTree as ET

def window_title():
    user = getpass.getuser()
    host = socket.gethostname()
    return f"Эмулятор - [{user}@{host}]"

def safe_split(command_line):
    try:
        return shlex.split(command_line)
    except ValueError:
        return None

def echo(text_widget, *lines):
    text_widget.configure(state='normal')
    for line in lines:
        text_widget.insert(tk.END, line + '\n')
    text_widget.see(tk.END)
    text_widget.configure(state='disabled')

def expand_env_vars_custom(s, env):
    res = ''
    i = 0
    L = len(s)
    while i < L:
        ch = s[i]
        if ch == '$':
            if i+1 < L and s[i+1] == '{':
                j = i+2
                var = ''
                while j < L and s[j] != '}':
                    var += s[j]; j += 1
                if j < L and s[j] == '}':
                    res += env.get(var, '')
                    i = j+1
                else:
                    res += '$'; i += 1
            else:
                j = i+1
                var = ''
                while j < L and (s[j].isalnum() or s[j] == '_'):
                    var += s[j]; j += 1
                if var:
                    res += env.get(var, '')
                    i = j
                else:
                    res += '$'; i += 1
        else:
            res += ch; i += 1
    return res

class VFSNode:
    def __init__(self, name, is_dir=True, content=None):
        self.name = name
        self.is_dir = is_dir
        self.content = content
        self.children = {} if is_dir else None

class VFS:
    def __init__(self):
        self.root = VFSNode('/', True)

    def load_from_xml(self, xml_file):
        tree = ET.parse(xml_file)
        root_elem = tree.getroot()
        self._load_node(self.root, root_elem)

    def _load_node(self, parent_node, xml_elem):
        for elem in xml_elem:
            if elem.tag == 'dir':
                node = VFSNode(elem.attrib['name'], True)
                parent_node.children[node.name] = node
                self._load_node(node, elem)
            elif elem.tag == 'file':
                data = base64.b64decode(elem.text.encode()) if elem.text else b''
                node = VFSNode(elem.attrib['name'], False, data)
                parent_node.children[node.name] = node

    def resolve_path(self, path, cwd='/'):
        if path.startswith('/'):
            node = self.root
            parts = path.strip('/').split('/')
        else:
            node = self._resolve_path(cwd)
            parts = path.split('/')
        for part in parts:
            if not part or part == '.':
                continue
            if part == '..':
                # Не реализуем возврат выше корня
                continue
            if part not in node.children:
                return None
            node = node.children[part]
        return node

    def _resolve_path(self, path):
        return self.resolve_path(path)

class ShellProto:
    def __init__(self, text_widget):
        self.text = text_widget
        self.env = dict(os.environ)
        self.cwd = '/'
        self.vfs = VFS()
        # Загружаем минимальный VFS по умолчанию
        self.vfs.load_from_xml('vfs_minimal.xml')
        self.history = []

    def run_line(self, raw_line, echo_input=True):
        line = raw_line.rstrip('\n')
        if line.strip() == '':
            return
        self.history.append(line)
        if echo_input:
            echo(self.text, f"$ {line}")
        expanded = expand_env_vars_custom(line, self.env)
        tokens = safe_split(expanded)
        if tokens is None:
            echo(self.text, "Ошибка: неверное использование кавычек")
            return
        cmd = tokens[0]
        args = tokens[1:]
        if cmd == 'exit':
            echo(self.text, "Выход из эмулятора.")
            self.text.event_generate("<<EmuExitRequested>>")
        elif cmd == 'ls':
            self.cmd_ls(args)
        elif cmd == 'cd':
            self.cmd_cd(args)
        elif cmd == 'history':
            self.cmd_history(args)
        elif cmd == 'head':
            self.cmd_head(args)
        elif cmd == 'du':
            self.cmd_du(args)
        elif cmd == 'rmdir':
            self.cmd_rmdir(args)
        else:
            echo(self.text, f"{cmd}: команда не найдена")

    def cmd_ls(self, args):
        node = self.vfs.resolve_path(args[0] if args else self.cwd)
        if node is None or not node.is_dir:
            echo(self.text, f"ls: каталог не найден: {args[0] if args else self.cwd}")
            return
        echo(self.text, '  '.join(node.children.keys()))

    def cmd_cd(self, args):
        target = args[0] if args else self.env.get('HOME', '/')
        node = self.vfs.resolve_path(target, self.cwd)
        if node is None or not node.is_dir:
            echo(self.text, f"cd: нет такого файла или каталога: {target}")
            return
        # просто меняем cwd
        self.cwd = target if target.startswith('/') else self.cwd.rstrip('/') + '/' + target

    def cmd_history(self, args):
        for i, cmd in enumerate(self.history, 1):
            echo(self.text, f"{i}: {cmd}")

    def cmd_head(self, args):
        if not args:
            echo(self.text, "head: требуется имя файла")
            return
        node = self.vfs.resolve_path(args[0], self.cwd)
        if node is None or node.is_dir:
            echo(self.text, f"head: файл не найден: {args[0]}")
            return
        content = node.content.decode(errors='ignore').splitlines()
        for line in content[:10]:
            echo(self.text, line)

    def cmd_du(self, args):
        node = self.vfs.resolve_path(args[0] if args else self.cwd)
        if node is None:
            echo(self.text, f"du: путь не найден: {args[0] if args else self.cwd}")
            return
        size = self._du_size(node)
        echo(self.text, f"{size}\t{args[0] if args else self.cwd}")

    def _du_size(self, node):
        if node.is_dir:
            return sum(self._du_size(child) for child in node.children.values())
        else:
            return len(node.content)

    def cmd_rmdir(self, args):
        if not args:
            echo(self.text, "rmdir: требуется имя каталога")
            return
        path = args[0]
        if path == '/':
            echo(self.text, "rmdir: нельзя удалить корень")
            return
        parent_path, _, dir_name = path.rstrip('/').rpartition('/')
        parent_node = self.vfs.resolve_path(parent_path if parent_path else '/')
        if parent_node is None or not parent_node.is_dir:
            echo(self.text, f"rmdir: родительский каталог не найден: {parent_path}")
            return
        node_to_remove = parent_node.children.get(dir_name)
        if node_to_remove is None or not node_to_remove.is_dir:
            echo(self.text, f"rmdir: каталог не найден: {path}")
            return
        if node_to_remove.children:
            echo(self.text, f"rmdir: каталог не пуст: {path}")
            return
        del parent_node.children[dir_name]
        echo(self.text, f"Каталог удален: {path}")

class EmulatorGUI:
    def __init__(self, root):
        self.root = root
        root.title(window_title())
        self.text = ScrolledText(root, state='disabled', wrap='word', width=96, height=28)
        self.text.pack(fill='both', expand=True)
        bottom = tk.Frame(root)
        bottom.pack(fill='x')
        self.prompt = tk.Label(bottom, text='$ ')
        self.prompt.pack(side='left')
        self.entry = tk.Entry(bottom)
        self.entry.pack(side='left', fill='x', expand=True)
        self.entry.bind('<Return>', self.on_enter)
        self.shell = ShellProto(self.text)
        self.text.bind("<<EmuExitRequested>>", self.on_exit_requested)
        echo(self.text, "Прототип эмулятора (Этап 5). Введите команду.")
        self.entry.focus_set()

    def on_enter(self, event):
        line = self.entry.get()
        self.entry.delete(0, tk.END)
        try:
            self.shell.run_line(line, echo_input=True)
        except Exception as e:
            echo(self.text, f"Внутренняя ошибка: {e}")

    def on_exit_requested(self, event=None):
        self.root.quit()

def main():
    root = tk.Tk()
    app = EmulatorGUI(root)
    root.mainloop()

if __name__ == '__main__':
    main()
