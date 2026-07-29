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
_CAT_DB_CACHE = None

def get_cat_max_forms(cat_id: int, sf=None) -> int:
    global _CAT_DB_CACHE
    try:
        if sf is not None and core is not None and hasattr(core, "Cat") and hasattr(core.Cat, "get_names"):
            names = core.Cat.get_names(cat_id, sf)
            if names:
                return len(names)
    except Exception:
        pass
    try:
        if _CAT_DB_CACHE is None:
            cat_db_path = r'C:\Users\USER\Desktop\database.json'
            if os.path.exists(cat_db_path):
                import json
                with open(cat_db_path, 'r', encoding='utf-8') as f:
                    _CAT_DB_CACHE = json.load(f)
            else:
                _CAT_DB_CACHE = {}
        forms = _CAT_DB_CACHE.get(str(cat_id), [])
        valid = [x for x in forms if isinstance(x, str) and x.strip()]
        if valid:
            return len(valid)
    except Exception:
        pass
    return 3

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
    behemoth_stones: Any = None,
    catamins: Any = None,
    battle_items: Any = None,
    gamatoto_level: Optional[int] = None,
    gamatoto_xp: Optional[int] = None,
    gamatoto_helpers: Any = None,
    gamatoto_helper_ids: Optional[List[int]] = None,
    gamatoto_helper_rarities: Optional[Dict[str, int]] = None,
    ototo_engineers: Optional[int] = None,
    ototo_materials: Any = None,
    base_materials: Any = None,
    unlock_cats: bool = False,
    unlock_cat_ids: Optional[List[int]] = None,
    remove_cat_ids: Optional[List[int]] = None,
    cat_levels: Any = None,
    cat_evolutions: Any = None,
    cat_forms: Any = None,
    max_cat_levels: bool = False,
    true_form_all: bool = False,
    max_cat_evolutions: bool = False,
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

    # Catfruit & Seeds (개다래 열매 및 씨앗)
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

    # Behemoth Stones & Gems (수석 및 수석 결정)
    if behemoth_stones is not None and hasattr(sf, "catfruit"):
        try:
            if len(sf.catfruit) < 30:
                sf.catfruit.extend([0] * (30 - len(sf.catfruit)))
            if isinstance(behemoth_stones, list):
                for idx, val in enumerate(behemoth_stones):
                    if 18 + idx < len(sf.catfruit):
                        sf.catfruit[18 + idx] = max(0, min(int(val), INT32_MAX))
            else:
                val = max(0, min(int(behemoth_stones), INT32_MAX))
                for i in range(18, min(30, len(sf.catfruit))):
                    sf.catfruit[i] = val
            res["new_behemoth_stones"] = sf.catfruit[18:]
        except Exception:
            pass

    # Catamins (비타민 A, B, C)
    if catamins is not None and hasattr(sf, "catamins"):
        try:
            if isinstance(catamins, dict):
                a_val = int(catamins.get("a", catamins.get("catamins_a", 0)))
                b_val = int(catamins.get("b", catamins.get("catamins_b", 0)))
                c_val = int(catamins.get("c", catamins.get("catamins_c", 0)))
                sf.catamins = [max(0, min(x, INT32_MAX)) for x in [a_val, b_val, c_val]]
            elif isinstance(catamins, list):
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

    # Ototo Engineers & Base Building Materials
    m_val = ototo_materials if ototo_materials is not None else base_materials
    if (ototo_engineers is not None or m_val is not None) and hasattr(sf, "ototo") and sf.ototo:
        try:
            if ototo_engineers is not None:
                sf.ototo.engineers = max(0, min(int(ototo_engineers), 10))
                res["new_ototo_engineers"] = sf.ototo.engineers
            if m_val is not None and hasattr(sf.ototo, "base_materials") and sf.ototo.base_materials:
                if isinstance(m_val, list):
                    sf.ototo.base_materials.materials = [max(0, min(int(x), INT32_MAX)) for x in m_val]
                elif isinstance(m_val, dict):
                    mat_list = getattr(sf.ototo.base_materials, "materials", [0]*24)
                    if len(mat_list) < 24:
                        mat_list.extend([0]*(24 - len(mat_list)))
                    for i, (k, v) in enumerate(m_val.items()):
                        if i < len(mat_list):
                            mat_list[i] = max(0, min(int(v), INT32_MAX))
                    sf.ototo.base_materials.materials = mat_list
                else:
                    val = max(0, min(int(m_val), INT32_MAX))
                    curr_len = max(len(getattr(sf.ototo.base_materials, "materials", [])), 24)
                    sf.ototo.base_materials.materials = [val] * curr_len
                res["new_base_materials"] = sf.ototo.base_materials.materials
        except Exception:
            pass

    # Unlock All Cats
    if unlock_cats and hasattr(sf, "cats"):
        try:
            try:
                sf.unlock_equip_menu()
            except Exception:
                pass
            try:
                sf.unlock_popups()
            except Exception:
                pass
            for cat in getattr(sf.cats, "cats", []):
                cat.unlocked = 1
                cat.gatya_seen = 1
                try:
                    cat.unlock(sf)
                except Exception:
                    pass
            res["unlock_cats"] = True
        except Exception:
            pass

    # Unlock Specific Cat IDs
    if unlock_cat_ids and hasattr(sf, "cats"):
        count = 0
        try:
            for cid in unlock_cat_ids:
                try:
                    cid = int(cid)
                    cat = None
                    if hasattr(sf.cats, "get_cat_by_id"):
                        cat = sf.cats.get_cat_by_id(cid)
                    elif hasattr(sf.cats, "cats") and 0 <= cid < len(sf.cats.cats):
                        cat = sf.cats.cats[cid]
                    if cat:
                        cat.unlocked = 1
                        cat.gatya_seen = 1
                        try:
                            cat.unlock(sf)
                        except Exception:
                            pass
                        count += 1
                except Exception:
                    pass
            res["unlocked_cat_ids_count"] = count
        except Exception:
            pass

    # Remove Specific Cat IDs
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
                        cat.unlocked = 0
                        cat.gatya_seen = 0
                        try:
                            cat.remove(reset=True, save_file=sf)
                        except Exception:
                            pass
                        count += 1
                except Exception:
                    pass
            res["removed_cat_ids_count"] = count
        except Exception:
            pass

    # Cat Levels & Upgrades (특정 캐릭터 레벨 및 만렙 세팅)
    if (cat_levels or max_cat_levels) and hasattr(sf, "cats"):
        count = 0
        try:
            if max_cat_levels:
                for cat in getattr(sf.cats, "cats", []):
                    if getattr(cat, "unlocked", False):
                        if hasattr(cat, "upgrade") and cat.upgrade:
                            cat.upgrade.base = 49 # Level 50
                            cat.upgrade.plus = 90 # +90
                        count += 1
                res["max_cat_levels_count"] = count

            if cat_levels:
                items = cat_levels if isinstance(cat_levels, list) else [cat_levels]
                if isinstance(cat_levels, dict):
                    items = [{"id": k, **(v if isinstance(v, dict) else {"level": v})} for k, v in cat_levels.items()]
                for item in items:
                    if isinstance(item, dict):
                        cid = int(item.get("id", item.get("cat_id", 0)))
                        lvl = int(item.get("level", item.get("upgrade", 50)))
                        plus = int(item.get("plus_level", item.get("plus", 0)))
                        cat = None
                        if hasattr(sf.cats, "get_cat_by_id"):
                            cat = sf.cats.get_cat_by_id(cid)
                        elif hasattr(sf.cats, "cats") and 0 <= cid < len(sf.cats.cats):
                            cat = sf.cats.cats[cid]
                        if cat:
                            cat.unlocked = 1
                            cat.gatya_seen = 1
                            if hasattr(cat, "upgrade") and cat.upgrade:
                                cat.upgrade.base = max(0, min(lvl - 1, 99))
                                cat.upgrade.plus = max(0, min(plus, 100))
                            count += 1
                res["updated_cat_levels_count"] = count
        except Exception:
            pass

    # Cat Evolutions & Forms (1진, 2진, 3진/True Form, 4진/Ultra Form 설정)
    evo_data = cat_evolutions if cat_evolutions is not None else cat_forms
    if (evo_data or true_form_all or max_cat_evolutions) and hasattr(sf, "cats"):
        count = 0
        try:
            if true_form_all or max_cat_evolutions:
                cats_list = getattr(sf.cats, "cats", [])
                for idx, cat in enumerate(cats_list):
                    if getattr(cat, "unlocked", False):
                        cid = getattr(cat, "id", idx)
                        max_forms = get_cat_max_forms(cid, sf)
                        target_form_idx = max(0, max_forms - 1)
                        cat.unlocked = 1
                        cat.gatya_seen = 1
                        cat.unlocked_forms = max_forms
                        cat.current_form = target_form_idx
                        count += 1
                res["max_cat_evolutions_count"] = count

            if evo_data:
                items = evo_data if isinstance(evo_data, list) else [evo_data]
                if isinstance(evo_data, dict):
                    items = [{"id": k, "form": v} for k, v in evo_data.items()]
                for item in items:
                    if isinstance(item, dict):
                        cid = int(item.get("id", item.get("cat_id", 0)))
                        form_val = int(item.get("form", item.get("evolution", 3)))
                        cat = None
                        if hasattr(sf.cats, "get_cat_by_id"):
                            cat = sf.cats.get_cat_by_id(cid)
                        elif hasattr(sf.cats, "cats") and 0 <= cid < len(sf.cats.cats):
                            cat = sf.cats.cats[cid]
                        if cat:
                            cat.unlocked = 1
                            cat.gatya_seen = 1
                            max_forms = get_cat_max_forms(cid, sf)
                            target_form = max(0, min(form_val - 1, max_forms - 1))
                            cat.unlocked_forms = max(getattr(cat, "unlocked_forms", 1), target_form + 1)
                            cat.current_form = target_form
                            count += 1
                res["updated_cat_evolutions_count"] = count
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
