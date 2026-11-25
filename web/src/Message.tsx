import type { ChatResponse } from "./api";

export interface ChatMessage {
  id: number;
  role: "user" | "assistant" | "error";
  text: string;
  response?: ChatResponse;
}

// Turn guardrail rule names from the API into words a customer understands.
function guardrailNotice(rules: string[]): string | null {
  if (rules.some((rule) => rule.startsWith("input:") && rule !== "input:redacted_card")) {
    return "Blocked by a safety check";
  }
  if (rules.some((rule) => rule.startsWith("output:"))) return "Reply replaced by a safety check";
  return null;
}

export function Message({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="message user" data-testid="user-message">
        {message.text}
      </div>
    );
  }
  if (message.role === "error") {
    return (
      <div className="message error" role="alert" data-testid="error-message">
        {message.text}
      </div>
    );
  }

  const response = message.response!;
  const notice = guardrailNotice(response.guardrails);
  return (
    <article
      className="message assistant"
      data-testid="assistant-message"
      data-refused={response.refused}
      data-guardrails={response.guardrails.join(" ")}
    >
      <p className="answer" data-testid="answer-text">
        {message.text}
      </p>
      <div className="badges">
        {notice && (
          <span className="badge badge-guard" data-testid="guardrail-badge" title={response.guardrails.join(", ")}>
            {notice}
          </span>
        )}
        {response.guardrails.includes("input:redacted_card") && (
          <span className="badge badge-info" data-testid="redacted-badge">
            Card number hidden from the assistant
          </span>
        )}
        {response.refused && !notice && (
          <span className="badge badge-muted" data-testid="refused-badge">
            Not covered by NovaBank policies
          </span>
        )}
      </div>
      {response.citations.length > 0 && (
        <ol className="sources" aria-label="Sources" data-testid="sources">
          {response.citations.map((citation) => (
            <li key={citation.number} data-testid="source" value={citation.number}>
              <span className="source-file">{citation.source}</span>
              {citation.section && <span className="source-section"> · {citation.section}</span>}
            </li>
          ))}
        </ol>
      )}
    </article>
  );
}
