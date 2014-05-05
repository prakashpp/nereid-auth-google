# -*- coding: utf-8 -*-
"""
    __init__.py

    :copyright: (c) 2014 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
from trytond.pool import Pool

from user import Website, NereidUser


def register():
    Pool.register(
        Website,
        NereidUser,
        module='auth_google', type_='model'
    )
