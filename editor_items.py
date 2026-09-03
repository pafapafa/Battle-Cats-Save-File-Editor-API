"""Strict adapters for scalar resources, indexed items and account fields."""
import math
import random
import re
from functools import wraps
from jsonschema import Draft202012Validator, validators
from bcsfe import core
from bcsfe.cli.edits.cat_editor import CatEditor

I32 = 2**31 - 1
U32 = 2**32 - 1
U16 = 2**16 - 1
INDEX_PATTERN = r"^(0|[1-9][0-9]*)$"
StrictValidator = validators.extend(Draft202012Validator, type_checker=Draft202012Validator.TYPE_CHECKER.redefine("integer", lambda checker, value: type(value) is int))
ACTIONS = {}

def integer(value, name='value', minimum=0, maximum=I32):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f'{name} must be an integer from {minimum} to {maximum}.')
    return value

def boolean(value, name):
    if type(value) is not bool:
        raise ValueError(name + ' must be a boolean.')
    return value

def obj(properties, required=()):
    return {'type': 'object', 'properties': properties, 'required': list(required), 'additionalProperties': False}

def num(maximum=I32, minimum=0):
    return {'type': 'integer', 'minimum': minimum, 'maximum': maximum}

def register(name, description, schema, apply, source):
    @wraps(apply)
    def checked(sf, args):
        error = next(StrictValidator(schema).iter_errors(args), None)
        if error is not None:
            path = '/'.join(map(str, error.absolute_path))
            raise ValueError(f'{name} args/{path}: violates {error.validator}.')
        return apply(sf, args)
    ACTIONS[name] = dict(description=description, schema=schema, apply=checked, source=source)

def limit(value, key, args, hard=I32):
    integer(value, maximum=hard)
    if boolean(args.get('respect_maxima', True), 'respect_maxima'):
        cap = getattr(core.core_data.max_value_manager, key)
        if value > cap:
            raise ValueError(f'value exceeds the BCSFE configured maximum ({cap}); use respect_maxima=false to disable that limit.')
    return value

MANAGED = {'catfood': core.ManagedItemType.CATFOOD, 'rare_tickets': core.ManagedItemType.RARE_TICKET,
           'platinum_tickets': core.ManagedItemType.PLATINUM_TICKET, 'legend_tickets': core.ManagedItemType.LEGEND_TICKET}

def scalar_setter(field, maximum=I32, max_key=None):
    def apply(sf, args):
        value = integer(args['value'], maximum=maximum)
        if max_key:
            limit(value, max_key, args, maximum)
        if field == 'platinum_shards' and args.get('respect_maxima', True):
            cap = max(0, (core.core_data.max_value_manager.platinum_tickets - sf.platinum_tickets) * 10 + 9)
            if value > cap:
                raise ValueError(f'platinum_shards exceeds remaining ticket capacity ({cap}).')
        previous = getattr(sf, field)
        setattr(sf, field, value)
        if field in MANAGED and value != previous:
            core.BackupMetaData(sf).add_managed_item(core.ManagedItem.from_change(value - previous, MANAGED[field]))
    return apply

for field in ('catfood','xp','normal_tickets','rare_tickets','platinum_tickets','legend_tickets',
              'platinum_shards','np','leadership','hundred_million_ticket','restart_pack','golden_cpu_count'):
    hard = 32767 if field == 'leadership' else 127 if field in ('restart_pack', 'golden_cpu_count') else I32
    max_key = {'hundred_million_ticket':'hundred_million_tickets'}.get(field,field)
    if field in ('platinum_shards','restart_pack','golden_cpu_count'):
        max_key = None
    register('items.'+field, 'Set '+field+' without changing other resources.',
             obj({'value':num(hard), 'respect_maxima':{'type':'boolean','default':True}}, ['value']),
             scalar_setter(field,hard,max_key), 'cli/edits/basic_items.py:BasicItems')

def indices(values, length, name='values'):
    if type(values) is int:
        result = list(enumerate([values] * length))
    elif isinstance(values, list):
        if len(values) > length:
            raise ValueError(name + ' exceeds the number of stored items.')
        result = list(enumerate(values))
    elif isinstance(values, dict):
        result = []
        for key, value in values.items():
            if not isinstance(key,str) or re.fullmatch(INDEX_PATTERN,key) is None:
                raise ValueError(name + ' keys must be zero-based numeric indexes.')
            result.append((int(key), value))
    else:
        raise ValueError(name + ' must be an indexed object or array.')
    if not result:
        raise ValueError(name + ' must not be empty.')
    for index,_ in result:
        integer(index, 'index', maximum=length-1)
    return result

