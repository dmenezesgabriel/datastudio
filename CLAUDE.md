## Code style

- Functions: 4-20 lines. Split if longer.
- Files: under 500 lines. Split by responsibility.
- One thing per function, one responsibility per module (SRP).
- Names: specific and unique. Avoid `data`, `handler`, `Manager`.
  Prefer names that return <5 grep hits in the codebase.
- Types: explicit. No `any`, no `Dict`, no untyped functions.
- Type aliases that narrow a generic to a component-specific concrete type use
  the `Typed` prefix (e.g. `TypedChatGraph`), following Python's `TypedDict`
  convention. If an alias is shared across more than one module inside the same
  component, it lives in `<component>/infrastructure/types.py` and is imported
  from there — never redefined locally.
- No code duplication. Extract shared logic into a function/module.
- Early returns over nested ifs. Max 2 levels of indentation.
- Exception messages must include the offending value and expected shape.

## Comments

- Keep your own comments. Don't strip them on refactor — they carry
  intent and provenance.
- Write WHY, not WHAT. Skip `// increment counter` above `i++`.
- Docstrings on public functions: intent + one usage example, use google conventions.
- Reference issue numbers / commit SHAs when a line exists because
  of a specific bug or upstream constraint.

## Dependencies

- Inject dependencies through constructor/parameter, not global/import.
- Wrap third-party libs behind a thin interface owned by this project.

## Structure

- Prefer small focused modules over god files.
- Use Package by component (src/component/domain/entities, src/component/domain/value_objects, src/component/application/ports, src/component/application/use_cases, src/component/infrastructure)
- Data-agnostic core: no dataset identity in `src/`. Table/column names and domain
  values (and prompt examples that name them) are discovered at runtime via
  `SqlEnginePort` — never hardcoded. Sample-dataset identity lives only in
  `scripts/seed_dev_data.py`, `test/`, and `dev_data/`. Use neutral placeholders
  (`events`, `category`, `amount`) in docstrings/examples. Guarded by
  `test/unit/architecture/test_no_dataset_identity_in_src.py`.

## Formatting

- Use the language default formatter (`cargo fmt`, `gofmt`, `prettier`,
  `ruff`, `rubocop -A`). Don't discuss style beyond that.

## Logging

- Structured JSON when logging for debugging / observability.
- Plain text only for user-facing CLI output.
