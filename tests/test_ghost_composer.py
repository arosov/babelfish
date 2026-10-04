"""
Shared span-based Ghost composer tests (ADR 0010).

The composition tests that lived on TerminalDisplay moved here onto the
shared GhostComposer; the terminal display and the typed InputSimulator
both consume this one composer, so these tests cover both consumers'
append-only behavior. "Committed"/"live" are the vocabulary for window
text; the GLOSSARY's Ghost/Final terms and their avoid-list stand.
"""

import unittest
from unittest.mock import MagicMock, patch

import grapheme

from babelfish_stt.ghost_composer import GhostComposer


class TestGhostComposition(unittest.TestCase):
    """Ghost updates compose incrementally: window updates append instead
    of overwriting, and mid-window rewrites replace cleanly."""

    def test_ghost_appends_across_window_slides(self):
        composer = GhostComposer()
        composer.update("A woman gets on a")
        composer.update("A woman gets on a bus")  # pure append
        composer.update("gets on a bus with her")  # window slid past "A woman"
        composer.update("on a bus with her baby.")  # slid further
        self.assertEqual(composer.line, "A woman gets on a bus with her baby.")

    def test_partial_rewrite_replaces_tail(self):
        composer = GhostComposer()
        composer.update("A woman gets on a bus with her")
        # Model revises "a" -> "the" inside the window and appends
        composer.update("on the bus with her baby.")
        self.assertEqual(composer.line, "A woman gets on the bus with her baby.")

    def test_total_rewording_replaces_instead_of_duplicating(self):
        composer = GhostComposer()
        composer.update("But then he said.")
        # Model re-words the whole window: nothing may be committed, the
        # new Ghost replaces the line (no "But But then indeed").
        composer.update("But then indeed")
        self.assertEqual(composer.line, "But then indeed")
        self.assertEqual(composer.committed, [])
        self.assertNotIn("But But", composer.line)

    def test_weak_alignment_commits_nothing(self):
        composer = GhostComposer()
        composer.update("I think I used to be a little bit")
        # New ghost shares almost nothing with the previous one: even though
        # it is shorter, no head words may be committed (they would be
        # re-covered by the new Ghost and duplicated).
        composer.update("Are you")
        self.assertEqual(composer.committed, [])
        # The live tail is replaced wholesale by the new Ghost
        self.assertEqual(composer.line, "Are you")

    def test_committed_words_survive_rewrites(self):
        composer = GhostComposer()
        composer.update("A woman gets on a")
        composer.update("gets on a bus with her")  # commits "A woman"
        self.assertEqual(composer.committed, ["A", "woman"])
        # Even a fully different-looking update cannot rewrite committed text
        composer.update("with her monkey")
        self.assertEqual(composer.line, "A woman gets on a bus with her monkey")

    def test_finalize_resets_composition(self):
        composer = GhostComposer()
        composer.update("first utterance ghost")
        composer.reset()
        self.assertEqual(composer.committed, [])
        self.assertEqual(composer.live, [])
        self.assertEqual(composer.line, "")
        # Next utterance composes fresh
        composer.update("second")
        self.assertEqual(composer.line, "second")

    def test_empty_ghost_does_not_advance(self):
        composer = GhostComposer()
        composer.update("hello world")
        composer.update("")
        self.assertEqual(composer.live, ["hello", "world"])
        self.assertEqual(composer.line, "hello world")


