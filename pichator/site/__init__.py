#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

__all__ = ['make_site']

from sqlalchemy import *
from sqlalchemy.exc import *
from werkzeug.exceptions import *
from pichator.site.util import *
from functools import wraps


from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError
from datetime import date, datetime, timedelta
from dateutil.relativedelta import *
from xml.sax.saxutils import escape


import flask
import os
import re


def make_site(manager, access_model, debug=False):
    app = flask.Flask('.'.join(__name__.split('.')[:-1]))
    app.secret_key = os.urandom(16)
    app.debug = debug

    @app.template_filter('to_alert')
    def category_to_alert(category):
        return {
            'warning': 'alert-warning',
            'error': 'alert-danger',
        }[category]

    @app.template_filter('to_icon')
    def category_to_icon(category):
        return {
            'warning': 'pficon-warning-triangle-o',
            'error': 'pficon-error-circle-o',
        }[category]

    def has_privilege(privilege):
        roles = flask.request.headers.get('X-Roles', '')

        if not roles or '(null)' == roles:
            roles = ['impotent']
        else:
            roles = re.findall(r'\w+', roles)

        return access_model.have_privilege(privilege, roles)

    def pass_user_info(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            uid = flask.request.headers.get('X-User-Id', '0')
            username = flask.request.headers.get('X-Full-Name', 'brabemi')

            kwargs.update({
                'uid': int(uid),
                'username': username.encode('latin1').decode('utf8'),
            })

            return fn(*args, **kwargs)
        return wrapper

    def authorized_only(privilege='user'):
        def make_wrapper(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                if not has_privilege(privilege):
                    raise Forbidden('RBAC Forbidden')

                return fn(*args, **kwargs)

            return wrapper
        return make_wrapper

    @app.errorhandler(Forbidden.code)
    def unauthorized(e):
        return flask.render_template('forbidden.html')

    @app.route('/')
    @authorized_only('admin')
    def index():
        nonlocal has_privilege
        return flask.render_template('graph.html', **locals())

    @app.route('/timetable')
    @authorized_only('user')
    @pass_user_info
    def show_timetable(uid, username):
        nonlocal has_privilege
        emp_no = manager.get_emp_no(username)
        return flask.render_template('timetable.html', **locals())

    @app.route('/timetable_data/<emp_no>')
    @authorized_only('admin')
    def get_timetables_data(emp_no):
        nonlocal has_privilege
        return flask.jsonify(manager.get_timetables(emp_no))

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        manager.pich_db.rollback()

    return app


# vim:set sw=4 ts=4 et:
# -*- coding: utf-8 -*-
