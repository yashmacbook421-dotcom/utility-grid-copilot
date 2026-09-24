/** Splits a "**Bottom line:** ... \n\n <detail>" answer (see rag.SYSTEM_PROMPT /
 * agentic.SYSTEM_PROMPT) into the always-visible headline and the collapsible
 * detail beneath it. Falls back to showing the whole thing as detail with no
 * headline if the model didn't follow the format for some reason — a display
 * fallback, not a hidden failure (the raw answer is never dropped).
 */
export function splitBottomLine(markdown: string): { headline: string; rest: string } {
  const marker = "**Bottom line:**";
  if (!markdown.trimStart().startsWith(marker)) {
    return { headline: "", rest: markdown };
  }
  const trimmed = markdown.trimStart();
  const splitIndex = trimmed.indexOf("\n\n");
  if (splitIndex === -1) {
    return { headline: trimmed, rest: "" };
  }
  return { headline: trimmed.slice(0, splitIndex), rest: trimmed.slice(splitIndex + 2).trim() };
}
