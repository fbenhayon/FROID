#!/usr/bin/env python3
import argparse
import os
import stat
import sys
import tempfile
from pathlib import Path
import re

# ANSI Color Codes for beautiful terminal output (no external dependencies required)
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"

PATTERN_START = re.compile(r"^<{7}(?:\s+(.*))?$")
PATTERN_BASE = re.compile(r"^\|{7}(?:\s+.*)?$")
PATTERN_MIDDLE = re.compile(r"^={7}$")
PATTERN_END = re.compile(r"^>{7}(?:\s+(.*))?$")
DEFAULT_EXCLUDES = {".git", "node_modules", "__pycache__", "venv", ".venv", "dist", "build"}


def read_lines(file_path: Path):
    data = file_path.read_bytes()
    encoding = "utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else "utf-8"
    return data.decode(encoding).splitlines(keepends=True), encoding


def write_lines_atomically(file_path: Path, lines, encoding):
    mode = stat.S_IMODE(file_path.stat().st_mode)
    temporary_path = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{file_path.name}.", dir=file_path.parent)
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as output:
            output.write("".join(lines).encode(encoding))
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, file_path)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise

def scan_file_for_markers(file_path: Path):
    """
    Scans a single file for git conflict markers.
    Returns a list of tuples: (line_number, line_content, marker_type)
    """
    try:
        lines, _ = read_lines(file_path)
    except (OSError, UnicodeError) as error:
        return [], str(error)
    found_markers = []
    for line_number, line in enumerate(lines, 1):
        clean_line = line.strip()
        if PATTERN_START.match(clean_line):
            marker_type = "START"
        elif PATTERN_BASE.match(clean_line):
            marker_type = "BASE"
        elif PATTERN_MIDDLE.match(clean_line):
            marker_type = "SEPARATOR"
        elif PATTERN_END.match(clean_line):
            marker_type = "END"
        else:
            continue
        found_markers.append((line_number, line.rstrip("\r\n"), marker_type))
    return found_markers, None

def run_scanner(directory: Path, exclude_dirs=None):
    """
    Recursively scans the directory for files with git markers.
    """
    exclude_dirs = DEFAULT_EXCLUDES if exclude_dirs is None else set(exclude_dirs)
    total_files_scanned = 0
    files_with_conflicts = {}
    read_errors = {}

    for path in directory.rglob("*"):
        if path.is_file():
            if any(part in exclude_dirs for part in path.parts):
                continue
            total_files_scanned += 1
            markers, error = scan_file_for_markers(path)
            if markers:
                files_with_conflicts[path] = markers
            if error:
                read_errors[path] = error

    return total_files_scanned, files_with_conflicts, read_errors

def parse_and_resolve_interactively(file_path: Path):
    try:
        lines, encoding = read_lines(file_path)
    except (OSError, UnicodeError) as error:
        print(f"{COLOR_RED}Erro ao ler {file_path}: {error}{COLOR_RESET}")
        return False, 0

    resolved_lines = []
    index = 0
    resolved_count = 0
    while index < len(lines):
        start_match = PATTERN_START.match(lines[index].strip())
        if not start_match:
            resolved_lines.append(lines[index])
            index += 1
            continue

        block_start = index
        local_label = start_match.group(1) or "LOCAL (HEAD)"
        index += 1
        local_block = []
        while index < len(lines) and not PATTERN_BASE.match(lines[index].strip()) and not PATTERN_MIDDLE.match(lines[index].strip()):
            local_block.append(lines[index])
            index += 1

        has_base = index < len(lines) and PATTERN_BASE.match(lines[index].strip())
        base_block = []
        if has_base:
            index += 1
            while index < len(lines) and not PATTERN_MIDDLE.match(lines[index].strip()):
                base_block.append(lines[index])
                index += 1

        if index >= len(lines) or not PATTERN_MIDDLE.match(lines[index].strip()):
            print(f"{COLOR_RED}Aviso: conflito malformado (sem separador =======) em {file_path}.{COLOR_RESET}")
            resolved_lines.extend(lines[block_start:])
            break

        index += 1
        incoming_block = []
        while index < len(lines) and not PATTERN_END.match(lines[index].strip()):
            incoming_block.append(lines[index])
            index += 1
        if index >= len(lines):
            print(f"{COLOR_RED}Aviso: conflito malformado (sem marcador de fechamento) em {file_path}.{COLOR_RESET}")
            resolved_lines.extend(lines[block_start:])
            break

        incoming_label = PATTERN_END.match(lines[index].strip()).group(1) or "RECEBIDO (INCOMING)"
        original_block = lines[block_start:index + 1]
        index += 1

        print(f"\n{COLOR_CYAN}{'=' * 60}{COLOR_RESET}")
        print(f"{COLOR_BOLD}CONFLITO EM:{COLOR_RESET} {COLOR_GREEN}{file_path.name}{COLOR_RESET}")
        print(f"{COLOR_BOLD}{COLOR_BLUE}OPÇÃO A: {local_label}{COLOR_RESET}\n{'-' * 40}")
        print("".join(local_block).rstrip() or f"{COLOR_YELLOW}(Vazio){COLOR_RESET}")
        if has_base:
            print(f"{COLOR_BOLD}BASE (não selecionável):{COLOR_RESET}\n{'-' * 40}")
            print("".join(base_block).rstrip() or f"{COLOR_YELLOW}(Vazio){COLOR_RESET}")
        print(f"{COLOR_BOLD}{COLOR_YELLOW}OPÇÃO B: {incoming_label}{COLOR_RESET}\n{'-' * 40}")
        print("".join(incoming_block).rstrip() or f"{COLOR_YELLOW}(Vazio){COLOR_RESET}")
        print("\n[1] Aceitar A\n[2] Aceitar B\n[3] Concatenar A + B\n[4] Concatenar B + A\n[5] Pular e preservar o bloco")

        while True:
            try:
                choice = input(f"\n{COLOR_BOLD}Escolha [1-5]: {COLOR_RESET}").strip()
            except (KeyboardInterrupt, EOFError):
                print(f"\n{COLOR_RED}Operação cancelada; nada foi salvo.{COLOR_RESET}")
                return False, resolved_count
            if choice in {"1", "2", "3", "4", "5"}:
                break
            print(f"{COLOR_RED}Opção inválida.{COLOR_RESET}")

        if choice == "1":
            resolved_lines.extend(local_block)
        elif choice == "2":
            resolved_lines.extend(incoming_block)
        elif choice == "3":
            resolved_lines.extend(local_block + incoming_block)
        elif choice == "4":
            resolved_lines.extend(incoming_block + local_block)
        else:
            resolved_lines.extend(original_block)
            continue
        resolved_count += 1

    if resolved_count:
        try:
            write_lines_atomically(file_path, resolved_lines, encoding)
        except (OSError, UnicodeError) as error:
            print(f"{COLOR_RED}Erro ao salvar {file_path}: {error}{COLOR_RESET}")
            return False, 0
        return True, resolved_count
    return False, 0

