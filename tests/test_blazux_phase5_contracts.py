"""Phase 5 synthetic correctness tests: NOT engine integration tests.

No GPU/HTTP/model calls; oracle behavior is not evidence of preview/v0.32 ABI.
"""

from __future__ import annotations

import itertools
import unittest

from src.phase5_offline_contracts import (
    ContractError,
    argmax_draft,
    classify_tool_call,
    mamba_state_slot,
    reduced_draft_vocab,
    require_cache_state_alignment,
    responses_terminal_event,
    synthetic_acceptance,
)


class PrefixStateContractTests(unittest.TestCase):
    def test_mamba_block_1600_not_small_qsa_block_16(self):
        self.assertIsNone(mamba_state_slot(0, 1600))
        for count, slot in ((1, 0), (16, 0), (1599, 0), (1600, 0),
                            (1601, 1), (3200, 1), (3201, 2)):
            with self.subTest(count=count):
                self.assertEqual(mamba_state_slot(count, 1600), slot)
        self.assertNotEqual(mamba_state_slot(1601, 1600), mamba_state_slot(1601, 16))

    def test_cache_hit_requires_both_scheduler_and_mamba_alignment(self):
        self.assertEqual(require_cache_state_alignment(1600, 1600, 1600), 0)
        self.assertEqual(require_cache_state_alignment(3200, 1600, 1600), 1)
        for count, mamba, sched in ((0,1600,1600), (1599,1600,1600),
                                     (1600,1600,1601), (1616,1600,16)):
            with self.subTest(count=count, sched=sched), self.assertRaises(ContractError):
                require_cache_state_alignment(count, mamba, sched)

    def test_reject_invalid_block_and_token_types(self):
        for count, block in ((-1,1600), (True,1600), (1600,0), (1600,-1),
                             (1600,16.0), ("1600",1600)):
            with self.subTest(count=count, block=block), self.assertRaises(ContractError):
                mamba_state_slot(count, block)


TOOLS = {
    "get_weather": {
        "properties": {"city": {"type": "string"}, "days": {"type": "integer"}},
        "required": ["city"],
    },
    "is_enabled": {
        "properties": {"enabled": {"type": "boolean"}},
        "required": ["enabled"],
    },
}


class ToolClientOracleTests(unittest.TestCase):
    def test_known_and_valid_call_is_executable_in_both_protocols(self):
        for protocol in ("chat", "responses"):
            with self.subTest(protocol=protocol):
                self.assertEqual(classify_tool_call(
                    "get_weather", '{"city": "Daejeon", "days": 2}',
                    TOOLS, protocol=protocol
                ), "executable")

    def test_unoffered_call_may_pass_chat_as_untrusted_not_executable(self):
        self.assertEqual(classify_tool_call(
            "shell", '{"command": "echo test"}', TOOLS, protocol="chat",
        ), "untrusted")
        self.assertEqual(classify_tool_call(
            "shell", '{"command": "echo test"}', TOOLS, protocol="responses",
        ), "rejected")

    def test_partial_json_wrapped_arguments_invalid_schema_and_wrong_types(self):
        bad_arguments = (
            '{"city":',
            '{"arguments": {"city": "Daejeon"}}',
            '{"days": 1}',
            '{"city": 23}',
            '{"city": "Daejeon", "extra": 42}',
            '["Daejeon"]',
            '{"city": "Daejeon"} trailing',
        )
        for protocol, payload in itertools.product(("chat", "responses"), bad_arguments):
            expected = "untrusted" if protocol == "chat" else "rejected"
            with self.subTest(protocol=protocol, payload=payload):
                self.assertEqual(
                    classify_tool_call("get_weather", payload, TOOLS, protocol=protocol),
                    expected,
                )

    def test_invalid_envelope_and_unsupported_schema_fail_closed(self):
        with self.assertRaises(ContractError):
            classify_tool_call("get_weather", "{}", TOOLS, protocol="maybe")
        with self.assertRaisesRegex(ContractError, "unsupported schema"):
            classify_tool_call(
                "nested", '{"tags":[]}',
                {"nested": {"properties": {"tags": {"type": "array"}}, "required": []}},
                protocol="responses",
            )
        self.assertEqual(
            classify_tool_call("is_enabled", '{"enabled": true}', TOOLS, protocol="chat"),
            "executable"
        )
        self.assertEqual(
            classify_tool_call("is_enabled", '{"enabled": 1}', TOOLS, protocol="responses"),
            "rejected"
        )


