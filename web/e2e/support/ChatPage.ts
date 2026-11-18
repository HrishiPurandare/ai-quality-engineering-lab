import { expect, type Locator, type Page } from "@playwright/test";

/** Page object for the chat screen: tests talk about questions and answers, not selectors. */
export class ChatPage {
  readonly input: Locator;
  readonly sendButton: Locator;
  readonly status: Locator;
  readonly thinking: Locator;
  readonly userMessages: Locator;
  readonly answers: Locator;
  readonly errors: Locator;
  readonly suggestions: Locator;
  readonly emptyState: Locator;
  readonly counter: Locator;
  readonly clearButton: Locator;

  constructor(readonly page: Page) {
    this.input = page.getByTestId("question-input");
    this.sendButton = page.getByTestId("send-button");
    this.status = page.getByTestId("api-status");
    this.thinking = page.getByTestId("thinking");
    this.userMessages = page.getByTestId("user-message");
    this.answers = page.getByTestId("assistant-message");
    this.errors = page.getByTestId("error-message");
    this.suggestions = page.getByTestId("suggestion");
    this.emptyState = page.getByTestId("empty-state");
    this.counter = page.getByTestId("char-counter");
    this.clearButton = page.getByTestId("clear-chat");
  }

  async open() {
    await this.page.goto("/");
  }

  async ask(question: string) {
    await this.input.fill(question);
    await this.sendButton.click();
  }

  lastAnswer() {
    const answer = this.answers.last();
    return {
      root: answer,
      text: answer.getByTestId("answer-text"),
      sources: answer.getByTestId("source"),
      guardrailBadge: answer.getByTestId("guardrail-badge"),
      refusedBadge: answer.getByTestId("refused-badge"),
      redactedBadge: answer.getByTestId("redacted-badge"),
    };
  }

  /** Waits for the next answer to finish and returns its text. */
  async waitForAnswer(count: number): Promise<string> {
    await expect(this.answers).toHaveCount(count);
    await expect(this.thinking).toBeHidden();
    return (await this.lastAnswer().text.textContent()) ?? "";
  }
}
