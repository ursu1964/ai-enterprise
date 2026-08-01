import re
from typing import Literal

from pydantic import Field, model_validator

from .kernel import Compatibility, StrictSpecification


class ColumnSpecification(StrictSpecification):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    type: Literal["uuid", "text", "integer", "bigint", "boolean", "timestamptz", "jsonb"]
    nullable: bool = False
    primary_key: bool = False
    unique: bool = False
    default_sql: str | None = None

    @model_validator(mode="after")
    def safe_default(self) -> "ColumnSpecification":
        if self.default_sql is not None and not re.fullmatch(
            r"(?:now\(\)|gen_random_uuid\(\)|true|false|\d+)", self.default_sql
        ):
            raise ValueError("default SQL is outside the deterministic allowlist")
        return self


class IndexSpecification(StrictSpecification):
    name: str = Field(pattern=r"^ix_[a-z0-9_]+$")
    columns: tuple[str, ...] = Field(min_length=1)
    unique: bool = False


class ForeignKeySpecification(StrictSpecification):
    column: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    referenced_table: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    referenced_column: str = Field(default="id", pattern=r"^[a-z][a-z0-9_]*$")
    on_delete: Literal["RESTRICT", "CASCADE", "SET NULL"] = "RESTRICT"


class EntitySpecification(StrictSpecification):
    table_name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    columns: tuple[ColumnSpecification, ...] = Field(min_length=1)
    indexes: tuple[IndexSpecification, ...] = ()
    foreign_keys: tuple[ForeignKeySpecification, ...] = ()
    audited: bool = True

    @model_validator(mode="after")
    def validate_structure(self) -> "EntitySpecification":
        names = [column.name for column in self.columns]
        if names != sorted(set(names)) or sum(column.primary_key for column in self.columns) != 1:
            raise ValueError("columns must be sorted/unique with exactly one primary key")
        if any(not set(index.columns).issubset(names) for index in self.indexes):
            raise ValueError("index references an unknown column")
        if any(foreign_key.column not in names for foreign_key in self.foreign_keys):
            raise ValueError("foreign key references an unknown local column")
        return self


_SQL_TYPES = {
    "uuid": "UUID",
    "text": "TEXT",
    "integer": "INTEGER",
    "bigint": "BIGINT",
    "boolean": "BOOLEAN",
    "timestamptz": "TIMESTAMPTZ",
    "jsonb": "JSONB",
}


def generate_create_table(entity: EntitySpecification) -> str:
    definitions: list[str] = []
    for column in entity.columns:
        parts = [column.name, _SQL_TYPES[column.type]]
        if column.primary_key:
            parts.append("PRIMARY KEY")
        if not column.nullable:
            parts.append("NOT NULL")
        if column.unique:
            parts.append("UNIQUE")
        if column.default_sql is not None:
            parts.extend(("DEFAULT", column.default_sql))
        definitions.append(" ".join(parts))
    definitions.extend(
        "FOREIGN KEY "
        f"({fk.column}) REFERENCES {fk.referenced_table}({fk.referenced_column}) "
        f"ON DELETE {fk.on_delete}"
        for fk in sorted(entity.foreign_keys, key=lambda item: item.column)
    )
    body = ",\n  ".join(definitions)
    indexes = "\n".join(
        f"CREATE {'UNIQUE ' if index.unique else ''}INDEX {index.name} "
        f"ON {entity.table_name} ({', '.join(index.columns)});"
        for index in sorted(entity.indexes, key=lambda item: item.name)
    )
    return f"CREATE TABLE {entity.table_name} (\n  {body}\n);" + (f"\n{indexes}" if indexes else "")


def classify_database_change(old: EntitySpecification, new: EntitySpecification) -> Compatibility:
    old_columns, new_columns = (
        {column.name: column for column in old.columns},
        {column.name: column for column in new.columns},
    )
    if old.table_name != new.table_name or not set(old_columns).issubset(new_columns):
        return Compatibility.BREAKING
    if any(
        new_columns[name].type != column.type
        or (column.nullable and not new_columns[name].nullable)
        or new_columns[name].primary_key != column.primary_key
        or new_columns[name].unique != column.unique
        or new_columns[name].default_sql != column.default_sql
        for name, column in old_columns.items()
    ):
        return Compatibility.BREAKING
    old_indexes = {index.name: index for index in old.indexes}
    new_indexes = {index.name: index for index in new.indexes}
    old_foreign_keys = {foreign_key.column: foreign_key for foreign_key in old.foreign_keys}
    new_foreign_keys = {foreign_key.column: foreign_key for foreign_key in new.foreign_keys}
    if any(new_indexes.get(key) != value for key, value in old_indexes.items()) or any(
        new_foreign_keys.get(key) != value for key, value in old_foreign_keys.items()
    ):
        return Compatibility.BREAKING
    added = [column for name, column in new_columns.items() if name not in old_columns]
    if any(not column.nullable and column.default_sql is None for column in added):
        return Compatibility.BREAKING
    return Compatibility.CONDITIONALLY_COMPATIBLE if added else Compatibility.COMPATIBLE
