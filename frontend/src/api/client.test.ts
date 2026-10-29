import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch } from "./client";

describe("API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("always sends same-origin credentials", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" }
      })
    );

    await apiFetch<{ ok: boolean }>("/api/v1/meta");

    expect(fetchMock).toHaveBeenCalledOnce();
    const [, init] = fetchMock.mock.calls[0];
    expect(init?.credentials).toBe("include");
  });

  it("surfaces FastAPI detail messages", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "authentication required" }), {
        status: 401,
        headers: { "content-type": "application/json" }
      })
    );

    await expect(apiFetch("/api/v1/auth/me")).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
      message: "authentication required"
    });
  });
});
