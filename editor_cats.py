from __future__ import annotations

import functools
import re
from typing import Any
from bcsfe import core

ACTIONS: dict[str, dict[str, Any]] = {}
I32 = 2147483647


def obj(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}


def integer(minimum=0, maximum=I32):
    return {"type": "integer", "minimum": minimum, "maximum": maximum}


def array(item, minimum=1):
    return {"type": "array", "items": item, "minItems": minimum, "maxItems": 10000}


BOOL = {"type": "boolean"}
IDS = array(integer())
TEXT = {"type": "string", "minLength": 1, "maxLength": 256}
MAX_LEVEL = {"anyOf": [integer(), {"const": "max"}]}
LEVEL_RANGE = obj({"min": integer(), "max": integer()}, ["min", "max"])
LEVEL_VALUE = {"anyOf": [integer(), {"const": "max"}, LEVEL_RANGE]}
SELECT_STEP = obj({
    "kind": {"enum": ["all", "current", "not_unlocked", "ids", "name", "rarity", "obtainable", "not_obtainable", "non_gacha", "banner", "banner_name", "game_version"]},
    "mode": {"enum": ["replace", "and", "or"]},
    "ids": IDS, "name": TEXT, "rarities": IDS,
    "versions": array(integer(1)),
    "version_ranges": array(obj({"min": integer(1), "max": integer(1)}, ["min", "max"])),
}, ["kind"])
SELECTION = array(SELECT_STEP)


def validate(value, schema, path="args"):

    if "anyOf" in schema:
        failures = []
        for alternative in schema["anyOf"]:
            try:
                validate(value, alternative, path)
                return
            except ValueError as exc:
                failures.append(str(exc))
        raise ValueError(f"{path}: value does not match the supported types")
    if "const" in schema and (type(value) is not type(schema["const"]) or value != schema["const"]):
        raise ValueError(f"{path}: expected {schema['const']!r}")
    if "enum" in schema and not any(type(value) is type(v) and value == v for v in schema["enum"]):
        raise ValueError(f"{path}: unsupported value")
    kind = schema.get("type")
    types = {"object": dict, "array": list, "integer": int, "boolean": bool, "string": str}
    if kind and type(value) is not types[kind]:
        raise ValueError(f"{path}: expected {kind}")
    if kind == "object":
        missing = set(schema.get("required", [])) - value.keys()
        if missing:
            raise ValueError(f"{path}: missing {', '.join(sorted(missing))}")
        props = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key, child in value.items():
            if type(key) is not str:
                raise ValueError(f"{path}: keys must be strings")
            if key in props:
                validate(child, props[key], f"{path}.{key}")
            elif additional is False:
                raise ValueError(f"{path}: unknown field {key}")
            elif type(additional) is dict:
                validate(child, additional, f"{path}.{key}")
    elif kind == "array":
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", I32):
            raise ValueError(f"{path}: invalid number of items")
        for index, child in enumerate(value):
            validate(child, schema["items"], f"{path}[{index}]")
    elif kind == "integer":
        if not schema.get("minimum", -I32-1) <= value <= schema.get("maximum", I32):
            raise ValueError(f"{path}: integer out of range")
    elif kind == "string":
        if not schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", I32):
            raise ValueError(f"{path}: invalid string length")


def action(name, description, schema, source):
    def decorate(fn):
        @functools.wraps(fn)
        def checked(sf, args):
            validate(args, schema)
            return fn(sf, args)
        ACTIONS[name] = {"description": description, "schema": schema, "apply": checked, "source": source}
        return checked
    return decorate


def needed(value, label):
    if value is None:
        raise ValueError(f"Required BCSFE game metadata unavailable: {label}")
    return value


def _cats_by_ids(sf, ids):
    mapping = {cat.id: cat for cat in sf.cats.cats}
    missing = set(ids) - mapping.keys()
    if missing:
        raise ValueError(f"Unknown cat IDs: {sorted(missing)}")
    return [cat for cat in sf.cats.cats if cat.id in ids]


def _unit_buy(sf):
    value = sf.cats.read_unitbuy(sf)
    needed(value.unit_buy, "unitbuy.csv")
    return value