def main():
    parser = argparse.ArgumentParser(
        description="FROID Git conflict marker scanner and interactive resolver",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "directory", 
        nargs="?", 
        default=".", 
        help="Directory to scan (default: current directory)"
    )
    parser.add_argument(
        "--clean", 
        action="store_true", 
        help="Strip the git conflict markers from the files automatically"
    )
    parser.add_argument(
        "--exclude", 
        nargs="+", 
        help="Additional directories to exclude from scanning"
    )

    args = parser.parse_args()
    
    scan_dir = Path(args.directory).resolve()
    
    exclude = {".git", "node_modules", "__pycache__", "venv", ".venv", "dist", "build"}
    if args.exclude:
        exclude.update(args.exclude)

    print(f"\n{COLOR_BOLD}{COLOR_BLUE}🔍 Iniciando Varredura de Higienização Cognitiva{COLOR_RESET}")
    print(f"{COLOR_BOLD}Diretório de Busca:{COLOR_RESET} {scan_dir}")
    print(f"{COLOR_BOLD}Excluindo pastas:{COLOR_RESET} {', '.join(exclude)}\n")

    total_scanned, conflicts, read_errors = run_scanner(scan_dir, exclude)

    for file_path, error in read_errors.items():
        print(f"{COLOR_RED}Não foi possível ler {file_path}: {error}{COLOR_RESET}")

    if not conflicts and not read_errors:
        print(f"{COLOR_GREEN}{COLOR_BOLD}✅ NENHUM marcador de conflito pendente encontrado!{COLOR_RESET}")
        print(f"Total de arquivos limpos analisados: {total_scanned}\n")
        return 0

    print(f"{COLOR_RED}{COLOR_BOLD}⚠️ ATENÇÃO: Encontrados marcadores de conflito em {len(conflicts)} arquivo(s)!{COLOR_RESET}\n")

    for file_path, markers in conflicts.items():
        rel_path = file_path.relative_to(scan_dir) if file_path.is_relative_to(scan_dir) else file_path
        print(f"{COLOR_BOLD}{COLOR_YELLOW}📄 Arquivo:{COLOR_RESET} {COLOR_BOLD}{rel_path}{COLOR_RESET}")
        for line_num, line_content, marker_type in markers:
            print(f"   [Linha {line_num:4d}] {COLOR_RED}{marker_type.upper()}:{COLOR_RESET} {line_content}")
        print()

    if args.clean and conflicts:
        for file_path in list(conflicts):
            parse_and_resolve_interactively(file_path)
        _, remaining_conflicts, remaining_errors = run_scanner(scan_dir, exclude)
        return 2 if remaining_conflicts or remaining_errors else 0
    if read_errors:
        return 2
    print(f"{COLOR_BOLD}{COLOR_YELLOW}Revise o relatório e use --clean somente após confirmação.{COLOR_RESET}")
    return 1

if __name__ == "__main__":
    sys.exit(main())
