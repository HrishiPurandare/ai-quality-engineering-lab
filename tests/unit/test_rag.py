import pytest

from app.prompts import NO_ANSWER, SYSTEM_PROMPT
from app.rag import RAGPipeline


def test_retrieval_finds_the_right_policy(pipeline: RAGPipeline):
    hits = pipeline.retrieve("international SWIFT transfer fee correspondent charges")
    assert hits, "expected at least one relevant chunk"
    assert hits[0].source == "fees-and-charges.md"
    assert hits[0].section == "Transfer fees"


def test_retrieval_results_are_sorted_by_distance(pipeline: RAGPipeline):
    hits = pipeline.retrieve("lost stolen card freeze replacement")
    distances = [h.distance for h in hits]
    assert distances == sorted(distances)


def test_off_topic_question_is_refused_without_calling_the_model(pipeline: RAGPipeline, fake_llm):
    answer = pipeline.ask("Who won the football world cup?")
    assert answer.refused
    assert answer.answer == NO_ANSWER
    assert answer.citations == []
    assert fake_llm.chat_calls == []


def test_prompt_contains_system_rules_question_and_numbered_context(pipeline: RAGPipeline, fake_llm):
    pipeline.ask("What is the daily transfer limit?")
    system, user = fake_llm.chat_calls[0]
    assert system == {"role": "system", "content": SYSTEM_PROMPT}
    assert "Customer question: What is the daily transfer limit?" in user["content"]
    assert "[1] " in user["content"]


def test_citation_numbers_map_back_to_sources(pipeline: RAGPipeline, fake_llm):
    fake_llm.reply = "The limit is AED 50,000 [1]."
    answer = pipeline.ask("What is the daily transfer limit?")
    assert [c.number for c in answer.citations] == [1]
    assert answer.citations[0].source == "transfers-and-limits.md"
    assert not answer.refused


def test_citations_outside_the_context_range_are_ignored(pipeline: RAGPipeline, fake_llm):
    fake_llm.reply = "Made-up reference [99] and a real one [1]."
    answer = pipeline.ask("What is the daily transfer limit?")
    assert [c.number for c in answer.citations] == [1]


def test_model_saying_no_answer_is_marked_refused(pipeline: RAGPipeline, fake_llm):
    fake_llm.reply = NO_ANSWER
    answer = pipeline.ask("What is the daily transfer limit for crypto?")
    assert answer.refused


def test_a_refusal_has_no_sources_even_with_a_citation_marker(pipeline: RAGPipeline, fake_llm):
    # Seen with llama3.2:3b after the bank was renamed: "I don't have that information... [1]".
    fake_llm.reply = f"{NO_ANSWER} [1]"
    answer = pipeline.ask("What is the interest rate on a savings account?")
    assert answer.refused
    assert answer.citations == []


def test_contexts_are_returned_for_evaluation(pipeline: RAGPipeline):
    answer = pipeline.ask("How do I dispute a card transaction?")
    assert answer.contexts
    assert any("60 days" in c for c in answer.contexts)


@pytest.mark.parametrize("question", ["", "   "])
def test_blank_question_is_rejected(pipeline: RAGPipeline, question: str):
    with pytest.raises(ValueError):
        pipeline.ask(question)
