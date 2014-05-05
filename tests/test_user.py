# -*- coding: utf-8 -*-
"""
    test_user

    :copyright: (c) 2014 by Openlabs Technologies & Consulting (P) LTD
    :license: BSD, see LICENSE for more details.
"""
import os
import unittest
import BaseHTTPServer
import threading
import webbrowser
from StringIO import StringIO
from lxml import etree

import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, USER, DB_NAME, CONTEXT
from trytond.transaction import Transaction
from nereid.testing import NereidTestCase


_def = []


def get_from_env(key):
    """
    Find a value from environ or return the default if specified
    If the return value is not specified then raise an error if
    the value is NOT in the environment
    """
    try:
        return os.environ[key]
    except KeyError:
        raise Exception("%s is not set in environ" % key)

REQUEST_RECEIVED = None


class RequestStack(threading.local):
    "Stack for storing the responses from async server"
    items = []

_request_ctx_stack = RequestStack()


class GoogleHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    "Special Class to handle the POST from LinkedIn"

    def do_GET(self):
        "Handle POST"
        self.send_response(200)
        self.end_headers()
        self.wfile.write(
            "Hola, go back to your terminal window to see results"
        )
        return


class TestGoogleAuth(NereidTestCase):
    "Test google Authenticated login"

    def setUp(self):
        "Setup"
        trytond.tests.test_tryton.install_module('auth_google')

        self.Party = POOL.get('party.party')
        self.Company = POOL.get('company.company')
        self.Currency = POOL.get('currency.currency')
        self.NereidUser = POOL.get('nereid.user')
        self.UrlMap = POOL.get('nereid.url_map')
        self.Language = POOL.get('ir.lang')
        self.Website = POOL.get('nereid.website')
        self.WebsiteLocale = POOL.get('nereid.website.locale')
        self.templates = {
            'home.jinja': '{{ get_flashed_messages() }}',
            'login.jinja':
            '{{ login_form.errors }} {{ get_flashed_messages() }}'
        }

    def setup_defaults(self):
        "Setup defaults"

        usd, = self.Currency.create([{
            'name': 'US Dollar',
            'code': 'USD',
            'symbol': '$',
        }])
        self.company, = self.Company.create([{
            'party': self.Party.create([{'name': 'Openlabs'}])[0].id,
            'currency': usd.id
        }])

        guest_user_party, = self.Party.create([{
            'name': 'Guest User',
        }])
        self.guest_user, = self.NereidUser.create([{
            'party': guest_user_party.id,
            'display_name': 'Guest User',
            'email': 'guest@openlabs.co.in',
            'password': 'password',
            'company': self.company.id,
        }])
        registered_user_party, = self.Party.create([{
            'name': 'Registered User',
        }])
        self.registered_user, = self.NereidUser.create([{
            'party': registered_user_party.id,
            'display_name': 'Registered User',
            'email': 'email@example.com',
            'password': 'password',
            'company': self.company.id,
        }])
        en_us, = self.Language.search([('code', '=', 'en_US')])
        url_map, = self.UrlMap.search([], limit=1)
        locale, = self.WebsiteLocale.create([{
            'code': 'en_US',
            'language': en_us.id,
            'currency': usd.id,
        }])
        self.site, = self.Website.create([{
            'name': 'localhost',
            'url_map': url_map.id,
            'company': self.company.id,
            'application_user': USER,
            'default_locale': locale.id,
            'guest_user': self.guest_user.id,
        }])

    def test_0010_login(self):
        """
        Check for login with the next argument without API settings
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c:
                response = c.get('/auth/google?next=/')
                self.assertEqual(response.status_code, 302)

                # Redirect to the home page since
                self.assertTrue(
                    '<a href="/login">/login</a>' in response.data
                )
                response = c.get('/')
                self.assertTrue(
                    'Google login is not available at the moment' in
                    response.data
                )

    def test_0020_login(self):
        """
        Login with google settings
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()
            self.Website.write([self.site], {
                'google_app_id': get_from_env('GOOGLE_APP_ID'),
                'google_app_secret': get_from_env('GOOGLE_APP_SECRET'),
            })

            with app.test_client() as c:
                response = c.get('/auth/google?next=/')
                self.assertEqual(response.status_code, 302)
                print response.data
                self.assertTrue(
                    'https://accounts.google.com/o/oauth2/auth' in
                    response.data
                )

                # send the user to the webbrowser and wait for a redirect
                parser = etree.HTMLParser()
                tree = etree.parse(StringIO(response.data), parser)
                webbrowser.open(tree.xpath('//p/a')[0].values()[0])


def suite():
    "Nereid test suite"
    suite = unittest.TestSuite()
    suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(TestGoogleAuth)
    )
    return suite


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