def stream(terminal: str, status: str):
    return [
        {"sequence_number": 0, "type": "response.created"},
        {"sequence_number": 1, "type": "response.output_text.delta"},
        {
            "sequence_number": 2,
            "type": terminal,
            "response": {"status": status},
        },
    ]


class ResponsesEventOracleTests(unittest.TestCase):
    def test_three_distinct_terminal_statuses(self):
        for name, status in (("response.completed", "completed"),
                             ("response.failed", "failed"),
                             ("response.incomplete", "incomplete")):
            with self.subTest(name=name):
                self.assertEqual(responses_terminal_event(stream(name, status)), status)

    def test_error_event_is_terminal(self):
        self.assertEqual(
            responses_terminal_event([
                {"sequence_number": 0, "type": "response.created"},
                {"sequence_number": 1, "type": "error"},
            ]), "error",
        )

    def test_missing_terminal_duplicate_sequence_or_post_terminal_are_invalid(self):
        base = stream("response.completed", "completed")
        bad = (
            base[:-1],
            [base[0], {**base[1], "sequence_number": 0}, base[2]],
            [*base, {"sequence_number": 3, "type": "response.output_text.delta"}],
            [base[0], {**base[1], "sequence_number": 0}, base[2]],
            stream("response.failed", "completed"),
            [],
        )
        for index, events in enumerate(bad):
            with self.subTest(index=index), self.assertRaises(ContractError):
                responses_terminal_event(events)


class ReducedDraftVocabularyTests(unittest.TestCase):
    def test_valid_candidate_requires_mandatory_tokens(self):
        self.assertEqual(reduced_draft_vocab([0, 2, 5, 7], 10, [0, 7]),
                         frozenset((0, 2, 5, 7)))
        with self.assertRaisesRegex(ContractError, "omits required"):
            reduced_draft_vocab([0, 2], 10, [7])

    def test_reject_duplicate_oob_empty_or_invalid_vocab(self):
        bad = (
            ([1, 1], 10), ([1, -1], 10), ([1, 10], 10),
            ([], 10), ([True], 10), ([1], 0),
        )
        for ids, vocab in bad:
            with self.subTest(ids=ids, vocab=vocab), self.assertRaises(ContractError):
                reduced_draft_vocab(ids, vocab, [])

    def test_reduced_draft_can_change_proposal_and_acceptance(self):
        scores = ((0.1, 0.2, 0.9), (0.9, 0.1, 0.2), (0.1, 0.8, 0.7))
        all_ids = frozenset((0, 1, 2))
        reduced = reduced_draft_vocab([0, 1], 3, [0])
        self.assertEqual(argmax_draft(scores[0], all_ids), 2)
        self.assertEqual(argmax_draft(scores[0], reduced), 1)
        target = (2, 0, 1)
        self.assertEqual(synthetic_acceptance(scores, target, all_ids), (3, 3))
        self.assertEqual(synthetic_acceptance(scores, target, reduced), (2, 3))
        # This is an illustrative argmax oracle, not real MTP acceptance.

    def test_reject_invalid_logits_and_missing_target_alignment(self):
        with self.assertRaisesRegex(ContractError, "invalid logits"):
            argmax_draft((0.1, float("nan")), frozenset((0, 1)))
        with self.assertRaisesRegex(ContractError, "length mismatch"):
            synthetic_acceptance(((0.1, 0.2),), (0, 1), frozenset((0, 1)))


if __name__ == "__main__":
    unittest.main()
