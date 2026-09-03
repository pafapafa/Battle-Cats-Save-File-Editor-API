"""Explicit stage edits using the vendored BCSFE models and game metadata.

Story chapter ids are 0..8 (EoC, ItF, CotC). Stage/map ids are zero based;
crowns are one based. No edits run simply because a save is loaded.
"""
from __future__ import annotations

import random
import time
from functools import partial
from bcsfe import core

I32 = 2**31 - 1
I16 = 2**15 - 1


def _int(value, name, low=0, high=I32):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer between {low} and {high}")
    return value


def _bool(value, name):
    if type(value) is not bool:
        raise ValueError(f"{name} must be a boolean")
    return value


def _args(args, allowed, required=()):
    if not isinstance(args, dict):
        raise ValueError("args must be an object")
    extra = set(args) - set(allowed)
    missing = set(required) - set(args)
    if extra or missing:
        raise ValueError(f"Unexpected fields: {sorted(extra)}; missing fields: {sorted(missing)}")


def _select(value, available, name):
    available = list(available)
    if value == "all":
        if not available:
            raise ValueError(f"No available {name} in this save/metadata")
        return available
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} must be 'all' or a nonempty integer array")
    selected = [_int(v, name) for v in value]
    if len(set(selected)) != len(selected) or any(v not in available for v in selected):
        raise ValueError(f"{name} contains duplicates or unavailable ids")
    return sorted(selected)


def _story(sf, args):
    _args(args, {"chapters", "stages", "clear_count", "progress", "reset_after", "clear_prerequisites"}, {"chapters"})
    if ("clear_count" in args) == ("progress" in args):
        raise ValueError("Provide exactly one of clear_count or progress")
    reset = _bool(args.get("reset_after", False), "reset_after")
    prerequisites = _bool(args.get("clear_prerequisites", False), "clear_prerequisites")
    if "progress" in args and "stages" in args:
        raise ValueError("stages cannot be combined with progress")
    if "progress" in args and "reset_after" in args:
        raise ValueError("progress already resets stages after that position")
    chapters = sf.story.get_real_chapters()
    ids = _select(args["chapters"], range(len(chapters)), "chapters")
    plans = []
    for cid in ids:
        ch = chapters[cid]
        count = len(ch.get_valid_treasure_stages())
        if "progress" in args:
            progress = _int(args["progress"], "progress", 0, count)
            plans.append((ch, list(range(count)), progress, None))
        else:
            selected = _select(args.get("stages", "all"), range(count), "stages")
            value = _int(args["clear_count"], "clear_count", 0, I16)
            plans.append((ch, selected, None, value))
    for ch, selected, progress, value in plans:
        if progress is not None:
            for sid in selected:
                ch.stages[sid].clear_times = 1 if sid < progress else 0
            ch.progress = progress
        else:
            if reset:
                for sid in range(max(selected) + 1, len(ch.get_valid_treasure_stages())):
                    ch.stages[sid].clear_times = 0
                ch.progress = min(ch.progress, max(selected) + 1)
            for sid in selected:
                ch.stages[sid].clear_times = value
            ch.progress = max(ch.progress, max(selected) + 1) if value else min(ch.progress, min(selected))
    if prerequisites:
        for cid in ids:
            sf.story.clear_previous_chapters(cid)


def _treasures(sf, args):
    _args(args, {"chapters", "stages", "groups", "level"}, {"chapters", "level"})
    if "stages" in args and "groups" in args:
        raise ValueError("Choose stages or groups")
    level = _int(args["level"], "level")
    chapters = sf.story.get_real_chapters()
    ids = _select(args["chapters"], range(len(chapters)), "chapters")
    targets = []
    for cid in ids:
        ch = chapters[cid]
        valid = range(len(ch.get_valid_treasure_stages()))
        if "groups" in args:
            groups = core.game.map.story.TreasureGroupData(sf, core.StoryChapters.get_chapter_type_from_index(cid)).treasure_group_data
            if groups is None:
                raise ValueError("Treasure group metadata is unavailable")
            group_ids = _select(args["groups"], range(len(groups)), "groups")
            selected = sorted({sid for gid in group_ids for sid in groups[gid]})
            if not selected or any(type(sid) is not int or sid not in valid for sid in selected):
                raise ValueError("Treasure group metadata contains invalid stage ids")
        else:
            selected = _select(args.get("stages", "all"), valid, "stages")
            # BCSFE stores treasures in reverse geographic order, unlike clear counts.
            selected = [core.StoryChapters.convert_stage_id(sid) for sid in selected]
        targets.extend(ch.stages[sid] for sid in selected)
    for stage in targets:
        stage.treasure = level


