"""Regression tests for stage adapters using real BCSFE model objects."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from bcsfe import core
from bcsfe.core.game.map import aku, chapters, event, gauntlets, legend_quest, outbreaks, zero_legends
from editor_stages import ACTIONS, MAPS


def generic_maps(module=chapters, total=3, stars=3, stages=5):
    result = []
    for _ in range(total):
        values = []
        for _ in range(stars):
            if module is zero_legends:
                ch = module.Chapter(0, 0, 0, [module.Stage(0) for _ in range(stages)])
            else:
                ch = module.Chapter.init(stages)
                if module is legend_quest:
                    for stage in ch.stages:
                        stage.tries = 0
            values.append(ch)
        if module is zero_legends:
            result.append(module.ChaptersStars(0, values))
        else:
            result.append(module.ChaptersStars(values))
    return result


def new_save():
    groups = [event.EventChapterGroup([event.EventSubChapterStars([event.EventSubChapter.init(5) for _ in range(3)]) for _ in range(3)]) for _ in range(3)]
    return SimpleNamespace(
        story=core.StoryChapters.init(), event_stages=core.EventChapters(groups),
        gauntlets=core.GauntletChapters(generic_maps(gauntlets), [0] * 3),
        collab_gauntlets=core.GauntletChapters(generic_maps(gauntlets), [0] * 3),
        behemoth_culling=core.GauntletChapters(generic_maps(gauntlets), [0] * 3),
        enigma_clears=core.GauntletChapters(generic_maps(gauntlets), [0] * 3),
        uncanny=core.UncannyChapters(core.Chapters(generic_maps()), [0] * 3),
        catamin_stages=core.UncannyChapters(core.Chapters(generic_maps()), [0] * 3),
        tower=core.TowerChapters(core.Chapters(generic_maps())),
        legend_quest=core.LegendQuestChapters(generic_maps(legend_quest), [0] * 3, list(range(5))),
        zero_legends=core.ZeroLegendsChapters(generic_maps(zero_legends)),
        dojo_chapters=core.ZeroLegendsChapters(generic_maps(zero_legends)),
        aku=core.AkuChapters([aku.ChaptersStars.init(7, 1)]),
        outbreaks=core.Outbreaks({4: outbreaks.Chapter(4, {0: outbreaks.Outbreak(False), 2: outbreaks.Outbreak(True)})}),
        enigma=core.Enigma.init(), dojo=core.Dojo.init(),
        challenge=core.ChallengeChapters(core.Chapters(generic_maps())),
        tutorial_state=0, koreaSuperiorTreasureState=0, ui6=0, new_dialogs_2=[],
        filibuster_stage_enabled=False, filibuster_stage_id=0,
        xp=12345, marker={"preserve": [1, 2, 3]},
    )


def fake_names(*args, **kwargs):
    return SimpleNamespace(map_names={0: "Alpha", 1: "Beta", 2: "Gamma"}, stage_names={i: ["A", "B", "C", "＠", ""] for i in range(3)})


def fake_options(*args):
    return SimpleNamespace(get_map=lambda _: SimpleNamespace(crown_count=2))


def run(sf, name, args):
    ACTIONS["stages." + name]["apply"](sf, args)


class StageAdapterTests(unittest.TestCase):
    def setUp(self):
        self.sf = new_save()
        self.names = patch.object(core, "MapNames", side_effect=fake_names)
        self.options = patch.object(core.MapOption, "from_save", side_effect=fake_options)
        self.names.start()
        self.options.start()
        self.addCleanup(self.names.stop)
        self.addCleanup(self.options.stop)

    def test_story_progress_resets_boundary_preserves_scores_and_treasures(self):
        ch = self.sf.story.get_real_chapters()[4]
        for st in ch.stages:
            st.clear_times, st.treasure, st.itf_timed_score = 9, 2, 6000
        before = copy.deepcopy(self.sf.story.get_real_chapters()[3].serialize())
        run(self.sf, "story", {"chapters": [4], "progress": 2})
        self.assertEqual([s.clear_times for s in ch.stages[:4]], [1, 1, 0, 0])
        self.assertEqual(ch.stages[48].clear_times, 9)
        self.assertTrue(all(s.treasure == 2 and s.itf_timed_score == 6000 for s in ch.stages))
        self.assertEqual(self.sf.story.get_real_chapters()[3].serialize(), before)

    def test_story_partial_counts_and_reset_after(self):
        ch = self.sf.story.get_real_chapters()[0]
        ch.stages[4].clear_times = 9
        ch.progress = 5
        run(self.sf, "story", {"chapters": [0], "stages": [1], "clear_count": 6})
        self.assertEqual(ch.stages[4].clear_times, 9)
        self.assertEqual(ch.progress, 5)
        run(self.sf, "story", {"chapters": [0], "stages": [1], "clear_count": 6, "reset_after": True})
        self.assertEqual(ch.stages[4].clear_times, 0)
        self.assertEqual(ch.progress, 2)

    def test_treasure_geographical_index_conversion(self):
        ch = self.sf.story.get_real_chapters()[0]
        run(self.sf, "treasures", {"chapters": [0], "stages": [0, 47], "level": 3})
        self.assertEqual(ch.stages[45].treasure, 3)
        self.assertEqual(ch.stages[47].treasure, 3)
        self.assertEqual(ch.stages[0].treasure, 0)
        self.assertEqual(ch.progress, 0)

    def test_treasure_groups_use_metadata_and_only_selected_group(self):
        fixture = SimpleNamespace(treasure_group_data=[[4, 7], [1, 3]])
        with patch.object(core.game.map.story, "TreasureGroupData", return_value=fixture):
            run(self.sf, "treasures", {"chapters": [1], "groups": [1], "level": 2})
        ch = self.sf.story.get_real_chapters()[1]
        self.assertEqual([s.treasure for s in ch.stages[:8]], [0, 2, 0, 2, 0, 0, 0, 0])

    def test_treasures_all_only_valid_48(self):
        run(self.sf, "treasures", {"chapters": "all", "level": 3})
        for ch in self.sf.story.get_real_chapters():
            self.assertEqual([s.treasure for s in ch.stages], [3] * 48 + [0] * 3)
        self.assertTrue(all(s.treasure == 0 for s in self.sf.story.chapters[3].stages))

    def test_itf_scores_target_correct_chapters_and_preserve_other_fields(self):
        run(self.sf, "itf_scores", {"chapters": [3, 5], "stages": [1], "score_range": [6000, 6010]})
        for cid in [3, 5]:
            ch = self.sf.story.get_real_chapters()[cid]
            self.assertTrue(6000 <= ch.stages[1].itf_timed_score <= 6010)
            self.assertEqual(ch.stages[1].treasure, 0)
            self.assertEqual(ch.stages[1].clear_times, 0)
        self.assertEqual(self.sf.story.get_real_chapters()[4].stages[1].itf_timed_score, 0)
        with self.assertRaises(ValueError):
            run(self.sf, "itf_scores", {"chapters": [0], "score": 1})

    def test_every_map_type_clears_real_stages_and_respects_crowns(self):
        for kind, (path, _, _, category) in MAPS.items():
            with self.subTest(kind=kind):
                sf = new_save()
                run(sf, kind, {"maps": [0], "clear_count": 4})
                group = sf
                for field in path.split("."):
                    group = getattr(group, field)
                maps = group.chapters[category].chapters if category is not None else group.chapters
                for ch in maps[0].chapters[:2]:
                    vals = [s.clear_amount if hasattr(s, "clear_amount") else s.clear_times for s in ch.stages]
                    self.assertEqual(vals, [4, 4, 4, 0, 0])
                    self.assertEqual(ch.clear_progress, 3)
                last = maps[0].chapters[2]
                self.assertTrue(all((s.clear_amount if hasattr(s, "clear_amount") else s.clear_times) == 0 for s in last.stages))
                self.assertEqual(sf.xp, 12345)
                self.assertEqual(sf.marker, {"preserve": [1, 2, 3]})

    def test_map_partial_edit_preserves_unselected_map_crown_and_counts(self):
        ch = self.sf.gauntlets.chapters[0].chapters[0]
        ch.stages[2].clear_times = 5
        run(self.sf, "gauntlets", {"maps": [0], "crowns": [1], "stages": [0], "clear_count": 8})
        self.assertEqual([s.clear_times for s in ch.stages], [8, 0, 5, 0, 0])
        self.assertEqual(self.sf.gauntlets.chapters[0].chapters[1].stages[0].clear_times, 0)
        self.assertEqual(self.sf.gauntlets.chapters[1].chapters[0].stages[0].clear_times, 0)

    def test_map_progress_resets_all_remaining_valid_stages(self):
        ch = self.sf.gauntlets.chapters[0].chapters[0]
        for stage in ch.stages:
            stage.clear_times = 7
        run(self.sf, "gauntlets", {"maps": [0], "crowns": [1], "progress": 1})
        self.assertEqual([s.clear_times for s in ch.stages], [7, 0, 0, 7, 7])
        self.assertEqual(ch.clear_progress, 1)

    def test_zero_legends_unlock_is_serialized(self):
        run(self.sf, "zero_legends", {"maps": [0], "crowns": [1], "clear_count": 1})
        ch = self.sf.zero_legends.chapters[0].chapters[0]
        self.assertEqual(ch.unlock_state, 3)
        self.assertFalse(hasattr(ch, "chapter_unlock_state"))
        data = core.Data()
        ch.write(data)
        data.pos = 0
        decoded = zero_legends.Chapter.read(data)
        self.assertEqual(decoded.unlock_state, 3)
        self.assertEqual([s.clear_times for s in decoded.stages], [1, 1, 1, 0, 0])

    def test_legend_quest_retains_original_try_count_semantics(self):
        run(self.sf, "legend_quest", {"maps": [0], "crowns": [1], "stages": [0], "clear_count": 9})
        stage = self.sf.legend_quest.chapters[0].chapters[0].stages[0]
        self.assertEqual((stage.clear_times, stage.tries), (9, 9))

    def test_invalid_metadata_or_selector_never_mutates(self):
        before = copy.deepcopy(self.sf.gauntlets.serialize())
        with patch.object(core.MapOption, "from_save", return_value=None):
            with self.assertRaises(ValueError):
                run(self.sf, "gauntlets", {"maps": [0], "clear_count": 1})
        for fields in ({"maps": [0, 99]}, {"crowns": [3]}, {"stages": [3]}, {"maps": [0, 0]}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                run(self.sf, "gauntlets", {"maps": [0], "clear_count": 1, **fields})
        self.assertEqual(self.sf.gauntlets.serialize(), before)

    def test_bool_integer_and_unknown_fields_are_rejected(self):
        for kind, args in [
            ("story", {"chapters": [True], "progress": 1}),
            ("story", {"chapters": [0], "clear_count": True}),
            ("story", {"chapters": [0], "progress": 1, "reset_after": 1}),
            ("gauntlets", {"maps": [0], "clear_count": "1"}),
            ("gauntlets", {"maps": [0], "clear_count": 32768}),
            ("treasures", {"chapters": [0], "level": 3, "typo": 1}),
            ("outbreaks", {"chapters": [3], "cleared": 1}),
        ]:
            with self.subTest(kind=kind, args=args), self.assertRaises(ValueError):
                run(self.sf, kind, args)

    def test_catamin_completion_counts_preserve_other_maps(self):
        self.sf.event_stages.chapter_completion_count[14001] = 7
        run(self.sf, "catamin", {"maps": [0], "completion_count": 123})
        self.assertEqual(self.sf.event_stages.chapter_completion_count, {14000: 123, 14001: 7})

    def test_outbreak_true_chapter_id_and_current_clear(self):
        self.sf.outbreaks.current_outbreaks = {4: outbreaks.Chapter(4, {0: outbreaks.Outbreak(True)})}
        run(self.sf, "outbreaks", {"chapters": [3], "stages": [0], "cleared": True})
        self.assertTrue(self.sf.outbreaks.chapters[4].outbreaks[0].cleared)
        self.assertFalse(self.sf.outbreaks.current_outbreaks[4].outbreaks[0].cleared)
        self.assertTrue(self.sf.outbreaks.chapters[4].outbreaks[2].cleared)

    def test_aku_individual_counts_and_reset(self):
        ch = self.sf.aku.chapters[0].chapters[0]
        ch.current_stage = 4
        run(self.sf, "aku", {"progress": 2, "clear_counts": [3, 4]})
        self.assertEqual([s.clear_times for s in ch.stages], [3, 4, 0, 0, 0, 0, 0])
        self.assertEqual(ch.current_stage, 4)

    def test_aku_all_and_partial_stage_counts(self):
        ch = self.sf.aku.chapters[0].chapters[0]
        run(self.sf, "aku", {"progress": "all", "clear_count": 4})
        self.assertTrue(all(stage.clear_times == 4 for stage in ch.stages))
        run(self.sf, "aku", {"stages": [2], "clear_count": 0})
        self.assertEqual([stage.clear_times for stage in ch.stages], [4, 4, 0, 4, 4, 4, 4])

    def test_aku_all_maps_and_crowns_use_each_model_shape(self):
        self.sf.aku.chapters.append(aku.ChaptersStars.init(4, 2))
        run(self.sf, "aku", {"map": "all", "crown": "all", "progress": "all", "clear_count": 2})
        for chapter in self.sf.aku.chapters:
            for crown in chapter.chapters:
                self.assertTrue(all(stage.clear_times == 2 for stage in crown.stages))

    def test_map_reset_following_crowns_is_explicit(self):
        stars = self.sf.gauntlets.chapters[0].chapters
        for crown in stars:
            for stage in crown.stages:
                stage.clear_times = 9
            crown.clear_progress = 3
            crown.chapter_unlock_state = 3
        run(self.sf, "gauntlets", {"maps": [0], "crowns": [1], "progress": 1})
        self.assertEqual([stage.clear_times for stage in stars[1].stages], [9] * 5)
        run(self.sf, "gauntlets", {"maps": [0], "crowns": [1], "progress": 1, "reset_following_crowns": True})
        self.assertEqual([stage.clear_times for stage in stars[1].stages], [0, 0, 0, 9, 9])
        self.assertEqual((stars[1].clear_progress, stars[1].chapter_unlock_state), (0, 0))
        self.assertEqual([stage.clear_times for stage in stars[2].stages], [9] * 5)

    def test_map_reset_after_leaves_earlier_counts_and_next_crown(self):
        stars = self.sf.gauntlets.chapters[0].chapters
        for crown in stars:
            for stage in crown.stages:
                stage.clear_times = 9
            crown.clear_progress = 3
        run(self.sf, "gauntlets", {"maps": [0], "crowns": [1], "stages": [1], "clear_count": 4, "reset_after": True})
        self.assertEqual([stage.clear_times for stage in stars[0].stages], [9, 4, 0, 9, 9])
        self.assertEqual(stars[0].clear_progress, 2)
        self.assertEqual([stage.clear_times for stage in stars[1].stages], [9] * 5)

    def test_reset_following_preflights_other_crowns(self):
        stars = self.sf.gauntlets.chapters[0].chapters
        stars[1].stages = stars[1].stages[:1]
        before = copy.deepcopy(self.sf.gauntlets.serialize())
        with self.assertRaises(ValueError):
            run(self.sf, "gauntlets", {"maps": [0], "crowns": [1], "progress": 1, "reset_following_crowns": True})
        self.assertEqual(self.sf.gauntlets.serialize(), before)

    def test_enigma_uses_real_sparse_ids(self):
        fixture = SimpleNamespace(map_names={2: "A", 8: "B"}, stage_names={2: ["A"], 8: ["B"]})
        with patch.object(core, "MapNames", return_value=fixture):
            run(self.sf, "enigma", {"maps": [8]})
        self.assertEqual(self.sf.enigma.stages[0].stage_id, 25008)
        self.assertEqual(self.sf.event_stages.chapter_completion_count[25008], 0)

    def test_tutorial_and_filibuster_are_explicit(self):
        run(self.sf, "dojo_score", {"score": 4000})
        self.assertEqual(self.sf.tutorial_state, 0)
        self.assertEqual(self.sf.dojo.chapters.get_stage(0, 0).score, 4000)
        run(self.sf, "tutorial", {})
        self.assertEqual(self.sf.tutorial_state, 1)
        self.assertEqual(self.sf.story.chapters[0].stages[0].clear_times, 1)
        run(self.sf, "filibuster", {"stage_id": 47})
        self.assertTrue(self.sf.filibuster_stage_enabled)
        self.assertEqual(self.sf.filibuster_stage_id, 47)

    def test_challenge_score_preserves_other_scores(self):
        self.sf.challenge.scores = [1, 29]
        run(self.sf, "challenge_score", {"score": 5000})
        self.assertEqual(self.sf.challenge.scores, [5000, 29])
        self.assertTrue(self.sf.challenge.shown_popup)
        self.assertEqual(self.sf.challenge.chapters.chapters[0].chapters[0].stages[0].clear_times, 1)

    def test_unlock_aku_clears_only_original_quests(self):
        quest_ids = [255, 256, 257, 258, 265, 266, 268]
        self.sf.event_stages.chapters[1].chapters = [event.EventSubChapterStars([event.EventSubChapter.init(5)]) for _ in range(270)]
        fixture = SimpleNamespace(map_names={i: str(i) for i in range(270)}, stage_names={i: ["A", "B", "C", "＠"] for i in range(270)})
        with patch.object(core, "MapNames", return_value=fixture):
            run(self.sf, "unlock_aku", {})
        for mid, item in enumerate(self.sf.event_stages.chapters[1].chapters):
            vals = [stage.clear_amount for stage in item.chapters[0].stages]
            self.assertEqual(vals, [1, 1, 1, 0, 0] if mid in quest_ids else [0] * 5)

    def test_enigma_signed_byte_limit_and_wipe(self):
        stage = core.game.map.enigma.Stage(3, 25000, 2, 0)
        self.sf.enigma.stages = [copy.deepcopy(stage) for _ in range(127)]
        with self.assertRaises(ValueError):
            run(self.sf, "enigma", {"maps": [1]})
        self.assertEqual(len(self.sf.enigma.stages), 127)
        run(self.sf, "enigma", {"maps": [], "replace": True})
        self.assertEqual(self.sf.enigma.stages, [])
        self.assertEqual(self.sf.event_stages.chapter_completion_count[25000], 0)

    def test_schema_contains_every_original_level_menu_entry(self):
        sources = {action["source"].split(":")[-1] for action in ACTIONS.values()}
        expected = {
            "clear_tutorial", "StoryChapters.clear_story", "edit_challenge_score", "edit_dojo_score", "edit_enigma",
            "GauntletChapters.edit_enigma_stages", "unlock_aku_realm", "StoryChapters.edit_treasures", "Outbreaks.edit_outbreaks",
            "AkuChapters.edit_aku_chapters", "StoryChapters.edit_itf_timed_scores", "BasicItems.allow_filibuster_stage_reclearing",
            "EventChapters.edit_sol_chapters", "EventChapters.edit_event_chapters", "EventChapters.edit_collab_chapters",
            "GauntletChapters.edit_gauntlets", "GauntletChapters.edit_collab_gauntlets", "UncannyChapters.edit_uncanny",
            "UncannyChapters.edit_catamin_stages", "GauntletChapters.edit_behemoth_culling", "LegendQuestChapters.edit_legend_quest",
            "TowerChapters.edit_towers", "ZeroLegendsChapters.edit_zero_legends", "ZeroLegendsChapters.edit_catclaw_championships",
        }
        self.assertEqual(sources, expected)


if __name__ == "__main__":
    unittest.main()
