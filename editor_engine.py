"""Validated atomic save editing and loss checks at the binary boundary."""
from __future__ import annotations
import copy
import datetime
import math
import time

from jsonschema import Draft202012Validator, validators
from bcsfe_runtime import core, scoped_runtime
from editor_items import ACTIONS as ITEM_ACTIONS
from editor_cats import ACTIONS as CAT_ACTIONS
from editor_stages import ACTIONS as STAGE_ACTIONS
from editor_misc import ACTIONS as MISC_ACTIONS

ACTIONS = {}
for group in (ITEM_ACTIONS, CAT_ACTIONS, STAGE_ACTIONS, MISC_ACTIONS):
    if set(ACTIONS) & set(group):
        raise RuntimeError('Duplicate edit action registration.')
    ACTIONS.update(group)

StrictValidator = validators.extend(Draft202012Validator, type_checker=Draft202012Validator.TYPE_CHECKER.redefine("integer", lambda checker, value: type(value) is int))

class EditError(ValueError):
    pass

class PortableDate(datetime.datetime):
    def timestamp(self):
        try:
            return super().timestamp()
        except OSError:
            # Windows mktime rejects some valid dates around the Unix epoch.
            naive = datetime.datetime(self.year,self.month,self.day,self.hour,self.minute,self.second,self.microsecond)
            return (naive-datetime.datetime(1970,1,1)).total_seconds()+time.timezone

def json_values(value):
    if isinstance(value,str):
        return str(value)
    if isinstance(value,dict):
        return {str(k):json_values(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):
        return [json_values(v) for v in value]
    if isinstance(value,float) and not math.isfinite(value):
        return 'Infinity' if value>0 else '-Infinity' if value<0 else 'NaN'
    return value

def to_state(sf):
    copied=copy.copy(sf)
    for field in ('date','date_2','date_3','date_4'):
        value=getattr(sf,field)
        setattr(copied,field,PortableDate(value.year,value.month,value.day,value.hour,value.minute,value.second,value.microsecond))
    return json_values(copied.to_dict())

def changes(before,after,path=''):
    result=[]
    if isinstance(before,dict) and isinstance(after,dict):
        for key in sorted(set(before)|set(after)):
            p=path+'/'+str(key).replace('~','~0').replace('/','~1')
            if key not in before or key not in after:
                result.append({'path':p,'before':before.get(key),'after':after.get(key)})
            else:
                result.extend(changes(before[key],after[key],p))
    elif isinstance(before,list) and isinstance(after,list):
        for index in range(max(len(before),len(after))):
            p=path+'/'+str(index)
            if index>=len(before) or index>=len(after):
                result.append({'path':p,'before':before[index] if index<len(before) else None,
                               'after':after[index] if index<len(after) else None})
            else:
                result.extend(changes(before[index],after[index],p))
    elif type(before) != type(after) and not (type(before) in (int,float) and type(after) in (int,float)):
        result.append({'path':path,'before':before,'after':after})
    elif before != after:
        result.append({'path':path,'before':before,'after':after})
    return result

def comparable(sf):
    state=to_state(sf)
    for name in ('date','date_2','date_3','date_4'):
        if name in state:
            state[name]=math.floor(state[name])
    return state

def validate_operations(operations):
    if not isinstance(operations,list) or not 1 <= len(operations) <= 100:
        raise EditError('operations must contain 1 to 100 actions.')
    for index,operation in enumerate(operations):
        if not isinstance(operation,dict) or set(operation)-{'action','args'}:
            raise EditError(f'operation {index}: use only action and args.')
        name=operation.get('action')
        if not isinstance(name,str) or name not in ACTIONS:
            raise EditError(f'operation {index}: unknown action.')
        args=operation.get('args',{})
        errors=list(StrictValidator(ACTIONS[name]['schema']).iter_errors(args))
        if errors:
            error=errors[0]
            path='/'.join(map(str,error.absolute_path))
            # jsonschema's default message may include submitted secrets.
            raise EditError(f'operation {index} ({name}), args/{path}: violates {error.validator}.')
    return operations

def serialize_checked(sf):
    expected=comparable(sf)
    try:
        raw=sf.to_data().data
        parsed=core.SaveFile(core.Data(raw),cc=sf.cc)
        if not parsed.verify_hash() or parsed.to_data().data != raw:
            raise EditError('The output does not preserve a stable save-file round trip.')
        lost=changes(expected,comparable(parsed))
        if lost:
            paths=', '.join(x['path'] for x in lost[:8])
            raise EditError('These values cannot be persisted by this save format: '+paths)
    except EditError:
        raise
    except Exception as exc:
        raise EditError('The edited save could not be serialized and parsed ('+type(exc).__name__+').') from None
    return raw,parsed

METADATA_CACHES = ('game_data_getter','gatya_item_names','gatya_item_buy','chara_drop','gamatoto_levels',
                  'gamatoto_members_name','localizable','abilty_data','enemy_names','rank_gift_descriptions',
                  'rank_gifts','treasure_text','cat_shrine_levels','medal_names','mission_names','mission_conditions')

def clear_metadata_caches(sf):
    # A batch may change its region or version between two metadata edits.
    for field in METADATA_CACHES:
        setattr(core.core_data,field,None)
    for field in ('unit_buy','unit_limit','nyanko_picture_book','talent_data'):
        setattr(sf.cats,field,None)
    for cat in sf.cats.cats:
        cat.names=None


def apply_operations(sf,operations, *, isolate=True):
    validate_operations(operations)
    working=copy.deepcopy(sf)
    before=comparable(sf)
    def run():
        for index,operation in enumerate(operations):
            name=operation['action']
            try:
                context=(working.cc.get_code(),working.game_version.game_version)
                ACTIONS[name]['apply'](working,operation.get('args',{}))
                if context != (working.cc.get_code(),working.game_version.game_version):
                    clear_metadata_caches(working)
            except (ValueError,KeyError,IndexError,TypeError,AttributeError) as exc:
                raise EditError(f'operation {index} ({name}) failed: {str(exc)}') from None
        raw,parsed=serialize_checked(working)
        delta=changes(before,comparable(parsed))
        return parsed,raw,delta
    if isolate:
        with scoped_runtime():
            return run()
    return run()

def public_catalog():
    return {name:{key:value for key,value in action.items() if key!='apply'} for name,action in ACTIONS.items()}
