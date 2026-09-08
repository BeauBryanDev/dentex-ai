// HTTP client for the DentaVision backend.
//
// The backend has exactly three endpoints. There is no /upload, no /analysis/:id and no
// /report/:id — analysis is a single multipart POST that runs both detectors and fuses them,
// and its result is held server-side against a `session_id` rather than fetched back by id.
//
//   POST /analyze   multipart: file + optional session_id  -> AnalyzeResponse
//   POST /chat      json: message + optional session_id    -> ChatResponse
//   GET  /health                                           -> HealthResponse
// */

import axios, { AxiosError } from "axios";
import type { AnalyzeResponse, ChatResponse, HealthResponse } from "../types";

// Port 8012 is not arbitrary — 8000-8007 are occupied by other processes and containers on
// the dev machine. Keep this in sync with .env.example and the uvicorn command.
const API_URL =
  (import.meta as any).env?.VITE_API_URL ?? "http://localhost:8012";
                                  //TODO: IT MUST GOES TO ENVIRONMENT VARIABLE
const api = axios.create({ baseURL: API_URL });

/** Every failure the UI can show, in one shape. `retryable` mirrors the backend's own
 *  judgement: 429/503/504 are worth another attempt, a 415 decode failure is not. */
export class ApiError extends Error {
  status: number;
  retryable: boolean;

  constructor(message: string, status: number, retryable: boolean) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.retryable = retryable;
  }
}

const RETRYABLE = new Set([429, 502, 503, 504]);

/** Translate an axios failure into an ApiError carrying something a dentist can act on.
 *
 *  FastAPI puts the message in `detail`, which is either a string (HTTPException) or an
 *  array of field errors (422 validation). The backend's DentaVisionError handler returns
 *  the string form, and those messages are already written to be shown to a user — see
 *  `client_message` in app/core/exception.py. */
function toApiError(err: unknown, fallback: string): ApiError {
  const ax = err as AxiosError<{ detail?: unknown }>;

  if (ax?.code === "ECONNABORTED") {
    return new ApiError("The backend took too long to respond.", 504, true);
  }
  if (!ax?.response) {
    return new ApiError(
      `Cannot reach the backend at ${API_URL}. Is uvicorn running on port 8012?`,
      0,
      true
    );
  }

  const status = ax.response.status;
  const detail = ax.response.data?.detail;
  let message = fallback;
  if (typeof detail === "string") {
    message = detail;
  } else if (Array.isArray(detail) && detail.length) {
    message = (detail[0] as any)?.msg ?? fallback;
  }

  if (status === 413) message = "That file is too large — the limit is 20 MB.";

  return new ApiError(message, status, RETRYABLE.has(status));
}

/**
 * Run both detectors over one X-ray and fuse the results.
 *
 * Pass an existing `sessionId` to upload a new X-ray into a running consultation: the chat
 * history is kept and re-pointed at the new findings. Omit it to start fresh. Either way the
 * response carries the session id to use from then on.
 *
 */
export async function analyzeImage(
  file: File,
  sessionId?: string | null
): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("file", file);
  if (sessionId) form.append("session_id", sessionId);

  try {
    const res = await api.post<AnalyzeResponse>("/analyze", form, {
      timeout: 60_000,
      // Content-Type is deliberately unset: the browser must add the multipart boundary,
      // and hard-coding "multipart/form-data" omits it and produces a 422.
    });
    return res.data;
  } catch (err) {
    throw toApiError(err, "The X-ray could not be analysed.");
  }
}

/**
 * One conversational turn.
 *
 * No image and no findings are sent — `sessionId` is what connects this turn to the analysis
 * the backend already holds. Omitting it does not merely lose context: the agent is told no
 * X-ray exists and will ask for an upload, which is why the store must persist the id from
 * the analyze response.
 *
 * No history is sent either. The backend owns the message list (`core/session_store.py`);
 * sending a client-side copy would duplicate the turns and double the token bill.
 */
export async function sendChatMessage(
  message: string,
  sessionId?: string | null
): Promise<ChatResponse> {
  try {
    const res = await api.post<ChatResponse>(
      "/chat",
      { message, session_id: sessionId ?? null },
      {
        // Long: a grounded answer may make several retrievals and Claude thinks before
        // replying. 30s was cutting off legitimate turns.
        timeout: 120_000,
        headers: { "Content-Type": "application/json" },
      }
    );
    return res.data;
  } catch (err) {
    throw toApiError(err, "The assistant could not answer.");
  }
}

/** Component-by-component readiness. Used for the header status lamp. */
export async function getHealth(): Promise<HealthResponse> {
  try {
    const res = await api.get<HealthResponse>("/health", { timeout: 5_000 });
    return res.data;
  } catch (err) {
    throw toApiError(err, "Health check failed.");
  }
}

export { API_URL };
