#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

__all__ = ['make_site']

from sqlalchemy import *
from sqlalchemy.exc import *
from werkzeug.exceptions import NotAcceptable, Forbidden, InternalServerError
from pichator.site.util import *
from functools import wraps
from pichator.site.xlsx_export import xlsx_export

from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError
from datetime import date, datetime, timedelta
from dateutil.relativedelta import *
from xml.sax.saxutils import escape

from time import time
from shutil import rmtree


from twisted.python import log

from weasyprint import HTML, CSS
from weasyprint.fonts import FontConfiguration

from os.path import join, abspath, dirname
from os import urandom

import flask
import re
import holidays



def make_site(manager, access_model, debug=False):
    app = flask.Flask('.'.join(__name__.split('.')[:-1]))
    app.secret_key = urandom(16)
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

    @app.template_filter('short_time')
    def short_time(t):
        if not t:
            return ''

        return t.strftime('%H:%M')

    @app.template_filter('today_time')
    def today_time(t):
        if not t:
            return ''

        return datetime.combine(datetime.today(), t)
        
    @app.template_filter('time')
    def time(t):
        if not t:
            return ''
        sec = t.seconds
        hrs = sec // 3600 + t.days * 24
        rest = sec % 3600
        mins = rest // 60
        return '{}:{}'.format(str(hrs).zfill(2),str(mins).zfill(2))

    @app.template_filter('month_name')
    def month_name(t):
        return ('', 'Leden', 'Únor', 'Březen', 'Duben', 'Květen',
                'Červen', 'Červenec', 'Srpen', 'Září', 'Říjen', 'Listopad', 'Prosinec')[t]

    @app.template_filter('day_name')
    def day_name(t):
        return ('Pondělí', 'Úterý', 'Středa', 'Čtvrtek', 'Pátek', 'Sobota', 'Neděle')[t]
    
    @app.template_filter('mode_name')
    def mode_name(t):
        obj_mapping = {
        'Employer difficulties': 'Překážka na straně zaměstnavatele',
        'Vacation': 'Dovolená',
        'Vacation 0.5': 'Dovolená 0.5 dne',
        'Presence': 'Presence',
        'Absence': 'Absence',
        'On call time': 'Pracovní pohotovost',
        'Sickness': 'Nemoc',
        'Compensatory time off': 'Náhradní volno',
        'Family member care': 'Ošetřování člena rodiny',
        'Personal trouble': 'Osobní překážky',
        'Business trip': 'Služební cesta',
        'Study': 'Studium při zaměstnání',
        'Training': 'Školení',
        'Injury and disease from profession': 'Úraz/nemoc z povolání',
        'Unpaid leave': 'Neplacené volno',
        'Public benefit': 'Obecný zájem',
        'Sickday': 'Zdravotní volno'
        }
        return obj_mapping[t]


    @app.template_filter('unit_type')
    def unit_type(t):
        types = {
            1: 'Odbor',
            2: 'Oddělení',
            3: 'Referát'
        }
        return '{} {}'.format(types[len(str(t))], t)

    @app.template_global('attendance_class')
    def attendance_row_class(day):
        date = day['date']
        cz_holidays = holidays.CountryHoliday('CZ')
        today = date.today()

        if date.weekday() in (5, 6) or date in cz_holidays:
            return 'weekend'

        if date == today:
            return 'info clickable'

        if day['mode'] == 'Absence':
            return 'absence clickable'
        
        if day['timetable'] and day['arrival'] and day['departure'] and day['mode'] == 'Presence' and ((day['timetable'].lower.hour < day['arrival'].hour or 
                        (day['timetable'].lower.hour == day['arrival'].hour and day['timetable'].lower.minute < day['arrival'].minute)) or
                        (day['timetable'].upper.hour > day['departure'].hour or 
                        (day['timetable'].upper.hour == day['departure'].hour and day['timetable'].upper.minute > day['departure'].minute))):
            return 'warning clickable'

        return 'clickable'

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
            username = flask.request.headers.get('X-User-Name', 'john-doe')

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
        return flask.render_template('forbidden.html'), 403

    @app.errorhandler(NotAcceptable.code)
    def notacceptable(e):
        return flask.render_template('not_acceptable.html'), 400

    @app.errorhandler(InternalServerError.code)
    def internalservererror(e):
        return flask.render_template('internal_server_error.html'), 500

    @app.route('/', defaults={'year': None, 'month': None, 'pvid': None})
    @app.route('/<int:year>/<int:month>/<pvid>')
    @authorized_only('user')
    @pass_user_info
    def index(uid, username, year, month, pvid):
        admin = has_privilege('admin')
        acl = manager.get_acl(username)
        today = date.today()

        year = year or today.year
        month = month or today.month

        pvs = manager.get_pvs(uid, month, year)
        pvid = pvid or pvs[0]['pvid']
        department = manager.get_dept(pvid, date(year, month, 1)) or manager.get_dept(pvid, date(year, month, 28))

        attendance = manager.get_attendance(uid, pvid, month, year, username, admin)
        
        # Restrictive mode - if one of your superiors blocked edit mode on any level of hierarchy you cant edit.
        readonly = False
        for i in range(1, 4):
            readonly = readonly or manager.get_dept_mode(str(department)[:i]) == 'readonly'

        return flask.render_template('attendance.html', **locals())

    @app.route('/get_emp')
    @authorized_only('user')
    @pass_user_info
    def employees(uid, username):
        acl = manager.get_acl(username)
        dept = flask.request.values.get('dept')
        period = flask.request.values.get('period').split('-')
        return flask.jsonify(manager.get_employees(dept, int(period[0]), int(period[1])))
    
    @app.route('/present', defaults={'day': None, 'month': None, 'year': None})
    @app.route('/present/<int:day>/<int:month>/<int:year>')
    @authorized_only('user')
    @pass_user_info
    def present(uid, username, day, month, year):
        acl = manager.get_acl(username)
        admin = has_privilege('admin')
        if not day or not month or not year:
            date_val = date.today()
            day = date_val.day
            month = date_val.month
            year = date_val.year
        else:
            date_val = date(year, month, day)
        data = manager.get_present(date_val)
        return flask.render_template('present.html', **locals())

    @app.route('/dept', methods=['GET', 'POST'], defaults={'dept': None, 'month': None, 'year': None})
    @app.route('/dept/<dept>', methods=['GET', 'POST'], defaults={'month': None, 'year': None})
    @app.route('/dept/<dept>/<int:year>/<int:month>', methods=['GET', 'POST'])
    @authorized_only('user')
    @pass_user_info
    def display_dept(uid, username, dept, month, year):
        acl = manager.get_acl(username)
        admin = has_privilege('admin')
        today = date.today()
        month = month or today.month
        year = year or today.year
        dept = dept or acl
        data = manager.get_department(dept, month, year)['data']
        pdf_view = flask.request.values.get('pdf') == 'true'
        xlsx_view = flask.request.values.get('xlsx') == 'true'

        font_config = FontConfiguration()
        font_path = join(dirname(abspath(__file__)), '../templates/fonts')

        if has_privilege('admin'):
            if flask.request.method == 'POST':
                new_mode = flask.request.form['modes']
                manager.set_dept_mode(dept, new_mode)
            mode = manager.get_dept_mode(dept)
            acl = dept
            data = manager.get_department(dept, month, year)['data']
            if pdf_view:
                pdf_template = HTML(string=flask.render_template('dept_pdf.html', **locals()))
                result = pdf_template.write_pdf( font_config=font_config)
                return flask.Response(response=result, mimetype='application/pdf')
            if xlsx_view:
                result = xlsx_export(**locals())
                return flask.send_file(result, attachment_filename="dochazka-{dept}-{year}-{month}.xlsx".format(dept=dept, year=year, month=month), as_attachment=True)

            return flask.render_template('attendance_department.html', **locals())

        if not acl.isdigit():
            log.msg('User {} tried to access department view with acl {}.'.format(username, acl))
            raise Forbidden
        if flask.request.method == 'POST':
            new_mode = flask.request.form['modes']
            manager.set_dept_mode(acl, new_mode)
        mode = manager.get_dept_mode(acl)
        if pdf_view:
                pdf_template = HTML(string=flask.render_template('dept_pdf.html', **locals()))
                result = pdf_template.write_pdf( font_config=font_config)
                return flask.Response(response=result, mimetype='application/pdf')
        if xlsx_view:
            result = xlsx_export(**locals())
            return flask.send_file(result, attachment_filename="dochazka-{dept}-{year}-{month}.xlsx".format(dept=dept, year=year, month=month), as_attachment=True)

        return flask.render_template('attendance_department.html', **locals())


    @app.route('/dept_data')
    @authorized_only('user')
    @pass_user_info
    def get_dept(uid, username):
        dept = flask.request.values.get('dept')
        if not dept:
            log.err(
                'Geting data for department without mandatory parameter department number.')
            raise NotAcceptable
        acl = manager.get_acl(username)
        if acl != str(dept)[0] and not has_privilege(admin):
            log.err(
                'Trying to acces data of department { }, but has no authorization to do so.'.format(dept))
            raise Forbidden
        period = flask.request.values.get('period', '').split('-')
        if len(period) != 2:
            today = date.today()
            period = (today.month, today.year)
        return flask.jsonify(manager.get_department(dept, int(period[0]), int(period[1])))

    @app.route('/timetable', methods=['GET', 'POST'], defaults={'forced': None})
    @app.route('/timetable/<forced>', methods=['GET', 'POST'])
    @authorized_only('user')
    @pass_user_info
    def show_timetable(uid, username, forced):
        admin = has_privilege('admin')
        if admin and forced is not None:
            username = forced
        acl = manager.get_acl(username)
        emp_no = manager.get_emp_no(username)
        employees = manager.get_all_employees()
        emp_info = manager.get_emp_info(username)
        if flask.request.method == 'GET':
            return flask.render_template('timetable.html', **locals())
        else:
            data_dict = flask.request.form.to_dict()
            if not manager.set_timetables(data_dict):
                flask.flash(
                    'Počet hodin v rozvrhu neodpovídá úvazku.', 'error')
            return flask.render_template('timetable.html', **locals())


    @app.route('/admin', methods=['GET', 'POST'])
    @authorized_only('admin')
    @pass_user_info
    def admin(uid, username):
        acl = manager.get_acl(username)
        admin = True
        if flask.request.method == 'POST':
            manager.set_acls(flask.request.form.to_dict())
        
        acl = manager.get_acl(username)
        employees = manager.get_all_employees()
        depts = manager.get_all_depts()
        
        return flask.render_template('admin.html', **locals())

    @app.route('/timetable_data', defaults={'forced': None})
    @app.route('/timetable_data/<forced>')
    @authorized_only('user')
    @pass_user_info
    def get_timetables_data(uid, username, forced):
        admin = has_privilege('admin')
        if admin and forced is not None:
            username = forced
            uid = manager.db.employee.filter_by(username=forced).first().uid
        acl = manager.get_acl(username)
        emp_no = manager.get_emp_no(username)
        if not emp_no:
            log.err('Query for timetable data for employee who is not in database.')
            raise NotAcceptable
        return flask.jsonify(manager.get_timetables(uid))

    @app.route('/pvs')
    @authorized_only('user')
    @pass_user_info
    def get_pvs(uid, username):
        period = flask.request.values.get('period').split('-')

        if not period:
            log.err('Query for list of PVs without required period parameter.')
            raise NotAcceptable

        return flask.jsonify(manager.get_pvs(uid, int(period[0]), int(period[1])))

    @app.route('/attendance_submit', methods=['POST'])
    @authorized_only('user')
    @pass_user_info
    def set_attendance_data(uid, username):
        acl = manager.get_acl(username)
        data = flask.request.get_json()

        user_uid = int(data.get('user_uid'))

        # check access
        if acl.isdigit() and uid != user_uid:
            if not manager.is_supervisor(uid, user_uid):
                log.err('Submiting data for person not in your department.')
                raise Forbidden
        elif uid != user_uid:
            log.err('Submiting attendance data for user other than is logged-in.')
            raise Forbidden

        mode = data.get('mode')
        if not mode:
            mode = 'Absence'

        start = data.get('start')
        end = data.get('end')
        if not start or not end:
            if mode != 'Presence':
                start = '00:00'
                end = '00:00'
            else:
                log.err(
                    'Query for attendance data without required parameter start or end.')
                raise NotAcceptable

        date = data.get('date')
        if not date:
            log.err('Query without required parameter date.')
            raise NotAcceptable

        return flask.jsonify(manager.set_attendance(date, user_uid, start, end, mode))

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        manager.db.rollback()

    return app


# vim:set sw=4 ts=4 et:
# -*- coding: utf-8 -*-
