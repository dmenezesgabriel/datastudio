from chat.domain.value_objects.chat_state import ChatState
from chat.domain.value_objects.render_tree import RenderTree
from chat.domain.value_objects.view_spec import ChartSpec, ViewSpec
from chat.infrastructure.graph.nodes.assemble_view import AssembleView
from shared.domain.value_objects.query_result import QueryResult


class TestAssembleView:
    def test_assembles_view_from_spec_and_result(self) -> None:
        # arrange
        state = ChatState(  # type: ignore[call-arg]
            question="Revenue?",
            response="Revenue grew.",
            query_result=QueryResult(columns=["month", "rev"], rows=[("Jan", 5)], row_count=1),
            view_spec=ViewSpec(
                kpis=[],
                charts=[
                    ChartSpec(kind="bar", title="t", label_column="month", value_columns=["rev"])
                ],
                show_table=True,
            ),
        )
        # act
        result = AssembleView()(state)
        # assert
        view = result["view"]
        assert isinstance(view, RenderTree)
        assert view.elements["root"].children == ["narrative", "chart-0", "table"]

    def test_falls_back_to_narrative_only_without_result(self) -> None:
        # arrange — failure path: response set, no query_result / view_spec
        state = ChatState(question="x", response="Could not answer.")  # type: ignore[call-arg]
        # act
        result = AssembleView()(state)
        # assert
        view = result["view"]
        assert isinstance(view, RenderTree)
        assert view.elements["root"].children == ["narrative"]
        assert view.elements["narrative"].props["text"] == "Could not answer."