class TestWindowComposition(unittest.TestCase):
    """Window-aware commits: the pipeline reports each Ghost's audio
    coverage, so the boundary is pinned by audio time when the model
    re-words the shared region."""

    def test_growing_window_commits_nothing(self):
        composer = GhostComposer()
        composer.update("hello world", (0, 5120))
        # Window still starts at 0 (growing): everything stays live
        composer.update("hello world foo", (0, 16000))
        self.assertEqual(composer.committed, [])
        self.assertEqual(composer.line, "hello world foo")

    def test_slide_commits_aged_out_head(self):
        composer = GhostComposer()
        composer.update("hello world foo", (0, 16000))
        # Window start slid 5120 samples into a 16000-sample window:
        # ~1 of 3 words ages out.
        composer.update("world foo bar", (5120, 21120))
        self.assertEqual(composer.committed, ["hello"])
        self.assertEqual(composer.line, "hello world foo bar")

    def test_reworded_slide_commits_by_audio_time(self):
        """The model re-words the shared region completely: the text
        alignment fails, but audio time still commits the aged-out head
        (losing the utterance opening is worse than a rough guess)."""
        composer = GhostComposer()
        composer.update("hello world foo", (0, 16000))
        composer.update("une crise qui s'aggrave", (5120, 21120))
        self.assertEqual(composer.committed, ["hello"])
        self.assertEqual(composer.line, "hello une crise qui s'aggrave")

    def test_text_alignment_pins_boundary_over_proportional(self):
        composer = GhostComposer()
        composer.update("one two three four five", (0, 16000))
        # Window slid a lot (2/3 of the window) but the text alignment says
        # only the first word aged out — the new Ghost re-covers the rest
        # (e.g. silence grew the buffer, not speech).
        composer.update("two three four five six", (10666, 26666))
        self.assertEqual(composer.committed, ["one"])
        self.assertEqual(composer.line, "one two three four five six")

    def test_empty_ghost_does_not_advance_window(self):
        composer = GhostComposer()
        composer.update("hello world", (0, 5120))
        # An empty Ghost result must not advance the window state, or the
        # next commit would age out words for audio that has no words yet.
        composer.update("", window=(5120, 10240))
        self.assertEqual(composer.live, ["hello", "world"])
        self.assertEqual(composer.window, (0, 5120))

    def test_overcommit_is_deduped(self):
        """A rough proportional commit that reaches into audio the new Ghost
        still re-covers is trimmed back: no duplicate phrases pile up, and
        the words are not lost (the live tail shows them)."""
        composer = GhostComposer()
        composer.update("hello world foo", (0, 16000))
        # New ghost re-covers "world foo" (boundary over-committed "world"):
        composer.update("world foo bar", (10240, 26240))
        self.assertEqual(composer.committed, ["hello"])
        self.assertEqual(composer.line, "hello world foo bar")

    def test_dedup_does_not_touch_clean_commits(self):
        composer = GhostComposer()
        composer.update("hello world", (0, 5120))
        # Clean slide: committed tail and new head are different audio
        composer.update("world goodbye", (2560, 13120))
        self.assertEqual(composer.committed, ["hello"])
        self.assertEqual(composer.line, "hello world goodbye")

    def test_capture_pair_6_7_window_did_not_slide(self):
        """Minimized from the red replay capture (dictation_fr.wav, frames
        6->7): the window START never moved (still growing — nothing aged
        out), but the new Ghost is a shorter re-transcription of the same
        audio, and a coincidental 1-word tail/head run ("la") aligned the
        boundary at j=2, committing 9 words the new Ghost still re-covers.
        The composed line then showed the same stretch twice — the start
        of the live pile-up."""
        composer = GhostComposer()
        composer.update(
            "La médiathèque centre ville est un peu plus de la clé.", (0, 22016)
        )
        composer.update("La médiathèque centre ville est un peu.", (0, 24064))
        # Nothing aged out of a window that never slid: nothing may commit
        self.assertEqual(composer.committed, [])
        self.assertEqual(
            composer.line, "La médiathèque centre ville est un peu."
        )

    def test_capture_pair_46_47_tiny_retranscription(self):
        """Minimized from the red replay capture (frames 46->47): the new
        Ghost re-transcribes only a 2-word fragment of the shared region
        while the window slid ~128ms of a ~3s window (~0.8 words of audio
        truth). The old composer trusted the text alignment and committed
        10 words; the audio bound allows at most two."""
        composer = GhostComposer()
        composer.update(
            "école de pré-apprentissage. Celle-ci avait été construite "
            "à la place de l'autre.",
            (60416, 108544),
        )
        composer.update("de pré-apprentissage.", (62464, 110592))
        # Audio bound: ceil(12 * 2048/48128) + 1 = 2 words max
        self.assertLessEqual(len(composer.committed), 2)
        # Whatever was committed must still read as one coherent line,
        # not a pile-up
        words = composer.line.split()
        self.assertLessEqual(len(words), 15)


