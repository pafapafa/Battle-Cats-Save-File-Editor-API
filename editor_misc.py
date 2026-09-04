from __future__ import annotations

import datetime
import math
from copy import deepcopy

from bcsfe import core
from bcsfe.core.game.gamoto.gamatoto import Helper, Helpers
from bcsfe.core.game.gamoto.ototo import CastleRecipeUnlock, Cannons

I32 = 2**31 - 1
I64 = 2**63 - 1

MAX_HELPERS_BY_SAVE_SIZE = 1024 * 1024 // 4


def _int(value, name, minimum=0, maximum=I32):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in {minimum}..{maximum}")
    return value


def _bool(value, name):
    if type(value) is not bool:
        raise ValueError(f"{name} must be a boolean")
    return value


def _respect(args):
    return _bool(args.get("respect_maxima", True), "respect_maxima")


def _args(args, allowed, required=()):
    if not isinstance(args, dict):
        raise ValueError("args must be an object")
    unknown = set(args) - set(allowed)
    if unknown:
        raise ValueError(f"Unknown arguments: {', '.join(sorted(unknown))}")
    missing = set(required) - set(args)
    if missing:
        raise ValueError(f"Missing arguments: {', '.join(sorted(missing))}")


def _meta(value, label):
    if value is None:
        raise ValueError(f"Required game metadata is unavailable: {label}")
    return value


def _ids(value, available, label="ids"):
    available = set(available)
    if value == "all":
        return sorted(available)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a nonempty integer array or 'all'")
    result = []
    for item in value:
        item = _int(item, label)
        if item not in available:
            raise ValueError(f"Unknown or unavailable {label}: {item}")
        if item not in result:
            result.append(item)
    return result


def _indexed(values, count, label, maximum=I32, minimum=0):
    if isinstance(values, list):
        if len(values) != count:
            raise ValueError(f"{label} array must contain exactly {count} entries")
        pairs = enumerate(values)
    elif isinstance(values, dict) and values:
        pairs = values.items()
    else:
        raise ValueError(f"{label} must be a full array or a nonempty index object")
    result = {}
    for key, value in pairs:
        if isinstance(key, str) and key.isdecimal():
            index = int(key)
        elif type(key) is int:
            index = key
        else:
            raise ValueError(f"{label} keys must be zero-based integer indexes")
        if not 0 <= index < count:
            raise ValueError(f"{label} index {index} is outside the save's {count} entries")
        if index in result:
            raise ValueError(f"Duplicate {label} index: {index}")
        result[index] = _int(value, label, minimum, maximum)
    return result


def gamatoto_xp(sf, args):
    _args(args, {"value"}, {"value"})
    sf.gamatoto.xp = _int(args["value"], "value")


def gamatoto_level(sf, args):
    _args(args, {"value", "respect_maxima"}, {"value"})
    levels = core.core_data.get_gamatoto_levels(sf)
    maximum = _meta(levels.get_max_level(), "GamatotoExpedition_Limit.csv")
    rows = _meta(levels.get_all_levels(), "GamatotoExpedition.csv")

    maximum = min(maximum if _respect(args) else I32, len(rows))
    level = _int(args["value"], "value", 1, maximum)
    xp = _meta(levels.get_xp_from_level(level), "GamatotoExpedition.csv")
    sf.gamatoto.xp = _int(xp, "level XP")


