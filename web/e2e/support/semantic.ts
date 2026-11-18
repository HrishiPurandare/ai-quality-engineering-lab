import { expect as baseExpect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const OLLAMA_URL = process.env.OLLAMA_URL ?? "http://localhost:11434";
const EMBED_MODEL = process.env.EMBED_MODEL ?? "nomic-embed-text";

/**
 * Minimum cosine similarity for "means the same thing". Calibrated on 2026-11-18 with
 * nomic-embed-text: correct answers 0.77-0.89, a related but wrong topic 0.64, refusals 0.45.
 * The margin is small, and embeddings are blind to numbers ("AED 500" vs "AED 50" scored 0.97),
 * so always pair this with an exact check on the key facts.
 */
export const SIMILARITY_THRESHOLD = 0.7;

export async function embed(texts: string[]): Promise<number[][]> {
  const response = await fetch(`${OLLAMA_URL}/api/embed`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model: EMBED_MODEL, input: texts }),
  });
  if (!response.ok) throw new Error(`Ollama embed failed: HTTP ${response.status}`);
  return ((await response.json()) as { embeddings: number[][] }).embeddings;
}

export function cosine(a: number[], b: number[]): number {
  let dot = 0;
  let normA = 0;
  let normB = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  return dot / Math.sqrt(normA * normB);
}

export async function similarity(a: string, b: string): Promise<number> {
  const [ea, eb] = await embed([a, b]);
  return cosine(ea, eb);
}

/** expect(answer).toMeanTheSameAs(expected): a custom matcher with a readable failure message. */
export const expect = baseExpect.extend({
  async toMeanTheSameAs(received: string, expected: string, threshold = SIMILARITY_THRESHOLD) {
    const score = await similarity(received, expected);
    const pass = score >= threshold;
    return {
      pass,
      name: "toMeanTheSameAs",
      message: () =>
        `similarity ${score.toFixed(3)} is ${pass ? ">=" : "<"} ${threshold}\n` +
        `  answer:   ${received}\n  expected: ${expected}`,
    };
  },
});

export interface GoldenItem {
  id: string;
  category: string;
  question: string;
  expected_answer: string;
  expected_sources: string[];
  must_include: string[];
  should_refuse: boolean;
}

/** The same golden dataset the Python evals use: one source of truth for expected answers. */
export function goldenItems(ids: string[]): GoldenItem[] {
  const path = fileURLToPath(new URL("../../../evals/golden/ledgerly_golden.jsonl", import.meta.url));
  const all = readFileSync(path, "utf-8")
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line) as GoldenItem);
  return ids.map((id) => {
    const item = all.find((candidate) => candidate.id === id);
    if (!item) throw new Error(`golden item ${id} not found`);
    return item;
  });
}