def _picture_book(sf):
    value = sf.cats.read_nyanko_picture_book(sf)
    needed(value.cats, "nyankoPictureBook.csv")
    return value


def select_cats(sf, steps):

    validate(steps, SELECTION, "select")
    selected = set()
    required = {"ids": {"ids"}, "name": {"name"}, "rarity": {"rarities"}, "banner": {"ids"}, "banner_name": {"name"}}
    for index, step in enumerate(steps):
        kind = step["kind"]
        allowed = {"kind", "mode"} | required.get(kind, set())
        if kind == "game_version":
            allowed |= {"versions", "version_ranges"}
            if not (step.get("versions") or step.get("version_ranges")):
                raise ValueError("game_version selector requires versions or version_ranges")
        if set(step) - allowed or required.get(kind, set()) - step.keys():
            raise ValueError(f"Invalid fields for cat selector {kind}")
        if index == 0 and step.get("mode", "replace") != "replace":
            raise ValueError("The first selector must use replace mode")
        if kind == "all":
            found = sf.cats.cats
        elif kind == "current":
            found = sf.cats.get_unlocked_cats()
        elif kind == "not_unlocked":
            found = sf.cats.get_non_unlocked_cats()
        elif kind == "ids":
            found = _cats_by_ids(sf, step["ids"])
        elif kind == "name":
            found = []
            for cat in sf.cats.cats:
                names = needed(cat.get_names_cls(sf), f"cat names {cat.id}")
                if any(step["name"].casefold() in name.casefold() for name in names):
                    found.append(cat)
        elif kind in ("rarity", "non_gacha", "game_version"):
            unitbuy = _unit_buy(sf)
            found = []
            for cat in sf.cats.cats:
                row = needed(unitbuy.get_unit_buy(cat.id), f"unitbuy cat {cat.id}")
                if kind == "rarity":
                    match = row.rarity in step["rarities"]
                elif kind == "non_gacha":
                    match = row.unlock_source != 2
                else:
                    ranges = step.get("version_ranges", [])
                    if any(r["min"] > r["max"] for r in ranges):
                        raise ValueError("version range min must not exceed max")
                    match = row.game_version in step.get("versions", []) or any(r["min"] <= row.game_version <= r["max"] for r in ranges)
                if match:
                    found.append(cat)
        elif kind in ("obtainable", "not_obtainable"):
            book = _picture_book(sf)
            obtainable = needed(book.get_obtainable_cats(), "obtainable cats")
            ids = {item.cat_id for item in obtainable}
            found = [cat for cat in sf.cats.cats if (cat.id in ids) == (kind == "obtainable")]
        else:
            banner_ids = step.get("ids")
            if kind == "banner_name":
                names = needed(core.GatyaInfos(sf).get_all_names(), "gacha banner names")
                if not names:
                    raise ValueError("Gacha banner names unavailable")
                banner_ids = [bid for bid, name in names.items() if step["name"].casefold() in name.casefold()]
            gatya = sf.gatya.read_gatya_data_set(sf)
            needed(gatya.gatya_data_set, "GatyaDataSet")
            ids = set()
            for bid in banner_ids:
                ids.update(needed(gatya.get_cat_ids(bid), f"gacha banner {bid}"))
            found = _cats_by_ids(sf, ids)
        ids = {cat.id for cat in found}
        mode = step.get("mode", "replace")
        if mode == "and":
            selected &= ids
        elif mode == "or":
            selected |= ids
        else:
            selected = ids
    if not selected:
        raise ValueError("Cat selection matched no cats")
    return _cats_by_ids(sf, selected)


def _drop_plan(sf, cats):
    drops = core.core_data.get_chara_drop(sf)
    needed(drops.drops, "drop_chara.csv")
    result = []
    for cat in cats:
        for drop in needed(drops.get_drops_from_chara_id(cat.id), f"drops cat {cat.id}"):
            if not 0 <= drop.save_id < len(sf.unit_drops):
                raise ValueError("Drop metadata is incompatible with save unit_drops")
            result.append(drop.save_id)
    return result


