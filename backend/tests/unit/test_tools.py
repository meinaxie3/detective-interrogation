"""
test_tools.py — Unit tests for Claude tool definitions and implementations.

Two test groups:
  1. TOOL_DEFINITION shape — the dicts we register with Claude are valid.
     These pass without Phase 3 (definitions were written in Phase 0).

  2. Implementation contracts — verify return types / values of check(),
     extract(), and evaluate().  Phase 3 implements all three.

No Claude API calls anywhere — all three tools are pure Python.
"""

import pytest
from app.agents.tools import consistency, clue_extractor, pressure
from app.models.session import ExtractedClue


# ══════════════════════════════════════════════════════════════════════════════
# TOOL_DEFINITION schemas
# ══════════════════════════════════════════════════════════════════════════════

class TestToolDefinitionSchemas:

    def test_consistency_tool_name(self):
        assert consistency.TOOL_DEFINITION["name"] == "check_consistency"

    def test_consistency_tool_required_fields(self):
        schema = consistency.TOOL_DEFINITION["input_schema"]
        assert set(schema["required"]) == {"draft_response", "prior_statements", "suspect_id"}

    def test_extract_clues_tool_name(self):
        assert clue_extractor.TOOL_DEFINITION["name"] == "extract_clues"

    def test_extract_clues_tool_required_fields(self):
        schema = clue_extractor.TOOL_DEFINITION["input_schema"]
        assert set(schema["required"]) == {"response_text", "suspect_id", "turn_number"}

    def test_pressure_tool_name(self):
        assert pressure.TOOL_DEFINITION["name"] == "get_pressure_level"

    def test_pressure_tool_required_fields(self):
        schema = pressure.TOOL_DEFINITION["input_schema"]
        assert set(schema["required"]) == {"player_message", "conversation_history", "current_pressure"}

    def test_all_tools_have_non_trivial_descriptions(self):
        """Anthropic SDK rejects tool definitions with empty or short descriptions."""
        for module in [consistency, clue_extractor, pressure]:
            desc = module.TOOL_DEFINITION.get("description", "")
            assert isinstance(desc, str) and len(desc) > 20, (
                f"{module.__name__} tool description is too short or missing"
            )

    def test_all_input_schemas_are_object_type(self):
        for module in [consistency, clue_extractor, pressure]:
            schema = module.TOOL_DEFINITION["input_schema"]
            assert schema["type"] == "object"


# ══════════════════════════════════════════════════════════════════════════════
# consistency.check()
# ══════════════════════════════════════════════════════════════════════════════

class TestConsistencyCheck:

    def test_passes_with_no_prior_statements(self):
        """First turn — nothing to contradict."""
        result = consistency.check(
            draft_response="I was in the kitchen all evening.",
            prior_statements=[],
            suspect_id="butler",
        )
        assert result["passed"] is True
        assert result["contradictions"] == []

    def test_passes_when_times_match(self):
        """Same time in draft and prior — no contradiction."""
        result = consistency.check(
            draft_response="I retired at 11 PM as I said.",
            prior_statements=["I retired at 11 PM."],
            suspect_id="butler",
        )
        assert result["passed"] is True

    def test_detects_time_contradiction(self):
        """Prior says 11 PM; draft says 10 PM — should flag."""
        result = consistency.check(
            draft_response="I retired to my quarters at around 10 PM.",
            prior_statements=["I retired to my quarters at 11 PM sharp."],
            suspect_id="butler",
        )
        assert result["passed"] is False
        assert len(result["contradictions"]) >= 1

    def test_detects_location_contradiction(self):
        """Prior 'I was in the kitchen'; draft 'I was in the study'."""
        result = consistency.check(
            draft_response="I was in the study at that hour.",
            prior_statements=["I was in the kitchen all evening."],
            suspect_id="butler",
        )
        assert result["passed"] is False
        assert len(result["contradictions"]) >= 1

    def test_ignores_irrelevant_phrasing_variation(self):
        """Minor phrasing changes with no factual conflict should PASS."""
        result = consistency.check(
            draft_response="The dining room was cleared by half ten, as I said.",
            prior_statements=["I was supervising the dinner clearing throughout the evening."],
            suspect_id="butler",
        )
        assert result["passed"] is True

    def test_result_has_required_keys(self):
        result = consistency.check("Any draft.", [], "butler")
        assert "passed" in result
        assert "contradictions" in result
        assert isinstance(result["contradictions"], list)

    def test_passed_is_bool(self):
        result = consistency.check("Any draft.", [], "butler")
        assert isinstance(result["passed"], bool)

    def test_no_contradiction_multiple_prior_statements(self):
        """Consistent across several turns — should pass."""
        result = consistency.check(
            draft_response="I was in the kitchen, Detective, as I have already stated.",
            prior_statements=[
                "I was in the kitchen until 11 PM.",
                "The kitchen inventory was my priority that evening.",
            ],
            suspect_id="butler",
        )
        assert result["passed"] is True


# ══════════════════════════════════════════════════════════════════════════════
# clue_extractor.extract()
# ══════════════════════════════════════════════════════════════════════════════

