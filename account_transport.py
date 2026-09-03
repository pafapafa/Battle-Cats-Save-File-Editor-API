"""BCSFE account protocol with bounded attempts for HTTP requests.

Credential failures never create a replacement account. Account creation is an
explicit operation; its normal upstream request bodies and signatures are kept.
"""
from __future__ import annotations

import jwt

from bcsfe_runtime import core


class HeadlessServerHandler(core.ServerHandler):
    def get_password(self, tries: int = 0) -> str | None:
        password = self.get_stored_password()
        if password is not None:
            return password
        password = self.refresh_password()
        if password is not None:
            return password
        # A refresh can store credentials before its managed-item sync fails.
        # Do not register another password after that partially completed result.
        if self.get_stored_password() is not None:
            return None
        return self.get_password_new()

    def get_auth_token(self, tries: int = 1) -> str | None:
        token = self.get_stored_auth_token()
        if token is not None:
            try:
                valid = self.validate_auth_token(token)
            except (jwt.InvalidTokenError, ValueError, TypeError):
                valid = False
            if valid:
                return token
            self.remove_stored_auth_token()
        password = self.get_password()
        if password is None:
            return None
        # Upstream do_password_request can obtain a token while synchronizing
        # the returned account identity. Preserve that completed step.
        token = self.get_stored_auth_token()
        if token is not None:
            return token
        return self.get_auth_token_new(password)

    def get_codes(self, upload_managed_items: bool = True, tries: int = 1):
        # Upstream recursively calls this method with zero after an uncertain
        # response. Preserve that stop condition even if a caller requests more.
        return super().get_codes(upload_managed_items, tries=1 if tries > 0 else 0)

    def create_new_account(self, tries: int = 1) -> bool:
        if tries <= 0:
            return False
        new_iq = self.get_new_inquiry_code()
        if not isinstance(new_iq, str) or not new_iq:
            return False
        if new_iq == self.save_file.inquiry_code:
            return False
        self.save_file.inquiry_code = new_iq
        self.remove_stored_auth_token()
        self.remove_stored_save_key_data()
        self.remove_stored_password()
        # Original create-account protocol intentionally makes refresh fail so
        # /v1/users can register the newly allocated account code.
        fail_text = 'EXPECT_THIS_TO_FAIL'
        start_count = (40 - len(fail_text)) // 2
        self.save_file.password_refresh_token = (
            '_' * start_count + fail_text + '_' * (40 - len(fail_text) - start_count)
        )
        if self.get_password() is None:
            return False
        if self.get_auth_token() is None:
            return False
        if self.get_save_key() is None:
            return False
        if self.update_managed_items() is not True:
            return False
        self.save_file.show_ban_message = False
        return True

    def upload_save_data(self, save_key: dict) -> bool:
        # Retain the original multipart protocol, but its no_timeout=True is
        # unsuitable for a function that must return recovery bytes on failure.
        from bcsfe.core.server.server_handler import RequestResult
        form = self.get_upload_request_form(save_key)
        url = save_key.get('url') or f'{self.aws_url}/'
        headers = {
            'accept-encoding': 'gzip',
            'connection': 'keep-alive',
            'user-agent': 'Dalvik/2.1.0 (Linux; U; Android 9; SM-G955F Build/N2G48B)',
        }
        response = core.RequestHandler(url, headers, form=form).post()
        if response is None:
            self.log_no_internet(RequestResult(url, None, headers, ''))
            return False
        if response.status_code != 204:
            self.log_error('upload_fail_aws', RequestResult(
                url, response, headers, form.get_all_type('text-plain')))
            self.remove_stored_save_key_data()
            return False
        return True
