from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCANNED_PATHS = [
    ROOT / "app",
    ROOT / "static",
    ROOT / "README.md",
    ROOT / "requirements.txt",
    ROOT / "run_tocall_census.py",
]


def test_project_files_do_not_contain_private_local_paths() -> None:
    forbidden = [
        "C:\\",
        "C:/",
        "\\Users\\",
        "/Users/",
        "NC" + "FI",
        "Stu" + "dent",
        "Documents\\New project",
        "Documents/New project",
        "file://",
    ]

    matches: list[str] = []
    for source_path in iter_source_files():
        content = source_path.read_text(encoding="utf-8")
        for pattern in forbidden:
            if pattern in content:
                matches.append(f"{source_path.relative_to(ROOT)} contains {pattern!r}")

    assert matches == []


def iter_source_files():
    for path in SCANNED_PATHS:
        if path.is_file():
            yield path
            continue
        yield from (
            child
            for child in path.rglob("*")
            if child.is_file() and child.suffix not in {".pyc", ".sqlite3"}
        )