def gamatoto_helpers(sf, args):
    _args(args, {"ids", "rarities", "respect_maxima"})
    if ("ids" in args) == ("rarities" in args):
        raise ValueError("Provide exactly one of ids or rarities")
    names = core.core_data.get_gamatoto_members_name(sf)
    members = _meta(names.members, "GamatotoExpedition_Members_name")
    maximum = _meta(core.core_data.get_gamatoto_levels(sf).get_total_helpers(), "GamatotoExpedition_Limit.csv")
    maximum = min(maximum if _respect(args) else I32, MAX_HELPERS_BY_SAVE_SIZE)
    by_id = {member.member_id: member for member in members}
    if "ids" in args:
        ids = args["ids"]
        if not isinstance(ids, list):
            raise ValueError("ids must be an array; use [] to remove all helpers")
        for item in ids:
            _int(item, "helper id")
            if item not in by_id:
                raise ValueError(f"Unknown helper id: {item}")
        new_ids = ids.copy()
    else:
        amounts = args["rarities"]
        if not isinstance(amounts, dict) or not amounts:
            raise ValueError("rarities must be a nonempty object keyed by rarity")
        groups = {}
        for member in members:
            groups.setdefault(member.rarity, []).append(member.member_id)
        edits = {}
        for key, value in amounts.items():
            if not isinstance(key, str) or not key.isdecimal() or int(key) not in groups:
                raise ValueError(f"Unknown helper rarity: {key}")
            rarity = int(key)
            if rarity in edits:
                raise ValueError(f"Duplicate rarity: {rarity}")
            edits[rarity] = _int(value, "rarity count", 0, maximum)


        new_ids = [helper.id for helper in sf.gamatoto.helpers.helpers
                   if helper.is_valid() and (helper.id not in by_id or by_id[helper.id].rarity not in edits)]
        if len(new_ids) + sum(edits.values()) > maximum:
            raise ValueError(f"Total helper count exceeds limit {maximum}")
        for rarity, count in edits.items():
            candidates = groups[rarity]
            if count and not candidates:
                raise ValueError(f"No metadata for helper rarity {rarity}")
            new_ids.extend(candidates[i % len(candidates)] for i in range(count))
    if len(new_ids) > maximum:
        raise ValueError(f"Total helper count exceeds limit {maximum}")
    sf.gamatoto.helpers = Helpers([Helper(item) for item in new_ids])


def ototo_engineers(sf, args):
    _args(args, {"value", "respect_maxima"}, {"value"})
    data = _meta(core.core_data.get_game_data_getter(sf).download("DataLocal", "CastleCustomLimit.csv"), "CastleCustomLimit.csv")
    maximum = core.CSV(data).lines[0][0].to_int()
    sf.ototo.engineers = _int(args["value"], "value", 0, min(maximum, I32) if _respect(args) else I32)


def ototo_materials(sf, args):
    _args(args, {"values", "respect_maxima"}, {"values"})
    materials = sf.ototo.base_materials.materials
    maximum = _meta(getattr(core.core_data.max_value_manager, "base_materials", None), "base_materials limit")
    edits = _indexed(args["values"], len(materials), "values", min(maximum, I32) if _respect(args) else I32)
    for index, amount in edits.items():
        materials[index].amount = amount


def ototo_cannons(sf, args):
    _args(args, {"ids", "entries", "development", "levels", "max", "respect_maxima"})
    respect = _respect(args)
    cannons = sf.ototo.cannons
    if cannons is None:
        raise ValueError("This save has no cannon collection")
    if "entries" in args:
        if set(args) - {"entries", "respect_maxima"} or not isinstance(args["entries"], list) or not args["entries"]:
            raise ValueError("entries must be a nonempty array and cannot be combined with other arguments")
        entries = args["entries"]
    else:
        if "ids" not in args or not any(key in args for key in ("development", "levels", "max")):
            raise ValueError("Provide ids and development, levels, or max")
        selected = _ids(args["ids"], cannons.cannons, "cannon ids")
        entries = [dict(id=item, **{k: v for k, v in args.items() if k not in ("ids", "respect_maxima")}) for item in selected]
    if any(not isinstance(entry, dict) for entry in entries):
        raise ValueError("Each cannon entry must be an object")
    needs_recipe = any("levels" in entry or entry.get("max") is True for entry in entries)
    recipe = CastleRecipeUnlock(sf) if needs_recipe else None
    if recipe is not None:
        _meta(recipe.level_part_recipe_unlocks, "CastleRecipeUnlock.csv")
    changes = {}
    for entry in entries:
        _args(entry, {"id", "development", "levels", "max"}, {"id"})
        cannon_id = _int(entry["id"], "cannon id")
        if cannon_id not in cannons.cannons:
            raise ValueError(f"Cannon {cannon_id} is absent from this save")
        if cannon_id in changes:
            raise ValueError(f"Duplicate cannon id: {cannon_id}")
        if not any(k in entry for k in ("development", "levels", "max")):
            raise ValueError("Each cannon entry must request a change")
        current = deepcopy(cannons.cannons[cannon_id])
        if "development" in entry:
            development = _int(entry["development"], "development", 0, 3)
            if cannon_id == 0:
                raise ValueError("The base cannon has no development editor")
            current.development = development
        use_max = _bool(entry["max"], "max") if "max" in entry else False
        if "max" in entry and not use_max:
            raise ValueError("max must be true when supplied")
        if use_max and "levels" in entry:
            raise ValueError("max and levels cannot be combined")
        if "levels" in entry or use_max:
            if "development" in entry and current.development < 3:
                raise ValueError("Editing cannon levels requires development 3")
            if not current.levels:
                raise ValueError(f"Cannon {cannon_id} has no editable level parts")
            if use_max:
                level_edits = {part: _meta(recipe.get_max_level(cannon_id, part), "cannon part level") for part in range(len(current.levels))}
            else:
                level_edits = _indexed(entry["levels"], len(current.levels), "levels")
            for part, level in level_edits.items():
                matching = [row for row in recipe.level_part_recipe_unlocks if row.cannon_id == cannon_id and row.part_id == part]
                if not matching:
                    raise ValueError(f"No recipe metadata for cannon {cannon_id}, part {part}")
                maximum = _meta(recipe.get_max_level(cannon_id, part), "cannon part level")
                level = _int(level, f"cannon {cannon_id} part {part} level", 0, min(maximum, I32) if respect else I32)
                current.levels[part] = level - 1 if part == 0 else level
            current.development = max(current.development, 3)
        changes[cannon_id] = current
    cannons.cannons.update(changes)


