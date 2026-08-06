"""Agentic variant of the recommendation pipeline.

`rag.generate_answer` (used by /api/recommend) always pre-fetches retrieval +
forecast context before asking Claude — a deterministic single-pass RAG
pipeline. Here, Claude is given the retrieval and forecast steps as *tools*
and decides for itself, via a manual tool-use loop, whether and how to use
them for a given question. Contrast the two to see what "agentic" actually
buys you over a fixed pipeline (and what it costs in latency/tokens).
"""

from dataclasses import dataclass, field

from anthropic import Anthropic
from sqlalchemy.orm import Session

from app.data.generate_synthetic_data import REGION_PROFILES
from app.schemas import SourceCitation
from app.services import forecasting, rag

_MAX_ITERATIONS = 5

SYSTEM_PROMPT = """You are a grid operations copilot for a utility company. You help operators \
decide how to respond to demand forecasts using the utility's own operating procedures.

You have two tools:
- search_procedures: search the utility's operating procedures for relevant guidance.
- get_forecast: get the live demand forecast for the operator's region.

Decide for yourself which tools, if any, you need to answer the question well — don't call a \
tool just because it exists. A question about a general grid concept might need neither; a \
question about tonight's peak needs both.

Rules:
- Start with one line, in this exact form: "**Bottom line:** <the single most important action, in one \
sentence>." An operator mid-event doesn't have time to read several paragraphs before finding out what \
to do — that one line must be the actual complete recommendation, not a teaser for the rest.
- Ground every recommendation in retrieved procedure excerpts. Cite them inline like [Source: <title>].
- If you didn't retrieve any procedure covering the situation, say so explicitly rather than inventing one \
— the bottom line in that case is that there isn't one, stated in the same first-line form.
- Be concise and operational: an on-shift engineer should be able to act on your answer immediately.
"""

TOOLS = [
    {
        "name": "search_procedures",
        "description": (
            "Search the utility's operating procedures (peak demand response, solar duck-curve "
            "ramp, EV charging load management, heatwave cooling load) for passages relevant to "
            "a query. Returns the top matching excerpts with similarity scores."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for."},
                "top_k": {"type": "integer", "description": "Number of results to return, 1-10.", "default": 4},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_forecast",
        "description": "Get the live demand forecast for the operator's region, including the forecast peak.",
        "input_schema": {
            "type": "object",
            "properties": {
                "horizon_hours": {"type": "integer", "description": "Hours ahead to forecast, 1-72.", "default": 24},
            },
        },
    },
]


@dataclass
class ToolCallRecord:
    tool: str
    input: dict
    summary: str


@dataclass
class AgenticResult:
    answer: str = ""
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    sources: list[SourceCitation] = field(default_factory=list)
    forecast_context: dict | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    iterations: int = 0


def _execute_tool(
    db: Session, region: str, name: str, tool_input: dict
) -> tuple[str, ToolCallRecord, list[SourceCitation], dict | None]:
    if name == "search_procedures":
        query = tool_input["query"]
        top_k = int(tool_input.get("top_k", 4))
        sources = rag.retrieve(db, query, top_k=top_k)
        result_text = (
            "\n\n".join(f"[Source: {s.title}] (similarity {s.similarity})\n{s.excerpt}" for s in sources)
            or "No matching procedures found."
        )
        record = ToolCallRecord(tool=name, input=tool_input, summary=f"{len(sources)} result(s) for '{query}'")
        return result_text, record, sources, None

    if name == "get_forecast":
        horizon_hours = int(tool_input.get("horizon_hours", 24))
        if region not in REGION_PROFILES:
            record = ToolCallRecord(tool=name, input=tool_input, summary="unknown region")
            return f"No forecast available: unknown region '{region}'.", record, [], None
        try:
            forecast_data = forecasting.forecast(db, region, REGION_PROFILES[region], horizon_hours=horizon_hours)
        except ValueError as exc:
            record = ToolCallRecord(tool=name, input=tool_input, summary="no seeded demand data")
            return str(exc), record, [], None
        summary = rag.summarize_forecast(forecast_data)
        record = ToolCallRecord(tool=name, input=tool_input, summary=summary)
        return summary, record, [], forecast_data

    record = ToolCallRecord(tool=name, input=tool_input, summary="unknown tool")
    return f"Unknown tool '{name}'", record, [], None


def run_agentic_recommend(db: Session, client: Anthropic, model: str, region: str, question: str) -> AgenticResult:
    messages: list[dict] = [{"role": "user", "content": f"Region: {region}\nOperator question: {question}"}]
    result = AgenticResult()

    for iteration in range(1, _MAX_ITERATIONS + 1):
        response = client.messages.create(
            model=model,
            max_tokens=2048,  # headroom for adaptive thinking — see rag.generate_answer for why
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        result.input_tokens += response.usage.input_tokens
        result.output_tokens += response.usage.output_tokens
        result.iterations = iteration

        if response.stop_reason != "tool_use":
            result.answer = "".join(block.text for block in response.content if block.type == "text")
            return result

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result_text, record, sources, forecast_data = _execute_tool(db, region, block.name, block.input)
            result.tool_calls.append(record)
            result.sources.extend(sources)
            if forecast_data is not None:
                result.forecast_context = forecast_data
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result_text})

        messages.append({"role": "user", "content": tool_results})

    result.answer = (
        "I wasn't able to finish reasoning about this within the allotted tool-call budget "
        f"({_MAX_ITERATIONS} iterations). Please try a more specific question."
    )
    return result
