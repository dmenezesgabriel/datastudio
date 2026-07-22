"""Immutable value objects describing one table's columns."""

from dataclasses import dataclass

from shared.domain.errors import InvariantViolationError


@dataclass(frozen=True)
class ColumnDescriptor:
    """One column of a table, as the engine reports it.

    Example:
        column = ColumnDescriptor(name="amount", data_type="DOUBLE")
    """

    name: str
    data_type: str

    def __post_init__(self) -> None:
        """Reject a column that cannot be referred to."""
        if not self.name:
            raise InvariantViolationError(
                f"ColumnDescriptor.name={self.name!r} is empty; expected a column name"
            )


@dataclass(frozen=True)
class TableSchema:
    """A table and the columns it holds.

    Names and types only — enough to refer to a column, deliberately not the annotated
    DDL the model is prompted with (see ``SqlEnginePort.get_table_schema``).

    Example:
        schema = TableSchema(
            name="events",
            columns=(ColumnDescriptor(name="amount", data_type="DOUBLE"),),
        )
    """

    name: str
    columns: tuple[ColumnDescriptor, ...]

    def __post_init__(self) -> None:
        """Reject a table that cannot be referred to."""
        if not self.name:
            raise InvariantViolationError(
                f"TableSchema.name={self.name!r} is empty; expected a table name"
            )