def shrine_set(sf, args):
    _args(args, {"level", "xp", "visible", "respect_maxima"})
    respect = _respect(args)
    if not any(k in args for k in ("level", "xp", "visible")) or ("level" in args and "xp" in args):
        raise ValueError("Provide level or xp, optionally visible; level and xp are exclusive")
    levels = core.core_data.get_cat_shrine_levels(sf)
    boundaries = _meta(levels.boundaries, "jinja_level.csv")
    if not boundaries:
        raise ValueError("jinja_level.csv is empty")
    xp = sf.cat_shrine.xp_offering
    if "level" in args:
        level = _int(args["level"], "level", 1, len(boundaries) if respect else I32)


        xp = 0 if level == 1 else (max(boundaries) if level > len(boundaries) else boundaries[level - 2])
    elif "xp" in args:


        xp = _int(args["xp"], "xp", 0, min(max(boundaries), I64) if respect else I32)
    if "visible" in args:
        _bool(args["visible"], "visible")
    level = _meta(levels.get_level_from_xp(xp), "shrine level")
    sf.cat_shrine.xp_offering = xp
    sf.cat_shrine.dialogs = level - 1
    if "visible" in args:
        if args["visible"]:
            sf.cat_shrine.appear()
        else:
            sf.cat_shrine.disappear()


def rewards_claim(sf, args):
    _args(args, {"ids", "mode"}, {"mode"})
    mode = args["mode"]
    if mode not in ("claim", "unclaim", "fix_claimed"):
        raise ValueError("mode must be claim, unclaim, or fix_claimed")
    gifts = _meta(core.core_data.get_rank_gifts(sf).rank_gift, "rankGift.csv")
    user_rank = sf.calculate_user_rank()
    rewards = sf.user_rank_rewards.rewards
    if mode == "fix_claimed":
        if "ids" in args:
            raise ValueError("fix_claimed does not accept ids")
        for gift in gifts:
            if gift.threshold > user_rank and gift.index < len(rewards):
                rewards[gift.index].claimed = False
        return
    available = {gift.index for gift in gifts if gift.threshold <= user_rank and 0 <= gift.index < len(rewards)}
    selected = _ids(args.get("ids"), available, "reward ids")
    for index in selected:
        sf.user_rank_rewards.set_claimed(index, mode == "claim")


def medals_set(sf, args):
    _args(args, {"ids", "owned"}, {"ids", "owned"})
    owned = _bool(args["owned"], "owned")
    names = _meta(core.core_data.get_medal_names(sf).medal_names, "medalname.tsv")
    selected = _ids(args["ids"], (i for i, name in enumerate(names) if name), "medal ids")
    for medal_id in selected:
        if owned:
            sf.medals.add_medal(medal_id)
        else:
            sf.medals.remove_medal(medal_id)


