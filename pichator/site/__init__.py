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

    @app.errorhandler(ImATeapot.code)
    def imateapot(e):
        return flask.render_template('teapot.html')

    @app.route('/')
    @authorized_only('admin')
    @pass_user_info
    def index(uid, username):
        nonlocal has_privilege
        emp_no = manager.get_emp_no(username)
        return flask.render_template('attendance.html', **locals())

    @app.route('/timetable', methods=['GET', 'POST'])
    @authorized_only('user')
    @pass_user_info
    def show_timetable(uid, username):
        nonlocal has_privilege
        emp_no = manager.get_emp_no(username)
        if flask.request.method == 'GET':
            return flask.render_template('timetable.html', **locals())
        else:
            data_dict = flask.request.form.to_dict()
            if not manager.set_timetables(data_dict):
                flask.flash(
                    'Počet hodin v rozvrhu neodpovídá úvazku.', 'error')
            return flask.render_template('timetable.html', **locals())

    @app.route('/timetable_data')
    @authorized_only('admin')
    @pass_user_info
    def get_timetables_data(uid, username):
        nonlocal has_privilege
        emp_no = manager.get_emp_no(username)
        if not emp_no:
            raise ImATeapot
        return flask.jsonify(manager.get_timetables(emp_no))

    @app.route('/pvs')
    @authorized_only('admin')
    @pass_user_info
    def get_pvs(uid, username):
        nonlocal has_privilege
        period = flask.request.headers.get('X-period')
        if not period:
            raise ImATeapot
        emp_no = manager.get_emp_no(username)
        return flask.jsonify(manager.get_pvs(emp_no, period))

    @app.route('/attendance_data')
    @authorized_only('admin')
    @pass_user_info
    def get_attendance_data(uid, username):
        nonlocal has_privilege
        pvid = flask.request.headers.get('X-pvid')
        period = flask.request.headers.get('X-period')
        if not pvid or not period:
            raise ImATeapot
        return flask.jsonify(manager.get_attendance(uid, pvid, period, username))

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        manager.pich_db.rollback()

    return app


# vim:set sw=4 ts=4 et:
# -*- coding: utf-8 -*-
