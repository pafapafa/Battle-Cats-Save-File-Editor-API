import sys
import os
import tempfile
from typing import Optional, Dict, Any, Tuple, List

os.environ["HOME"] = tempfile.gettempdir()

try:
    from bcsfe import core
    if hasattr(core, "core_data") and hasattr(core.core_data, "init_data"):
        try:
            core.core_data.init_data()
        except Exception:
            pass
except ImportError:
    core = None

INT32_MAX = 2_147_483_647
SAFE_CATFOOD_MAX = 45_000
SAFE_XP_MAX = 99_999_999

_CC_CACHE = {}

def get_country_code(cc_str: str = "kr"):
    if core is None:
        return cc_str
    cc_key = (cc_str or "kr").lower()
    if cc_key in _CC_CACHE:
        return _CC_CACHE[cc_key]
    try:
        res = core.CountryCode.from_code(cc_key)
        _CC_CACHE[cc_key] = res
        return res
    except Exception:
        res = core.CountryCode.from_code("kr")
        _CC_CACHE[cc_key] = res
        return res

_DEFAULT_GV = None

def get_default_gv():
    global _DEFAULT_GV
    if _DEFAULT_GV is None and core is not None:
        try:
            _DEFAULT_GV = core.GameVersion(150400)
        except Exception:
            _DEFAULT_GV = None
    return _DEFAULT_GV

def download_ponos_save(tc: str, cc: str, country: str = "kr"):
    if core is None:
        return None, None
    try:
        country_code = get_country_code(country)
        gv = get_default_gv()
        sh, req_res = core.ServerHandler.from_codes(
            tc,
            cc,
            cc=country_code,
            gv=gv,
            print=False,
            save_backup=False,
        )
        if sh is None or getattr(sh, "save_file", None) is None:
            return None, None
        return sh.save_file, sh
    except Exception:
        return None, None