def _unlock(sf, cats):
    if len(sf.menu_unlocks) < 3:
        raise ValueError("Save has no equip-menu unlock field")
    drops = _drop_plan(sf, cats)
    for cat in cats:
        cat.unlocked = 1
        cat.gatya_seen = 1
    for index in drops:
        sf.unit_drops[index] = 1
    sf.unlock_equip_menu()


@action("cats.unlock", "Unlock selected cats, original stage-drop flags and equip menu.", obj({"select": SELECTION}, ["select"]), "cli/edits/cat_editor.py:CatEditor.unlock_cats")
def unlock(sf, args):
    _unlock(sf, select_cats(sf, args["select"]))


@action("cats.remove", "Remove selected cats; reset=true also resets cat progress, new flags and stage drops.", obj({"select": SELECTION, "reset": BOOL}, ["select"]), "cli/edits/cat_editor.py:CatEditor.remove_cats")
def remove(sf, args):
    cats = select_cats(sf, args["select"])
    reset = args.get("reset", False)
    drops = _drop_plan(sf, cats) if reset else []
    for cat in cats:
        if reset:
            cat.reset()
            sf.cats.chara_new_flags[cat.id] = 0
        else:
            cat.unlocked = 0
    for index in drops:
        sf.unit_drops[index] = 0


@action("cats.forms", "Grant/remove true or fourth forms, or select a 1-based current form. force permits original forced evolution. unlock/set_current are explicit.", obj({"select": SELECTION, "operation": {"enum": ["true", "fourth", "remove_true", "remove_fourth", "current"]}, "force": BOOL, "unlock": BOOL, "set_current": BOOL, "form": integer(1, 4)}, ["select", "operation"]), "cli/edits/cat_editor.py:CatEditor.true_form_cats/fourth_form_cats/remove_true_form_cats/remove_fourth_form_cats")
def forms(sf, args):
    cats = select_cats(sf, args["select"])
    operation = args["operation"]
    if ("form" in args) != (operation == "current"):
        raise ValueError("form is required only for current operation")
    if operation.startswith("remove") and any(k in args for k in ("force", "unlock", "set_current")):
        raise ValueError("Remove form operations do not accept grant options")
    if operation == "current" and any(k in args for k in ("force", "set_current")):
        raise ValueError("Current form operation does not accept force/set_current")
    counts = {}
    if operation in ("true", "fourth", "current") and not args.get("force", False):
        book = _picture_book(sf)
        for cat in cats:
            entry = needed(book.get_cat(cat.id), f"picture book cat {cat.id}")
            counts[cat.id] = entry.total_forms
            if operation == "current" and args["form"] > entry.total_forms:
                raise ValueError(f"Cat {cat.id} has no form {args['form']}")
            if operation == "current" and args["form"] == 4 and cat.fourth_form == 0:
                raise ValueError(f"Cat {cat.id} fourth form is not unlocked")
            if operation == "current" and args["form"] == 3 and cat.unlocked_forms < 3:
                raise ValueError(f"Cat {cat.id} true form is not unlocked")
    if args.get("unlock", False):
        _unlock(sf, cats)
    for cat in cats:
        if operation == "remove_true":
            cat.remove_true_form()
        elif operation == "remove_fourth":
            cat.remove_fourth_form()
        elif operation == "current":
            cat.current_form = args["form"] - 1
        else:
            count = 4 if args.get("force", False) and operation == "fourth" else 3 if args.get("force", False) else counts[cat.id]
            if count == 4 and operation == "fourth":
                cat.unlocked_forms = 3
                cat.fourth_form = 2
                current = 3
            elif count >= 3:
                cat.unlocked_forms = 3
                current = 2
            else:
                cat.unlocked_forms = 0
                current = max(0, count - 1)
            if args.get("set_current", False):
                cat.current_form = current


class _PowerUp(core.PowerUpHelper):

    def __init__(self, cat, sf, strict):
        self.strict = strict
        super().__init__(cat, sf)
    def has_strict_upgrade(self):
        return self.strict
    def upgrade_cat(self, force=False):
        if force or self.can_power_up():
            self.cat.upgrade.upgrade()
            return True
        current_max = self.get_current_max_level()
        if self.can_use_catseye() and current_max is not None and self.unit_buy.max_upgrade_level_no_catseye <= current_max and self.cat.upgrade.get_base() < self.unit_buy.max_upgrade_level_catseye:
            self.cat.upgrade.upgrade()
            self.cat.catseyes_used += 1
            self.cat.max_upgrade_level.upgrade()
            return True
        return False


