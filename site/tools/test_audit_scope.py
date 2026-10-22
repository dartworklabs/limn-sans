"""English/research symbol quality gates retain the explicitly deferred language boundary."""

import unittest

from audit import in_scope
from hypothesis import given
from hypothesis import strategies as st


class AuditScopeContracts(unittest.TestCase):
    """Exercise the quality policy without loading a font or invoking any generator."""

    def test_numeric_superscripts_subscripts_and_signs_are_required(self):
        """Digits and mathematical signs used in formulas are quality-gated at both baselines."""
        for char in "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎":
            with self.subTest(char=char):
                self.assertTrue(in_scope(char))

    @given(
        st.sampled_from(
            ((0x20A0, 0x20CF), (0x2100, 0x214F), (0x2150, 0x218F), (0x2190, 0x21FF), (0x2200, 0x22FF), (0x2300, 0x23FF))
        ),
        st.integers(min_value=0, max_value=0xFFFF),
    )
    def test_every_character_in_a_required_symbol_block_is_in_scope(self, block, offset):
        """The declared currency, letterlike, number, arrow, math and technical blocks are complete."""
        first, last = block
        char = chr(first + offset % (last - first + 1))
        self.assertTrue(in_scope(char), f"U+{ord(char):04X}")

    def test_research_and_supported_supplemental_symbols_are_required(self):
        """Representative formulas and all current supplemental drawing symbols fail the gate on defects."""
        for char in "₹₱₦₾ℕℝℤ℧⅓Ⅷ↩⇔∫∂∑√∞⊂⌘⌈⟨⟩⟵⟶⟷✓✔✗✘":
            with self.subTest(char=char):
                self.assertTrue(in_scope(char))

    def test_deferred_alphabets_remain_informational(self):
        """Greek, extended Latin and modifier/subscript letters including ₑ keep their deferred status."""
        for char in "ₑⁿⁱᵢⱼₐₒₓₕₖₗₘₙₚₛₜˣʲᵀéắΩα":
            with self.subTest(char=char):
                self.assertFalse(in_scope(char))

    def test_existing_korean_english_punctuation_and_symbols_stay_required(self):
        """The symbol-policy repair preserves previously proofed Korean/English families."""
        for char in "AZaz09림갂ㄱㅣ，！₩€℃№™−≠≤≥①□♥㎏":
            with self.subTest(char=char):
                self.assertTrue(in_scope(char))


if __name__ == "__main__":
    unittest.main()
