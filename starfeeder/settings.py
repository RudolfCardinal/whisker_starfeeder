#!/usr/bin/env python
# starfeeder/settings.py

"""
    Copyright (C) 2015-2015 Rudolf Cardinal (rudolf@pobox.com).

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""

import os

from starfeeder.constants import DB_URL_ENV_VAR

if DB_URL_ENV_VAR not in os.environ:
    raise ValueError("""
===============================================================================
You must specify the {var} environment variable (which is an
SQLAlchemy database URL). Examples follow.

Windows:
    set {var}=sqlite:///C:\\path\\to\\database.sqlite3
Linux:
    export {var}=sqlite:////absolute/path/to/database.sqlite3
===============================================================================
    """.format(var=DB_URL_ENV_VAR))

DATABASE_ENGINE = {
    # three slashes for a relative path
    'url': os.environ[DB_URL_ENV_VAR],
    # 'echo': True,
    'echo': False,
    'connect_args': {
        # 'timeout': 15,
    },
}

# http://docs.sqlalchemy.org/en/latest/core/engines.html
# http://stackoverflow.com/questions/15065037
# http://beets.radbox.org/blog/sqlite-nightmare.html
