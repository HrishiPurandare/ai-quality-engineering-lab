// Types mirror the FastAPI response models in app/main.py.
export interface Citation {
  number: number;
  source: string;
  section: string;
}

export interface ChatResponse {
  question: string;
  answer: string;
  citations: Citation[];
  contexts: string[];
  refused: boolean;
  guardrails: string[];
}

export interface Health {
  status: string;
  indexed_chunks: number;
}

export const MAX_QUESTION_LENGTH = 1000; // same limit as ChatRequest in app/main.py

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
  }
}

export async function ask(question: string, signal?: AbortSignal): Promise<ChatResponse> {
  let response: Response;
  try {
    response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
      signal,
    });
  } catch {
    throw new ApiError("Can't reach the assistant. Is the API running on port 8000?");
  }
  if (response.status === 503) {
    throw new ApiError("The assistant is unavailable right now (is Ollama running?). Please try again.", 503);
  }
  if (!response.ok) {
    throw new ApiError(`Something went wrong (HTTP ${response.status}). Please try again.`, response.status);
  }
  return (await response.json()) as ChatResponse;
}

export async function health(): Promise<Health> {
  const response = await fetch("/api/health");
  if (!response.ok) throw new ApiError(`HTTP ${response.status}`, response.status);
  return (await response.json()) as Health;
}
