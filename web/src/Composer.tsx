import { useState, type FormEvent, type KeyboardEvent } from "react";
import { MAX_QUESTION_LENGTH } from "./api";

export function Composer({ onSend, disabled }: { onSend: (question: string) => void; disabled: boolean }) {
  const [text, setText] = useState("");
  const question = text.trim();
  const canSend = !disabled && question.length > 0;

  function submit(event?: FormEvent) {
    event?.preventDefault();
    if (!canSend) return;
    onSend(question);
    setText("");
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends, Shift+Enter adds a new line.
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form className="composer" onSubmit={submit}>
      <label htmlFor="question" className="visually-hidden">
        Your question
      </label>
      <textarea
        id="question"
        data-testid="question-input"
        placeholder="Ask a question about NovaBank…"
        rows={2}
        maxLength={MAX_QUESTION_LENGTH}
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={onKeyDown}
      />
      <div className="composer-footer">
        <span className="counter" data-testid="char-counter">
          {text.length}/{MAX_QUESTION_LENGTH}
        </span>
        <button type="submit" disabled={!canSend} data-testid="send-button">
          Send
        </button>
      </div>
    </form>
  );
}
