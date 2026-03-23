from __future__ import annotations

import ast
import re
from pathlib import Path

from app.models.document import DocumentType


def _migration_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _extract_documenttype_labels() -> set[str]:
    labels: set[str] = set()

    for path in _migration_dir().glob("*.py"):
        source = path.read_text(encoding="utf-8", errors="ignore")

        labels.update(
            value
            for value in re.findall(
                r"ALTER TYPE documenttype ADD VALUE IF NOT EXISTS '([^']+)'",
                source,
            )
            if not value.startswith("{")
        )

        for enum_args in re.findall(
            r"sa\.Enum\((.*?)name='documenttype'\)",
            source,
            flags=re.DOTALL,
        ):
            labels.update(re.findall(r"'([^']+)'", enum_args))

        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if not any(
                isinstance(target, ast.Name) and target.id == "_DOCUMENTTYPE_VALUES"
                for target in node.targets
            ):
                continue
            if not isinstance(node.value, (ast.Tuple, ast.List)):
                continue

            for element in node.value.elts:
                if isinstance(element, ast.Constant) and isinstance(element.value, str):
                    labels.add(element.value)
                    labels.add(element.value.lower())

    return labels


def test_documenttype_enum_migrations_cover_current_model_values():
    migrated_labels = _extract_documenttype_labels()

    missing = [
        f"{member.name}={member.value}"
        for member in DocumentType
        if member.name not in migrated_labels and member.value not in migrated_labels
    ]

    assert not missing, (
        "Alembic documenttype enum migrations are missing current DocumentType "
        f"members: {', '.join(missing)}"
    )
