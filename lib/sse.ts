/**
 * parseSSEStream — reads an SSE ReadableStream and yields parsed event objects.
 *
 * Usage:
 *   const res = await fetch('/api/backend/chat/stream', { method: 'POST', ... });
 *   for await (const evt of parseSSEStream(res)) {
 *     if (evt.type === 'token') appendToken(evt.content);
 *     if (evt.type === 'done')  finish(evt);
 *   }
 */
export async function* parseSSEStream(
  response: Response
): AsyncGenerator<Record<string, unknown>> {
  const reader = response.body?.getReader();
  if (!reader) return;

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? ""; // keep incomplete line

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || !trimmed.startsWith("data:")) continue;
      const jsonStr = trimmed.slice(5).trim();
      if (!jsonStr) continue;
      try {
        yield JSON.parse(jsonStr) as Record<string, unknown>;
      } catch {
        // malformed chunk — skip
      }
    }
  }
}