def missions_set(sf, args):
    _args(args, {"ids", "state"}, {"ids", "state"})
    state = args["state"]
    states = {"complete_reward": 2, "complete_claim": 4, "uncomplete": 0}
    if not isinstance(state, str) or state not in states:
        raise ValueError("state must be complete_reward, complete_claim, or uncomplete")
    conditions = _meta(core.core_data.get_mission_conditions(sf).conditions, "Mission_Condition.csv")
    names = _meta(core.core_data.get_mission_names(sf).names, "Mission_Name.csv")
    available = set(sf.missions.clear_states) & set(conditions) & set(names)
    selected = _ids(args["ids"], available, "mission ids")
    for mission_id in selected:
        sf.missions.clear_states[mission_id] = states[state]
        if state != "uncomplete":
            sf.missions.requirements[mission_id] = conditions[mission_id].progress_count
        elif mission_id in sf.missions.requirements:
            sf.missions.requirements[mission_id] = 0


def gold_pass(sf, args):
    _args(args, {"enabled", "officer_id"}, {"enabled"})
    enabled = _bool(args["enabled"], "enabled")
    club = sf.officer_pass.gold_pass
    if not enabled:
        if "officer_id" in args:
            raise ValueError("officer_id is only used when enabled is true")
        club.remove_gold_pass(sf)
    else:
        officer = _int(args["officer_id"], "officer_id") if "officer_id" in args else core.NyankoClub.get_random_officer_id()
        club.get_gold_pass(officer, 30, sf)


def enemy_guide(sf, args):
    _args(args, {"ids", "group", "name", "unlocked", "id_space"}, {"unlocked"})
    unlocked = _bool(args["unlocked"], "unlocked")
    if sum(key in args for key in ("ids", "group", "name")) != 1:
        raise ValueError("Provide exactly one selector: ids, group, or name")
    available = set(range(len(sf.enemy_guide)))
    if "ids" in args:
        space = args.get("id_space", "save")
        if space not in ("save", "game"):
            raise ValueError("id_space must be save or game")
        values = args["ids"]
        if space == "game" and isinstance(values, list):
            values = [_int(item, "game enemy id", 2) - 2 for item in values]
        selected = _ids(values, available, "enemy ids")
    else:
        if "id_space" in args:
            raise ValueError("id_space is only used with ids")
        if "name" in args:
            query = args["name"]
            if not isinstance(query, str) or not query.strip():
                raise ValueError("name must be a nonempty string")
            names = core.core_data.get_enemy_names(sf)
            _meta(names.names, "enemy names")
            selected = [i for i in sorted(available) if query.casefold() in (names.get_name(i) or "").casefold()]
            if not selected:
                raise ValueError("No enemies match name")
        elif args["group"] == "all":
            selected = sorted(available)
        elif args["group"] in ("valid", "invalid"):
            valid = set(_meta(core.EnemyDictionary(sf).get_valid_enemies(), "enemy_dictionary_list.csv"))
            selected = sorted(available & valid if args["group"] == "valid" else available - valid)
        else:
            raise ValueError("group must be all, valid, or invalid")
    for enemy_id in selected:
        enemy = core.Enemy(enemy_id)
        if unlocked:
            enemy.unlock_enemy_guide(sf)
        else:
            enemy.reset_enemy_guide(sf)


def playtime_set(sf, args):
    _args(args, {"frames", "hours", "minutes", "seconds"})
    if "frames" in args:
        if len(args) != 1:
            raise ValueError("frames cannot be combined with hours, minutes, or seconds")
        frames = _int(args["frames"], "frames")
    else:
        if not args:
            raise ValueError("Provide frames or at least one time component")

        hours = _int(args.get("hours", 0), "hours")
        minutes = _int(args.get("minutes", 0), "minutes")
        seconds = _int(args.get("seconds", 0), "seconds")
        frames = core.PlayTime.from_hours_mins_secs(hours, minutes, seconds).frames
        _int(frames, "resulting frame count")
    sf.officer_pass.play_time = frames


def gambling_reset(sf, args):
    _args(args, {"events"})
    events = args.get("events", ["wildcat_slots", "cat_scratcher"])
    if not isinstance(events, list) or not events or any(item not in ("wildcat_slots", "cat_scratcher") for item in events):
        raise ValueError("events must select wildcat_slots and/or cat_scratcher")
    for event in events:
        getattr(sf, event).reset()


def unlocked_slots(sf, args):
    _args(args, {"value", "respect_maxima"}, {"value"})

    hard = 10 if sf.game_version < 90700 else 127
    maximum = min(hard, sf.lineups.slot_names_length) if _respect(args) else hard
    sf.lineups.unlocked_slots = _int(args["value"], "value", 0, maximum)


