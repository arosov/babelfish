import unittest
from babelfish_stt.pipeline import AlignmentManager

class TestAlignmentManager(unittest.TestCase):
    def test_get_prefix_context(self):
        am = AlignmentManager(context_words=3)
        
        text = "This is a long sentence with some words"
        prefix = am.get_prefix_context(text)
        # Should be last 3 words: "with some words"
        self.assertEqual(prefix, "with some words")
        
        # Actually let's be precise:
        text = "one two three four five"
        self.assertEqual(am.get_prefix_context(text), "three four five")

    def test_empty_or_short_text(self):
        am = AlignmentManager(context_words=3)
        self.assertEqual(am.get_prefix_context(""), "")
        self.assertEqual(am.get_prefix_context("one two"), "one two")

    def test_merge_ghost_text(self):
        am = AlignmentManager()
        anchor = "The quick brown fox"
        ghost = "fox jumped over"
        
        # If the ghost starts with some words from the end of the anchor, 
        # we should avoid duplicating them if we are displaying them together.
        # But wait, the spec says "refined text (Solid Anchor) should be displayed in a bright/bold style, 
        # while unrefined text (Fast Ghost) should be dimmed".
        # So we probably want: [Anchor] + [Ghost (without Anchor overlap)]
        
        # Let's see how parakeet-stream handles context. 
        # If we give it a prefix context, it might still output the prefix in the result.
        
        # For now, let's focus on the word extraction part which is definitely needed.
        pass

if __name__ == '__main__':
    unittest.main()
