import sys
import argparse
from typing import List


class DependencyConfig:
    def __init__(self):
        self.package_name = ""
        self.repo_url = ""
        self.test_mode = False
        self.tree_output = False
        self.max_depth = 10
        self.filter = ""
        self.errors: List[str] = []

    def validate(self) -> bool:
        self.errors = []

        if not self.package_name:
            self.errors.append("Не указано имя пакета (--package)")

        if not self.repo_url:
            self.errors.append("Не указан репозиторий (--repo)")

        if self.max_depth < 1:
            self.errors.append("Максимальная глубина должна быть положительным числом")

        if self.max_depth > 100:
            self.errors.append("Максимальная глубина не может превышать 100")

        return len(self.errors) == 0

    def print_config(self):
        print("=== ПАРАМЕТРЫ КОНФИГУРАЦИИ ===")
        print(f"package: {self.package_name}")
        print(f"repo: {self.repo_url}")
        print(f"test-mode: {self.test_mode}")
        print(f"tree-output: {self.tree_output}")
        print(f"max-depth: {self.max_depth}")
        print(f"filter: {self.filter if self.filter else '(не задан)'}")
        print("=" * 33)


def parse_arguments() -> DependencyConfig:
    config = DependencyConfig()

    parser = argparse.ArgumentParser(description="Инструмент визуализации графа зависимостей")

    parser.add_argument('--package', required=True, help='Имя анализируемого пакета')
    parser.add_argument('--repo', required=True, help='URL репозитория или путь к файлу')
    parser.add_argument('--test-mode', action='store_true', help='Режим тестового репозитория')
    parser.add_argument('--tree-output', action='store_true', help='Вывод в формате ASCII-дерева')
    parser.add_argument('--max-depth', type=int, default=10, help='Максимальная глубина анализа')
    parser.add_argument('--filter', default='', help='Подстрока для фильтрации пакетов')

    try:
        args = parser.parse_args()

        config.package_name = args.package
        config.repo_url = args.repo
        config.test_mode = args.test_mode
        config.tree_output = args.tree_output
        config.max_depth = args.max_depth
        config.filter = args.filter

    except SystemExit:
        sys.exit(0)
    except Exception as e:
        config.errors.append(f"Ошибка парсинга аргументов: {str(e)}")

    return config


def print_errors(errors: List[str]):
    print("ОШИБКИ КОНФИГУРАЦИИ:", file=sys.stderr)
    for error in errors:
        print(f"  • {error}", file=sys.stderr)
    print("\nИспользуйте --help для справки", file=sys.stderr)


def main():
    print("=== ИНСТРУМЕНТ ВИЗУАЛИЗАЦИИ ГРАФА ЗАВИСИМОСТЕЙ ===")
    print("Этап 1: Минимальный прототип с конфигурацией\n")

    config = parse_arguments()

    if not config.validate():
        print_errors(config.errors)
        sys.exit(1)

    config.print_config()

    print("\nКонфигурация успешно загружена.")


if __name__ == "__main__":
    main()