from pathlib import Path


def _emit(file_path: Path, content: str, dry_run: bool) -> None:
    if dry_run:
        print(f"# --- {file_path} (dry run) ---")
        print(content, end="" if content.endswith("\n") else "\n")
    else:
        file_path.write_text(content)


def append_to_list(file_path: Path, list_var: str, entry_text: str, dry_run: bool = False) -> None:
    """Insert entry_text just before the closing bracket of a top-level `list_var = [ ... ]`.

    entry_text must include its own indentation and trailing newline. The closing `]` is
    expected at column 0 (as it is for the top-level lists in the target config modules).
    """
    lines = file_path.read_text().splitlines(keepends=True)

    start = next(
        (i for i, line in enumerate(lines) if line.startswith(f"{list_var} = [")),
        None,
    )
    if start is None:
        raise ValueError(f"Could not find `{list_var} = [` in {file_path}")

    close = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("]")),
        None,
    )
    if close is None:
        raise ValueError(f"Could not find closing `]` for `{list_var}` in {file_path}")

    lines.insert(close, entry_text)
    _emit(file_path, "".join(lines), dry_run)


def append_secret(file_path: Path, line_text: str, dry_run: bool = False) -> None:
    """Insert line_text after the last `SecretString(...)` assignment in a secrets module.

    Keeps the trailing `SecretString.populate_cache_sync()` call as the final statement.
    line_text should not include a trailing newline.
    """
    lines = file_path.read_text().splitlines(keepends=True)

    last_assignment = next(
        (i for i in range(len(lines) - 1, -1, -1) if "SecretString(" in lines[i]),
        None,
    )
    if last_assignment is None:
        raise ValueError(f"Could not find a SecretString assignment in {file_path}")

    lines.insert(last_assignment + 1, line_text + "\n")
    _emit(file_path, "".join(lines), dry_run)
