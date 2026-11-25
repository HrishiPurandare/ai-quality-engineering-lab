import { useEffect, useRef, useState } from "react";
import { ApiError, ask, health, type ChatResponse, type Health } from "./api";
import { Composer } from "./Composer";
import { Message, type ChatMessage } from "./Message";

const SUGGESTIONS = [
  "How much does an international SWIFT transfer cost?",
  "What is the overdraft fee?",
  "Can you check my account balance for me?",
];

type Status = { state: "checking" } | { state: "online"; info: Health } | { state: "offline" };

export function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pending, setPending] = useState(false);
  const [status, setStatus] = useState<Status>({ state: "checking" });
  const nextId = useRef(1);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    health()
      .then((info) => setStatus({ state: "online", info }))
      .catch(() => setStatus({ state: "offline" }));
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "end" });
  }, [messages, pending]);

  const add = (message: Omit<ChatMessage, "id">) =>
    setMessages((current) => [...current, { ...message, id: nextId.current++ }]);

  async function send(question: string) {
    // The button is disabled while waiting, but a fast double Enter could still get here twice.
    if (pending) return;
    add({ role: "user", text: question });
    setPending(true);
    try {
      const response: ChatResponse = await ask(question);
      add({ role: "assistant", text: response.answer, response });
    } catch (error) {
      add({ role: "error", text: error instanceof ApiError ? error.message : "Unexpected error." });
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="shell">
      <header className="header">
        <div>
          <h1>NovaAsk</h1>
          <p className="tagline">Answers from NovaBank policies, with sources</p>
        </div>
        <div className="header-actions">
          <span className={`status status-${status.state}`} data-testid="api-status">
            {status.state === "checking" && "Connecting…"}
            {status.state === "online" && `Online · ${status.info.indexed_chunks} policy chunks`}
            {status.state === "offline" && "Offline"}
          </span>
          <button
            type="button"
            className="link-button"
            onClick={() => setMessages([])}
            disabled={messages.length === 0 || pending}
            data-testid="clear-chat"
          >
            Clear chat
          </button>
        </div>
      </header>

      <main className="conversation" aria-live="polite" data-testid="conversation">
        {messages.length === 0 && (
          <section className="empty" data-testid="empty-state">
            <p>Ask about fees, transfers, cards, accounts or security. Try one of these:</p>
            <div className="suggestions">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  className="suggestion"
                  onClick={() => send(suggestion)}
                  disabled={pending}
                  data-testid="suggestion"
                >
                  {suggestion}
                </button>
              ))}
            </div>
            <p className="disclaimer">
              Demo with a fictional bank. Never type real card numbers, PINs or passwords.
            </p>
          </section>
        )}
        {messages.map((message) => (
          <Message key={message.id} message={message} />
        ))}
        {pending && (
          <div className="thinking" role="status" data-testid="thinking">
            NovaBank is thinking…
          </div>
        )}
        <div ref={endRef} />
      </main>

      <Composer onSend={send} disabled={pending} />
    </div>
  );
}