VECTOR_FIELDS = ('catamins','catseyes','catfruit','labyrinth_medals','treasure_chests',
                 'event_capsules','lucky_tickets','event_capsules_2')
def vector_setter(field):
    def apply(sf,args):
        values = getattr(sf,field)
        changes = indices(args['values'],len(values))
        key = field if field not in ('event_capsules','lucky_tickets','event_capsules_2') else 'event_tickets'
        if field == 'catfruit':
            key = 'catfruit_old' if sf.game_version < 110400 else 'catfruit_new'
        for index, value in changes:
            limit(value,key,args)
        updated = values.copy()
        for index,value in changes:
            updated[index] = value
        if field=='catfruit' and sf.game_version<110400 and args.get('respect_maxima',True):
            if sum(updated)>core.core_data.max_value_manager.catfruit_old:
                raise ValueError('This game version has a cumulative catfruit storage limit.')
        setattr(sf,field,updated)
    return apply

VALUES = {'oneOf':[num(), {'type':'array','items':num(),'minItems':1},
                   {'type':'object','patternProperties':{INDEX_PATTERN:num()},'additionalProperties':False,'minProperties':1}]}
for field in VECTOR_FIELDS:
    register('items.'+field, 'Edit selected '+field+' indexes; unspecified entries are preserved.',
             obj({'values':VALUES,'respect_maxima':{'type':'boolean','default':True}},['values']),
             vector_setter(field), 'cli/edits/basic_items.py:BasicItems')

def battle_items(sf,args):
    changes = [(index, limit(value,'battle_items',args)) for index,value in indices(args['values'],len(sf.battle_items.items))]
    for index,value in changes:
        sf.battle_items.items[index].amount = value

register('items.battle_items','Edit selected battle item quantities.',
         obj({'values':VALUES,'respect_maxima':{'type':'boolean','default':True}},['values']),
         battle_items,'core/game/battle/battle_items.py:BattleItems.edit')

def endless(sf,args):
    durations = args['minutes']
    if isinstance(durations, (int, float, str)) and not isinstance(durations, bool):
        durations = [durations] * len(sf.battle_items.items)
    changes = []
    for index, minutes in indices(durations,len(sf.battle_items.items),'minutes'):
        if minutes == 'infinity':
            minutes = math.inf
        else:
            if isinstance(minutes,bool) or not isinstance(minutes,(int,float)) or minutes < 0:
                raise ValueError('duration must be nonnegative minutes or "infinity".')
            try:
                finite = math.isfinite(minutes) and math.isfinite(minutes * 60)
            except OverflowError:
                finite = False
            if not finite:
                raise ValueError('duration cannot overflow seconds; use the explicit infinity value instead.')
        changes.append((index,minutes))
    for index,minutes in changes:
        sf.battle_items.items[index].endless_item.set_duration_mins(minutes,0)

DURATION = {'oneOf':[{'type':'number','minimum':0},{'const':'infinity'}]}
register('items.endless','Set endless-item durations in minutes; a scalar applies to all items.',
         obj({'minutes':{'oneOf':[DURATION,
              {'type':'array','items':DURATION,'minItems':1},
              {'type':'object','patternProperties':{INDEX_PATTERN:DURATION},'additionalProperties':False,'minProperties':1}]}},['minutes']),
         endless,'core/game/battle/battle_items.py:BattleItems.edit_endless_items')


def trade(sf,args):
    amount=integer(args['amount'])
    limit(sf.rare_tickets+amount,'rare_tickets',args)
    progress=integer(amount*5, 'trade_progress')
    for item in sf.cats.storage_items:
        if item.item_type == 0 or (item.item_id==1 and item.item_type==2):
            item.item_id,item.item_type=1,2
            sf.gatya.trade_progress=progress
            return
    raise ValueError('Cat storage has no free slot for rare-ticket trade.')