def fix_gamatoto(sf, args):
    _args(args, ())
    sf.gamatoto.skin = 2


def fix_ototo(sf, args):
    _args(args, ())
    sf.ototo.cannons = Cannons.init(sf.game_version)


def fix_time(sf, args):
    _args(args, {"timestamp"})
    if "timestamp" in args:
        value = args["timestamp"]
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 253402300799:
            raise ValueError("timestamp must be a finite supported Unix timestamp")
        try:
            now = datetime.datetime.fromtimestamp(value)
        except (ValueError, OSError, OverflowError) as exc:
            raise ValueError("timestamp is outside this platform's date range") from exc
    else:
        now = datetime.datetime.now()
    sf.date_3 = now
    sf.timestamp = now.timestamp()
    sf.energy_penalty_timestamp = now.timestamp()


def fix_officer_pass(sf, args):
    _args(args, ())
    sf.officer_pass.reset(sf)


def fix_equip(sf, args):
    _args(args, ())
    if len(sf.menu_unlocks) < 3:
        raise ValueError("This save does not contain the equip-menu flags")
    sf.unlock_equip_menu()


def _schema(properties=None, required=()):
    return {"type": "object", "properties": properties or {}, "required": list(required), "additionalProperties": False}


INT = {"type": "integer", "minimum": 0, "maximum": I32}
BOOL = {"type": "boolean"}
IDS = {"oneOf": [{"type": "array", "items": INT, "minItems": 1, "uniqueItems": True}, {"const": "all"}]}
INDEXED = {"oneOf": [{"type": "array", "items": INT}, {"type": "object", "propertyNames": {"pattern": "^[0-9]+$"}, "additionalProperties": INT, "minProperties": 1}]}
CANNON_ENTRY = _schema({"id": INT, "development": {"type": "integer", "minimum": 0, "maximum": 3}, "levels": INDEXED, "max": {"const": True}}, ["id"])


def _action(description, properties, required, apply, source):
    return {"description": description, "schema": _schema(properties, required), "apply": apply, "source": source}


