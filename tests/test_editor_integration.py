import copy
import datetime
import json
import unittest
from contextlib import ExitStack
from types import SimpleNamespace as NS
from unittest.mock import patch

from bcsfe import core
from bcsfe.core.game.gamoto.gamatoto import GamatotoLevel, GamatotoLimit, MemberName, Helper, Helpers
from bcsfe.core.game.gamoto.ototo import Cannon, Cannons, CastleRecipeUnlock, LevelPartRecipeUnlock
from bcsfe.core.game.catbase.user_rank_rewards import RankGift, Reward
from bcsfe.core.game.map import event
import editor_engine as engine
import editor_items
import editor_misc
import editor_stages
import test_editor_cats as cat_fixtures
import test_editor_stages as stage_fixtures


CASES = {}
for field in ('catfood', 'xp', 'normal_tickets', 'rare_tickets', 'platinum_tickets', 'legend_tickets', 'platinum_shards', 'np', 'leadership', 'hundred_million_ticket', 'restart_pack', 'golden_cpu_count'):
    CASES['items.' + field] = {'value': 123, 'respect_maxima': False}
for field in editor_items.VECTOR_FIELDS:
    CASES['items.' + field] = {'values': {'1': 34}, 'respect_maxima': False}
for name in ('rare', 'normal', 'event'):
    CASES['gatya.' + name + '_seed'] = {'value': 4000000000}
for kind in editor_stages.MAPS:
    CASES['stages.' + kind] = {'maps': [0], 'crowns': [1], 'clear_count': 3}
CASES.update({
    'items.battle_items': {'values': {'1': 98}, 'respect_maxima': False},
    'items.endless': {'minutes': {'0': 60}},
    'items.rare_ticket_trade': {'amount': 2, 'respect_maxima': False},
    'items.event_tickets': {'items': {'501': 45}, 'respect_maxima': False},
    'items.evolve_by_id': {'items': {'502': 67}, 'respect_maxima': False},
    'items.scheme': {'ids': [2], 'mode': 'add'},
    'skills.set': {'skills': {'0': {'level': 11, 'plus': 5}}},
    'account.inquiry_code': {'value': 'offline-test-id'},
    'account.password_refresh_token': {'value': 'offline-test-token'},
    'save.region': {'country_code': 'en'},
    'save.version': {'game_version': 150600},
    'cats.unlock': {'select': cat_fixtures.selection(1, 3)},
    'cats.remove': {'select': cat_fixtures.selection(0)},
    'cats.forms': {'select': cat_fixtures.selection(3), 'operation': 'fourth', 'set_current': True},
    'cats.levels': {'select': cat_fixtures.selection(0), 'base': 40, 'plus': 12},
    'cats.talents': {'select': cat_fixtures.selection(0), 'operation': 'set', 'levels': {'1': 9}},
    'cats.guide': {'select': cat_fixtures.selection(1), 'collected': True},
    'cats.storage.add': {'items': [{'kind': 'cat', 'id': 1, 'quantity': 2}]},
    'cats.storage.remove': {'slots': [0]},
    'cats.storage.clear': {'confirm': True},
    'cats.orbs': {'values': {'1': 50}},
    'cats.lineups': {'lineups': [{'id': 0, 'slots': {'1': 3}, 'name': 'saved'}], 'selected': 2},
    'stages.story': {'chapters': [4], 'progress': 3},
    'stages.treasures': {'chapters': [0], 'stages': [0, 47], 'level': 3},
    'stages.itf_scores': {'chapters': [3], 'stages': [0], 'score': 6333},
    'stages.outbreaks': {'chapters': [3], 'stages': [0], 'cleared': True},
    'stages.aku': {'progress': 3, 'clear_count': 2},
    'stages.unlock_aku': {},
    'stages.enigma': {'maps': [1]},
    'stages.tutorial': {},
    'stages.filibuster': {'stage_id': 47},
    'stages.dojo_score': {'score': 3333},
    'stages.challenge_score': {'score': 4333},
    'gamatoto.xp': {'value': 4123},
    'gamatoto.level': {'value': 3},
    'gamatoto.helpers': {'rarities': {'0': 3}},
    'ototo.engineers': {'value': 8},
    'ototo.materials': {'values': {'2': 71}},
    'ototo.cannons': {'ids': [13], 'max': True},
    'shrine.set': {'level': 3, 'visible': True},
    'rewards.claim': {'ids': [0], 'mode': 'unclaim'},
    'medals.set': {'ids': [211], 'owned': True},
    'missions.set': {'ids': [7], 'state': 'complete_reward'},
    'account.gold_pass': {'enabled': True, 'officer_id': 777},
    'enemy_guide.set': {'ids': [3], 'unlocked': True},
    'playtime.set': {'hours': 100, 'minutes': 3, 'seconds': 2},
    'gambling.reset': {},
    'lineups.unlocked_slots': {'value': 14},
    'fixes.gamatoto': {},
    'fixes.ototo': {},
    'fixes.time': {'timestamp': 1735689600},
    'fixes.officer_pass': {},
    'fixes.equip_menu': {},
})


class EditorIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.original_maxima = copy.deepcopy(core.core_data.max_value_manager)
        fixture = cat_fixtures.CatEditorTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.addCleanup(self.stack.close)
        self.cats_fixture = fixture
        self.stack.enter_context(patch.object(core.core_data, 'max_value_manager', self.original_maxima))
        self.sf = fixture.sf
        stages = stage_fixtures.new_save()
        fields = ('story', 'event_stages', 'gauntlets', 'collab_gauntlets', 'behemoth_culling', 'enigma_clears', 'uncanny', 'catamin_stages', 'tower', 'legend_quest', 'zero_legends', 'dojo_chapters', 'aku', 'outbreaks', 'enigma', 'dojo', 'challenge')
        for field in fields:
            setattr(self.sf, field, getattr(stages, field))
        for field in ('date', 'date_2', 'date_3', 'date_4'):
            setattr(self.sf, field, datetime.datetime(2024, 1, 2, 3, 4, 5))
        for field in editor_items.VECTOR_FIELDS:
            values = getattr(self.sf, field)
            if len(values) < 3:
                setattr(self.sf, field, [11, 22, 33])
        self.sf.officer_pass.gold_pass.officer_id = 55
        self.sf.enemy_guide = [0, 1, 0, 0, 0]
        self.sf.ototo.base_materials = core.BaseMaterials.deserialize([11, 22, 33, 44])
        self.sf.ototo.cannons = Cannons({0: Cannon(0, [9]), 13: Cannon(1, [2, 3, 4])}, [[13, 0, 0]])
        self.sf.gamatoto.helpers = Helpers([Helper(10), Helper(23)])
        self.sf.medals.add_medal(999)
        self.sf.missions.clear_states = {7: 0, 999: 4}
        self.sf.missions.requirements = {7: 0, 999: 25}
        self.sf.wildcat_slots.completed = {4: True}
        self.sf.cat_scratcher.completed = {8: True}
        self.setup_metadata()
        self.raw = self.sf.to_data().data
        self.sf = core.SaveFile(core.Data(self.raw))
        self.assertEqual(self.sf.to_data().data, self.raw)

    def patch_meta(self, method, value):
        self.stack.enter_context(patch.object(core.core_data, method, return_value=value))

    def setup_metadata(self):
        def maps(sf, code, *args, **kwargs):
            count = 269 if code == 'S' else 3
            return NS(map_names={i: 'Map ' + str(i) for i in range(count)}, stage_names={i: ['A', 'B', 'C', '＠', ''] for i in range(count)})
        self.stack.enter_context(patch.object(core, 'MapNames', side_effect=maps))
        self.stack.enter_context(patch.object(core.MapOption, 'from_save', return_value=NS(get_map=lambda _: NS(crown_count=2))))
        recipe = object.__new__(CastleRecipeUnlock)
        recipe.level_part_recipe_unlocks = [LevelPartRecipeUnlock(i, cannon, part, 0, 0, maximum) for i, (cannon, part, maximum) in enumerate([(0, 0, 30), (13, 0, 25), (13, 1, 12), (13, 2, 7)])]
        self.stack.enter_context(patch.object(editor_misc, 'CastleRecipeUnlock', return_value=recipe))
        levels = object.__new__(core.GamatotoLevels)
        levels.levels = [GamatotoLevel(1, 100, 0, 0), GamatotoLevel(2, 300, 0, 0), GamatotoLevel(3, 600, 0, 0)]
        levels.limit = GamatotoLimit(3, 99, 8)
        self.patch_meta('get_gamatoto_levels', levels)
        members = object.__new__(core.GamatotoMembersName)
        members.members = [MemberName(10, 0, 0, 'A', 'R', []), MemberName(23, 1, 0, 'B', 'S', [])]
        self.patch_meta('get_gamatoto_members_name', members)
        shrine = object.__new__(core.CatShrineLevels)
        shrine.boundaries = [100, 300, 600]
        self.patch_meta('get_cat_shrine_levels', shrine)
        self.patch_meta('get_rank_gifts', NS(rank_gift=[RankGift(0, 0, [])]))
        names = [[] for _ in range(213)]
        names[211] = ['Medal 211', 'Requirement']
        self.patch_meta('get_medal_names', NS(medal_names=names))
        self.patch_meta('get_mission_conditions', NS(conditions={7: NS(progress_count=27)}))
        self.patch_meta('get_mission_names', NS(names={7: 'Mission 7'}))
        def download(folder, name):
            if name == 'CastleCustomLimit.csv':
                return core.Data(b'9\n')
            if name == 'schemeItemData.tsv':
                return core.Data(b'id\tname\n2\tFixture\n')
            raise AssertionError('Unmocked game metadata requested: ' + name)
        self.patch_meta('get_game_data_getter', NS(download=download, does_save_version_match=lambda sf: True))
        ticket = NS(category=core.GatyaItemCategory.EVENT_TICKETS.value, index=1)
        evolution = NS(category=core.GatyaItemCategory.EVOLVE_ITEMS.value, index=1)
        self.patch_meta('get_gatya_item_buy', NS(get=lambda item: {501: ticket, 502: evolution}.get(item), get_names_by_category=lambda category: [(NS(id=i), str(i)) for i in range(3)]))
        ability = NS(max_base_level=30, max_plus_level=20)
        self.patch_meta('get_ability_data', NS(ability_data=[ability] * 20, get_ability_data_item=lambda index: ability))

    def run_action(self, action, args):
        original = core.SaveFile(core.Data(self.raw))
        input_raw = self.raw
        if action == 'stages.unlock_aku':


            for group in original.event_stages.chapters:
                group.chapters = [event.EventSubChapterStars([event.EventSubChapter.init(5) for _ in range(3)]) for _ in range(269)]
            input_raw = original.to_data().data
            original = core.SaveFile(core.Data(input_raw))
        result, raw, delta = engine.apply_operations(original, [{'action': action, 'args': args}], isolate=False)
        self.assertEqual(original.to_data().data, input_raw, action + ' mutated original')
        self.assertTrue(result.verify_hash(), action)
        self.assertEqual(core.SaveFile(core.Data(raw)).to_data().data, raw, action)
        self.assertTrue(delta, action + ' produced no persisted change')
        if action not in ('account.gold_pass', 'playtime.set', 'fixes.officer_pass'):
            self.assertEqual(result.officer_pass.serialize(), original.officer_pass.serialize(), action + ' changed officer pass')
        if action not in ('cats.lineups', 'lineups.unlocked_slots'):
            self.assertEqual(result.lineups.serialize(), original.lineups.serialize(), action + ' changed lineup')
        if action.startswith('gatya.'):
            field = action.split('.')[1]
            self.assertEqual(getattr(result.gatya, field), 4000000000)
        if action == 'items.evolve_by_id':
            expected = original.catfruit.copy()
            expected[1] = 67
            self.assertEqual(result.catfruit, expected)
        if action == 'missions.set':
            self.assertEqual(result.missions.clear_states, {7: 2, 999: 4})
            self.assertEqual(result.missions.requirements, {7: 27, 999: 25})
        if action == 'ototo.cannons':
            self.assertEqual(result.ototo.cannons.cannons[13].serialize(), [3, 24, 12, 7])
        if action == 'account.gold_pass':
            self.assertEqual(result.officer_pass.gold_pass.officer_id, 777)
            self.assertEqual(result.officer_pass.play_time, original.officer_pass.play_time)
        if action == 'cats.storage.add':
            self.assertEqual([(item.item_type, item.item_id) for item in result.cats.storage_items], [(1, 2), (1, 1), (1, 1), (0, 0), (0, 0)])
        if action == 'cats.talents':
            self.assertEqual([(talent.id, talent.level) for talent in result.cats.cats[0].talents], [(1, 9), (2, 3)])
        if action == 'cats.forms':
            self.assertEqual((result.cats.cats[3].fourth_form, result.cats.cats[3].current_form), (2, 3))
        return delta

    def test_all_registered_actions_through_strict_binary_engine(self):
        self.assertEqual(set(CASES), set(engine.ACTIONS), 'Update cases when actions are added')
        failures = []
        for action, args in CASES.items():
            try:
                self.run_action(action, args)
            except Exception as exc:
                failures.append({'action': action, 'error': type(exc).__name__, 'detail': str(exc)})
        if failures:
            self.fail(json.dumps({'total': len(CASES), 'passed': len(CASES)-len(failures), 'failures': failures}, ensure_ascii=False, indent=2))

    def test_later_semantic_failure_is_atomic(self):
        before = self.sf.to_data().data
        operations = [
            {'action': 'items.xp', 'args': {'value': 4567}},
            {'action': 'ototo.cannons', 'args': {'ids': [987654], 'development': 3}},
        ]
        with self.assertRaises(engine.EditError):
            engine.apply_operations(self.sf, operations, isolate=False)
        self.assertEqual(self.sf.to_data().data, before)
        self.assertEqual(self.sf.officer_pass.play_time, 654321)

    def test_plain_xp_edit_changes_only_xp(self):
        before = engine.comparable(self.sf)
        result, _, delta = engine.apply_operations(self.sf, [{'action': 'items.xp', 'args': {'value': 9876}}], isolate=False)
        expected = copy.deepcopy(before)
        expected['xp'] = 9876
        self.assertEqual(engine.comparable(result), expected)
        self.assertEqual([change['path'] for change in delta], ['/xp'])

    def test_full_uint32_seeds_survive_one_batch(self):
        operations = [{'action': 'gatya.' + name + '_seed', 'args': {'value': 4294967295}} for name in ('normal', 'rare', 'event')]
        result, raw, _ = engine.apply_operations(self.sf, operations, isolate=False)
        reread = core.SaveFile(core.Data(raw))
        self.assertEqual([getattr(reread.gatya, name + '_seed') for name in ('normal', 'rare', 'event')], [4294967295] * 3)
        self.assertEqual(result.officer_pass.serialize(), self.sf.officer_pass.serialize())
        self.assertEqual(result.lineups.serialize(), self.sf.lineups.serialize())


if __name__ == '__main__':
    unittest.main()
