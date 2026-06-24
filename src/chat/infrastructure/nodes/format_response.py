from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from chat.domain.value_objects.chat_state import ChatState

_SYSTEM_PROMPT = (
    "You are a helpful data analyst. Given a question and the SQL query results as a table, "
    "provide a concise natural language answer. Do not include the SQL or the raw table."
)


class _AnswerOutput(BaseModel):
    answer: str


class FormatResponse:
    """Node that uses an LLM with structured output to format query results as natural language.

    Example:
        node = FormatResponse(chat_model)
        result = node({"question": "Count orders", "query_result": ..., "sql_query": ...})
        # result == {"response": "There are 42 orders."}
    """

    def __init__(self, chat_model: BaseChatModel) -> None:
        self._model = chat_model.with_structured_output(_AnswerOutput)

    def __call__(self, state: ChatState) -> dict[str, str]:
        table = state["query_result"].to_markdown_table()
        human_content = f"Question: {state['question']}\n\nResults:\n{table}"
        messages = [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=human_content)]
        result: _AnswerOutput = self._model.invoke(messages)  # type: ignore[assignment]
        return {"response": result.answer}
