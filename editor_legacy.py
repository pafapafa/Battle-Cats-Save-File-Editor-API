"""Translate the legacy /edit payload to explicit, validated editor operations.

No save, network, configuration, or account mutation occurs here. Ambiguous old
menu booleans now require an explicit value/object instead of reporting success.
"""
from __future__ import annotations

from copy import deepcopy
import re
from jsonschema import Draft202012Validator, validators


CREDENTIAL_FIELDS = frozenset("transfer_code tc confirmation_code cc confirmation_pin country_code country cc_str".split())
ALIASES = {
    "stones": "behemoth_stones", "cat_forms": "cat_evolutions", "max_cat_evolutions": "true_form_all",
    "claim_rewards": "claim_all_rewards", "max_talents": "max_all_talents", "talents": "cat_talents",
    "orbs": "talent_orbs", "base_materials": "ototo_materials",
}
SCALARS = {
    **{k: "items." + k for k in "catfood xp normal_tickets rare_tickets platinum_tickets legend_tickets platinum_shards np leadership hundred_million_ticket restart_pack".split()},
    "gamatoto_level": "gamatoto.level", "gamatoto_xp": "gamatoto.xp", "ototo_engineers": "ototo.engineers",
    "unlocked_slots": "lineups.unlocked_slots", "challenge_score": "stages.challenge_score", "dojo_score": "stages.dojo_score",
    "rare_gatya_seed": "gatya.rare_seed", "normal_gatya_seed": "gatya.normal_seed", "event_gatya_seed": "gatya.event_seed",
    "inquiry_code": "account.inquiry_code", "password_refresh_token": "account.password_refresh_token",
}
VECTORS = {k: "items." + k for k in "catseyes catfruit catamins battle_items treasure_chests labyrinth_medals".split()}
MAP_FLAGS = {
    "sol": "sol", "event": "event", "collab": "collab", "gauntlets": "gauntlets", "collab_gauntlets": "collab_gauntlets",
    "uncanny": "uncanny", "catamin_stages": "catamin", "behemoth_culling": "behemoth", "legend_quest": "legend_quest",
    "towers": "towers", "zero_legends": "zero_legends", "dojo_catclaw_championships": "dojo_catclaw", "clear_enigma_stages": "enigma_clears",
}
SIMPLE_FLAGS = {
    "fix_gamatoto_crash": ("fixes.gamatoto", {}), "fix_ototo_crash": ("fixes.ototo", {}), "fix_time_errors": ("fixes.time", {}),
    "fix_officer_pass_crash": ("fixes.officer_pass", {}), "unlock_equip_menu": ("fixes.equip_menu", {}),
    "reset_gambling_events": ("gambling.reset", {}), "reset_golden_cat_cpus": ("items.golden_cpu_count", {"value": 0}),
    "unlock_aku_realm": ("stages.unlock_aku", {}), "filibuster_reclearing": ("stages.filibuster", {}),
    "clear_tutorial": ("stages.tutorial", {}),
    "clear_story_all": ("stages.story", {"chapters": "all", "clear_count": 1}),
    "clear_into_the_future": ("stages.story", {"chapters": [3, 4, 5], "clear_count": 1}),
    "clear_cats_of_the_cosmos": ("stages.story", {"chapters": [6, 7, 8], "clear_count": 1}),
    "unlock_cats": ("cats.unlock", {"select": [{"kind": "obtainable"}]}),
    "max_cat_levels": ("cats.levels", {"select": [{"kind": "current"}, {"kind": "obtainable", "mode": "and"}], "base": "max", "plus": "max"}),
    "true_form_all": ("cats.forms", {"select": [{"kind": "current"}], "operation": "true", "set_current": True}),
    "max_special_skills": ("skills.set", {"skills": "all"}),
    "claim_all_rewards": ("rewards.claim", {"ids": "all", "mode": "claim"}),
    "complete_missions": ("missions.set", {"ids": "all", "state": "complete_reward"}),
    "max_all_talents": ("cats.talents", {"select": [{"kind": "current"}], "operation": "max"}),
    "max_talent_orbs": ("cats.orbs", {"all": True, "count": "max"}),
    "max_castle_development": ("ototo.cannons", {"ids": "all", "max": True}),
    "max_treasures": ("stages.treasures", {"chapters": "all", "level": 3}),
    "unlock_cat_guide": ("cats.guide", {"select": [{"kind": "all"}], "collected": True}),
}
OBJECT_OR_FLAG = {
    "outbreaks": ("stages.outbreaks", {"chapters": "all", "cleared": True}),
    "aku_chapters": ("stages.aku", {"progress": "all", "map": "all", "crown": "all"}),
    "medals": ("medals.set", {"ids": "all", "owned": True}),
    "missions": ("missions.set", {"ids": "all", "state": "complete_reward"}),
    "enemy_guide": ("enemy_guide.set", {"ids": "all", "group": "all", "unlocked": True}),
    "scheme_items": ("items.scheme", {"ids": "all", "mode": "add"}),
}
SPECIAL_FIELDS = frozenset("catamins_a catamins_b catamins_c behemoth_stones battle_items_endless gamatoto_helpers gamatoto_helper_ids gamatoto_helper_rarities ototo_materials unlock_cat_ids remove_cat_ids cat_levels cat_evolutions cat_talents talent_orbs special_skills castle_development castle_levels clear_all_stages clear_chapters clear_stages max_chapter_treasures stage_treasures itf_timed_scores event_tickets cat_storage cat_shrine ototo_cat_cannon playtime unban_account upload_items enable_safety".split())
SUPPORTED_FIELDS = frozenset(set(CREDENTIAL_FIELDS) | set(ALIASES) | set(SCALARS) | set(VECTORS) | set(MAP_FLAGS) | set(SIMPLE_FLAGS) | set(OBJECT_OR_FLAG) | set(SPECIAL_FIELDS))


