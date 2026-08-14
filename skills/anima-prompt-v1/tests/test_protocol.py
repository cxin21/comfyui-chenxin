from anima_prompt_v1.domain import Fact, PromptBrief, Subject


def test_prompt_brief_validates_unique_fact_and_subject_ids():
    brief = PromptBrief(facts=(Fact("fact:one", "one", "appearance", "explicit", "user"),), subjects=(Subject("subject:0", "woman"),))
    assert brief.explicit_facts() == brief.facts