def patch_and_upload_save(
    save_file_or_bytes: Any = None,
    server_handler: Any = None,
    cc_str: str = "kr",
    catfood: Optional[int] = None,
    xp: Optional[int] = None,
    normal_tickets: Optional[int] = None,
    rare_tickets: Optional[int] = None,
    platinum_tickets: Optional[int] = None,
    legend_tickets: Optional[int] = None,
    platinum_shards: Optional[int] = None,
    np: Optional[int] = None,
    leadership: Optional[int] = None,
    catseyes: Any = None,
    catfruit: Any = None,
    catamins: Any = None,
    battle_items: Any = None,
    gamatoto_level: Optional[int] = None,
    gamatoto_xp: Optional[int] = None,
    gamatoto_helpers: Any = None,
    gamatoto_helper_ids: Optional[List[int]] = None,
    gamatoto_helper_rarities: Optional[Dict[str, int]] = None,
    ototo_engineers: Optional[int] = None,
    ototo_materials: Any = None,
    unlock_cats: bool = False,
    unlock_cat_ids: Optional[List[int]] = None,
    remove_cat_ids: Optional[List[int]] = None,
    clear_all_stages: bool = False,
    clear_chapters: Optional[List[int]] = None,
    clear_stages: Optional[List[Dict[str, int]]] = None,
    max_treasures: bool = False,
    max_chapter_treasures: Optional[List[int]] = None,
    stage_treasures: Optional[List[Dict[str, int]]] = None,
    enable_safety: bool = False,
    save_file: Any = None,
    **kwargs: Any,
) -> Tuple[Dict[str, Any], Optional[Tuple[str, str]]]:
    if enable_safety:
        if catfood is not None:
            catfood = min(catfood, SAFE_CATFOOD_MAX)
        if xp is not None:
            xp = min(xp, SAFE_XP_MAX)

    sh = server_handler or kwargs.get("sh")
    sf = save_file or save_file_or_bytes or getattr(sh, "save_file", None) or kwargs.get("sf")

    if sh is None or sf is None:
        return {}, None

    res = {
        "original_catfood": getattr(sf, "catfood", 0),
        "original_xp": getattr(sf, "xp", 0),
    }

    if catfood is not None:
        try:
            sf.catfood = max(0, min(int(catfood), INT32_MAX))
            res["new_catfood"] = sf.catfood
        except Exception:
            pass

    if xp is not None:
        try:
            sf.xp = max(0, min(int(xp), INT32_MAX))
            res["new_xp"] = sf.xp
        except Exception:
            pass

    if normal_tickets is not None and hasattr(sf, "normal_tickets"):
        try:
            sf.normal_tickets = max(0, min(int(normal_tickets), INT32_MAX))
            res["new_normal_tickets"] = sf.normal_tickets
        except Exception:
            pass

    if rare_tickets is not None:
        try:
            sf.rare_tickets = max(0, min(int(rare_tickets), INT32_MAX))
            res["new_rare_tickets"] = sf.rare_tickets
        except Exception:
            pass

    if platinum_tickets is not None:
        try:
            sf.platinum_tickets = max(0, min(int(platinum_tickets), INT32_MAX))
            res["new_platinum_tickets"] = sf.platinum_tickets
        except Exception:
            pass

    if legend_tickets is not None:
        try:
            sf.legend_tickets = max(0, min(int(legend_tickets), INT32_MAX))
            res["new_legend_tickets"] = sf.legend_tickets
        except Exception:
            pass

    if platinum_shards is not None and hasattr(sf, "platinum_shards"):
        try:
            sf.platinum_shards = max(0, min(int(platinum_shards), INT32_MAX))
            res["new_platinum_shards"] = sf.platinum_shards
        except Exception:
            pass

    if np is not None and hasattr(sf, "np"):
        try:
            sf.np = max(0, min(int(np), INT32_MAX))
            res["new_np"] = sf.np
        except Exception:
            pass

    if leadership is not None and hasattr(sf, "leadership"):
        try:
            sf.leadership = max(0, min(int(leadership), 32767))
            res["new_leadership"] = sf.leadership
        except Exception:
            pass

    # Catseyes
    if catseyes is not None and hasattr(sf, "catseyes"):
        try:
            if isinstance(catseyes, dict):
                ex_val = int(catseyes.get("ex", catseyes.get("special", 0)))
                rare_val = int(catseyes.get("rare", 0))
                sr_val = int(catseyes.get("super_rare", catseyes.get("super", 0)))
                ur_val = int(catseyes.get("uber_rare", catseyes.get("uber", 0)))
                leg_val = int(catseyes.get("legend", 0))
                catseyes_list = [ex_val, rare_val, sr_val, ur_val, leg_val]
                if len(sf.catseyes) > 5:
                    catseyes_list.extend([ex_val] * (len(sf.catseyes) - 5))
                sf.catseyes = [max(0, min(x, INT32_MAX)) for x in catseyes_list]
            elif isinstance(catseyes, list):
                sf.catseyes = [max(0, min(int(x), INT32_MAX)) for x in catseyes]
            else:
                val = max(0, min(int(catseyes), INT32_MAX))
                if len(sf.catseyes) > 0:
                    sf.catseyes = [val] * len(sf.catseyes)
                else:
                    sf.catseyes = [val] * 6
            res["new_catseyes"] = sf.catseyes
        except Exception:
            pass

    # Catfruit (개불/개개불)
    if catfruit is not None and hasattr(sf, "catfruit"):
        try:
            if isinstance(catfruit, list):
                sf.catfruit = [max(0, min(int(x), INT32_MAX)) for x in catfruit]
            else:
                val = max(0, min(int(catfruit), INT32_MAX))
                if len(sf.catfruit) > 0:
                    sf.catfruit = [val] * len(sf.catfruit)
                else:
                    sf.catfruit = [val] * 30
            res["new_catfruit"] = sf.catfruit
        except Exception:
            pass

    # Catamins (비타민)
    if catamins is not None and hasattr(sf, "catamins"):
        try:
            if isinstance(catamins, list):
                sf.catamins = [max(0, min(int(x), INT32_MAX)) for x in catamins]
            else:
                val = max(0, min(int(catamins), INT32_MAX))
                if len(sf.catamins) > 0:
                    sf.catamins = [val] * len(sf.catamins)
                else:
                    sf.catamins = [val] * 3
            res["new_catamins"] = sf.catamins
        except Exception:
            pass

    # Gamatoto Level & XP (가마토토 레벨 및 경험치)
    if (gamatoto_level is not None or gamatoto_xp is not None) and hasattr(sf, "gamatoto") and sf.gamatoto:
        try:
            if gamatoto_xp is not None:
                sf.gamatoto.xp = max(0, min(int(gamatoto_xp), INT32_MAX))
                res["new_gamatoto_xp"] = sf.gamatoto.xp
            elif gamatoto_level is not None:
                lvl = max(1, min(int(gamatoto_level), 150))
                try:
                    gl = core.core_data.get_gamatoto_levels(sf)
                    xp = gl.get_xp_from_level(lvl)
                    if xp is not None:
                        sf.gamatoto.xp = xp
                    else:
                        sf.gamatoto.xp = lvl * 10000
                except Exception:
                    sf.gamatoto.xp = lvl * 10000
                res["new_gamatoto_level"] = lvl
        except Exception:
            pass

    # Gamatoto Helpers / Members (가마토토 10개 대원 슬롯 각각 "gold", "silver", "bronze" 직접 입력 지원)
    if (gamatoto_helpers or gamatoto_helper_ids or gamatoto_helper_rarities) and hasattr(sf, "gamatoto") and sf.gamatoto:
        try:
            from bcsfe.core.game.gamoto.gamatoto import Helper, Helpers
            members_name = core.core_data.get_gamatoto_members_name(sf)
            r2_members = members_name.get_all_rarity(2) or [] # Gold / Legend / Master (금색 상급)
            r1_members = members_name.get_all_rarity(1) or [] # Silver / Rare (은색 중급)
            r0_members = members_name.get_all_rarity(0) or [] # White / Bronze / Common (백색/브론즈 하급)

            new_helpers = []

            if isinstance(gamatoto_helpers, list):
                r2_idx, r1_idx, r0_idx = 0, 0, 0
                for item in gamatoto_helpers[:10]:
                    val = str(item).lower()
                    if any(k in val for k in ["gold", "legend", "master", "grandmaster", "senior", "superior", "top", "2"]):
                        if r2_members:
                            new_helpers.append(Helper(r2_members[r2_idx % len(r2_members)].member_id))
                            r2_idx += 1
                    elif any(k in val for k in ["silver", "rare", "apprentice", "middle", "medium", "1"]):
                        if r1_members:
                            new_helpers.append(Helper(r1_members[r1_idx % len(r1_members)].member_id))
                            r1_idx += 1
                    else: # white / bronze / common / intern / junior / basic / 0
                        if r0_members:
                            new_helpers.append(Helper(r0_members[r0_idx % len(r0_members)].member_id))
                            r0_idx += 1
            elif gamatoto_helper_ids and isinstance(gamatoto_helper_ids, list):
                for hid in gamatoto_helper_ids[:10]:
                    new_helpers.append(Helper(int(hid)))
            elif gamatoto_helper_rarities and isinstance(gamatoto_helper_rarities, dict) or isinstance(gamatoto_helpers, dict):
                h_dict = gamatoto_helper_rarities if isinstance(gamatoto_helper_rarities, dict) else gamatoto_helpers
                count_r2 = int(h_dict.get("gold", h_dict.get("legend", h_dict.get("rarity_2", 0))))
                count_r1 = int(h_dict.get("silver", h_dict.get("rare", h_dict.get("rarity_1", 0))))
                count_r0 = int(h_dict.get("bronze", h_dict.get("white", h_dict.get("common", h_dict.get("rarity_0", 0)))))

                for i in range(min(count_r2, len(r2_members))):
                    if len(new_helpers) < 10:
                        new_helpers.append(Helper(r2_members[i].member_id))
                for i in range(min(count_r1, len(r1_members))):
                    if len(new_helpers) < 10:
                        new_helpers.append(Helper(r1_members[i].member_id))
                for i in range(min(count_r0, len(r0_members))):
                    if len(new_helpers) < 10:
                        new_helpers.append(Helper(r0_members[i].member_id))
            else:
                rarity_idx = 2
                if isinstance(gamatoto_helpers, str):
                    h_str = gamatoto_helpers.lower()
                    if "silver" in h_str or "rare" in h_str:
                        rarity_idx = 1
                    elif "white" in h_str or "bronze" in h_str or "common" in h_str:
                        rarity_idx = 0

                members = members_name.get_all_rarity(rarity_idx) or r2_members
                if members:
                    for i in range(min(10, len(members))):
                        new_helpers.append(Helper(members[i].member_id))

            if new_helpers:
                sf.gamatoto.helpers = Helpers(new_helpers)
                res["gamatoto_helpers_updated"] = len(new_helpers)
        except Exception:
            pass

    # Ototo Engineers & Base Materials
    if (ototo_engineers is not None or ototo_materials is not None) and hasattr(sf, "ototo") and sf.ototo:
        try:
            if ototo_engineers is not None:
                sf.ototo.engineers = max(0, min(int(ototo_engineers), 10))
                res["new_ototo_engineers"] = sf.ototo.engineers
            if ototo_materials is not None and hasattr(sf.ototo, "base_materials") and sf.ototo.base_materials:
                if isinstance(ototo_materials, list):
                    sf.ototo.base_materials.materials = [max(0, min(int(x), INT32_MAX)) for x in ototo_materials]
                else:
                    val = max(0, min(int(ototo_materials), INT32_MAX))
                    sf.ototo.base_materials.materials = [val] * 12
                res["new_ototo_materials"] = sf.ototo.base_materials.materials
        except Exception:
            pass

    if unlock_cats:
        try:
            sf.unlock_equip_menu()
            sf.unlock_popups()
            if hasattr(sf, "cats") and hasattr(sf.cats, "get_cats_obtainable"):
                obtainable = sf.cats.get_cats_obtainable(sf) if hasattr(sf.cats.get_cats_obtainable, "__code__") and sf.cats.get_cats_obtainable.__code__.co_argcount > 1 else sf.cats.get_cats_obtainable()
                if obtainable:
                    for cat in obtainable:
                        cat.unlock(sf)
            res["unlock_cats"] = True
        except Exception:
            pass

    if unlock_cat_ids and hasattr(sf, "cats"):
        count = 0
        try:
            sf.unlock_equip_menu()
            sf.unlock_popups()
            for cid in unlock_cat_ids:
                try:
                    cid = int(cid)
                    cat = None
                    if hasattr(sf.cats, "get_cat_by_id"):
                        cat = sf.cats.get_cat_by_id(cid)
                    elif hasattr(sf.cats, "cats") and 0 <= cid < len(sf.cats.cats):
                        cat = sf.cats.cats[cid]
                    if cat:
                        cat.unlock(sf)
                        count += 1
                except Exception:
                    pass
            res["unlocked_cat_ids_count"] = count
        except Exception:
            pass

    if remove_cat_ids and hasattr(sf, "cats"):
        count = 0
        try:
            for cid in remove_cat_ids:
                try:
                    cid = int(cid)
                    cat = None
                    if hasattr(sf.cats, "get_cat_by_id"):
                        cat = sf.cats.get_cat_by_id(cid)
                    elif hasattr(sf.cats, "cats") and 0 <= cid < len(sf.cats.cats):
                        cat = sf.cats.cats[cid]
                    if cat:
                        cat.remove(reset=True, save_file=sf)
                        count += 1
                except Exception:
                    pass
            res["removed_cat_ids_count"] = count
        except Exception:
            pass

    if clear_all_stages and hasattr(sf, "story") and hasattr(sf.story, "chapters"):
        try:
            for ch in sf.story.chapters:
                ch.clear_chapter()
            if hasattr(sf, "aku") and hasattr(sf.aku, "clear_chapters"):
                sf.aku.clear_chapters()
            res["clear_all_stages"] = True
        except Exception:
            pass

    if clear_chapters and hasattr(sf, "story") and hasattr(sf.story, "chapters"):
        count = 0
        for item in clear_chapters:
            try:
                if isinstance(item, dict):
                    ch_id = int(item.get("chapter", 0))
                    amt = int(item.get("clear_amount", item.get("clears", 1)))
                    if 0 <= ch_id < len(sf.story.chapters):
                        ch = sf.story.chapters[ch_id]
                        if hasattr(ch, "stages") and ch.stages:
                            for st_id in range(len(ch.stages)):
                                ch.clear_stage(st_id, amt, overwrite_clear_progress=True)
                        else:
                            ch.clear_chapter()
                        count += 1
                else:
                    ch_id = int(item)
                    if 0 <= ch_id < len(sf.story.chapters):
                        sf.story.chapters[ch_id].clear_chapter()
                        count += 1
            except Exception:
                pass
        res["cleared_chapters_count"] = count

    if clear_stages and hasattr(sf, "story") and hasattr(sf.story, "chapters"):
        count = 0
        for item in clear_stages:
            try:
                if isinstance(item, dict):
                    ch_id = int(item.get("chapter", 0))
                    st_id = int(item.get("stage", 0))
                    amt = int(item.get("clear_amount", item.get("clears", 1)))
                    if 0 <= ch_id < len(sf.story.chapters):
                        sf.story.chapters[ch_id].clear_stage(st_id, amt, overwrite_clear_progress=True)
                        count += 1
            except Exception:
                pass
        res["cleared_stages_count"] = count

    if max_treasures and hasattr(sf, "story") and hasattr(sf.story, "chapters"):
        try:
            for ch in sf.story.chapters:
                for st_id in range(48):
                    ch.set_treasure(st_id, 3)
            res["max_treasures"] = True
        except Exception:
            pass

    if max_chapter_treasures and hasattr(sf, "story") and hasattr(sf.story, "chapters"):
        count = 0
        for item in max_chapter_treasures:
            try:
                if isinstance(item, dict):
                    ch_id = int(item.get("chapter", 0))
                    tr_val = int(item.get("treasure", 3))
                    if 0 <= ch_id < len(sf.story.chapters):
                        ch = sf.story.chapters[ch_id]
                        for st_id in range(48):
                            ch.set_treasure(st_id, min(3, max(0, tr_val)))
                        count += 1
                else:
                    ch_id = int(item)
                    if 0 <= ch_id < len(sf.story.chapters):
                        for st_id in range(48):
                            sf.story.chapters[ch_id].set_treasure(st_id, 3)
                        count += 1
            except Exception:
                pass
        res["max_chapter_treasures_count"] = count

    if stage_treasures and hasattr(sf, "story") and hasattr(sf.story, "chapters"):
        count = 0
        for item in stage_treasures:
            try:
                if isinstance(item, dict):
                    ch_id = int(item.get("chapter", 0))
                    st_id = int(item.get("stage", 0))
                    tr_val = int(item.get("treasure", 3))
                    if 0 <= ch_id < len(sf.story.chapters):
                        sf.story.chapters[ch_id].set_treasure(st_id, min(3, max(0, tr_val)))
                        count += 1
            except Exception:
                pass
        res["set_stage_treasures_count"] = count

    try:
        sh.update_managed_items()
    except Exception:
        pass

    try:
        codes = sh.get_codes()
        if codes and len(codes) == 2:
            return res, codes
    except Exception:
        pass

    return res, None
