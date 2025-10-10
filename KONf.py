import os
import socket
import getpass
import shlex
import base64
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter.scrolledtext import ScrolledText

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
    def __init__(self, name, is_dir=False, content=None):
        self.name = name
        self.is_dir = is_dir
        self.content = content or b''
        self.children = {} if is_dir else None

    def add_child(self, node):
        if self.is_dir:
            self.children[node.name] = node

class ShellProto:
    def __init__(self, text_widget):
        self.text = text_widget
        self.env = dict(os.environ)
        self.cwd = '/'
        self.history = []
        self.vfs_root = VFSNode('/', True)

    def load_vfs_from_xml(self, xml_path):
        tree = ET.parse(xml_path)
        root_elem = tree.getroot()
        self.vfs_root = self._parse_vfs_element(root_elem)

    def _parse_vfs_element(self, elem):
        node_type = elem.attrib.get('type', 'file')
        name = elem.attrib.get('name', 'unnamed')
        if node_type == 'dir':
            node = VFSNode(name, True)
            for child in elem:
                node.add_child(self._parse_vfs_element(child))
            return node
        else:
            content = base64.b64decode(elem.text or '')
            return VFSNode(name, False, content)

    def _resolve_path(self, path):
        if path.startswith('/'):
            node = self.vfs_root
            parts = path.strip('/').split('/')
        else:
            node = self._get_node_by_path(self.cwd)
            parts = path.strip().split('/')
        for part in parts:
            if part == '' or part == '.':
                continue
            elif part == '..':
                # в корне остаемся
                pass
            elif node.is_dir and part in node.children:
                node = node.children[part]
            else:
                return None
        return node

    def _get_node_by_path(self, path):
        if path == '/':
            return self.vfs_root
        parts = path.strip('/').split('/')
        node = self.vfs_root
        for part in parts:
            if node.is_dir and part in node.children:
                node = node.children[part]
            else:
                return None
        return node

    def run_line(self, raw_line, echo_input=True):
        line = raw_line.rstrip('\n')
        if line.strip() == '':
            return
        if echo_input:
            echo(self.text, f"$ {line}")
        self.history.append(line)
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
        else:
            echo(self.text, f"{cmd}: команда не найдена")

    def cmd_ls(self, args):
        target = args[0] if args else self.cwd
        node = self._resolve_path(target)
        if node is None or not node.is_dir:
            echo(self.text, f"ls: нет такого каталога: {target}")
            return
        echo(self.text, '  '.join(node.children.keys()))

    def cmd_cd(self, args):
        target = args[0] if args else '/'
        node = self._resolve_path(target)
        if node is None or not node.is_dir:
            echo(self.text, f"cd: нет такого файла или каталога: {target}")
            return
        # смена текущей директории
        if target.startswith('/'):
            self.cwd = target.rstrip('/')
        else:
            self.cwd = self.cwd.rstrip('/') + '/' + target

    def cmd_history(self, args):
        for i, cmd in enumerate(self.history, start=1):
            echo(self.text, f"{i}  {cmd}")

    def cmd_head(self, args):
        if not args:
            echo(self.text, "head: требуется имя файла")
            return
        node = self._resolve_path(args[0])
        if node is None or node.is_dir:
            echo(self.text, f"head: файл не найден: {args[0]}")
            return
        lines = node.content.decode(errors='ignore').splitlines()[:10]
        for line in lines:
            echo(self.text, line)

    def cmd_du(self, args):
        target = args[0] if args else '/'
        node = self._resolve_path(target)
        if node is None:
            echo(self.text, f"du: нет такого файла или каталога: {target}")
            return
        size = self._calculate_size(node)
        echo(self.text, f"{size}\t{target}")

    def _calculate_size(self, node):
        if node.is_dir:
            return sum(self._calculate_size(c) for c in node.children.values())
        else:
            return len(node.content)

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

        echo(self.text, "Прототип эмулятора (Этап 4). Введите команду.")
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
