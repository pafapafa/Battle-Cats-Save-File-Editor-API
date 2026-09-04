from contextlib import contextmanager
from pathlib import Path
import os
import tempfile
import threading

from bcsfe import core

LOCK = threading.RLock()
READY = False

def initialize():
    global READY
    with LOCK:
        if READY:
            return
        cache = Path(os.environ.get('BCSFE_DATA_DIR', str(Path(tempfile.gettempdir()) / 'bcsfe-api-data')))
        cache.mkdir(parents=True, exist_ok=True)
        core.data_dir_path = core.Path(str(cache))

        core.Path.get_config_folder = staticmethod(lambda: core.Path(str(cache / 'config')).generate_dirs())
        core.config_path = core.Path(str(cache / 'config' / 'config.yaml'))
        core.log_path = core.Path(str(cache / 'server.log'))
        (cache / 'config').mkdir(exist_ok=True)
        core.core_data.init_data()
        from editor_metadata import install_headless_metadata
        install_headless_metadata()
        READY = True

@contextmanager
def scoped_runtime():
    initialize()


    with LOCK:
        previous = core.core_data
        current = core.CoreData()
        core.core_data = current
        try:
            current.init_data()
            yield current
        finally:
            core.core_data = previous

initialize()