ACTIONS = {
    "gamatoto.xp": _action("Set expedition XP without changing skin or helpers.", {"value": INT}, ["value"], gamatoto_xp, "core/game/gamoto/gamatoto.py:Gamatoto.edit_raw_xp"),
    "gamatoto.level": _action("Set expedition level using this game version's XP table.", {"value": {**INT, "minimum": 1}}, ["value"], gamatoto_level, "core/game/gamoto/gamatoto.py:Gamatoto.edit_level"),
    "gamatoto.helpers": _action("Replace helper IDs, or edit selected rarity counts while preserving other helpers; counts obey game metadata.", {"ids": {"type": "array", "items": INT}, "rarities": {"type": "object", "propertyNames": {"pattern": "^[0-9]+$"}, "additionalProperties": INT}}, [], gamatoto_helpers, "core/game/gamoto/gamatoto.py:Gamatoto.edit_helpers"),
    "ototo.engineers": _action("Set engineers within CastleCustomLimit.csv.", {"value": INT}, ["value"], ototo_engineers, "core/game/gamoto/ototo.py:Ototo.edit_engineers"),
    "ototo.materials": _action("Edit material amounts by zero-based save index; omitted entries are preserved.", {"values": INDEXED}, ["values"], ototo_materials, "core/game/gamoto/base_materials.py:BaseMaterials.edit_base_materials"),
    "ototo.cannons": _action("Edit existing cannon development and visible part levels, individually or together. Part 0 uses displayed level (stored one lower). max uses per-cannon recipe limits; selected parts are preserved.", {"ids": IDS, "entries": {"type": "array", "items": CANNON_ENTRY, "minItems": 1}, "development": {"type": "integer", "minimum": 0, "maximum": 3}, "levels": INDEXED, "max": {"const": True}}, [], ototo_cannons, "core/game/gamoto/ototo.py:Ototo.edit_cannon"),
    "shrine.set": _action("Set shrine level or offering XP and/or visibility. Level 1 is corrected to zero XP; dialogs follow level.", {"level": {**INT, "minimum": 1}, "xp": {"type": "integer", "minimum": 0}, "visible": BOOL}, [], shrine_set, "core/game/gamoto/cat_shrine.py:CatShrine.edit_catshrine"),
    "rewards.claim": _action("Claim/unclaim eligible user-rank reward flags by metadata index, or clear claims above current rank. Does not grant reward items.", {"ids": IDS, "mode": {"enum": ["claim", "unclaim", "fix_claimed"]}}, ["mode"], rewards_claim, "core/game/catbase/user_rank_rewards.py:UserRankRewards.edit"),
    "medals.set": _action("Add/remove medals from the game metadata; unknown existing medals are preserved.", {"ids": IDS, "owned": BOOL}, ["ids", "owned"], medals_set, "core/game/catbase/medals.py:Medals.edit_medals"),
    "missions.set": _action("Change existing missions to reward-ready, claimed, or incomplete; progress requirements follow mission metadata.", {"ids": IDS, "state": {"enum": ["complete_reward", "complete_claim", "uncomplete"]}}, ["ids", "state"], missions_set, "core/game/catbase/mission.py:Missions.edit_missions"),
    "account.gold_pass": _action("Apply/remove BCSFE's local gold-pass save state; apply uses the original 30-day periods. Does not purchase or verify a server subscription.", {"enabled": BOOL, "officer_id": INT}, ["enabled"], gold_pass, "core/game/catbase/nyanko_club.py:NyankoClub.edit_gold_pass"),
    "enemy_guide.set": _action("Unlock/remove enemy guide entries. save IDs are zero based; game IDs subtract 2 explicitly. Select IDs, valid/invalid/all, or a name substring.", {"ids": IDS, "group": {"enum": ["all", "valid", "invalid"]}, "name": {"type": "string", "minLength": 1}, "id_space": {"enum": ["save", "game"]}, "unlocked": BOOL}, ["unlocked"], enemy_guide, "cli/edits/enemy_editor.py:EnemyEditor.edit_enemy_guide"),
    "playtime.set": _action("Set total play duration in frames or hours/minutes/seconds (30 FPS). Missing duration components are zero; the gold pass is preserved.", {"frames": INT, "hours": INT, "minutes": INT, "seconds": INT}, [], playtime_set, "core/game/catbase/playtime.py:edit"),
    "gambling.reset": _action("Reset selected gambling event completion, values, and start dates, matching the original reset.", {"events": {"type": "array", "items": {"enum": ["wildcat_slots", "cat_scratcher"]}, "minItems": 1}}, [], gambling_reset, "core/game/catbase/gambling.py:GamblingEvent.reset_events"),
    "lineups.unlocked_slots": _action("Set unlocked lineup count within the save's slot-name capacity; lineup units are preserved.", {"value": INT}, ["value"], unlocked_slots, "core/game/battle/slots.py:LineUps.edit_unlocked_slots"),
    "fixes.gamatoto": _action("Explicit original crash repair: set expedition skin to 2.", {}, [], fix_gamatoto, "cli/edits/fixes.py:Fixes.fix_gamatoto_crash"),
    "fixes.ototo": _action("Explicit original crash repair: reset the cannon collection and selected parts.", {}, [], fix_ototo, "cli/edits/fixes.py:Fixes.fix_ototo_crash"),
    "fixes.time": _action("Set date_3, timestamp, and energy penalty timestamp to the specified device time or current server time.", {"timestamp": {"type": "number", "minimum": 0, "maximum": 253402300799}}, [], fix_time, "cli/edits/fixes.py:Fixes.fix_time_errors"),
    "fixes.officer_pass": _action("Explicit original crash repair: reset officer cat, play time, gold pass, and its login rewards.", {}, [], fix_officer_pass, "core/game/catbase/officer_pass.py:OfficerPass.fix_crash"),
    "fixes.equip_menu": _action("Unlock the equip menu using the original SaveFile method.", {}, [], fix_equip, "cli/edits/basic_items.py:BasicItems.unlock_equip_menu"),
}


for _name in ("gamatoto.level", "gamatoto.helpers", "ototo.engineers", "ototo.materials", "ototo.cannons", "shrine.set", "lineups.unlocked_slots"):
    ACTIONS[_name]["schema"]["properties"]["respect_maxima"] = {"type": "boolean", "default": True}
    ACTIONS[_name]["description"] += " respect_maxima=false disables recommended game maxima; binary bounds and valid metadata identities still apply."