class TestSpanIsGroundTruth(unittest.TestCase):
    """The audio span bounds every commit; text only refines within it."""

    def test_one_word_coincidental_run_never_commits(self):
        """A single shared word ("la") at the tail/head boundary aligns
        nothing: the commit is bounded by the audio slide, never the
        whole live tail."""
        composer = GhostComposer()
        composer.update("on va essayer la", (0, 16000))
        composer.update("la réponse est simple", (5120, 21120))
        # Audio bound: ceil(4 * 5120/16000) + 1 = 3; the coincidental
        # alignment may not push past it
        self.assertLessEqual(len(composer.committed), 3)
        # The new ghost's text appears exactly once
        self.assertEqual(composer.line.count("la réponse est simple"), 1)

    def test_bound_clamps_eager_text_alignment(self):
        """The text alignment wants to commit 4 words; the audio span
        (the window slid 0.25s of a 1s window, ~2 words + margin) says
        at most 3. The bound wins."""
        composer = GhostComposer()
        composer.update("one two three four five six seven", (0, 16000))
        composer.update("five six seven eight", (4000, 20000))
        # Text alignment: j=3 ("five six seven") -> commit 4 words.
        # Audio bound: ceil(7 * 4000/16000) + 1 = 3.
        self.assertLessEqual(len(composer.committed), 3)
        self.assertEqual(composer.committed, ["one", "two", "three"])

    def test_degenerate_ghost_commits_nothing_but_displays(self):
        """A Ghost claiming ~6x more words than its window can hold is a
        TDT repetition seam: no text alignment and no dedup may derive
        from it — the aged-out head still commits by audio time, and the
        loop text still displays live."""
        composer = GhostComposer()
        composer.update("hello world", (0, 16000))
        looped = " ".join(["la"] * 48)  # ~48 words in a 1s window
        composer.update(looped, (16000, 32000))
        # The aged-out head committed by audio truth (the whole previous
        # window left); nothing was derived from the loop text itself
        self.assertEqual(composer.committed, ["hello", "world"])
        self.assertEqual(composer.live, looped.split())  # still displayed
        self.assertIn("hello world", composer.line)

    def test_after_degenerate_prev_commits_stay_bounded(self):
        """The frame after a degenerate Ghost: the garbage word count must
        not inflate the audio bound."""
        composer = GhostComposer()
        composer.update("hello world", (0, 16000))
        looped = " ".join(["la"] * 48)
        composer.update(looped, (16000, 32000))  # degenerate
        before = len(composer.committed)
        # Next frame: sane text again, window slid 1600 samples (~100ms)
        composer.update("bonjour le monde", (17600, 33600))
        delta = len(composer.committed) - before
        # Unclamped, the 48-word garbage would bound the commit at
        # ceil(48 * 0.1) + 1 = 6; clamped to the window's plausible
        # budget (8 words), the audio bound allows at most 2.
        self.assertLessEqual(delta, 2)

    def test_word_loss_pattern_keeps_the_opening(self):
        """The old algorithm's failure mode (word loss: over-deleting
        committed words on churny subset re-transcriptions) must not lose
        the utterance opening. Sequence modeled on the red capture's
        growing-window frames 4-8 (subset re-transcriptions, window start
        pinned at 0)."""
        composer = GhostComposer()
        sequence = [
            ("La médiathèque centre.", (0, 17920)),
            ("La médiathèque centre ville est un peu plus de la clé.", (0, 22016)),
            ("La médiathèque centre ville est un peu.", (0, 24064)),
            ("La médiathèque centre-ville est installée.", (0, 26112)),
            ("La médiathèque centre ville est installée depuis.", (0, 28160)),
        ]
        for ghost, window in sequence:
            composer.update(ghost, window)
            self.assertTrue(
                composer.line.startswith("La médiathèque"),
                f"opening lost at {ghost!r}: {composer.line!r}",
            )
        self.assertLessEqual(len(composer.line.split()), 12)


class TestFastSpeechRegression(unittest.TestCase):
    """ADR 0010's regression test: a fast-speech ghost sequence (short
    window, rapid span advance, revising transcriptions) must compose an
    append-only line — the opening words never vanish — and every applied
    backspace count must equal the grapheme length of the line presently
    pasted.
    """

    # Windows: 1.5s window (~6 words) sliding ~0.5s between frames
    # (~2 words); the second frame re-words the shared region entirely
    # (model revises freely as right-context grows). Against the retired
    # `_stitch_words` heuristics this exact replay hits the replace-all
    # branch on the second frame — no difflib block exceeds 3 words and
    # every fuzzy score stays at or below 70 — so the stitched line
    # collapses to the last window's words, losing the utterance opening.
    FAST_SEQUENCES = [
        ("yesterday morning folks walked across the plaza", (0, 24000)),
        ("morning people strolled through that quiet park", (6000, 30000)),
        ("people strolled through that quiet park all day", (12000, 44000)),
        ("strolled through that quiet park all day long", (18000, 50000)),
    ]

    def test_composer_line_is_append_only(self):
        composer = GhostComposer()
        for ghost, window in self.FAST_SEQUENCES:
            composer.update(ghost, window)
            # The opening words are never lost mid-utterance
            self.assertTrue(
                composer.line.startswith("yesterday morning"),
                f"line collapsed at {ghost!r}: {composer.line!r}",
            )

    def test_typed_path_backspaces_match_pasted_line(self):
        """Every backspace burst erases exactly the graphemes currently on
        screen — what is tracked and what is on screen cannot diverge."""
        from pynput.keyboard import Key as PynputKey

        from babelfish_stt.input_manager import InputSimulator

        def backspaces(mock_keyboard, before):
            return sum(
                1
                for c in mock_keyboard.press.call_args_list[before:]
                if c.args and c.args[0] == PynputKey.backspace
            )

        mock_keyboard = MagicMock()
        with patch("babelfish_stt.input_strategies.pyperclip"):
            sim = InputSimulator(keyboard_controller=mock_keyboard, throttle_s=0.0)
            for ghost, window in self.FAST_SEQUENCES:
                graphemes_before = len(sim.displayed_graphemes)
                calls_before = len(mock_keyboard.press.call_args_list)
                sim.update_ghost(ghost, window=window)
                bs_count = backspaces(mock_keyboard, calls_before)
                # Every backspace erases exactly the displayed line; the
                # tracked accumulated text is exactly the composer's line.
                self.assertEqual(bs_count, graphemes_before)
                self.assertEqual(sim.accumulated_text, sim.composer.line)
                self.assertEqual(
                    len(sim.displayed_graphemes),
                    len(list(grapheme.graphemes(sim.accumulated_text))),
                )

        # Final composed line keeps the whole sentence (opening included)
        self.assertEqual(
            sim.accumulated_text,
            "yesterday morning people strolled through that quiet park all day long",
        )
