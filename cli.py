"""
Battle Cats Save File Editor API - CLI Client
Modeled after BCSFE-Python by fieryhenry.
"""
from __future__ import annotations

import requests
import sys
import os

API_URL = "https://battle-cats-save-file-editor-api.vercel.app"

# ──────────────────────────────────────────────────────
#  ANSI Color Helpers
# ──────────────────────────────────────────────────────

if os.name == "nt":
    os.system("color")

RESET = "\x1b[0m"
GREEN = "\x1b[38;5;34m"
CYAN = "\x1b[38;5;44m"
YELLOW = "\x1b[38;5;220m"
RED = "\x1b[38;5;196m"
GREY = "\x1b[38;5;245m"
WHITE = "\x1b[38;5;255m"
MAGENTA = "\x1b[38;5;207m"


def cprint(text: str, color: str = WHITE):
    print(f"{color}{text}{RESET}")


def cinput(prompt: str, color: str = CYAN) -> str:
    return input(f"{color}{prompt}{RESET}").strip()


# ──────────────────────────────────────────────────────
#  Locale
# ──────────────────────────────────────────────────────

STRINGS = {
    "en": {
        "select_language": "Select Language",
        "welcome": "Battle Cats Save File Editor",
        "version": "API Client v1.0.0",
        "select_save_option": "Select an option to load a save:",
        "download_save": "Download save using Transfer / Confirmation Code",
        "select_save_file": "Select a save file",
        "exit": "Exit",
        "enter_transfer_code": "Enter Transfer Code: ",
        "enter_confirmation_code": "Enter Confirmation Code: ",
        "select_country_code": "Select a country code:",
        "downloading_save": "Downloading save data from PONOS servers...",
        "save_downloaded": "Save data loaded successfully.",
        "invalid_codes": "Error: Invalid or expired transfer code / confirmation code.",
        "connection_error": "Connection error",
        "current_save": "Current save: gv={gv} cc={cc}",
        "select_features": "What do you want to edit? (enter a number or search): ",
        "features": "Features",
        "save_management": "Save Management",
        "items": "Items",
        "cats_and_levels": "Cats & Levels",
        "other": "Other",
        "go_back": "Go Back",
        "catfood": "Cat Food",
        "xp": "XP",
        "normal_tickets": "Normal Tickets",
        "rare_tickets": "Rare Tickets",
        "platinum_tickets": "Platinum Tickets",
        "legend_tickets": "Legend Tickets",
        "platinum_shards": "Platinum Shards",
        "np": "NP",
        "leadership": "Leadership",
        "unlock_cats": "Unlock All Cats",
        "max_treasures": "Max All Treasures",
        "clear_tutorial": "Clear Tutorial",
        "safety_limits": "Safety Limits",
        "save_upload": "Save & Upload (get new transfer code)",
        "save_save": "Save locally",
        "input": "{name} (Current: {value}) (Max: {max}): ",
        "input_no_max": "{name} (Current: {value}): ",
        "value_changed": "{name} set to {value}",
        "quit_key": "q",
        "yes_key": "y",
        "invalid_input": "Invalid input.",
        "catfood_warning": "Warning: Editing Cat Food directly can lead to a ban.\nDo you want to continue? (y/n): ",
        "rare_ticket_warning": "Warning: Editing Rare Tickets directly may cause issues.\nConsider using Rare Ticket Trade instead for safety.",
        "platinum_ticket_warning": "Warning: Editing Platinum Tickets directly may cause issues.\nConsider using Platinum Shards instead for safety.",
        "legend_ticket_warning": "Warning: Editing Legend Tickets directly is risky.\nDo you want to continue? (y/n): ",
        "no_feature_found": "No feature found with name: {name}",
        "patching": "Patching and uploading save to PONOS servers...",
        "upload_success": "Save modified and uploaded successfully.",
        "upload_fail": "Failed to upload save.",
        "new_codes": "Transfer Code: {tc}\nConfirmation Code: {cc}",
        "no_changes": "No changes to apply.",
        "on": "ON",
        "off": "OFF",
        "enable_yn": "Enable? (y/n): ",
        "file_not_found": "File not found.",
        "wip": "This feature is under development.",
        "leave": "Exiting editor.",
        "all_required": "All fields are required.",
        "country_jp": "jp (Japan)",
        "country_en": "en (Global / English)",
        "country_kr": "kr (Korea)",
        "country_tw": "tw (Taiwan)",
    },
    "kr": {
        "select_language": "언어 선택",
        "welcome": "Battle Cats Save File Editor",
        "version": "API Client v1.0.0",
        "select_save_option": "세이브를 불러올 방법을 선택하세요:",
        "download_save": "전송 코드 / 인증번호로 세이브 다운로드",
        "select_save_file": "세이브 파일 선택",
        "exit": "종료",
        "enter_transfer_code": "전송 코드 입력: ",
        "enter_confirmation_code": "인증번호 입력: ",
        "select_country_code": "국가 코드를 선택하세요:",
        "downloading_save": "PONOS 서버에서 세이브 데이터 다운로드 중...",
        "save_downloaded": "세이브 데이터 로드 성공.",
        "invalid_codes": "오류: 유효하지 않거나 만료된 전송 코드 / 인증번호.",
        "connection_error": "연결 오류",
        "current_save": "현재 세이브: gv={gv} cc={cc}",
        "select_features": "무엇을 수정할까요? (번호 또는 검색어 입력): ",
        "features": "기능 목록",
        "save_management": "세이브 관리",
        "items": "아이템",
        "cats_and_levels": "캐릭터 & 스테이지",
        "other": "기타",
        "go_back": "뒤로가기",
        "catfood": "냥코 열매",
        "xp": "XP",
        "normal_tickets": "일반 티켓",
        "rare_tickets": "레어 티켓",
        "platinum_tickets": "플래티넘 티켓",
        "legend_tickets": "레전드 티켓",
        "platinum_shards": "플래티넘 파편",
        "np": "NP",
        "leadership": "리더십",
        "unlock_cats": "모든 캐릭터 해금",
        "max_treasures": "모든 보물 최대화",
        "clear_tutorial": "튜토리얼 클리어",
        "safety_limits": "안전 제한",
        "save_upload": "세이브 업로드 (새 전송 코드 발급)",
        "save_save": "로컬에 저장",
        "input": "{name} (현재: {value}) (최대: {max}): ",
        "input_no_max": "{name} (현재: {value}): ",
        "value_changed": "{name} -> {value} (으)로 설정",
        "quit_key": "q",
        "yes_key": "y",
        "invalid_input": "잘못된 입력입니다.",
        "catfood_warning": "경고: 냥코 열매 직접 수정은 밴 위험이 있습니다.\n계속하시겠습니까? (y/n): ",
        "rare_ticket_warning": "경고: 레어 티켓 직접 수정은 문제를 일으킬 수 있습니다.",
        "platinum_ticket_warning": "경고: 플래티넘 티켓 직접 수정은 문제를 일으킬 수 있습니다.\n플래티넘 파편 사용을 권장합니다.",
        "legend_ticket_warning": "경고: 레전드 티켓 직접 수정은 위험합니다.\n계속하시겠습니까? (y/n): ",
        "no_feature_found": "'{name}'(와)과 일치하는 기능을 찾을 수 없습니다.",
        "patching": "세이브 패치 및 PONOS 서버 업로드 중...",
        "upload_success": "세이브 수정 및 업로드 성공.",
        "upload_fail": "세이브 업로드 실패.",
        "new_codes": "전송 코드: {tc}\n인증번호: {cc}",
        "no_changes": "적용할 변경사항이 없습니다.",
        "on": "ON",
        "off": "OFF",
        "enable_yn": "활성화? (y/n): ",
        "file_not_found": "파일을 찾을 수 없습니다.",
        "wip": "이 기능은 개발 중입니다.",
        "leave": "에디터를 종료합니다.",
        "all_required": "모든 항목을 입력해야 합니다.",
        "country_jp": "jp (일본)",
        "country_en": "en (글로벌 / 영어)",
        "country_kr": "kr (한국)",
        "country_tw": "tw (대만)",
    },
}

