import datetime
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
from bcsfe_runtime import core,scoped_runtime
import editor_engine as engine

class EngineContextTests(unittest.TestCase):
    def test_region_change_reloads_core_and_cat_metadata_inside_batch(self):
        sf=core.SaveFile(cc=core.CountryCode.from_code('kr'),gv=core.GameVersion(150500),load=False)
        for field in ('date','date_2','date_3','date_4'):setattr(sf,field,datetime.datetime(2024,1,2))
        sf=core.SaveFile(core.Data(sf.to_data().data))
        seen=[]
        def data(sf):
            seen.append(sf.cc.get_code())
            return NS(country=sf.cc.get_code())
        def probe(sf,args):
            mission=core.core_data.get_mission_names(sf)
            buy=sf.cats.read_unitbuy(sf)
            if mission.country!=sf.cc.get_code() or buy.country!=sf.cc.get_code():
                raise ValueError('Stale metadata used after a region change')
            sf.xp=1 if mission.country=='kr' else 2
        action={'apply':probe,'schema':{'type':'object'},'source':'test','description':'test'}
        with scoped_runtime(),patch.object(core,'MissionNames',side_effect=data),patch('bcsfe.core.game.catbase.cat.UnitBuy',side_effect=data),patch.dict(engine.ACTIONS,{'test.metadata':action}):
            result,raw,_=engine.apply_operations(sf,[{'action':'test.metadata'},
                {'action':'save.region','args':{'country_code':'en'}},{'action':'test.metadata'}],isolate=False)
        self.assertEqual(seen,['kr','kr','en','en'])
        self.assertEqual(result.xp,2)
        self.assertEqual(core.SaveFile(core.Data(raw)).cc.get_code(),'en')
        self.assertEqual(sf.cc.get_code(),'kr')
    def test_runtime_restores_parent_even_on_exception(self):
        parent=core.core_data
        with self.assertRaises(RuntimeError):
            with scoped_runtime():
                self.assertIsNot(parent,core.core_data)
                raise RuntimeError('test')
        self.assertIs(core.core_data,parent)

if __name__=='__main__':unittest.main()
