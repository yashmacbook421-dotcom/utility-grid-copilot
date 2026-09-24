import Anthropic from "@anthropic-ai/sdk";
import { config } from "./config";
import { REGION_PROFILES } from "./regions";
import { forecast, type ForecastData } from "./forecasting";
import { retrieve, summarizeForecast, type SourceCitation } from "./rag";

const MAX_ITERATIONS = 5;

const SYSTEM_PROMPT = `You are a grid operations copilot for a utility company. You help operators \
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
- Be concise and operational: an on-shift engineer should be able to act on your answer immediately.`;

const TOOLS: Anthropic.Tool[] = [
  {
    name: "search_procedures",
    description:
      "Search the utility's operating procedures (peak demand response, solar duck-curve ramp, EV charging load management, heatwave cooling load) for passages relevant to a query. Returns the top matching excerpts with similarity scores.",
    input_schema: {
      type: "object",
      properties: {
        query: { type: "string", description: "What to search for." },
        top_k: { type: "integer", description: "Number of results to return, 1-10.", default: 4 },
      },
      required: ["query"],
    },
  },
  {
    name: "get_forecast",
    description: "Get the live demand forecast for the operator's region, including the forecast peak.",
    input_schema: {
      type: "object",
      properties: {
        horizon_hours: { type: "integer", description: "Hours ahead to forecast, 1-72.", default: 24 },
      },
    },
  },
];

export interface ToolCallRecord {
  tool: string;
  input: Record<string, unknown>;
  summary: string;
}

export interface AgenticResult {
  answer: string;
  toolCalls: ToolCallRecord[];
  sources: SourceCitation[];
  forecastContext: ForecastData | null;
  inputTokens: number;
  outputTokens: number;
  iterations: number;
}

async function executeTool(
  region: string,
  name: string,
  toolInput: Record<string, unknown>,
): Promise<{
  resultText: string;
  record: ToolCallRecord;
  sources: SourceCitation[];
  forecastData: ForecastData | null;
}> {
  if (name === "search_procedures") {
    const query = toolInput["query"] as string;
    const topK = parseInt(String(toolInput["top_k"] ?? 4), 10);
    const sources = await retrieve(query, topK);
    const resultText =
      sources.map((s) => `[Source: ${s.title}] (similarity ${s.similarity})\n${s.excerpt}`).join("\n\n") ||
      "No matching procedures found.";
    return {
      resultText,
      record: { tool: name, input: toolInput, summary: `${sources.length} result(s) for '${query}'` },
      sources,
      forecastData: null,
    };
  }

  if (name === "get_forecast") {
    const horizonHours = parseInt(String(toolInput["horizon_hours"] ?? 24), 10);
    if (!(region in REGION_PROFILES)) {
      return {
        resultText: `No forecast available: unknown region '${region}'.`,
        record: { tool: name, input: toolInput, summary: "unknown region" },
        sources: [],
        forecastData: null,
      };
    }
    try {
      const forecastData = await forecast(region, REGION_PROFILES[region], horizonHours);
      const summary = summarizeForecast(forecastData);
      return {
        resultText: summary,
        record: { tool: name, input: toolInput, summary },
        sources: [],
        forecastData,
      };
    } catch (e) {
      return {
        resultText: e instanceof Error ? e.message : String(e),
        record: { tool: name, input: toolInput, summary: "no seeded demand data" },
        sources: [],
        forecastData: null,
      };
    }
  }

  return {
    resultText: `Unknown tool '${name}'`,
    record: { tool: name, input: toolInput, summary: "unknown tool" },
    sources: [],
    forecastData: null,
  };
}

function blockToDict(block: Anthropic.ContentBlock): Record<string, unknown> {
  if (block.type === "text") return { type: "text", text: block.text };
  if (block.type === "tool_use") return { type: "tool_use", id: block.id, name: block.name, input: block.input };
  if (block.type === "thinking") return { type: "thinking", thinking: block.thinking, signature: block.signature };
  if (block.type === "redacted_thinking") return { type: "redacted_thinking", data: block.data };
  return { type: (block as { type: string }).type };
}

export async function runAgenticRecommend(
  client: Anthropic,
  model: string,
  region: string,
  question: string,
): Promise<AgenticResult> {
  const messages: Anthropic.MessageParam[] = [
    { role: "user", content: `Region: ${region}\nOperator question: ${question}` },
  ];

  const result: AgenticResult = {
    answer: "",
    toolCalls: [],
    sources: [],
    forecastContext: null,
    inputTokens: 0,
    outputTokens: 0,
    iterations: 0,
  };

  for (let iteration = 1; iteration <= MAX_ITERATIONS; iteration++) {
    const response = await client.messages.create({
      model,
      max_tokens: 2048,
      system: SYSTEM_PROMPT,
      tools: TOOLS,
      messages,
    });

    result.inputTokens += response.usage.input_tokens;
    result.outputTokens += response.usage.output_tokens;
    result.iterations = iteration;

    if (response.stop_reason !== "tool_use") {
      result.answer = response.content
        .filter((b): b is Anthropic.TextBlock => b.type === "text")
        .map((b) => b.text)
        .join("");
      return result;
    }

    messages.push({ role: "assistant", content: response.content.map(blockToDict) as unknown as Anthropic.ContentBlockParam[] });

    const toolResults: Anthropic.ToolResultBlockParam[] = [];
    for (const block of response.content) {
      if (block.type !== "tool_use") continue;
      const { resultText, record, sources, forecastData } = await executeTool(region, block.name, block.input as Record<string, unknown>);
      result.toolCalls.push(record);
      result.sources.push(...sources);
      if (forecastData) result.forecastContext = forecastData;
      toolResults.push({ type: "tool_result", tool_use_id: block.id, content: resultText });
    }

    messages.push({ role: "user", content: toolResults });
  }

  result.answer =
    `I wasn't able to finish reasoning about this within the allotted tool-call budget ` +
    `(${MAX_ITERATIONS} iterations). Please try a more specific question.`;
  return result;
}
