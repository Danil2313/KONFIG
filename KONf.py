import os
import socket
import getpass
import shlex
import argparse
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
import xml.etree.ElementTree as ET
import base64

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
    def __init__(self, name, nodetype='dir', content=None, encoding='text'):
        self.name = name
        self.type = nodetype
        self.children = {}
        self.content = content
        self.encoding = encoding

class VFS:
    def __init__(self):
        self.root = VFSNode('/', 'dir')
    def _add_dir(self, parent, name):
        if name not in parent.children:
            parent.children[name] = VFSNode(name, 'dir')
        return parent.children[name]
    def _add_file(self, parent, name, data, encoding):
        parent.children[name] = VFSNode(name, 'file', content=data, encoding=encoding)
    def _resolve_path(self, path, cwd='/'):
        if path == '':
            path = '.'
        if path.startswith('/'):
            parts = [p for p in path.split('/') if p]
            node = self.root
        else:
            parts = [p for p in (cwd.split('/') if cwd else ['/'])[0:] + [] if p is not None]  # will be replaced below
            if cwd == '/':
                parts = []
            else:
                parts = [p for p in cwd.split('/') if p]
            parts += [p for p in path.split('/') if p]
            node = self.root
        for p in parts:
            if p == '.':
                continue
            if p == '..':
                # move up
                # find parent by walking from root (inefficient but ok for prototype)
                node = self._parent_of(node)
                if node is None:
                    node = self.root
                continue
            if node.type != 'dir' or p not in node.children:
                return None
            node = node.children[p]
        return node
    def _parent_of(self, node):
        if node is self.root:
            return None
        stack = [(self.root, None)]
        while stack:
            cur, parent = stack.pop()
            if cur is node:
                return parent
            if cur.type == 'dir':
                for child in cur.children.values():
                    stack.append((child, cur))
        return None
    def listdir(self, cwd):
        node = self._resolve_path(cwd, '/')
        if node is None or node.type != 'dir':
            return None
        return sorted(node.children.keys())
    def is_dir(self, path, cwd):
        node = self._resolve_path(path, cwd)
        return node is not None and node.type == 'dir'
    def is_file(self, path, cwd):
        node = self._resolve_path(path, cwd)
        return node is not None and node.type == 'file'
    def read_file(self, path, cwd):
        node = self._resolve_path(path, cwd)
        if node is None or node.type != 'file':
            return None
        return node.content, node.encoding
    def change_dir(self, path, cwd):
        if path == '':
            return '/'
        node = self._resolve_path(path, cwd)
        if node is None or node.type != 'dir':
            return None
        # build absolute path string
        path_parts = []
        cur = node
        while cur is not None and cur is not self.root:
            path_parts.append(cur.name)
            cur = self._parent_of(cur)
        return '/' + '/'.join(reversed(path_parts)) if path_parts else '/'
    def load_from_xml(self, xml_path):
        tree = ET.parse(xml_path)
        root_elem = tree.getroot()
        self._parse_elem(root_elem, self.root)
    def _parse_elem(self, elem, parent_node):
        for child in elem:
            if child.tag == 'dir':
                name = child.attrib.get('name', '')
                if name == '':
                    continue
                dnode = self._add_dir(parent_node, name)
                self._parse_elem(child, dnode)
            elif child.tag == 'file':
                name = child.attrib.get('name', '')
                encoding = child.attrib.get('encoding', 'text')
                data = child.text or ''
                if encoding == 'base64':
                    try:
                        raw = base64.b64decode(data)
                    except Exception:
                        raw = data.encode('utf-8', errors='replace')
                    self._add_file(parent_node, name, raw, 'binary')
                else:
                    self._add_file(parent_node, name, data, 'text')

