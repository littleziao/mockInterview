// 消费 Server-Sent Events 流（fetch + ReadableStream，因为 EventSource 不支持 POST）。
// 后端 /interview-sessions/{id}/answers 与 /interviews/{id}/sessions 用 SSE 推送：
//   event: delta  data: {"text": "...", "reset"?: true}  // 逐字追加 / 降级时整体替换
//   event: done   data: <InterviewSession>               // 流结束，整体替换 session
//   event: error  data: {"detail": "...", "status": 400|502}

export type SSEHandlers = {
  onDelta: (text: string, reset: boolean) => void;
  onDone: (payload: unknown) => void;
  onError: (detail: string, status: number) => void;
};

export async function consumeSSEResponse(
  response: Response,
  handlers: SSEHandlers,
  signal?: AbortSignal,
): Promise<void> {
  if (!response.ok) {
    // 非 2xx（预检失败等仍走标准 JSON 错误体）。
    const detail = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(detail?.detail ?? "提交失败");
  }
  if (!response.body) {
    throw new Error("响应不支持流式读取");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      if (signal?.aborted) {
        await reader.cancel();
        return;
      }
      const { value, done } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      let separator: number;
      while ((separator = buffer.indexOf("\n\n")) >= 0) {
        const frame = buffer.slice(0, separator);
        buffer = buffer.slice(separator + 2);

        let event = "message";
        const dataLines: string[] = [];
        for (const line of frame.split("\n")) {
          if (line.startsWith("event:")) {
            event = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            dataLines.push(line.slice(5).trim());
          }
        }
        if (!dataLines.length) {
          continue;
        }

        let payload: unknown;
        try {
          payload = JSON.parse(dataLines.join("\n"));
        } catch {
          continue; // 跳过半截帧
        }

        if (event === "delta") {
          const data = payload as { text?: string; reset?: boolean };
          handlers.onDelta(data.text ?? "", Boolean(data.reset));
        } else if (event === "done") {
          handlers.onDone(payload);
        } else if (event === "error") {
          const data = payload as { detail?: string; status?: number };
          handlers.onError(data.detail ?? "提交失败", data.status ?? 500);
        }
      }
    }
  } finally {
    decoder.decode(); // flush
  }
}
