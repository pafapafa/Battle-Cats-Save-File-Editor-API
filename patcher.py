"""Legacy Python imports backed by the typed engine. Requires Flask app context."""
from editor_engine import apply_operations
from editor_legacy import legacy_to_operations
from bcsfe_runtime import core, scoped_runtime
INT32_MAX=2**31-1

def get_country_code(country='kr'):
    if country not in ('kr','en','jp','tw'):
        raise ValueError('Unsupported country_code.')
    return core.CountryCode.from_code(country)

def get_default_gv():
    return core.GameVersion(150500)

def download_ponos_save(tc,cc,country='kr'):
    from editor_api import receive_transfer
    _,sf,sh=receive_transfer(tc,cc,country)
    return sf,sh

def patch_and_upload_save(sf,sh,**payload):
    from editor_api import APIProblem, b64, confirmed_codes, handler
    operations=legacy_to_operations(payload)
    original=sf.to_data().data
    with scoped_runtime():
        if operations:
            edited,raw,delta=apply_operations(sf,operations,isolate=False)
        else:
            import copy
            edited,raw,delta=copy.deepcopy(sf),original,[]
        sh=handler(edited)
        if payload.get('unban_account'):
            old=edited.inquiry_code
            if sh.create_new_account(tries=1) is not True or not edited.inquiry_code or edited.inquiry_code==old:
                raise APIProblem('New account creation was not confirmed.',502,backup_base64=b64(original),save_base64=b64(edited.to_data().data),retry_safe=False)
        if payload.get('upload_items') and sh.upload_meta_data() is not True:
            raise APIProblem('Item upload was not confirmed.',502,backup_base64=b64(original),save_base64=b64(edited.to_data().data),retry_safe=False)
        codes=sh.get_codes(tries=1)
        if not confirmed_codes(codes):
            raise APIProblem('Upload/code issuance was not confirmed.',502,backup_base64=b64(original),save_base64=b64(edited.to_data().data),retry_safe=False)
        return {'changes':delta,'save_base64':b64(edited.to_data().data),'backup_base64':b64(original)},codes