class ShellProto:
    def __init__(self, text_widget, vfs=None):
        self.text = text_widget
        self.env = dict(os.environ)
        self.cwd = '/'
        self.vfs = vfs or VFS()
    def run_line(self, raw_line, echo_input=True):
        line = raw_line.rstrip('\n')
        if line.strip() == '':
            return
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
        elif cmd == 'cat':
            self.cmd_cat(args)
        elif cmd == 'vfsinfo':
            self.cmd_vfsinfo()
        else:
            echo(self.text, f"{cmd}: команда не найдена")
    def cmd_ls(self, args):
        target = args[0] if args else '.'
        if target == '.':
            target = self.cwd
        lst = self.vfs.listdir(target) if target.startswith('/') or target == self.cwd else self.vfs.listdir(target)
        if lst is None:
            echo(self.text, f"ls: нет такого каталога: {target}")
            return
        echo(self.text, f"ls: args = {args}")
        line = []
        for name in lst:
            node = self.vfs._resolve_path((target.rstrip('/') + '/' + name) if not name.startswith('/') else name, self.cwd)
            suffix = '/' if node and node.type == 'dir' else ''
            line.append(name + suffix)
        echo(self.text, '  '.join(line))
    def cmd_cd(self, args):
        target = args[0] if args else self.env.get('HOME', '/')
        echo(self.text, f"cd: args = {args}")
        new = self.vfs.change_dir(target, self.cwd)
        if new is None:
            echo(self.text, f"cd: нет такого файла или каталога: {target}")
            return
        self.cwd = new
        echo(self.text, f"(виртуальный) текущий каталог: {self.cwd}")
    def cmd_cat(self, args):
        if not args:
            echo(self.text, "cat: требуется имя файла")
            return
        target = args[0]
        res = self.vfs.read_file(target, self.cwd)
        if res is None:
            echo(self.text, f"cat: нет такого файла: {target}")
            return
        content, encoding = res
        if encoding == 'binary':
            b64 = base64.b64encode(content).decode('ascii')
            echo(self.text, f"(binary, base64) {b64}")
        else:
            for line in str(content).splitlines() or ['']:
                echo(self.text, line)
    def cmd_vfsinfo(self):
        cnt_files = 0
        cnt_dirs = 0
        stack = [self.vfs.root]
        while stack:
            cur = stack.pop()
            if cur.type == 'dir':
                cnt_dirs += 1
                for c in cur.children.values():
                    stack.append(c)
            else:
                cnt_files += 1
        echo(self.text, f"VFS: dirs={cnt_dirs}, files={cnt_files}")

class EmulatorGUI:
    def __init__(self, root, vfs_path=None, startup_script=None):
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
        self.vfs = VFS()
        if vfs_path and os.path.isfile(vfs_path):
            try:
                self.vfs.load_from_xml(vfs_path)
                echo(self.text, f"[VFS] загружен: {vfs_path}")
            except Exception as e:
                echo(self.text, f"[VFS] ошибка при загрузке: {e}")
        self.shell = ShellProto(self.text, vfs=self.vfs)
        self.text.bind("<<EmuExitRequested>>", self.on_exit_requested)
        self.vfs_path = vfs_path
        self.startup_script = startup_script
        echo(self.text, "Прототип эмулятора (Этап 3). Введите команду.")
        echo(self.text, f"[DEBUG] vfs_path = {self.vfs_path}")
        echo(self.text, f"[DEBUG] startup_script = {self.startup_script}")
        print("DEBUG: vfs_path =", self.vfs_path)
        print("DEBUG: startup_script =", self.startup_script)
        self.entry.focus_set()
        if self.startup_script:
            self.root.after(100, self.run_startup_script)
    def on_enter(self, event):
        line = self.entry.get()
        self.entry.delete(0, tk.END)
        try:
            self.shell.run_line(line, echo_input=True)
        except Exception as e:
            echo(self.text, f"Внутренняя ошибка: {e}")
    def on_exit_requested(self, event=None):
        self.root.quit()
    def run_startup_script(self):
        path = self.startup_script
        if not path:
            return
        if not os.path.isfile(path):
            echo(self.text, f"Ошибка: стартовый скрипт не найден: {path}")
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            echo(self.text, f"Ошибка при чтении скрипта: {e}")
            return
        echo(self.text, f"--- Выполнение стартового скрипта: {path} ---")
        for lineno, raw in enumerate(lines, start=1):
            line = raw.rstrip('\n')
            if line.strip() == '':
                continue
            try:
                self.shell.run_line(line, echo_input=True)
            except Exception as e:
                echo(self.text, f"Ошибка в строке {lineno}: {e}")
                continue
        echo(self.text, f"--- Конец скрипта: {path} ---")

def parse_args():
    parser = argparse.ArgumentParser(description="Эмулятор оболочки — этап 3 (VFS)")
    parser.add_argument('--vfs', dest='vfs_path', help='Путь к XML VFS', default=None)
    parser.add_argument('--startup', dest='startup_script', help='Путь к стартовому скрипту', default=None)
    return parser.parse_args()

def main():
    args = parse_args()
    root = tk.Tk()
    app = EmulatorGUI(root, vfs_path=args.vfs_path, startup_script=args.startup_script)
    root.mainloop()

if __name__ == '__main__':
    main()