def _catalog():
    from editor_items import ACTIONS as items
    from editor_cats import ACTIONS as cats
    from editor_stages import ACTIONS as stages
    from editor_misc import ACTIONS as misc
    return {**items, **cats, **stages, **misc}


StrictValidator = validators.extend(Draft202012Validator, type_checker=Draft202012Validator.TYPE_CHECKER.redefine("integer", lambda checker, value: type(value) is int))


def _bool(value, name):
    if type(value) is not bool:
        raise ValueError(f"{name} must be a JSON boolean")
    return value


def _int(value, name, minimum=0, maximum=2147483647):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in {minimum}..{maximum}; values are never clamped")
    return value


def _id(value, name):
    if isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]*", value):
        return _int(int(value), name)
    return _int(value, name)


def _obj(value, name, allowed=None, required=()):
    if type(value) is not dict:
        raise ValueError(f"{name} requires an explicit argument object; a menu boolean is insufficient")
    if allowed is not None and set(value) - set(allowed):
        raise ValueError(f"{name} has unknown fields: {sorted(set(value) - set(allowed))}")
    if set(required) - set(value):
        raise ValueError(f"{name} is missing: {sorted(set(required) - set(value))}")
    return deepcopy(value)


def _list(value, name):
    if type(value) is not list:
        raise ValueError(f"{name} must be an array")
    return value


def _normalize(payload):
    if type(payload) is not dict or any(type(k) is not str for k in payload):
        raise ValueError("Legacy payload must be an object with string keys")
    unknown = set(payload) - SUPPORTED_FIELDS
    if unknown:
        raise ValueError("Unknown legacy fields: " + ", ".join(sorted(unknown)))
    result = {k: deepcopy(v) for k, v in payload.items() if k not in CREDENTIAL_FIELDS}
    for alias, canonical in ALIASES.items():
        if alias not in result:
            continue
        value = result.pop(alias)
        if canonical in result and (type(value) is not type(result[canonical]) or value != result[canonical]):
            raise ValueError(f"Conflicting {canonical} and alias {alias}")
        result[canonical] = value
    return result


def _indexed_aliases(value, names, label):
    if type(value) is not dict:
        return deepcopy(value)
    result = {}
    for key, amount in value.items():
        target = names.get(key, key)
        index = str(_id(target, label + " index"))
        if index in result:
            raise ValueError(f"Duplicate {label} index through aliases: {key}")
        result[index] = amount
    return result


def _cat_records(value, name, scalar_field):
    if type(value) is dict and ("id" in value or "cat_id" in value):
        return [deepcopy(value)]
    if type(value) is dict:
        if any(type(entry) is dict and set(entry) & {"id", "cat_id"} for entry in value.values()):
            raise ValueError(name + " cannot specify a second id inside an id-keyed mapping")
        return [dict({"id": _id(key, name + " cat id")}, **(deepcopy(entry) if type(entry) is dict else {scalar_field: entry})) for key, entry in value.items()]
    return _list(value, name)


