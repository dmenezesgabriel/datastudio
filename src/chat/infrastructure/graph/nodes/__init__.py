"""LangGraph node implementations for the Text-to-SQL pipeline — each owning its own prompt.

**System prompts live inline, as module constants, on purpose.** Every one of them restates
something the same module type-checks: ``route_intent``'s prompt names the ``Literal`` members
of ``_IntentDecision.kind``; ``plan_widgets`` names its role/view Literals and the widget cap
``_MAX_WIDGETS``; ``generate_widget_view._VIEW_HINT_GUIDANCE`` is a ``dict[WidgetViewHint, str]``
whose missing key is a type error today, and the ``_DATA_ROOT`` prefix it tells the model to
bind is the same one ``_rewrite_state`` parses back out. Prompt assembly is also conditional
(``_element_guidance``, ``repair_sql._CANDIDATE_HINTS``), so an external file could hold only
the leaf strings while the branching stayed here. Moving the text away from the invariant it
mirrors buys editability nobody needs — nothing loads a prompt by name, and the eval harness
varies cases, not prompts — at the cost of the only thing keeping the two in agreement.

``prompts/catalog_prompt.generated.txt`` is the sole exception, and not a counter-example: it
is generated from ``frontend/src/catalog.ts`` by ``npm run gen:prompt`` because it crosses a
TypeScript → Python boundary, and a pre-commit hook diffs it to fail on drift.

Where a prompt must name something owned elsewhere, import the constant and interpolate it
(see ``author_edit_patches._RESTYLE_INSTRUCTIONS`` and
``chat.domain.value_objects.dashboard_layout``) rather than restating the value in prose.
"""
