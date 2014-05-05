# -*- coding: utf-8 -*-
"""
    user

    :copyright: (c) 2014 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
from nereid import url_for, flash, redirect, current_app, route
from nereid.globals import session, request
from nereid.signals import failed_login
from nereid.contrib.locale import make_lazy_gettext
from flask_oauth import OAuth
from flask.ext.login import login_user
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

_ = make_lazy_gettext('auth_google')

__all__ = ['Website', 'NereidUser']
__metaclass__ = PoolMeta


class Website:
    """Add Google auth settings to website"""
    __name__ = "nereid.website"

    google_app_id = fields.Char("Google App ID")
    google_app_secret = fields.Char("Google App Secret")

    def get_google_oauth_client(self):
        """
        Returns a instance of WebCollect
        """
        if not all([self.google_app_id, self.google_app_secret]):
            current_app.logger.error("Google api settings are missing")
            flash(_("Google login is not available at the moment"))
            return None

        oauth = OAuth()
        google = oauth.remote_app(
            'google',
            base_url='https://www.google.com/accounts/',
            request_token_url=None,
            access_token_url='https://accounts.google.com/o/oauth2/token',
            access_token_method='POST',
            authorize_url='https://accounts.google.com/o/oauth2/auth',
            consumer_key=self.google_app_id,
            consumer_secret=self.google_app_secret,
            request_token_params={
                'response_type': 'code',
                'scope': 'email',
            },
            access_token_params={'grant_type': 'authorization_code'}
        )
        google.tokengetter_func = lambda *a: session.get('google_oauth_token')
        return google


class NereidUser:
    "Nereid User"
    __name__ = "nereid.user"

    google_id = fields.Char('Google ID')

    @classmethod
    @route('/auth/google')
    def google_login(cls):
        """The URL to which a new request to authenticate to google begins
        Usually issues a redirect.
        """
        google = request.nereid_website.get_google_oauth_client()
        if google is None:
            return redirect(
                request.referrer or url_for('nereid.website.login')
            )
        return google.authorize(
            callback=url_for(
                'nereid.user.google_authorized_login',
                next=request.args.get('next') or request.referrer or None,
                _external=True
            )
        )

    @classmethod
    @route('/auth/google_authorized_login')
    def google_authorized_login(cls):
        """Authorized handler to which google will redirect the user to
        after the login attempt is made.
        """
        Party = Pool().get('party.party')

        google = request.nereid_website.get_google_oauth_client()
        if google is None:
            return redirect(
                request.referrer or url_for('nereid.website.login')
            )

        try:
            if 'oauth_verifier' in request.args:
                data = google.handle_oauth1_response()
            elif 'code' in request.args:
                data = google.handle_oauth2_response()
            else:
                data = google.handle_unknown_response()
            google.free_request_token()
        except Exception, exc:
            current_app.logger.error("Google login failed", exc)
            flash(
                _("We cannot talk to google at this time. Please try again")
            )
            return redirect(
                request.referrer or url_for('nereid.website.login')
            )

        if data is None:
            flash(_(
                "Access was denied to google: %(reason)s",
                reason=request.args['error_reason']
            ))
            failed_login.send(form=data)
            return redirect(url_for('nereid.website.login'))

        # Write the oauth token to the session
        session['google_oauth_token'] = (data['access_token'], '')

        # Find the information from google
        me = google.get(
            url='https://www.googleapis.com/oauth2/v1/userinfo',
            headers={'Authorization': 'OAuth ' + data['access_token']}
        )
        # Find the user
        with Transaction().set_context(active_test=False):
            users = cls.search([
                ('email', '=', me.data['email']),
                ('company', '=', request.nereid_website.company.id),
            ])
        if not users:
            current_app.logger.debug(
                "No Google user with email %s" % me.data['email']
            )
            current_app.logger.debug(
                "Registering new user %s" % me.data['name']
            )
            party, = Party.create([{'name': me.data['name']}])
            user, = cls.create([{
                'party': party.id,
                'display_name': me.data['name'],
                'email': me.data['email'],
                'google_id': me.data['id'],
                'active': True,
            }])
            flash(
                _('Thanks for registering with us using google')
            )
        else:
            user, = users

        if not user.google_id:
            # if the user has no facebook id save it
            cls.write([user], {'google_id': me.data['id']})
        flash(_(
            "You are now logged in. Welcome %(name)s", name=user.display_name
        ))
        login_user(user)
        if request.is_xhr:
            return 'OK'
        return redirect(
            request.values.get(
                'next', url_for('nereid.website.home')
            )
        )
