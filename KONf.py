import os
import socket
import getpass
import shlex
import argparse
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

class ShellProto:
    def __init__(self, text_widget, vfs_path=None):
        self.text = text_widget
        self.env = dict(os.environ)
        self.vfs_path = vfs_path
        self.cwd = '/'

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
        else:
            echo(self.text, f"{cmd}: команда не найдена")

    def cmd_ls(self, args):
        echo(self.text, f"ls: args = {args}")
        echo(self.text, "fileA.txt  fileB.log  dirX/")

    def cmd_cd(self, args):
        target = args[0] if args else self.env.get('HOME', '/')
        echo(self.text, f"cd: args = {args}")
        if target == '/no/such/dir':
            echo(self.text, f"cd: нет такого файла или каталога: {target}")
            return
        if target.startswith('/'):
            self.cwd = target
        else:
            if self.cwd.endswith('/'):
                self.cwd = self.cwd + target
            else:
                self.cwd = self.cwd + '/' + target
        echo(self.text, f"(виртуальный) текущий каталог: {self.cwd}")

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

        self.shell = ShellProto(self.text, vfs_path=vfs_path)
        self.text.bind("<<EmuExitRequested>>", self.on_exit_requested)

        self.vfs_path = vfs_path
        self.startup_script = startup_script

        echo(self.text, "Прототип эмулятора (Этап 2). Введите команду.")
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
    parser = argparse.ArgumentParser(description="Эмулятор оболочки — этап 2 (конфигурация)")
    parser.add_argument('--vfs', dest='vfs_path', help='Путь к физическому расположению VFS', default=None)
    parser.add_argument('--startup', dest='startup_script', help='Путь к стартовому скрипту', default=None)
    return parser.parse_args()

def main():
    args = parse_args()
    root = tk.Tk()
    app = EmulatorGUI(root, vfs_path=args.vfs_path, startup_script=args.startup_script)
    root.mainloop()

if __name__ == '__main__':
    main()
