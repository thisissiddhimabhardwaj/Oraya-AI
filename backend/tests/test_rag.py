"""Regression checks for evidence selection, including fragmented video captions."""
from app.services.rag import Retriever, tokenize
from app.services.tutor_context import cited_times, overview_question, retrieval_question


def test_instruction_words_do_not_hide_the_subject(monkeypatch):
    from app.services.rag import settings
    monkeypatch.setattr(settings, "gemini_api_key", "")
    hits = Retriever().retrieve(4, [(1, 33.04, 38.76, "Avengers assemble.")], "Explain Avengers in simple terms?")
    assert hits and "Avengers" in hits[0].quote


def test_quote_timestamp_points_to_the_actual_caption(monkeypatch):
    from app.services.rag import settings
    monkeypatch.setattr(settings, "gemini_api_key", "")
    hits = Retriever().retrieve(1, [
        (10, 0, 10, "Welcome to the lesson about forces."),
        (11, 40, 50, "The net force determines the acceleration of the object."),
    ], "What determines acceleration?")
    assert hits[0].quote_source.start == 40
    assert hits[0].quote_source.segment_ids == [11]


def test_tokenization_keeps_law_ordinals_math_and_unicode():
    assert {"first", "second", "third", "f", "m", "बल"} <= set(tokenize("first second third F = m बल"))
    assert not {"what", "does", "explain", "simple", "terms"} & set(tokenize("What does explain in simple terms mean?"))


def test_overviews_and_scoped_questions_are_distinguished():
    title = "Countdown to Avengers: Doomsday | Every Moment on Disney+"
    assert overview_question("Explain Avengers in simple terms?", title)
    assert overview_question("Summarize this lecture in 5 bullet points", title)
    assert not overview_question("What is the capital of France?", title)
    assert not overview_question("Summarize the explanation of gravity", title)


def test_follow_up_retains_the_previous_user_topic():
    history = [{"role": "user", "content": "Explain Newton's second law"}, {"role": "assistant", "content": "F equals m times a"}]
    assert "Newton's second law" in retrieval_question("Why?", history)
    assert retrieval_question("Explain photosynthesis", history) == "Explain photosynthesis"
    history += [{"role": "user", "content": "Explain that more simply"},
                {"role": "assistant", "content": "It relates mass and acceleration."}]
    assert "Newton's second law" in retrieval_question("Can you give an example?", history)


def test_model_citation_groups_and_ranges_are_recognized():
    assert cited_times("A team [0:06, 0:19]; Doom [0:51–0:57].") == {"0:06", "0:19", "0:51", "0:57"}
    assert cited_times("**1:20** — F equals m times a") == {"1:20"}
    assert cited_times("[00:06, 00:00:19]") == {"0:06", "0:19"}
    assert cited_times("[1:99]") == {"1:99"}