_lang = "en"


def localize(key: str, **kwargs) -> str:
    s = STRINGS.get(_lang, STRINGS["en"]).get(key, key)
    if kwargs:
        s = s.format(**kwargs)
    return s


# ──────────────────────────────────────────────────────
#  Dialog Creators (matching BCSFE dialog_creator.py)
# ──────────────────────────────────────────────────────

def display_options(options: list[str], title: str | None = None):
    if title:
        cprint(title, YELLOW)
    for i, opt in enumerate(options):
        cprint(f" {i + 1}. {opt}", CYAN)


def single_select(options: list[str], prompt: str) -> int | None:
    """BCSFE-style single select: show numbered list, return 0-based index."""
    display_options(options)
    print()
    while True:
        inp = cinput(prompt)
        if inp == localize("quit_key"):
            return None
        if inp.isdigit():
            idx = int(inp) - 1
            if 0 <= idx < len(options):
                return idx
            cprint(localize("invalid_input"), RED)
        else:
            # Search by text (BCSFE feature)
            inp_lower = inp.lower().replace(" ", "")
            for i, opt in enumerate(options):
                if inp_lower in opt.lower().replace(" ", ""):
                    return i
            cprint(localize("no_feature_found", name=inp), RED)


def yes_no(prompt: str) -> bool:
    inp = cinput(prompt)
    return inp.lower().strip() == localize("yes_key")