register('items.rare_ticket_trade','Prepare the original five-to-one ticket trade in cat storage.',
         obj({'amount':num(I32//5),'respect_maxima':{'type':'boolean','default':True}},['amount']),
         trade,'cli/edits/rare_ticket_trade.py:RareTicketTrade.rare_ticket_trade')

def event_tickets(sf,args):
    buy=core.core_data.get_gatya_item_buy(sf)
    categories = {core.GatyaItemCategory.EVENT_TICKETS.value:'event_capsules',
                  core.GatyaItemCategory.LUCKY_TICKETS_1.value:'lucky_tickets',
                  core.GatyaItemCategory.LUCKY_TICKETS_2.value:'event_capsules_2'}
    changes = []
    targets = set()
    for key,value in args['items'].items():
        if not key.isdecimal():
            raise ValueError('Event ticket item IDs must be numeric.')
        item=buy.get(int(key))
        if item is None or item.category not in categories:
            raise ValueError('Unknown event ticket item ID: '+key)
        values=getattr(sf,categories[item.category])
        integer(item.index,'ticket index',maximum=len(values)-1)
        target=(categories[item.category],item.index)
        if target in targets:
            raise ValueError('Multiple item IDs address the same event ticket slot.')
        targets.add(target)
        changes.append((values,item.index,limit(value,'event_tickets',args)))
    for values,index,value in changes:
        values[index]=value

register('items.event_tickets','Edit event/lucky tickets using original game item IDs.',
         obj({'items':{'type':'object','minProperties':1,'patternProperties':{INDEX_PATTERN:num()},'additionalProperties':False},
              'respect_maxima':{'type':'boolean','default':True}},['items']),
         event_tickets,'cli/edits/event_tickets.py:EventTickets.edit_ticket')

def evolve_by_id(sf,args):
    buy=core.core_data.get_gatya_item_buy(sf)
    updated=sf.catfruit.copy()
    key='catfruit_old' if sf.game_version < 110400 else 'catfruit_new'
    targets=set()
    for ident,value in args['items'].items():
        item=buy.get(int(ident))
        if item is None or item.category != core.GatyaItemCategory.EVOLVE_ITEMS.value:
            raise ValueError('Unknown evolution item ID: '+ident)
        integer(item.index,'evolution item index',maximum=len(updated)-1)
        if item.index in targets:
            raise ValueError('Multiple item IDs address the same evolution item slot.')
        targets.add(item.index)
        updated[item.index]=limit(value,key,args)
    if sf.game_version < 110400 and args.get('respect_maxima',True) and sum(updated)>core.core_data.max_value_manager.catfruit_old:
        raise ValueError('This game version has a cumulative catfruit storage limit.')
    sf.catfruit=updated

register('items.evolve_by_id','Edit evolution materials, including stones, by original game item IDs.',
         obj({'items':{'type':'object','minProperties':1,'patternProperties':{INDEX_PATTERN:num()},'additionalProperties':False},
              'respect_maxima':{'type':'boolean','default':True}},['items']),
         evolve_by_id,'cli/edits/basic_items.py:BasicItems.edit_catfruit')

def scheme(sf,args):
    raw=core.core_data.get_game_data_getter(sf).download('DataLocal','schemeItemData.tsv')
    if raw is None:
        raise ValueError('Scheme item metadata is unavailable.')
    valid={row[0].to_int() for row in core.CSV(raw,'\t').lines[1:] if len(row)}
    ids=sorted(valid) if args['ids']=='all' else args['ids']
    if not ids:
        raise ValueError('No scheme items are available in the metadata.')
    for ident in ids:
        integer(ident,'scheme ID')
        if ident not in valid:
            raise ValueError('Unknown scheme item ID.')
    for ident in ids:
        if args['mode']=='add' and ident not in sf.scheme_items.to_obtain:
            sf.scheme_items.to_obtain.append(ident)
        if args['mode']=='remove' and ident in sf.scheme_items.to_obtain:
            sf.scheme_items.to_obtain.remove(ident)
        if ident in sf.scheme_items.received:
            sf.scheme_items.received.remove(ident)

IDS={'oneOf':[{'const':'all'},{'type':'array','items':num(),'uniqueItems':True,'minItems':1}]}
register('items.scheme','Add or remove selected valid scheme rewards.',
         obj({'ids':IDS,'mode':{'enum':['add','remove']}},['ids','mode']),
         scheme,'core/game/catbase/scheme_items.py:SchemeItems')

def _skill_bounds(value, name, minimum, hard_maximum, metadata_maximum, respect):
    if value == 'max':
        value = metadata_maximum
    if type(value) is dict:
        if set(value) != {'min','max'}:
            raise ValueError(name + ' range requires exactly min and max.')
        low=integer(value['min'],name+'.min',minimum,hard_maximum)
        high=integer(value['max'],name+'.max',minimum,hard_maximum)
        if low > high:
            raise ValueError(name + ' range minimum exceeds maximum.')
    else:
        low=high=integer(value,name,minimum,hard_maximum)
    if respect and high > metadata_maximum:
        raise ValueError(name + ' exceeds the special-skill metadata limit.')
    return low,high


def special_skills(sf,args):
    data=core.core_data.get_ability_data(sf)
    if data.ability_data is None:
        raise ValueError('Special-skill metadata is unavailable.')
    respect=boolean(args.get('respect_maxima',True),'respect_maxima')
    changes=args['skills']
    skills=sf.special_skills.get_valid_skills()
    if changes=='all':
        changes={str(i):{'max':True} for i in range(len(skills))}
    plans=[]
    for key,change in changes.items():
        index=integer(int(key),'skill ID',maximum=len(skills)-1)
        if index >= len(data.ability_data):
            raise ValueError('Skill metadata is unavailable for the selected skill.')
        ability=data.get_ability_data_item(index)
        if ability is None:
            raise ValueError('Skill metadata is unavailable.')
        maximize=change.get('max',False)
        if maximize and ('level' in change or 'plus' in change):
            raise ValueError('Use max=true alone or choose level/plus explicitly.')
        if not maximize and not ('level' in change or 'plus' in change):
            raise ValueError('Provide a skill level, plus level or max=true.')
        base_range=plus_range=None
        if maximize or 'level' in change:
            base_range=_skill_bounds('max' if maximize else change['level'],'level',1,U16+1,ability.max_base_level,respect)
        if maximize or 'plus' in change:
            plus_range=_skill_bounds('max' if maximize else change['plus'],'plus',0,U16,ability.max_plus_level,respect)
        plans.append((index,base_range,plus_range))
    for index,base_range,plus_range in plans:
        # Resolve a range once for each requested component. Passing a range to
        # the upstream mirror would draw separately for the hidden cannon skill.
        level=-1 if base_range is None else random.randint(*base_range) if base_range[0] != base_range[1] else base_range[0]
        plus=-1 if plus_range is None else random.randint(*plus_range) if plus_range[0] != plus_range[1] else plus_range[0]
        upgrade=core.Upgrade(plus=plus,base=-1 if level == -1 else level-1)
        sf.special_skills.set_upgrade(index,upgrade)
    CatEditor.set_rank_up_sale(sf)


def skill_value(minimum,maximum):
    return {'oneOf':[num(maximum,minimum),{'const':'max'},obj({'min':num(maximum,minimum),'max':num(maximum,minimum)},['min','max'])]}


SKILL=obj({'level':skill_value(1,U16+1),'plus':skill_value(0,U16),'max':{'type':'boolean'}},[])
SKILL['minProperties']=1
register('skills.set','Edit displayed base/plus levels, inclusive random {min,max} ranges, or per-component max. Omitted components stay unchanged. max uses metadata; respect_maxima=false allows explicit larger values within the save format. The hidden cannon skill receives the same chosen values.',
         obj({'skills':{'oneOf':[{'const':'all'},{'type':'object','minProperties':1,'patternProperties':{INDEX_PATTERN:SKILL},'additionalProperties':False}]},
              'respect_maxima':{'type':'boolean','default':True}},['skills']),
         special_skills,'core/game/catbase/special_skill.py:SpecialSkills.set_upgrade;core/game/catbase/upgrade.py:Upgrade.get_user_upgrade')


def seed_setter(field):
    def apply(sf,args):
        setattr(sf.gatya,field,integer(args['value'],maximum=U32))
    return apply
for name in ('rare','normal','event'):
    register('gatya.'+name+'_seed','Set the full unsigned 32-bit '+name+' seed.',
             obj({'value':num(U32)},['value']),seed_setter(name+'_seed'),
             'core/game/catbase/gatya.py:Gatya.edit_'+name+'_gatya_seed')

def string_setter(field):
    def apply(sf,args):
        value=args['value']
        if not isinstance(value,str) or len(value)>512 or '\0' in value:
            raise ValueError('value must be a string of at most 512 characters without NUL.')
        setattr(sf,field,value)
    return apply
for field in ('inquiry_code','password_refresh_token'):
    register('account.'+field,'Set the account '+field+' field.',
             obj({'value':{'type':'string','maxLength':512}},['value']),string_setter(field),
             'cli/edits/basic_items.py:BasicItems.edit_'+field)

def region(sf,args):
    if args['country_code'] not in ('kr','en','jp','tw'):
        raise ValueError('Unsupported region.')
    sf.set_cc(core.CountryCode.from_code(args['country_code']))

def version(sf,args):
    sf.set_gv(core.GameVersion(integer(args['game_version'],minimum=1)))

register('save.region','Convert region using BCSFE set_cc.',obj({'country_code':{'enum':['kr','en','jp','tw']}},['country_code']),
         region,'cli/save_management.py:SaveManagement.convert_save_cc')
register('save.version','Convert format version; the edited file is reparsed before it is returned.',
         obj({'game_version':num(minimum=1)},['game_version']),version,'cli/save_management.py:SaveManagement.convert_save_gv')
