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


def get_database_settings():
    if DB_URL_ENV_VAR not in os.environ:
        raise ValueError(
            "Environment variable {} not specified".format(DB_URL_ENV_VAR))
    return {
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


def get_database_url():
    settings = get_database_settings()
    return settings['url']


def set_database_url(url):
    global dbsettings
    dbsettings['url'] = url


def set_database_echo(echo):
    global dbsettings
    dbsettings['echo'] = echo
