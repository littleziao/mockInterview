import { describe, expect, it } from "vitest";

import { consumeSSEResponse } from "./sse";

function sseResponse(chunks: string[], status = 200): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
  return new Response(stream, { status, headers: { "Content-Type": "text/event-stream" } });
}

describe("consumeSSEResponse", () => {
  it("parses delta frames then done", async () => {
    const deltas: string[] = [];
    let donePayload: unknown = null;
    await consumeSSEResponse(
      sseResponse([
        'event: delta\ndata: {"text":"你好"}\n\n',
        'event: delta\ndata: {"text":"世界"}\n\n',
        'event: done\ndata: {"id":1}\n\n',
      ]),
      {
        onDelta: (text) => deltas.push(text),
        onDone: (payload) => {
          donePayload = payload;
        },
        onError: () => {},
      }
    );
    expect(deltas).toEqual(["你好", "世界"]);
    expect(donePayload).toEqual({ id: 1 });
  });

  it("passes through reset flag on delta", async () => {
    const seen: { text: string; reset: boolean }[] = [];
    await consumeSSEResponse(
      sseResponse([
        'event: delta\ndata: {"text":"原"}\n\n',
        'event: delta\ndata: {"text":"替换","reset":true}\n\n',
      ]),
      {
        onDelta: (text, reset) => seen.push({ text, reset }),
        onDone: () => {},
        onError: () => {},
      }
    );
    expect(seen).toEqual([
      { text: "原", reset: false },
      { text: "替换", reset: true },
    ]);
  });

  it("reassembles frames split across single-byte chunks", async () => {
    const deltas: string[] = [];
    const frame = 'event: delta\ndata: {"text":"abc"}\n\nevent: done\ndata: {}\n\n';
    await consumeSSEResponse(
      sseResponse([...frame]),
      {
        onDelta: (text) => deltas.push(text),
        onDone: () => {},
        onError: () => {},
      }
    );
    expect(deltas).toEqual(["abc"]);
  });

  it("skips heartbeat comments and malformed data lines", async () => {
    const deltas: string[] = [];
    let done = false;
    await consumeSSEResponse(
      sseResponse([
        ": keepalive\n\n",
        'event: delta\ndata: {bad json}\n\n',
        'event: delta\ndata: {"text":"ok"}\n\n',
        'event: done\ndata: {}\n\n',
      ]),
      {
        onDelta: (text) => deltas.push(text),
        onDone: () => {
          done = true;
        },
        onError: () => {},
      }
    );
    expect(deltas).toEqual(["ok"]);
    expect(done).toBe(true);
  });

  it("delivers error frame with status", async () => {
    let detail = "";
    let status = 0;
    await consumeSSEResponse(
      sseResponse(['event: error\ndata: {"detail":"失败","status":502}\n\n']),
      {
        onDelta: () => {},
        onDone: () => {},
        onError: (d, s) => {
          detail = d;
          status = s;
        },
      }
    );
    expect(detail).toBe("失败");
    expect(status).toBe(502);
  });

  it("throws on non-ok response with json detail", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(JSON.stringify({ detail: "校验失败" })));
        controller.close();
      },
    });
    const response = new Response(stream, { status: 400 });
    await expect(
      consumeSSEResponse(response, {
        onDelta: () => {},
        onDone: () => {},
        onError: () => {},
      })
    ).rejects.toThrow("校验失败");
  });

  it("returns early when signal already aborted", async () => {
    let doneCalled = false;
    const controller = new AbortController();
    controller.abort();
    await consumeSSEResponse(
      sseResponse(['event: done\ndata: {}\n\n']),
      {
        onDelta: () => {},
        onDone: () => {
          doneCalled = true;
        },
        onError: () => {},
      },
      controller.signal
    );
    expect(doneCalled).toBe(false);
  });
});