def _itf_scores(sf, args):
    _args(args, {"chapters", "stages", "score", "score_range"}, {"chapters"})
    if ("score" in args) == ("score_range" in args):
        raise ValueError("Provide exactly one of score or score_range")
    if "score" in args:
        low = high = _int(args["score"], "score")
    else:
        values = args["score_range"]
        if not isinstance(values, list) or len(values) != 2:
            raise ValueError("score_range must contain [minimum, maximum], inclusive")
        low, high = [_int(v, "score_range") for v in values]
        if low > high:
            raise ValueError("score_range minimum must not exceed maximum")
    chapters = sf.story.get_real_chapters()
    ids = _select(args["chapters"], range(3, min(6, len(chapters))), "chapters")
    targets = []
    for cid in ids:
        ch = chapters[cid]
        selected = _select(args.get("stages", "all"), range(len(ch.get_valid_treasure_stages())), "stages")
        targets.extend(ch.stages[sid] for sid in selected)
    for stage in targets:
        stage.itf_timed_score = random.randint(low, high)


# Prefixes and category offsets are the exact FeatureHandler/CLI registrations.
MAPS = {
    "sol": ("event_stages", "N", 0, 0),
    "event": ("event_stages", "S", 1000, 1),
    "collab": ("event_stages", "C", 2000, 2),
    "gauntlets": ("gauntlets", "A", 24000, None),
    "collab_gauntlets": ("collab_gauntlets", "CA", 27000, None),
    "uncanny": ("uncanny.chapters", "NA", 13000, None),
    "catamin": ("catamin_stages.chapters", "B", 14000, None),
    "behemoth": ("behemoth_culling", "Q", 31000, None),
    "legend_quest": ("legend_quest", "D", 16000, None),
    "towers": ("tower.chapters", "V", 7000, None),
    "zero_legends": ("zero_legends", "ND", 34000, None),
    "dojo_catclaw": ("dojo_chapters", "G", 37000, None),
    "enigma_clears": ("enigma_clears", "H", 25000, None),
}


def _metadata(sf, code, base, no_r_prefix=False):
    names = core.MapNames(sf, code, base_index=base, output=False, no_r_prefix=no_r_prefix)
    options = core.MapOption.from_save(sf)
    if not names.map_names or not names.stage_names or options is None:
        raise ValueError(f"Game map metadata is unavailable for {code}")
    return names, options


def _map_info(sf, kind):
    path, code, base, category = MAPS[kind]
    group = sf
    for name in path.split("."):
        group = getattr(group, name)
    if category is not None and category >= len(group.chapters):
        raise ValueError(f"{kind} stage structure is absent from this save")
    maps = group.chapters[category].chapters if category is not None else group.chapters
    names, options = _metadata(sf, code, base, kind == "dojo_catclaw")
    return maps, names, options, base


def _valid_stages(ch, names, map_id):
    row = names.stage_names.get(map_id)
    if not row:
        raise ValueError(f"Stage metadata is unavailable for map {map_id}")
    ids = [i for i, name in enumerate(row) if name and name != "＠"]
    if not ids or max(ids) >= len(ch.stages):
        raise ValueError(f"Map {map_id} metadata does not fit the save structure")
    return ids


def _unlock(ch, value):
    # ZeroLegends serializes unlock_state, not chapter_unlock_state (upstream typo).
    field = "unlock_state" if hasattr(ch, "unlock_state") else "chapter_unlock_state"
    setattr(ch, field, value)


def _unlock_value(ch):
    return ch.unlock_state if hasattr(ch, "unlock_state") else ch.chapter_unlock_state


def _stage_count(stage):
    return stage.clear_amount if hasattr(stage, "clear_amount") else stage.clear_times