@action("cats.levels", "Set displayed base level (1-based) and/or plus level, or max / {min,max} random range. Omitted components stay unchanged; strict checks original progression limits.", obj({"select": SELECTION, "base": {"anyOf": [integer(1), {"const": "max"}, LEVEL_RANGE]}, "plus": LEVEL_VALUE, "unlock": BOOL, "strict": BOOL, "rank_up_sale": BOOL}, ["select"]), "cli/edits/cat_editor.py:CatEditor.upgrade_individual/upgrade_many;core/game/catbase/powerup.py:PowerUpHelper")
def levels(sf, args):
    if not any(k in args for k in ("base", "plus")):
        raise ValueError("base or plus is required")
    cats = select_cats(sf, args["select"])
    unitbuy = _unit_buy(sf)
    if "base" in args:
        needed(sf.cats.read_unitlimit(sf).unit_limit, "unitlimit.csv")
        needed(sf.user_rank_rewards.read_rank_gifts(sf).rank_gift, "rankGift.csv")
    plan = []
    for cat in cats:
        row = needed(unitbuy.get_unit_buy(cat.id), f"unitbuy cat {cat.id}")
        def resolve(value, maximum, minimum, component):
            if value is None:
                return None
            if value == "max":
                return maximum
            if isinstance(value, dict):
                if not minimum <= value["min"] <= value["max"] <= maximum:
                    raise ValueError(f"Invalid {component} range for cat {cat.id}")
                upgrade = core.Upgrade.init()
                if component == "base":
                    upgrade.base_range = (value["min"] - 1, value["max"] - 1)
                    return upgrade.get_random_base() + 1
                upgrade.plus_range = (value["min"], value["max"])
                return upgrade.get_random_plus()
            return value
        base = resolve(args.get("base"), row.max_upgrade_level_catseye, 1, "base")
        plus = resolve(args.get("plus"), row.max_plus_upgrade_level, 0, "plus")
        if base is not None and not 1 <= base <= row.max_upgrade_level_catseye:
            raise ValueError(f"base exceeds cat {cat.id} metadata limit")
        if plus is not None and not 0 <= plus <= row.max_plus_upgrade_level:
            raise ValueError(f"plus exceeds cat {cat.id} metadata limit")
        plan.append((cat, base, plus))
    if args.get("unlock", False):
        _unlock(sf, cats)
    for cat, base, plus in plan:
        if base is not None:
            power = _PowerUp(cat, sf, args.get("strict", False))
            power.reset_upgrade()
            power.upgrade_by(base - 1)
            if cat.upgrade.base != base - 1:
                raise ValueError(f"Requested base level is not reachable for cat {cat.id} with the selected progression limits")
        if plus is not None:
            cat.upgrade.plus = plus
    if args.get("rank_up_sale", False):
        sf.rank_up_sale_value = I32


TALENT_VALUES = {"type": "object", "additionalProperties": MAX_LEVEL}


