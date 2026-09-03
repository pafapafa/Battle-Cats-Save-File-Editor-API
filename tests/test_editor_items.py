"""Offline item regressions against the real vendored BCSFE binary format."""
import copy
import math
import unittest
from contextlib import ExitStack
from types import SimpleNamespace as NS
from unittest.mock import call, patch

from bcsfe import core
from bcsfe.core.game.catbase.special_skill import AbilityData, AbilityDataItem
import editor_items as editor
from test_editor_cats import make_save


class ItemEditorTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch('socket.socket.connect', side_effect=AssertionError('Network forbidden in item tests')))
        self.stack.enter_context(patch.object(core.core_data, 'config', NS(get_bool=lambda _: False), create=True))
        self.sf = make_save()
        self.caps = NS(**dict.fromkeys(('catfood', 'xp', 'normal_tickets', 'rare_tickets', 'platinum_tickets', 'legend_tickets', 'np', 'leadership', 'hundred_million_tickets', 'catamins', 'catseyes', 'catfruit_old', 'catfruit_new', 'labyrinth_medals', 'treasure_chests', 'event_tickets', 'battle_items'), 100))
        self.stack.enter_context(patch.object(core.core_data, 'max_value_manager', self.caps, create=True))
        for index, skill in enumerate(self.sf.special_skills.skills):
            skill.upgrade = core.Upgrade(plus=index + 2, base=index + 8)
        self.abilities = object.__new__(AbilityData)
        self.abilities.ability_data = [AbilityDataItem(i, 1, 0, 30 + i, 10 + i, 10) for i in range(len(self.sf.special_skills.get_valid_skills()))]
        self.stack.enter_context(patch.object(core.core_data, 'get_ability_data', return_value=self.abilities))
        for field in editor.VECTOR_FIELDS:
            values = getattr(self.sf, field)
            if len(values) < 3:
                setattr(self.sf, field, [11, 22, 33])
        self.sf.rare_tickets = 7
        self.sf.platinum_tickets = 98
        for i, item in enumerate(self.sf.battle_items.items):
            item.amount = 20 + i
            item.locked = bool(i % 2)
        self.sf.battle_items.items[0].endless_item.active = True
        self.sf.battle_items.items[0].endless_item.start = 1000.0
        self.sf.battle_items.items[0].endless_item.end = 5000.0
        self.tickets = {
            501: NS(category=core.GatyaItemCategory.EVENT_TICKETS.value, index=1),
            502: NS(category=core.GatyaItemCategory.LUCKY_TICKETS_1.value, index=0),
            503: NS(category=core.GatyaItemCategory.LUCKY_TICKETS_2.value, index=2),
            601: NS(category=core.GatyaItemCategory.EVOLVE_ITEMS.value, index=1),
        }
        self.stack.enter_context(patch.object(core.core_data, 'get_gatya_item_buy', return_value=NS(get=self.tickets.get)))
        self.stack.enter_context(patch.object(core.core_data, 'get_game_data_getter', return_value=NS(download=lambda *args: core.Data('id\ttype\n2\t1\n8\t1\n'))))
        self.sf = self.reload()
        self.before = self.sf.to_data().data

    def apply(self, action, args):
        editor.ACTIONS[action]['apply'](self.sf, args)

    def reload(self):
        raw = self.sf.to_data().data
        after = core.SaveFile(core.Data(raw))
        self.assertTrue(after.verify_hash())
        self.assertEqual(after.to_data().data, raw)
        return after

    def skill_values(self, sf=None):
        return [(s.upgrade.get_base(), s.upgrade.plus) for s in (sf or self.sf).special_skills.skills]

    def assert_unchanged(self, raw=None):
        self.assertEqual(self.sf.to_data().data, self.before if raw is None else raw)

    def assert_unrelated_preserved(self):
        before = core.SaveFile(core.Data(self.before))
        after = self.reload()
        self.assertEqual(after.officer_pass.serialize(), before.officer_pass.serialize())
        self.assertEqual(after.lineups.serialize(), before.lineups.serialize())
        self.assertEqual(after.cats.serialize(), before.cats.serialize())
        self.assertEqual(after.gamatoto.serialize(), before.gamatoto.serialize())
        self.assertEqual(after.xp, before.xp)

    def test_fixed_skill_values_do_not_swap_base_and_plus_in_binary(self):
        before = self.skill_values()
        self.apply('skills.set', {'skills': {'0': {'level': 11, 'plus': 5}}})
        after = self.reload()
        expected = [(11, 5), (11, 5)] + before[2:]
        self.assertEqual(self.skill_values(after), expected)
        self.assertEqual(after.rank_up_sale_value, 0x7FFFFFFF)
        self.assert_unrelated_preserved()

    def test_inclusive_skill_ranges_draw_independently_and_mirror_one_result(self):
        before = self.skill_values()
        with patch.object(editor.random, 'randint', side_effect=[17, 5, 23]) as randint:
            self.apply('skills.set', {'skills': {'0': {'level': {'min': 10, 'max': 20}, 'plus': {'min': 0, 'max': 10}}, '2': {'level': {'min': 20, 'max': 25}}}})
        self.assertEqual(randint.call_args_list, [call(10, 20), call(0, 10), call(20, 25)])
        expected = before.copy()
        expected[0] = expected[1] = (17, 5)
        expected[3] = (23, before[3][1])
        self.assertEqual(self.skill_values(self.reload()), expected)
        self.assert_unrelated_preserved()

    def test_omitted_skill_component_preserves_visible_and_hidden_independently(self):
        before = self.skill_values()
        self.apply('skills.set', {'skills': {'0': {'level': 12}}})
        after = self.skill_values(self.reload())
        self.assertEqual(after[:2], [(12, before[0][1]), (12, before[1][1])])
        self.assertEqual(after[2:], before[2:])
        self.apply('skills.set', {'skills': {'0': {'plus': 0}}})
        self.assertEqual(self.skill_values(self.reload())[:2], [(12, 0), (12, 0)])

    def test_skill_component_max_uses_metadata_even_when_caps_disabled(self):
        before = self.skill_values()
        self.apply('skills.set', {'skills': {'0': {'level': 'max'}, '1': {'plus': 'max'}, '2': {'max': True}}, 'respect_maxima': False})
        after = self.skill_values(self.reload())
        self.assertEqual(after[0], (30, before[0][1]))
        self.assertEqual(after[1], (30, before[1][1]))
        self.assertEqual(after[2], (before[2][0], 11))
        self.assertEqual(after[3], (32, 12))

    def test_all_skills_max_are_per_skill_not_highest_metadata_value(self):
        self.apply('skills.set', {'skills': 'all'})
        self.assertEqual(self.skill_values(self.reload()), [(30, 10), (30, 10)] + [(30+i, 10+i) for i in range(1, 10)])

    def test_skill_metadata_caps_reject_without_clamping_and_can_be_disabled(self):
        args = {'skills': {'0': {'level': {'min': 10, 'max': 31}}}}
        with patch.object(editor.random, 'randint') as draw, self.assertRaisesRegex(ValueError, 'metadata limit'):
            self.apply('skills.set', args)
        draw.assert_not_called()
        self.assert_unchanged()
        args['respect_maxima'] = False
        with patch.object(editor.random, 'randint', return_value=31):
            self.apply('skills.set', args)
        self.assertEqual(self.skill_values(self.reload())[0][0], 31)

    def test_skill_unsigned16_boundaries_persist_with_caps_disabled(self):
        self.apply('skills.set', {'skills': {'0': {'level': 65536, 'plus': 65535}}, 'respect_maxima': False})
        self.assertEqual(self.skill_values(self.reload())[:2], [(65536, 65535)] * 2)
        before = self.sf.to_data().data
        for change in ({'level': 65537}, {'plus': 65536}, {'level': 0}, {'plus': -1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.apply('skills.set', {'skills': {'0': change}, 'respect_maxima': False})
            self.assert_unchanged(before)

    def test_invalid_skill_ranges_and_ambiguous_max_fail_before_any_changes(self):
        invalid = [{'level': {'min': 20, 'max': 10}}, {'level': {'min': 1, 'max': True}}, {'plus': {'min': 1}}, {'max': True, 'level': 3}, {'max': False}, {'level': 3.0}, {'plus': False}, {'level': 'unknown'}, {'level': 3, 'extra': 1}]
        for change in invalid:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.apply('skills.set', {'skills': {'1': {'level': 4}, '0': change}})
            self.assert_unchanged()
        with self.assertRaises(ValueError):
            self.apply('skills.set', {'skills': {'01': {'level': 2}}})
        self.assert_unchanged()

    def test_missing_later_skill_metadata_prevents_partial_write(self):
        self.abilities.ability_data = self.abilities.ability_data[:1]
        with self.assertRaisesRegex(ValueError, 'metadata'):
            self.apply('skills.set', {'skills': {'0': {'level': 5}, '1': {'level': 6}}})
        self.assert_unchanged()

    def test_scalar_format_boundaries_apply_with_maxima_disabled(self):
        for field, maximum in [('restart_pack', 127), ('golden_cpu_count', 127), ('leadership', 32767), ('xp', editor.I32)]:
            with self.subTest(field=field):
                self.apply('items.' + field, {'value': maximum, 'respect_maxima': False})
                self.assertEqual(getattr(self.reload(), field), maximum)
                before = self.sf.to_data().data
                with self.assertRaises(ValueError):
                    self.apply('items.' + field, {'value': maximum + 1, 'respect_maxima': False})
                self.assert_unchanged(before)

    def test_configured_resource_caps_and_managed_delta_persist(self):
        with self.assertRaises(ValueError):
            self.apply('items.catfood', {'value': 101})
        self.assert_unchanged()
        self.apply('items.catfood', {'value': 500, 'respect_maxima': False})
        after = self.reload()
        self.assertEqual(after.catfood, 500)
        managed = core.BackupMetaData(after).get_managed_items()
        self.assertEqual([(m.amount, m.detail_type.value, m.managed_item_type.value) for m in managed], [(487, 'use', 'catfood')])
        self.assert_unrelated_preserved()

    def test_zero_vectors_partial_indices_and_strict_inputs(self):
        before = self.sf.catseyes.copy()
        self.apply('items.catseyes', {'values': {'1': 0}})
        expected = before.copy()
        expected[1] = 0
        self.assertEqual(self.reload().catseyes, expected)
        raw = self.sf.to_data().data
        for args in [{'values': {'01': 2}}, {'values': {'0': True}}, {'values': [1.0]}, {'values': {'0': 2}, 'respect_maxima': 0}, {'values': 3, 'unknown': True}]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.apply('items.catseyes', args)
            self.assert_unchanged(raw)
        self.apply('items.catseyes', {'values': 7})
        self.assertEqual(self.reload().catseyes, [7] * len(before))

    def test_platinum_shards_use_remaining_ticket_capacity(self):
        with self.assertRaisesRegex(ValueError, 'capacity'):
            self.apply('items.platinum_shards', {'value': 30})
        self.assert_unchanged()
        self.apply('items.platinum_shards', {'value': 29})
        self.assertEqual(self.reload().platinum_shards, 29)
        self.assertEqual(self.reload().platinum_tickets, 98)
        self.apply('items.platinum_shards', {'value': 300, 'respect_maxima': False})
        self.assertEqual(self.reload().platinum_shards, 300)

    def test_battle_item_batch_prevalidates_and_preserves_locks_and_endless(self):
        with self.assertRaises(ValueError):
            self.apply('items.battle_items', {'values': {'0': 9, '1': 101}})
        self.assert_unchanged()
        before = copy.deepcopy(self.sf.battle_items.serialize())
        self.apply('items.battle_items', {'values': {'0': 0, '2': 40}})
        before['items'][0]['amount'] = 0
        before['items'][2]['amount'] = 40
        self.assertEqual(self.reload().battle_items.serialize(), before)

    def test_endless_prevalidates_all_durations_and_requires_explicit_infinity(self):
        for values in ({'0': 5, '1': 1e308}, {'0': 5, '1': 10**400}, {'0': 5, '1': math.inf}, {'0': 5, '1': math.nan}, {'0': True}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.apply('items.endless', {'minutes': values})
            self.assert_unchanged()
        before = copy.deepcopy(self.sf.battle_items.serialize())
        self.apply('items.endless', {'minutes': {'1': 'infinity', '2': 0}})
        after = self.reload().battle_items
        self.assertTrue(math.isinf(after.items[1].endless_item.end))
        self.assertEqual(after.items[2].endless_item.start, after.items[2].endless_item.end)
        for i in (0, 3, 4, 5):
            self.assertEqual(after.items[i].serialize(), before['items'][i])
        self.assertEqual([i.amount for i in after.items], [20, 21, 22, 23, 24, 25])

    def test_ticket_trade_limit_and_progress_overflow_do_not_consume_storage(self):
        for amount, respect in [(94, True), (editor.I32 // 5 + 1, False)]:
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                self.apply('items.rare_ticket_trade', {'amount': amount, 'respect_maxima': respect})
            self.assert_unchanged()
        old_storage = self.sf.cats.storage_items[0].serialize()
        self.apply('items.rare_ticket_trade', {'amount': 95, 'respect_maxima': False})
        after = self.reload()
        self.assertEqual(after.gatya.trade_progress, 475)
        self.assertEqual(after.rare_tickets, 7)
        self.assertEqual(after.cats.storage_items[0].serialize(), old_storage)
        self.assertEqual((after.cats.storage_items[1].item_id, after.cats.storage_items[1].item_type), (1, 2))

    def test_event_ticket_ids_cover_all_three_original_categories(self):
        before = {f: getattr(self.sf, f).copy() for f in ('event_capsules', 'lucky_tickets', 'event_capsules_2')}
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            self.apply('items.event_tickets', {'items': {'501': 2, '999': 3}})
        self.assert_unchanged()
        self.tickets[504] = self.tickets[501]
        with self.assertRaisesRegex(ValueError, 'same event ticket slot'):
            self.apply('items.event_tickets', {'items': {'501': 2, '504': 3}})
        self.assert_unchanged()
        self.apply('items.event_tickets', {'items': {'501': 21, '502': 0, '503': 23}})
        before['event_capsules'][1] = 21
        before['lucky_tickets'][0] = 0
        before['event_capsules_2'][2] = 23
        after = self.reload()
        for field, expected in before.items():
            self.assertEqual(getattr(after, field), expected)

    def test_evolution_ids_use_category_and_preserve_unselected_materials(self):
        before = self.sf.catfruit.copy()
        self.tickets[602] = self.tickets[601]
        for items in ({'601': 2, '501': 3}, {'601': 2, '602': 3}):
            with self.subTest(items=items), self.assertRaises(ValueError):
                self.apply('items.evolve_by_id', {'items': items})
            self.assert_unchanged()
        self.apply('items.evolve_by_id', {'items': {'601': 77}})
        before[1] = 77
        self.assertEqual(self.reload().catfruit, before)

    def test_old_catfruit_cumulative_cap_applies_to_index_and_id_edits(self):
        self.sf.game_version = core.GameVersion(110300)
        self.sf.catfruit = [60, 30, 5]
        for action, args in [('items.catfruit', {'values': {'1': 40}}), ('items.evolve_by_id', {'items': {'601': 40}})]:
            with self.subTest(action=action), self.assertRaisesRegex(ValueError, 'cumulative'):
                self.apply(action, args)
            self.assertEqual(self.sf.catfruit, [60, 30, 5])
            args['respect_maxima'] = False
            self.apply(action, args)
            self.assertEqual(self.sf.catfruit, [60, 40, 5])
            self.sf.catfruit = [60, 30, 5]

    def test_scheme_metadata_prevalidation_and_received_flag_match_original(self):
        self.sf.scheme_items.to_obtain = [2]
        self.sf.scheme_items.received = [2, 8]
        raw = self.sf.to_data().data
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            self.apply('items.scheme', {'ids': [2, 999], 'mode': 'remove'})
        self.assert_unchanged(raw)
        self.apply('items.scheme', {'ids': [2], 'mode': 'remove'})
        self.assertEqual(self.reload().scheme_items.serialize(), {'to_obtain': [], 'received': [8]})
        self.apply('items.scheme', {'ids': 'all', 'mode': 'add'})
        self.assertEqual(self.reload().scheme_items.serialize(), {'to_obtain': [2, 8], 'received': []})


if __name__ == '__main__':
    unittest.main()