def _set_count(stage, value, ensure=False):
    # The original Legend Quest editor couples tries to clear count; retain that behavior.
    stage.clear_stage(value, ensure_cleared_only=ensure)


def _map_edit(sf, args, kind):
    allowed = {"maps", "crowns", "stages", "clear_count", "progress", "ensure_cleared", "reset_after", "reset_following_crowns"}
    if kind == "catamin":
        allowed.add("completion_count")
    _args(args, allowed, {"maps"})
    if kind == "catamin" and "completion_count" in args:
        if set(args) != {"maps", "completion_count"}:
            raise ValueError("completion_count is a separate map-level edit")
        value = _int(args["completion_count"], "completion_count")
        names, _ = _metadata(sf, "B", 14000)
        ids = _select(args["maps"], names.map_names, "maps")
        for mid in ids:
            sf.event_stages.chapter_completion_count[14000 + mid] = value
        return
    if ("clear_count" in args) == ("progress" in args):
        raise ValueError("Provide exactly one of clear_count or progress")
    if "progress" in args and "stages" in args:
        raise ValueError("stages cannot be combined with progress")
    ensure = _bool(args.get("ensure_cleared", False), "ensure_cleared")
    reset_after = _bool(args.get("reset_after", False), "reset_after")
    reset_crowns = _bool(args.get("reset_following_crowns", False), "reset_following_crowns")
    if "progress" in args and "reset_after" in args:
        raise ValueError("progress already resets the remaining stages of selected crowns")
    if "progress" in args and "ensure_cleared" in args:
        raise ValueError("ensure_cleared is only valid with clear_count")
    value = _int(args.get("clear_count", 1), "clear_count", 0, I16)
    if ensure and value == 0:
        raise ValueError("ensure_cleared requires a positive clear_count")
    maps, names, options, base = _map_info(sf, kind)
    ids = _select(args["maps"], [i for i in names.map_names if 0 <= i < len(maps)], "maps")
    plans = []
    for mid in ids:
        stars = maps[mid].chapters
        option = options.get_map(base + mid)
        crowns = min(len(stars), option.crown_count) if option is not None else len(stars)
        selected_crowns = _select(args.get("crowns", "all"), range(1, crowns + 1), "crowns")
        for crown in selected_crowns:
            ch = stars[crown - 1]
            valid = _valid_stages(ch, names, mid)
            if "progress" in args:
                progress = _int(args["progress"], "progress", 0, len(valid))
                plans.append((mid, crown, crowns, ch, valid, progress))
            else:
                selected = _select(args.get("stages", "all"), valid, "stages")
                plans.append((mid, crown, crowns, ch, selected, None))
    reset_plans = []
    if reset_crowns:
        for mid in ids:
            map_plans = [plan for plan in plans if plan[0] == mid]
            highest = max(plan[1] for plan in map_plans)
            for index in range(highest, map_plans[0][2]):
                ch = maps[mid].chapters[index]
                reset_plans.append((mid, highest, index, ch, _valid_stages(ch, names, mid)))
    # All selectors/metadata are validated before the first mutation.
    for mid, crown, crowns, ch, selected, progress in plans:
        if progress is not None:
            for i, sid in enumerate(selected):
                _set_count(ch.stages[sid], 1 if i < progress else 0, ensure=i < progress)
            ch.clear_progress = selected[progress - 1] + 1 if progress else 0
            _unlock(ch, 3 if progress else max(1, _unlock_value(ch)))
        else:
            for sid in selected:
                _set_count(ch.stages[sid], value, ensure=ensure)
            if reset_after:
                for sid in _valid_stages(ch, names, mid):
                    if sid > max(selected):
                        _set_count(ch.stages[sid], 0)
                ch.clear_progress = min(ch.clear_progress, max(selected) + 1)
            if value:
                ch.clear_progress = max(ch.clear_progress, max(selected) + 1)
                _unlock(ch, 3)
            else:
                ch.clear_progress = min(ch.clear_progress, min(selected))
        valid = _valid_stages(ch, names, mid)
        if all(_stage_count(ch.stages[sid]) > 0 for sid in valid):
            if crown < crowns:
                nxt = maps[mid].chapters[crown]
                _unlock(nxt, max(1, _unlock_value(nxt)))
            # Original models unlock the next map when a map is completed.
            if mid + 1 < len(maps) and mid + 1 in names.map_names and maps[mid + 1].chapters:
                nxt = maps[mid + 1].chapters[0]
                _unlock(nxt, max(1, _unlock_value(nxt)))

    # Only reset crowns after the highest selected one for each map. Doing
    # this per selected crown would erase counts before ensure_cleared runs.
    for mid, highest, index, ch, valid in reset_plans:
        previous = maps[mid].chapters[highest - 1]
        complete = all(_stage_count(previous.stages[sid]) > 0 for sid in _valid_stages(previous, names, mid))
        for sid in valid:
            _set_count(ch.stages[sid], 0)
        ch.clear_progress = 0
        _unlock(ch, 1 if index == highest and complete else 0)


