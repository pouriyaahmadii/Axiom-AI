import { NextRequest, NextResponse } from "next/server";

const BACKEND_BASE_URL =
  process.env["AGENTOPS_API_URL"] || "http://127.0.0.1:8000";
const INTERNAL_API_KEY =
  process.env["AGENTOPS_API_KEY"] || "agentops-dev-internal-key";

/**
 * Universal Next.js Server-Side Proxy Route Handler.
 *
 * Security Guardrails:
 * 1. Strictly injects the internal server-to-server `X-API-Key` on the server side.
 * 2. Never exposes credentials to client-side browser JavaScript.
 * 3. Sanitizes and forwards client correlation IDs.
 * 4. Catches backend network outages and returns a standardized JSON error envelope.
 */
async function proxyRequest(
  req: NextRequest,
  { params }: { params: { path: string[] } },
) {
  const subPath = params.path.join("/");
  const searchParams = req.nextUrl.searchParams.toString();
  const targetUrl = `${BACKEND_BASE_URL}/api/v1/${subPath}${
    searchParams ? `?${searchParams}` : ""
  }`;

  const correlationId =
    req.headers.get("x-correlation-id") ||
    `web-proxy-${Math.random().toString(36).substring(2, 10)}`;

  const headers: Record<string, string> = {
    "X-API-Key": INTERNAL_API_KEY,
    "X-Correlation-ID": correlationId,
    Accept: "application/json",
  };

  const clientContentType = req.headers.get("content-type");
  if (clientContentType) {
    headers["Content-Type"] = clientContentType;
  }

  // Forward operator identity headers if present
  const operatorHeader = req.headers.get("x-operator-id");
  if (operatorHeader) {
    headers["X-Operator-Id"] = operatorHeader;
  }

  let body: string | undefined = undefined;
  if (req.method !== "GET" && req.method !== "HEAD") {
    try {
      body = await req.text();
    } catch {
      body = undefined;
    }
  }

  try {
    const backendRes = await fetch(targetUrl, {
      method: req.method,
      headers,
      body,
      // Disable Next.js data cache for live operational state
      cache: "no-store",
    });

    const contentType = backendRes.headers.get("content-type") || "";
    let data: unknown;

    if (contentType.includes("application/json")) {
      data = await backendRes.json();
    } else {
      data = await backendRes.text();
    }

    return NextResponse.json(data, {
      status: backendRes.status,
      headers: {
        "x-correlation-id": correlationId,
      },
    });
  } catch (error) {
    // Gracefully handle backend offline / connection refused
    const errorMessage =
      error instanceof Error ? error.message : "Unknown backend proxy error";

    return NextResponse.json(
      {
        error: {
          code: "BACKEND_UNAVAILABLE",
          message:
            "AgentOps backend API service is unreachable. Ensure the FastAPI container is running.",
          details: errorMessage,
          correlation_id: correlationId,
        },
      },
      {
        status: 502,
        headers: {
          "x-correlation-id": correlationId,
        },
      },
    );
  }
}

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const DELETE = proxyRequest;