def _pick_alias(record, keys, label, required=False):
    present = [k for k in keys if k in record]
    if not present:
        if required:
            raise ValueError(label + " is required")
        return None, False
    first = record[present[0]]
    if any(type(record[k]) is not type(first) or record[k] != first for k in present[1:]):
        raise ValueError("Conflicting aliases for " + label)
    return first, True


def legacy_to_operations(payload):
    data = _normalize(payload)
    safety = _bool(data.pop("enable_safety", False), "enable_safety")
    for field in ("unban_account", "upload_items"):
        if field in data:
            _bool(data.pop(field), field)
    actions = _catalog()
    operations = []

    def add(action, args):
        if action not in actions:
            raise ValueError("Required editor action is unavailable: " + action)
        args = deepcopy(args)
        schema = actions[action]["schema"]
        if "respect_maxima" in schema.get("properties", {}):
            if "respect_maxima" in args and args["respect_maxima"] is not safety:
                raise ValueError("Use the top-level enable_safety option for legacy requests")
            args["respect_maxima"] = safety
        errors = sorted(StrictValidator(schema).iter_errors(args), key=lambda error: str(list(error.path)))
        if errors:
            error = errors[0]
            location = ".".join(map(str, error.path)) or "args"
            raise ValueError(f"{action}.{location}: {error.message}")
        operations.append({"action": action, "args": args})

    # Bulk requests are applied before individual overrides, independent of JSON key order.
    for field, (action, args) in SIMPLE_FLAGS.items():
        if field in data and _bool(data.pop(field), field):
            add(action, args)
    if "clear_all_stages" in data:
        value = data.pop("clear_all_stages")
        if type(value) is bool:
            scopes = ["story", "aku", *MAP_FLAGS.values(), "tutorial"] if value else []
        else:
            value = _obj(value, "clear_all_stages", {"scopes"}, {"scopes"})
            scopes = _list(value["scopes"], "clear_all_stages.scopes")
            if any(type(scope) is not str or scope not in {"story", "aku", "tutorial", *MAP_FLAGS.values()} for scope in scopes) or len(set(scopes)) != len(scopes):
                raise ValueError("clear_all_stages.scopes contains unknown or duplicate names")
        for scope in scopes:
            if scope == "story":
                add("stages.story", {"chapters": "all", "clear_count": 1})
            elif scope == "aku":
                add("stages.aku", {"progress": "all", "map": "all", "crown": "all"})
            elif scope == "tutorial":
                add("stages.tutorial", {})
            else:
                add("stages." + scope, {"maps": "all", "clear_count": 1, "ensure_cleared": True})
    for field, kind in MAP_FLAGS.items():
        if field not in data:
            continue
        value = data.pop(field)
        if type(value) is bool:
            if value:
                add("stages." + kind, {"maps": "all", "clear_count": 1, "ensure_cleared": True})
        else:
            add("stages." + kind, _obj(value, field))
    for field, (action, defaults) in OBJECT_OR_FLAG.items():
        if field not in data:
            continue
        value = data.pop(field)
        if type(value) is bool:
            if value:
                add(action, defaults)
        else:
            add(action, _obj(value, field))
    for field, action in SCALARS.items():
        if field in data:
            value = data.pop(field)
            key = "score" if field in ("challenge_score", "dojo_score") else "value"
            add(action, {key: value})
    for field, action in VECTORS.items():
        if field not in data:
            continue
        value = data.pop(field)
        if field == "catseyes":
            value = _indexed_aliases(value, {"ex": "0", "special": "0", "rare": "1", "super_rare": "2", "super": "2", "uber_rare": "3", "uber": "3", "legend": "4", "dark": "5"}, field)
        elif field == "catamins":
            value = _indexed_aliases(value, {"a": "0", "b": "1", "c": "2"}, field)
        add(action, {"values": value})
    catamin_changes = {str(i): data.pop(field) for i, field in enumerate(("catamins_a", "catamins_b", "catamins_c")) if field in data}
    if catamin_changes:
        add("items.catamins", {"values": catamin_changes})
    if "behemoth_stones" in data:
        value = _obj(data.pop("behemoth_stones"), "behemoth_stones (use {item_ids: {game_item_id: quantity}})", {"item_ids"}, {"item_ids"})
        add("items.evolve_by_id", {"items": value["item_ids"]})
    if "battle_items_endless" in data:
        add("items.endless", {"minutes": data.pop("battle_items_endless")})
    if "ototo_materials" in data:
        add("ototo.materials", {"values": data.pop("ototo_materials")})
    for field, key in (("gamatoto_helper_ids", "ids"), ("gamatoto_helper_rarities", "rarities")):
        if field in data:
            add("gamatoto.helpers", {key: data.pop(field)})
    if "gamatoto_helpers" in data:
        value = data.pop("gamatoto_helpers")
        if type(value) is list:
            args = {"ids": value}
        elif type(value) is dict and set(value) & {"ids", "rarities"}:
            args = value
        elif type(value) is dict:
            args = {"rarities": value}
        else:
            raise ValueError("gamatoto_helpers requires helper IDs or a rarity-count object")
        add("gamatoto.helpers", args)
    for field, action in (("unlock_cat_ids", "cats.unlock"), ("remove_cat_ids", "cats.remove")):
        if field in data:
            ids = _list(data.pop(field), field)
            if ids:
                add(action, {"select": [{"kind": "ids", "ids": ids}]})
    if "cat_levels" in data:
        value = data.pop("cat_levels")
        if type(value) is dict and "select" in value:
            add("cats.levels", value)
        else:
            for record in _cat_records(value, "cat_levels", "level"):
                record = _obj(record, "cat_levels entry", {"id", "cat_id", "level", "upgrade", "base", "plus_level", "plus", "unlock"})
                ident, _ = _pick_alias(record, ("id", "cat_id"), "cat id", True)
                args = {"select": [{"kind": "ids", "ids": [_id(ident, "cat id")]}]}
                for names, target in ((("level", "upgrade", "base"), "base"), (("plus_level", "plus"), "plus")):
                    amount, present = _pick_alias(record, names, target)
                    if present:
                        args[target] = amount
                if not set(args) & {"base", "plus"}:
                    raise ValueError("cat_levels requires base/level or plus")
                if "unlock" in record:
                    args["unlock"] = record["unlock"]
                add("cats.levels", args)
    if "cat_evolutions" in data:
        value = data.pop("cat_evolutions")
        if type(value) is dict and "select" in value:
            add("cats.forms", value)
        else:
            for record in _cat_records(value, "cat_evolutions", "form"):
                record = _obj(record, "cat_evolutions entry", {"id", "cat_id", "form", "evolution"})
                ident, _ = _pick_alias(record, ("id", "cat_id"), "cat id", True)
                form, _ = _pick_alias(record, ("form", "evolution"), "form", True)
                form = _int(form, "form", 1, 4)
                args = {"select": [{"kind": "ids", "ids": [_id(ident, "cat id")]}]}
                if form >= 3:
                    args.update(operation="true" if form == 3 else "fourth", set_current=True)
                else:
                    args.update(operation="current", form=form)
                add("cats.forms", args)
    if "cat_talents" in data:
        value = data.pop("cat_talents")
        if type(value) is dict and "select" in value:
            add("cats.talents", value)
        else:
            for record in _cat_records(value, "cat_talents", "levels"):
                record = _obj(record, "cat_talents entry")
                if "id" not in record and "cat_id" not in record:
                    raise ValueError("Each cat_talents entry requires a cat id")
                if set(record) - {"id", "cat_id", "levels", "talents"}:
                    # A numeric cat-id mapping whose value is directly a talent-id mapping.
                    ident = record.get("id", record.get("cat_id"))
                    levels = {key: val for key, val in record.items() if key not in ("id", "cat_id")}
                else:
                    ident, _ = _pick_alias(record, ("id", "cat_id"), "cat id", True)
                    levels, _ = _pick_alias(record, ("levels", "talents"), "talent levels", True)
                add("cats.talents", {"select": [{"kind": "ids", "ids": [_id(ident, "cat id")]}], "operation": "set", "levels": levels})
    if "talent_orbs" in data:
        value = _obj(data.pop("talent_orbs"), "talent_orbs")
        add("cats.orbs", value if set(value) & {"values", "all", "filters", "count"} else {"values": value})
    if "special_skills" in data:
        value = data.pop("special_skills")
        if type(value) is dict and "skills" in value:
            add("skills.set", value)
        else:
            pairs = enumerate(value) if type(value) is list else _obj(value, "special_skills").items()
            changes = {str(_id(key, "skill id")): deepcopy(amount) if type(amount) is dict else {"level": amount} for key, amount in pairs}
            add("skills.set", {"skills": changes})
    for field, target in (("castle_development", "development"), ("castle_levels", "levels")):
        if field not in data:
            continue
        value = data.pop(field)
        if target == "development" and type(value) is int:
            add("ototo.cannons", {"ids": "all", target: value})
        elif type(value) is dict and set(value) & {"ids", "entries"}:
            add("ototo.cannons", value)
        else:
            value = _obj(value, field)
            add("ototo.cannons", {"entries": [{"id": _id(key, "cannon id"), target: amount} for key, amount in value.items()]})
    for field, individual in (("clear_chapters", False), ("clear_stages", True), ("max_chapter_treasures", False), ("stage_treasures", True)):
        if field not in data:
            continue
        treasures = "treasure" in field
        for entry in _list(data.pop(field), field):
            if type(entry) is int and not individual:
                entry = {"chapter": entry}
            allowed = {"chapter", "stage", "treasure"} if treasures else {"chapter", "stage", "clear_amount", "clears", "map", "aku_map", "star"}
            if not individual:
                allowed -= {"stage", "map", "aku_map", "star"}
            required = {"chapter", "stage"} if individual else {"chapter"}
            entry = _obj(entry, field + " entry", allowed, required)
            cid = _int(entry["chapter"], "chapter", 0, 8 if treasures else 9)
            if treasures:
                args = {"chapters": [cid], "level": entry.get("treasure", 3)}
                if individual:
                    # This legacy field used a raw treasure slot. The typed API uses
                    # in-game order, so convert once here to preserve the old slot.
                    from bcsfe import core
                    raw_slot = _int(entry["stage"], "treasure stage", 0, 47)
                    args["stages"] = [core.StoryChapters.convert_stage_id(raw_slot)]
                add("stages.treasures", args)
            else:
                amount, present = _pick_alias(entry, ("clear_amount", "clears"), "clear count")
                amount = amount if present else 1
                if cid == 9:
                    args = {"clear_count": amount}
                    if individual:
                        mid, has_mid = _pick_alias(entry, ("map", "aku_map"), "Aku map")
                        args.update(stages=[entry["stage"]], map=mid if has_mid else 0, crown=_int(entry.get("star", 0), "star") + 1)
                    else:
                        args.update(progress="all", map="all", crown="all")
                    add("stages.aku", args)
                else:
                    if set(entry) & {"map", "aku_map", "star"}:
                        raise ValueError("map/aku_map/star are only supported for chapter 9 (Aku)")
                    args = {"chapters": [cid], "clear_count": amount}
                    if individual:
                        args["stages"] = [entry["stage"]]
                    add("stages.story", args)
    if "itf_timed_scores" in data:
        value = data.pop("itf_timed_scores")
        add("stages.itf_scores", value if type(value) is dict else {"chapters": "all", "score": value})
    if "event_tickets" in data:
        value = data.pop("event_tickets")
        if value is not False:
            value = _obj(value, "event_tickets (use {items: {game_item_id: quantity}})")
            add("items.event_tickets", value if "items" in value else {"items": value})
    for field, action in (("cat_shrine", "shrine.set"), ("ototo_cat_cannon", "ototo.cannons")):
        if field in data:
            value = data.pop(field)
            if value is not False:
                add(action, _obj(value, field))
    if "cat_storage" in data:
        value = data.pop("cat_storage")
        if value is not False:
            value = _obj(value, "cat_storage (use {operation: add/remove/clear, ...})")
            operation = value.pop("operation", None)
            if operation not in ("add", "remove", "clear"):
                raise ValueError("cat_storage.operation must be add, remove or clear")
            add("cats.storage." + operation, value)
    if "playtime" in data:
        value = data.pop("playtime")
        add("playtime.set", value if type(value) is dict else {"frames": value})
    if data:
        raise ValueError("Untranslated legacy fields: " + ", ".join(sorted(data)))
    return operations