def _outbreaks(sf, args):
    _args(args, {"chapters", "stages", "cleared"}, {"chapters", "cleared"})
    clear = _bool(args["cleared"], "cleared")
    chapters = {ch.get_true_id(): ch for ch in sf.outbreaks.chapters.values()}
    ids = _select(args["chapters"], chapters, "chapters")
    targets = [(cid, sid) for cid in ids for sid in _select(args.get("stages", "all"), chapters[cid].outbreaks, "stages")]
    for cid, sid in targets:
        sf.outbreaks.clear_outbreak(cid, sid, clear)


def _aku(sf, args):
    _args(args, {"progress", "stages", "map", "crown", "clear_count", "clear_counts"})
    if ("progress" in args) == ("stages" in args):
        raise ValueError("Provide exactly one of progress or stages")
    if "clear_count" in args and "clear_counts" in args:
        raise ValueError("Provide clear_count or clear_counts")
    selected_map = args.get("map", 0)
    mids = _select("all" if selected_map == "all" else [selected_map], range(len(sf.aku.chapters)), "map")
    plans = []
    for mid in mids:
        stars = sf.aku.chapters[mid].chapters
        selected_crown = args.get("crown", 1)
        crowns = _select("all" if selected_crown == "all" else [selected_crown], range(1, len(stars) + 1), "crown")
        for crown in crowns:
            ch = stars[crown - 1]
            if "stages" in args:
                if "clear_counts" in args or "clear_count" not in args:
                    raise ValueError("Selected Aku stages require clear_count")
                ids = _select(args["stages"], range(len(ch.stages)), "stages")
                value = _int(args["clear_count"], "clear_count", 0, I16)
                plans.append((ch, {sid: value for sid in ids}))
                continue
            progress = len(ch.stages) if args["progress"] == "all" else _int(args["progress"], "progress", 0, len(ch.stages))
            if "clear_counts" in args:
                values = args["clear_counts"]
                if not isinstance(values, list) or len(values) != progress:
                    raise ValueError("clear_counts must contain one count per cleared stage")
                values = [_int(v, "clear_counts", 0, I16) for v in values]
            else:
                values = [_int(args.get("clear_count", 1), "clear_count", 0, I16)] * progress
            plans.append((ch, {sid: values[sid] if sid < progress else 0 for sid in range(len(ch.stages))}))
    for ch, values in plans:
        for sid, value in values.items():
            ch.stages[sid].clear_times = value


def _unlock_aku(sf, args):
    _args(args, set())
    # Explicit original unlock quest ids, not inferred map or stage counts.
    _map_edit(sf, {"maps": [255, 256, 257, 258, 265, 266, 268], "crowns": [1], "clear_count": 1, "ensure_cleared": True}, "event")


def _enigma(sf, args):
    _args(args, {"maps", "replace"}, {"maps"})
    replace = _bool(args.get("replace", False), "replace")
    names, _ = _metadata(sf, "H", 25000)
    ids = [] if replace and args["maps"] == [] else _select(args["maps"], names.map_names, "maps")
    existing = [] if replace else list(sf.enigma.stages)
    if len(existing) + len(ids) > 127:
        raise ValueError("Enigma stage count exceeds the save's signed-byte field (127)")
    if replace:
        for stage in sf.enigma.stages:
            sf.event_stages.chapter_completion_count[stage.stage_id] = 0
    for mid in ids:
        absolute = 25000 + mid
        sf.event_stages.chapter_completion_count[absolute] = 0
        existing.append(core.game.map.enigma.Stage(3, absolute, 2, int(time.time())))
    sf.enigma.stages = existing


