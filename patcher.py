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
        for ch_id in clear_chapters:
            try:
                ch_id = int(ch_id)
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
                    ch_id = int(item.get("chapter"))
                    st_id = int(item.get("stage"))
                    amt = int(item.get("clear_amount", 1))
                    if 0 <= ch_id < len(sf.story.chapters) and 0 <= st_id < 51:
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
        for ch_id in max_chapter_treasures:
            try:
                ch_id = int(ch_id)
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
                    ch_id = int(item.get("chapter"))
                    st_id = int(item.get("stage"))
                    tr_val = int(item.get("treasure", 3))
                    if 0 <= ch_id < len(sf.story.chapters) and 0 <= st_id < 48:
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