@action("cats.talents", "Set selected talent IDs, maximize all existing talents or remove talent levels. Omitted talent IDs remain unchanged.", obj({"select": SELECTION, "operation": {"enum": ["set", "max", "remove"]}, "levels": TALENT_VALUES, "unlock": BOOL, "allow_metadata_version_mismatch": BOOL}, ["select", "operation"]), "cli/edits/cat_editor.py:CatEditor.edit_talent_individual/edit_talent_many/remove_talents_cats")
def talents(sf, args):
    cats = select_cats(sf, args["select"])
    operation = args["operation"]
    if ("levels" in args) != (operation == "set") or (operation == "set" and not args["levels"]):
        raise ValueError("Nonempty levels is required only for set operation")
    values = args.get("levels", {})
    if any(not re.fullmatch(r"0|[1-9][0-9]*", key) for key in values):
        raise ValueError("Talent level keys must be numeric talent IDs")
    plan = []
    if operation != "remove":
        gdg = core.core_data.get_game_data_getter(sf)
        if not args.get("allow_metadata_version_mismatch", False) and not gdg.does_save_version_match(sf):
            raise ValueError("Talent metadata version differs from save; explicit allow_metadata_version_mismatch is required")
        data = needed(sf.cats.read_talent_data(sf), "talent metadata")
        for cat in cats:
            skill = data.get_cat_skill(cat.id)
            if skill is None:
                if operation == "set":
                    raise ValueError(f"Cat {cat.id} has no talents in metadata")
                continue
            maxima = {item.ability_id: item.max_lv or 1 for item in skill.skills if item.ability_id > 0}
            if values and set(map(int, values)) - maxima.keys():
                raise ValueError(f"Unknown talent for cat {cat.id}")
            chosen = maxima if operation == "max" else {int(key): value for key, value in values.items()}
            for tid, value in chosen.items():
                talent = cat.get_talent_from_id(tid)
                if talent is None:
                    raise ValueError(f"Save has no talent {tid} for cat {cat.id}")
                level = maxima[tid] if value == "max" or operation == "max" else value
                if not 0 <= level <= maxima[tid]:
                    raise ValueError(f"Talent {tid} exceeds cat {cat.id} maximum")
                plan.append((talent, level))
    else:
        plan = [(talent, 0) for cat in cats for talent in cat.talents or []]
    if args.get("unlock", False):
        _unlock(sf, cats)
    for talent, level in plan:
        talent.level = level


@action("cats.guide", "Set collected status for only the selected cat-guide entries.", obj({"select": SELECTION, "collected": BOOL, "unlock": BOOL}, ["select", "collected"]), "cli/edits/cat_editor.py:CatEditor.unlock_cat_guide/remove_cat_guide")
def guide(sf, args):
    cats = select_cats(sf, args["select"])
    if args.get("unlock", False):
        _unlock(sf, cats)
    for cat in cats:
        cat.catguide_collected = args["collected"]


STORAGE_ITEM = obj({"kind": {"enum": ["cat", "special_skill"]}, "id": integer(), "quantity": integer(1)}, ["kind", "id", "quantity"])


@action("cats.storage.add", "Add exact quantities to empty storage slots; existing entries and storage capacity remain unchanged.", obj({"items": array(STORAGE_ITEM), "select": SELECTION, "quantity": integer(1)}), "cli/edits/storage.py:add_cats/add_special_skills")
def storage_add(sf, args):
    if ("items" in args) == ("select" in args) or ("quantity" in args) != ("select" in args):
        raise ValueError("Use items, or select with quantity for each selected cat")
    items = args.get("items")
    if items is None:
        items = [{"kind": "cat", "id": cat.id, "quantity": args["quantity"]} for cat in select_cats(sf, args["select"])]
    empty = [item for item in sf.cats.storage_items if item.item_type == 0]
    if sum(item["quantity"] for item in items) > len(empty):
        raise ValueError("Not enough empty storage slots")
    skills = None
    for item in items:
        if item["kind"] == "cat":
            _cats_by_ids(sf, [item["id"]])
        else:
            if skills is None:
                skills = needed(core.core_data.get_gatya_item_buy(sf).get_names_by_category(core.GatyaItemCategory.SPECIAL_SKILLS), "special skill names")
            if not 0 <= item["id"] < len(skills):
                raise ValueError("Unknown special skill storage index")
    offset = 0
    for item in items:
        for _ in range(item["quantity"]):
            empty[offset].item_type = 1 if item["kind"] == "cat" else 2
            empty[offset].item_id = item["id"]
            offset += 1


@action("cats.storage.remove", "Remove selected zero-based physical storage slots, leaving all other slots unchanged.", obj({"slots": IDS}, ["slots"]), "cli/edits/storage.py:remove_items")
def storage_remove(sf, args):
    if any(index >= len(sf.cats.storage_items) for index in args["slots"]):
        raise ValueError("Unknown storage slot")
    for index in args["slots"]:
        item = sf.cats.storage_items[index]
        item.item_id = 0
        item.item_type = 0


@action("cats.storage.clear", "Explicitly clear all existing storage slots without resizing storage.", obj({"confirm": {"const": True}}, ["confirm"]), "cli/edits/storage.py:clear_storage")
def storage_clear(sf, args):
    for item in sf.cats.storage_items:
        item.item_id = 0
        item.item_type = 0