def _tutorial(sf, args):
    _args(args, set())
    core.StoryChapters.clear_tutorial(sf)


def _filibuster(sf, args):
    _args(args, {"stage_id"})
    chapters = sf.story.get_real_chapters()
    if not chapters:
        raise ValueError("Story stage structure is absent")
    count = len(chapters[-1].get_valid_treasure_stages())
    stage_id = _int(args["stage_id"], "stage_id", 0, count - 1) if "stage_id" in args else random.randrange(count)
    sf.filibuster_stage_enabled = True
    sf.filibuster_stage_id = stage_id


def _dojo_score(sf, args):
    _args(args, {"score"}, {"score"})
    sf.dojo.chapters.get_stage(0, 0).score = _int(args["score"], "score")


def _challenge_score(sf, args):
    _args(args, {"score"}, {"score"})
    score = _int(args["score"], "score")
    maps = sf.challenge.chapters.chapters
    if not maps or not maps[0].chapters or not maps[0].chapters[0].stages:
        raise ValueError("Challenge stage structure is absent from this save")
    if not sf.challenge.scores:
        sf.challenge.scores = [score]
    else:
        sf.challenge.scores[0] = score
    sf.challenge.shown_popup = True
    ch = maps[0].chapters[0]
    _set_count(ch.stages[0], 1, ensure=True)
    ch.clear_progress = max(ch.clear_progress, 1)
    _unlock(ch, 3)


def _integer(maximum=I32, minimum=0):
    return {"type": "integer", "minimum": minimum, "maximum": maximum}


def _selection(description="Zero-based ids"):
    return {"description": description, "oneOf": [{"type": "string", "enum": ["all"]}, {"type": "array", "minItems": 1, "uniqueItems": True, "items": _integer()}]}


def _schema(properties, required=()):
    return {"type": "object", "additionalProperties": False, "properties": properties, "required": list(required)}


def _action(description, schema, apply, source):
    return {"description": description, "schema": schema, "apply": apply, "source": source}


