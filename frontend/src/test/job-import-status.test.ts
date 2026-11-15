import { afterEach, describe, expect, it, vi } from "vitest";
import { realApi } from "@/api/real";

const reply = (status: number) => vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ id: "j1" }), { status })));

describe("import from URL status", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("treats 200 as added to an existing job", async () => {
    reply(200);
    expect(await realApi.importJob({ url: "https://x.example.com" })).toEqual({ job: { id: "j1" }, created: false });
  });
  it("treats 201 as a new job", async () => {
    reply(201);
    expect((await realApi.importJob({ url: "https://x.example.com" })).created).toBe(true);
  });
});