ORB_FILTER = obj({"grade": TEXT, "attribute": TEXT, "effect": TEXT})
ORB_VALUES = {"type": "object", "additionalProperties": MAX_LEVEL}


@action("cats.orbs", "Edit exact orb IDs or metadata-selected orbs, including wildcard component filters. Unspecified counts remain unchanged.", obj({"values": ORB_VALUES, "all": BOOL, "filters": array(ORB_FILTER), "count": MAX_LEVEL}, []), "core/game/catbase/talent_orbs.py:SaveOrbs.edit_ind/edit_many/save")
def orbs(sf, args):
    modes = int("values" in args) + int(args.get("all", False)) + int("filters" in args)
    if modes != 1 or ("count" in args) != ("values" not in args):
        raise ValueError("Use values, or all=true/filters with count")
    orb_class = core.game.catbase.talent_orbs.OrbInfoList
    info = needed(orb_class.create(sf), "talent orb metadata")
    known = {orb.raw_orb_info.orb_id for orb in info.orb_info_list}
    if "values" in args:
        if not args["values"] or any(not re.fullmatch(r"0|[1-9][0-9]*", key) for key in args["values"]):
            raise ValueError("Orb values must be a nonempty mapping of numeric orb IDs")
        values = {int(key): value for key, value in args["values"].items()}
    else:
        ids = known if args.get("all", False) else set()
        for filters in args.get("filters", []):
            if not filters:
                raise ValueError("Orb filter requires at least one component; use '*' for wildcard")
            ids.update(orb.raw_orb_info.orb_id for orb in info.get_orbs_from_component_fuzzy(filters.get("grade", "*"), filters.get("attribute", "*"), filters.get("effect", "*")))
        values = {oid: args["count"] for oid in ids}
    if not values or set(values) - known:
        raise ValueError("Unknown or empty orb selection")
    maximum = min(core.core_data.max_value_manager.talent_orbs, 127 if sf.game_version < 110400 else 32767)
    plan = []
    for oid, count in values.items():
        if not 0 <= oid <= 32767:
            raise ValueError("Orb ID is not representable in the save")
        count = maximum if count == "max" else count
        if not 0 <= count <= maximum:
            raise ValueError(f"Orb count exceeds supported maximum {maximum}")
        plan.append((oid, count))
    for oid, count in plan:
        sf.talent_orbs.set_orb(oid, count)


SLOT_VALUES = {"type": "object", "additionalProperties": integer(-1)}
LINEUP_EDIT = obj({"id": integer(), "name": {"type": "string", "maxLength": 64}, "slots": SLOT_VALUES}, ["id"])


@action("cats.lineups", "Edit selected lineup names/physical slots or selected lineup. All omitted positions remain unchanged.", obj({"lineups": array(LINEUP_EDIT), "selected": integer()}), "core/game/battle/slots.py:LineUps/EquipSlots")
def lineups(sf, args):
    if not args:
        raise ValueError("At least one lineup change is required")
    total = len(sf.lineups.slots)
    if "selected" in args and args["selected"] >= total:
        raise ValueError("Unknown selected lineup")
    seen = set()
    for edit in args.get("lineups", []):
        if edit["id"] in seen or edit["id"] >= total:
            raise ValueError("Duplicate or unknown lineup")
        seen.add(edit["id"])
        if len(edit) == 1:
            raise ValueError("Lineup needs name or slots")
        slot_count = len(sf.lineups.slots[edit["id"]].slots)
        for key, cat_id in edit.get("slots", {}).items():
            if not re.fullmatch(r"0|[1-9][0-9]*", key) or int(key) >= slot_count:
                raise ValueError("Unknown physical lineup slot")
            if cat_id != -1:
                _cats_by_ids(sf, [cat_id])
    for edit in args.get("lineups", []):
        lineup = sf.lineups.slots[edit["id"]]
        if "name" in edit:
            lineup.name = edit["name"]
        for key, cat_id in edit.get("slots", {}).items():
            lineup.slots[int(key)].cat_id = cat_id
    if "selected" in args:
        sf.lineups.selected_slot = args["selected"]