def edit_int(name: str, current: int, max_val: int | None = None) -> int:
    """BCSFE-style edit_int_raw: show current and max, return new value."""
    if max_val is not None:
        prompt = localize("input", name=name, value=f"{current:,}", max=f"{max_val:,}")
    else:
        prompt = localize("input_no_max", name=name, value=f"{current:,}")

    while True:
        inp = cinput(prompt)
        if inp == localize("quit_key") or inp == "":
            return current
        try:
            val = int(inp)
            if max_val is not None and val > max_val:
                val = max_val
            cprint(localize("value_changed", name=name, value=f"{val:,}"), GREEN)
            return val
        except ValueError:
            cprint(localize("invalid_input"), RED)


# ──────────────────────────────────────────────────────
#  Country Code Select (matching BCSFE CountryCode.select)
# ──────────────────────────────────────────────────────

COUNTRY_CODES = ["jp", "en", "kr", "tw"]


def select_country_code() -> str | None:
    options = [
        localize("country_jp"),
        localize("country_en"),
        localize("country_kr"),
        localize("country_tw"),
    ]
    idx = single_select(options, localize("select_country_code") + " ")
    if idx is None:
        return None
    return COUNTRY_CODES[idx]


# ──────────────────────────────────────────────────────
#  Server CLI (matching BCSFE server_cli.py)
# ──────────────────────────────────────────────────────

def download_save() -> dict | None:
    """Download save using transfer/confirmation code, like BCSFE ServerCLI.download_save"""
    tc = cinput(localize("enter_transfer_code"))
    if not tc:
        return None

    cc_code = cinput(localize("enter_confirmation_code"))
    if not cc_code:
        return None

    country = select_country_code()
    if country is None:
        return None

    cprint(localize("downloading_save"), YELLOW)

    try:
        r = requests.post(
            f"{API_URL}/info",
            json={
                "transfer_code": tc,
                "confirmation_code": cc_code,
                "country_code": country,
            },
            timeout=30,
        )
        data = r.json()
    except Exception as e:
        cprint(f"{localize('connection_error')}: {e}", RED)
        return None

    if not data.get("success"):
        cprint(localize("invalid_codes"), RED)
        return None

    cprint(localize("save_downloaded"), GREEN)

    return {
        "transfer_code": tc,
        "confirmation_code": cc_code,
        "country_code": country,
        "game_version": data.get("game_version", 0),
        "catfood": data.get("catfood", 0),
        "xp": data.get("xp", 0),
        "rare_tickets": data.get("rare_tickets", 0),
        "platinum_tickets": data.get("platinum_tickets", 0),
        "legend_tickets": data.get("legend_tickets", 0),
    }


