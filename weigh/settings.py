#!/usr/bin/env python3
# weigh/settings.py

import os

db_url_env_var = "BIRD_MONITOR_DATABASE_URL"

if db_url_env_var not in os.environ:
    raise ValueError("""

You must specify the {var} environment variable (which is an SQLAlchemy
database URL). Examples follow.

Windows:
    SET {var}=sqlite:///C:\\path\\to\\database.db;
Linux:
    export {var}=sqlite:////absolute/path/to/database.db)
    """.format(var=db_url_env_var))

DATABASE_ENGINE = {
    # three slashes for a relative path
    'url': os.environ[db_url_env_var],
    'echo': True,
}