class TestClueExtractor:

    def test_returns_list_of_extracted_clues(self):
        result = clue_extractor.extract(
            response_text="I was in the library until midnight.",
            suspect_id="niece",
            turn_number=3,
        )
        assert isinstance(result["clues"], list)
        assert len(result["clues"]) >= 1

    def test_clues_are_extracted_clue_instances(self):
        result = clue_extractor.extract(
            response_text="I heard a noise at 11 PM.",
            suspect_id="niece",
            turn_number=1,
        )
        for clue in result["clues"]:
            assert isinstance(clue, ExtractedClue)

    def test_tags_time_correctly(self):
        result = clue_extractor.extract(
            response_text="I retired at exactly 11 PM.",
            suspect_id="butler",
            turn_number=1,
        )
        time_clues = [c for c in result["clues"] if c.category == "time"]
        assert len(time_clues) >= 1
        assert any("11" in c.text for c in time_clues)

    def test_tags_midnight(self):
        result = clue_extractor.extract(
            response_text="I was reading until midnight.",
            suspect_id="niece",
            turn_number=2,
        )
        time_clues = [c for c in result["clues"] if c.category == "time"]
        assert any("midnight" in c.text.lower() for c in time_clues)

    def test_tags_location_kitchen(self):
        result = clue_extractor.extract(
            response_text="I was in the kitchen, nowhere near the east wing.",
            suspect_id="butler",
            turn_number=2,
        )
        loc_clues = [c for c in result["clues"] if c.category == "location"]
        assert any("kitchen" in c.text.lower() for c in loc_clues)

    def test_tags_object_decanter(self):
        result = clue_extractor.extract(
            response_text="I served the decanter myself, as I do every evening.",
            suspect_id="butler",
            turn_number=1,
        )
        obj_clues = [c for c in result["clues"] if c.category == "object"]
        assert any("decanter" in c.text.lower() for c in obj_clues)

    def test_tags_person_dorothea(self):
        result = clue_extractor.extract(
            response_text="Dorothea left at half past eleven.",
            suspect_id="butler",
            turn_number=3,
        )
        person_clues = [c for c in result["clues"] if c.category == "person"]
        assert any("dorothea" in c.text.lower() for c in person_clues)

    def test_deduplicates_within_same_call(self):
        """Same location mentioned twice should produce only one clue."""
        result = clue_extractor.extract(
            response_text="The kitchen — I was in the kitchen all night.",
            suspect_id="butler",
            turn_number=1,
        )
        kitchen_clues = [c for c in result["clues"] if "kitchen" in c.text.lower()]
        assert len(kitchen_clues) == 1

    def test_suspect_id_on_clues(self):
        result = clue_extractor.extract(
            response_text="I was in the kitchen.",
            suspect_id="butler",
            turn_number=1,
        )
        for clue in result["clues"]:
            assert clue.suspect_id == "butler"

    def test_turn_number_on_clues(self):
        result = clue_extractor.extract(
            response_text="I was in the library.",
            suspect_id="niece",
            turn_number=5,
        )
        for clue in result["clues"]:
            assert clue.turn == 5

    def test_clue_id_is_non_empty_string(self):
        result = clue_extractor.extract(
            response_text="I heard a noise in the hallway at midnight.",
            suspect_id="niece",
            turn_number=2,
        )
        for clue in result["clues"]:
            assert isinstance(clue.clue_id, str) and len(clue.clue_id) > 0

    def test_empty_response_returns_no_clues(self):
        result = clue_extractor.extract(
            response_text="I have nothing further to say.",
            suspect_id="butler",
            turn_number=4,
        )
        # No known locations/times/objects/persons in this generic line
        assert isinstance(result["clues"], list)

    def test_multiple_categories_in_one_response(self):
        """A rich response should yield clues across multiple categories."""
        result = clue_extractor.extract(
            response_text=(
                "Dorothea left the kitchen at half past eleven. "
                "I sealed the decanter and retired at midnight."
            ),
            suspect_id="butler",
            turn_number=2,
        )
        categories = {c.category for c in result["clues"]}
        assert len(categories) >= 3   # time + location + object + person


# ══════════════════════════════════════════════════════════════════════════════
# pressure.evaluate()
# ══════════════════════════════════════════════════════════════════════════════

class TestPressureEvaluate:

    def test_delta_is_in_range(self):
        result = pressure.evaluate("Where were you?", [], 0)
        assert 1 <= result["pressure_delta"] <= 3

    def test_result_has_reasoning(self):
        result = pressure.evaluate("Where were you?", [], 0)
        assert isinstance(result["reasoning"], str) and len(result["reasoning"]) > 0

    def test_neutral_question_gives_delta_1(self):
        result = pressure.evaluate(
            "Good evening. Could you tell me your name?", [], 0
        )
        assert result["pressure_delta"] == 1

    def test_pointed_question_gives_delta_2(self):
        result = pressure.evaluate(
            "Why did you leave so early? Explain yourself.",
            [],
            2,
        )
        assert result["pressure_delta"] == 2

    def test_accusatory_question_gives_delta_3(self):
        result = pressure.evaluate(
            "You're lying. You were in the study and I have a witness.",
            ["I was in the kitchen."],
            4,
        )
        assert result["pressure_delta"] == 3

    def test_direct_lie_accusation_gives_delta_3(self):
        result = pressure.evaluate("I don't believe you.", [], 0)
        assert result["pressure_delta"] == 3

    def test_who_can_confirm_is_pointed(self):
        result = pressure.evaluate(
            "Who can confirm you were in the kitchen at that hour?", [], 1
        )
        assert result["pressure_delta"] == 2

    def test_revise_statement_is_accusatory(self):
        result = pressure.evaluate(
            "I know you were there. Would you like to revise your statement?", [], 3
        )
        assert result["pressure_delta"] == 3

    def test_are_you_certain_is_pointed(self):
        result = pressure.evaluate(
            "Are you certain about the time? Precisely?", [], 1
        )
        assert result["pressure_delta"] == 2

    def test_accepts_non_empty_history(self):
        """Function accepts conversation_history; doesn't crash."""
        result = pressure.evaluate(
            "What did you do next?",
            ["I was in the kitchen.", "The inventory was complete."],
            2,
        )
        assert 1 <= result["pressure_delta"] <= 3
