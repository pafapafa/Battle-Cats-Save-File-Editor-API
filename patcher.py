import sys
import os
import tempfile
from typing import Optional, Dict, Any, Tuple

# Use standard OS temp directory for bcsfe configuration and cache
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


def _get_country_code(cc_str: str):
    if core is None:
        return cc_str
    try:
        return core.CountryCode.from_code(cc_str.lower())
    except Exception:
        return core.CountryCode.from_code("kr")


def download_ponos_save(transfer_code: str, confirmation_code: str, cc_str: str = "kr"):
    if core is None:
        return None, None

    try:
        cc = _get_country_code(cc_str)
        gv = core.GameVersion(140300)

        # Call official bcsfe ServerHandler.from_codes
        sh, request_res = core.ServerHandler.from_codes(
            transfer_code,
            confirmation_code,
            cc=cc,
            gv=gv,
            print=False,
            save_backup=False,
        )

        if sh is None or sh.save_file is None:
            return None, None

        return sh.save_file, sh
    except Exception as e:
        print(f"Download Exception: {e}")
        return None, None


def patch_and_upload_save(
    save_file_or_bytes: Any,
    server_handler: Any,
    cc_str: str,
    catfood: Optional[int] = None,
    xp: Optional[int] = None,
    rare_tickets: Optional[int] = None,
    platinum_tickets: Optional[int] = None,
    legend_tickets: Optional[int] = None,
    unlock_cats: bool = False,
    max_treasures: bool = False,
    enable_safety: bool = False,
) -> Tuple[Dict[str, Any], Optional[Tuple[str, str]]]:
    if enable_safety:
        if catfood is not None:
            catfood = min(catfood, SAFE_CATFOOD_MAX)
        if xp is not None:
            xp = min(xp, SAFE_XP_MAX)

    if server_handler is None or not hasattr(server_handler, "save_file"):
        return {}, None

    sh = server_handler
    sf = sh.save_file

    result = {
        "original_catfood": getattr(sf, "catfood", 0),
        "original_xp": getattr(sf, "xp", 0),
    }

    # 1. Modify currency fields
    if catfood is not None:
        sf.catfood = catfood
        result["new_catfood"] = catfood
    if xp is not None:
        sf.xp = xp
        result["new_xp"] = xp
    if rare_tickets is not None:
        sf.rare_tickets = rare_tickets
        result["new_rare_tickets"] = rare_tickets
    if platinum_tickets is not None:
        sf.platinum_tickets = platinum_tickets
        result["new_platinum_tickets"] = platinum_tickets
    if legend_tickets is not None:
        sf.legend_tickets = legend_tickets
        result["new_legend_tickets"] = legend_tickets

    # 2. Unlock Cats if requested
    if unlock_cats:
        try:
            sf.unlock_equip_menu()
            sf.unlock_popups()
            result["unlock_cats"] = True
        except Exception:
            pass

    # 3. Max Treasures if requested
    if max_treasures:
        try:
            if hasattr(sf, "story") and hasattr(sf.story, "edit_treasures_whole_chapters"):
                sf.story.edit_treasures_whole_chapters(3)  # Gold treasure
            result["max_treasures"] = True
        except Exception:
            pass

    # 4. Sync managed items with PONOS server to prevent TE01 error
    try:
        sh.update_managed_items()
    except Exception as e:
        print(f"update_managed_items exception: {e}")

    # 5. Upload modified save file and issue new transfer codes
    try:
        codes = sh.get_codes()
        if codes and len(codes) == 2:
            return result, codes
    except Exception as e:
        print(f"get_codes exception: {e}")

    return result, None