# ──────────────────────────────────────────────────────
#  Select Save (matching BCSFE SaveManagement.select_save)
# ──────────────────────────────────────────────────────

def select_save() -> dict | None:
    """Main save selection menu, like BCSFE select_save."""
    print()
    cprint(localize("select_save_option"), YELLOW)

    options = [
        localize("download_save"),
        localize("select_save_file"),
        localize("exit"),
    ]
    idx = single_select(options, localize("select_features"))
    if idx is None:
        return None
    if idx == 0:
        return download_save()
    elif idx == 1:
        cprint(localize("wip"), GREY)
        return None
    elif idx == 2:
        cprint(localize("leave"), GREY)
        sys.exit(0)
    return None


# ──────────────────────────────────────────────────────
#  Feature Handler (matching BCSFE FeatureHandler)
# ──────────────────────────────────────────────────────

INT32_MAX = 2**31 - 1


class FeatureHandler:
    """Mimics BCSFE FeatureHandler with nested category dict navigation."""

    def __init__(self, session: dict):
        self.session = session
        self.edits: dict = {}
        self.flags: dict = {}

    def get_features(self) -> dict:
        return {
            localize("save_management"): {
                localize("save_upload"): self.save_upload,
            },
            localize("items"): {
                localize("catfood"): self.edit_catfood,
                localize("xp"): self.edit_xp,
                localize("rare_tickets"): self.edit_rare_tickets,
                localize("platinum_tickets"): self.edit_platinum_tickets,
                localize("legend_tickets"): self.edit_legend_tickets,
            },
            localize("cats_and_levels"): {
                localize("unlock_cats"): self.toggle_unlock_cats,
                localize("max_treasures"): self.toggle_max_treasures,
            },
            localize("other"): {
                localize("safety_limits"): self.toggle_safety,
            },
            localize("exit"): self.exit_editor,
        }

    def select_features_run(self):
        """Main feature selection loop, like BCSFE FeatureHandler.select_features_run"""
        features = self.get_features()
        feature_keys = list(features.keys())

        while True:
            print()
            cprint(
                localize(
                    "current_save",
                    gv=self.session.get("game_version", "?"),
                    cc=self.session.get("country_code", "?").upper(),
                ),
                GREY,
            )
            print()

            # Display top-level categories
            idx = single_select(feature_keys, localize("select_features"))
            if idx is None:
                continue

            selected_key = feature_keys[idx]
            selected = features[selected_key]

            if callable(selected):
                selected()
                features = self.get_features()
                feature_keys = list(features.keys())
                continue

            # Sub-menu
            if isinstance(selected, dict):
                self._run_submenu(selected_key, selected)
                features = self.get_features()
                feature_keys = list(features.keys())

    def _run_submenu(self, category_name: str, sub_features: dict):
        while True:
            print()
            sub_keys = [localize("go_back")] + list(sub_features.keys())
            cprint(category_name, YELLOW)
            idx = single_select(sub_keys, localize("select_features"))
            if idx is None or idx == 0:
                return

            selected_key = sub_keys[idx]
            func = sub_features.get(selected_key)
            if func and callable(func):
                func()

    # ── Item Edits (matching BCSFE BasicItems) ──

    def edit_catfood(self):
        if not yes_no(localize("catfood_warning")):
            return
        val = edit_int(
            localize("catfood"),
            self.session.get("catfood", 0),
            INT32_MAX,
        )
        self.edits["catfood"] = val

    def edit_xp(self):
        val = edit_int(
            localize("xp"),
            self.session.get("xp", 0),
            INT32_MAX,
        )
        self.edits["xp"] = val

    def edit_rare_tickets(self):
        cprint(localize("rare_ticket_warning"), YELLOW)
        val = edit_int(
            localize("rare_tickets"),
            self.session.get("rare_tickets", 0),
            INT32_MAX,
        )
        self.edits["rare_tickets"] = val

    def edit_platinum_tickets(self):
        cprint(localize("platinum_ticket_warning"), YELLOW)
        val = edit_int(
            localize("platinum_tickets"),
            self.session.get("platinum_tickets", 0),
            INT32_MAX,
        )
        self.edits["platinum_tickets"] = val

    def edit_legend_tickets(self):
        if not yes_no(localize("legend_ticket_warning")):
            return
        val = edit_int(
            localize("legend_tickets"),
            self.session.get("legend_tickets", 0),
            INT32_MAX,
        )
        self.edits["legend_tickets"] = val

    # ── Cats & Levels Toggles ──

    def toggle_unlock_cats(self):
        self.flags["unlock_cats"] = yes_no(
            f"{localize('unlock_cats')} - {localize('enable_yn')}"
        )
        status = localize("on") if self.flags["unlock_cats"] else localize("off")
        cprint(
            localize("value_changed", name=localize("unlock_cats"), value=status),
            GREEN,
        )

    def toggle_max_treasures(self):
        self.flags["max_treasures"] = yes_no(
            f"{localize('max_treasures')} - {localize('enable_yn')}"
        )
        status = localize("on") if self.flags["max_treasures"] else localize("off")
        cprint(
            localize("value_changed", name=localize("max_treasures"), value=status),
            GREEN,
        )

    # ── Other ──

    def toggle_safety(self):
        self.flags["enable_safety"] = yes_no(
            f"{localize('safety_limits')} - {localize('enable_yn')}"
        )
        status = localize("on") if self.flags["enable_safety"] else localize("off")
        cprint(
            localize("value_changed", name=localize("safety_limits"), value=status),
            GREEN,
        )

    # ── Save Upload (matching BCSFE SaveManagement.save_upload) ──

    def save_upload(self):
        has_work = bool(self.edits) or self.flags.get("unlock_cats") or self.flags.get("max_treasures")
        if not has_work:
            cprint(localize("no_changes"), YELLOW)
            return

        payload = {
            "transfer_code": self.session["transfer_code"],
            "confirmation_code": self.session["confirmation_code"],
            "country_code": self.session["country_code"],
            "enable_safety": self.flags.get("enable_safety", False),
        }
        payload.update(self.edits)
        if self.flags.get("unlock_cats"):
            payload["unlock_cats"] = True
        if self.flags.get("max_treasures"):
            payload["max_treasures"] = True

        cprint(localize("patching"), YELLOW)

        try:
            r = requests.post(f"{API_URL}/edit", json=payload, timeout=45)
            data = r.json()
        except Exception as e:
            cprint(f"{localize('connection_error')}: {e}", RED)
            return

        if not data or not data.get("success"):
            cprint(f"{localize('upload_fail')}: {data.get('message', '')}", RED)
            return

        new_tc = data.get("new_transfer_code")
        new_cc = data.get("new_confirmation_code")

        if new_tc and new_cc:
            cprint(localize("upload_success"), GREEN)
            print()
            cprint(localize("new_codes", tc=new_tc, cc=new_cc), GREEN)

            # Update session
            self.session["transfer_code"] = new_tc
            self.session["confirmation_code"] = new_cc
            for k, v in self.edits.items():
                self.session[k] = v
            self.edits = {}
            self.flags = {}
        else:
            cprint(localize("upload_fail"), RED)

    # ── Exit ──

    def exit_editor(self):
        if self.edits or any(self.flags.values()):
            cprint(localize("no_changes") + " " + localize("upload_fail"), YELLOW)
        cprint(localize("leave"), GREY)
        raise StopIteration


# ──────────────────────────────────────────────────────
#  Main (matching BCSFE Main class)
# ──────────────────────────────────────────────────────

def select_language():
    global _lang
    print()
    cprint(localize("select_language"), YELLOW)
    options = ["English", "Korean"]
    idx = single_select(options, "Select: ")
    if idx == 1:
        _lang = "kr"
    else:
        _lang = "en"


def main():
    select_language()

    print()
    cprint(f"{localize('welcome')} - {localize('version')}", CYAN)

    while True:
        session = select_save()
        if session is None:
            continue

        try:
            fh = FeatureHandler(session)
            fh.select_features_run()
        except StopIteration:
            pass
        except KeyboardInterrupt:
            cprint(localize("leave"), GREY)
            sys.exit(0)


if __name__ == "__main__":
    main()
