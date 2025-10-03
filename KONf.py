import os
import socket
import getpass
import shlex
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
                # ${VAR}
                j = i+2
                var = ''
                while j < L and s[j] != '}':
                    var += s[j]; j += 1
                if j < L and s[j] == '}':
                    res += env.get(var, '')
                    i = j+1
                else:
                    # нет закрывающей — оставляем "$"
                    res += '$'; i += 1
            else:
                # $VAR
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
    def __init__(self, text_widget):
        self.text = text_widget
        self.env = dict(os.environ)  # snapshot of environment
        self.cwd = '/'  # виртуальный cwd (строка)

    def run_line(self, raw_line, echo_input=True):
        line = raw_line.rstrip('\n')
        if line.strip() == '':
            return
        if echo_input:
            echo(self.text, f"$ {line}")
        # раскрываем переменные
        expanded = expand_env_vars_custom(line, self.env)
        tokens = safe_split(expanded)
        if tokens is None:
            echo(self.text, "Ошибка: неверное использование кавычек")
            return
        cmd = tokens[0]
        args = tokens[1:]
        # dispatch minimal commands
        if cmd == 'exit':
            echo(self.text, "Выход из эмулятора.")
            # сгенерируем событие для GUI чтобы закрыть
            self.text.event_generate("<<EmuExitRequested>>")
        elif cmd == 'ls':
            self.cmd_ls(args)
        elif cmd == 'cd':
            self.cmd_cd(args)
        else:
            echo(self.text, f"{cmd}: команда не найдена")

    def cmd_ls(self, args):
        # Заглушка: печатает свое имя и аргументы, затем фиктивный список.
        echo(self.text, f"ls: args = {args}")
        echo(self.text, "fileA.txt  fileB.log  dirX/")

    def cmd_cd(self, args):
        # Заглушка: печатает свое имя и аргументы, пытается менять cwd без доступа к реальной FS.
        target = args[0] if args else self.env.get('HOME', '/')
        echo(self.text, f"cd: args = {args}")
        # Симулируем ошибку для специального примера
        if target == '/no/such/dir':
            echo(self.text, f"cd: нет такого файла или каталога: {target}")
            return
        # простая смена cwd (без нормализации)
        if target.startswith('/'):
            self.cwd = target
        else:
            # относительный
            if self.cwd.endswith('/'):
                self.cwd = self.cwd + target
            else:
                self.cwd = self.cwd + '/' + target
        echo(self.text, f"(виртуальный) текущий каталог: {self.cwd}")

class EmulatorGUI:
    def __init__(self, root):
        self.root = root
        root.title(window_title())

        # Вывод
        self.text = ScrolledText(root, state='disabled', wrap='word', width=96, height=28)
        self.text.pack(fill='both', expand=True)

        # Ввод
        bottom = tk.Frame(root)
        bottom.pack(fill='x')
        self.prompt = tk.Label(bottom, text='$ ')
        self.prompt.pack(side='left')
        self.entry = tk.Entry(bottom)
        self.entry.pack(side='left', fill='x', expand=True)
        self.entry.bind('<Return>', self.on_enter)

        # логика shell
        self.shell = ShellProto(self.text)
        self.text.bind("<<EmuExitRequested>>", self.on_exit_requested)

        # первоначальное приветствие
        echo(self.text, "Минимальный прототип эмулятора (Этап 1). Введите команду.")
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