MAP_SCHEMA = _schema({"maps": _selection(), "crowns": _selection("One-based crowns, limited by save and Map_option.csv"), "stages": _selection(), "clear_count": _integer(I16), "progress": _integer(), "ensure_cleared": {"type": "boolean", "default": False}, "reset_after": {"type": "boolean", "default": False}, "reset_following_crowns": {"type": "boolean", "default": False}}, ("maps",))
MAP_SOURCES = {
    "sol": "event.py:EventChapters.edit_sol_chapters", "event": "event.py:EventChapters.edit_event_chapters", "collab": "event.py:EventChapters.edit_collab_chapters",
    "gauntlets": "gauntlets.py:GauntletChapters.edit_gauntlets", "collab_gauntlets": "gauntlets.py:GauntletChapters.edit_collab_gauntlets", "behemoth": "gauntlets.py:GauntletChapters.edit_behemoth_culling", "enigma_clears": "gauntlets.py:GauntletChapters.edit_enigma_stages",
    "uncanny": "uncanny.py:UncannyChapters.edit_uncanny", "catamin": "uncanny.py:UncannyChapters.edit_catamin_stages", "legend_quest": "legend_quest.py:LegendQuestChapters.edit_legend_quest", "towers": "tower.py:TowerChapters.edit_towers", "zero_legends": "zero_legends.py:ZeroLegendsChapters.edit_zero_legends", "dojo_catclaw": "zero_legends.py:ZeroLegendsChapters.edit_catclaw_championships",
}
ACTIONS = {
    f"stages.{kind}": _action("Edit selected maps/crowns: clear_count changes selected stages; progress clears a prefix and resets the remaining stages of selected crowns. reset_after resets stages beyond the last selected stage; reset_following_crowns resets later valid crowns. Both default to false. Metadata is required.", MAP_SCHEMA, partial(_map_edit, kind=kind), "src/bcsfe/core/game/map/" + MAP_SOURCES[kind])
    for kind in MAPS
}
ACTIONS["stages.catamin"]["schema"] = _schema({**MAP_SCHEMA["properties"], "completion_count": _integer()}, ("maps",))
ACTIONS.update({
    "stages.story": _action("Edit story clear counts or exact progress. Chapter ids 0..8; stage ids follow in-game progress order. Other chapters, treasures and scores are preserved unless prerequisites are explicitly requested.", _schema({"chapters": _selection(), "stages": _selection(), "clear_count": _integer(I16), "progress": _integer(), "reset_after": {"type": "boolean"}, "clear_prerequisites": {"type": "boolean"}}, ("chapters",)), _story, "src/bcsfe/core/game/map/story.py:StoryChapters.clear_story"),
    "stages.treasures": _action("Set treasure levels on selected chapters and stages or metadata-defined treasure groups. Stage ids follow in-game order; only treasures change.", _schema({"chapters": _selection(), "stages": _selection(), "groups": _selection(), "level": _integer()}, ("chapters", "level")), _treasures, "src/bcsfe/core/game/map/story.py:StoryChapters.edit_treasures"),
    "stages.itf_scores": _action("Set ItF timed scores; chapters 3..5, exact score or inclusive random range. Clears and treasures are preserved.", _schema({"chapters": _selection(), "stages": _selection(), "score": _integer(), "score_range": {"type": "array", "minItems": 2, "maxItems": 2, "items": _integer()}}, ("chapters",)), _itf_scores, "src/bcsfe/core/game/map/story.py:StoryChapters.edit_itf_timed_scores"),
    "stages.outbreaks": _action("Clear/reset existing zombie outbreaks. Chapter ids follow story ids 0..8; clearing also dismisses that current outbreak, as upstream.", _schema({"chapters": _selection(), "stages": _selection(), "cleared": {"type": "boolean"}}, ("chapters", "cleared")), _outbreaks, "src/bcsfe/core/game/map/outbreaks.py:Outbreaks.edit_outbreaks"),
    "stages.aku": _action("Set Aku Realm progress and optional individual counts; remaining stages reset. Unrelated Aku fields are preserved.", _schema({"progress": {"oneOf": [_integer(), {"const": "all"}]}, "stages": _selection(), "map": {"oneOf": [_integer(), {"const": "all"}]}, "crown": {"oneOf": [_integer(minimum=1), {"const": "all"}]}, "clear_count": _integer(I16), "clear_counts": {"type": "array", "items": _integer(I16)}}), _aku, "src/bcsfe/core/game/map/aku.py:AkuChapters.edit_aku_chapters"),
    "stages.unlock_aku": _action("Clear the original seven Aku unlock quests, requiring valid game metadata.", _schema({}), _unlock_aku, "src/bcsfe/cli/edits/aku_realm.py:unlock_aku_realm"),
    "stages.enigma": _action("Add decoded Enigma maps. replace=true clears the existing list; map ids are actual metadata ids, not positions in a menu. Use maps=[] with replace=true to remove all.", _schema({"maps": {"oneOf": [{"type": "string", "enum": ["all"]}, {"type": "array", "uniqueItems": True, "items": _integer()}]}, "replace": {"type": "boolean", "default": False}}, ("maps",)), _enigma, "src/bcsfe/core/game/map/enigma.py:edit_enigma"),
    "stages.tutorial": _action("Explicitly clear tutorial using the original StoryChapters routine.", _schema({}), _tutorial, "src/bcsfe/cli/edits/clear_tutorial.py:clear_tutorial"),
    "stages.filibuster": _action("Enable Filibuster replay, optionally selecting the stage; otherwise choose a valid random stage as upstream.", _schema({"stage_id": _integer()}), _filibuster, "src/bcsfe/cli/edits/basic_items.py:BasicItems.allow_filibuster_stage_reclearing"),
    "stages.dojo_score": _action("Set the regular dojo score. Online ranking submission is not performed.", _schema({"score": _integer()}, ("score",)), _dojo_score, "src/bcsfe/core/game/map/dojo.py:edit_dojo_score"),
    "stages.challenge_score": _action("Set challenge score and its completed/popup state; other challenge scores are preserved.", _schema({"score": _integer()}, ("score",)), _challenge_score, "src/bcsfe/core/game/map/challenge.py:edit_challenge_score"),
})
