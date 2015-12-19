#!/usr/bin/env python
# weigh/settings.py

import os

db_url_env_var = "BIRD_MONITOR_DATABASE_URL"

if db_url_env_var not in os.environ:
    raise ValueError("""

You must specify the {var} environment variable (which is an SQLAlchemy
database URL). Examples follow.

Windows:
    set {var}=sqlite:///C:\\path\\to\\database.sqlite3
Linux:
    export {var}=sqlite:////absolute/path/to/database.sqlite3
    """.format(var=db_url_env_var))

DATABASE_ENGINE = {
    # three slashes for a relative path
    'url': os.environ[db_url_env_var],
    # 'echo': True,
    'echo': False,
    'connect_args': {
        # 'timeout': 15,
    },
}

# http://docs.sqlalchemy.org/en/latest/core/engines.html
# http://stackoverflow.com/questions/15065037
# http://beets.radbox.org/blog/sqlite-nightmare.html
