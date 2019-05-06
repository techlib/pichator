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


def make_site(db, manager, access_model, debug=False):
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
            username = flask.request.headers.get('X-Full-Name', 'Someone')

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
    @authorized_only('admin')
    def display_changes():
        nonlocal has_privilege
        return flask.render_template('timetable.html', **locals())

    @app.route('/detail', defaults={'dept': None})
    @app.route('/detail/<dept>')
    @authorized_only('admin')
    def show_detail(dept):
        nonlocal has_privilege
        return flask.render_template('details.html', **locals())

    @app.route('/recounted_occupancy')
    @authorized_only('admin')
    def show_recounted():
        nonlocal has_privilege
        return flask.render_template('recounted.html', **locals())

    @app.route('/line')
    @authorized_only('admin')
    def show_line():
        nonlocal has_privilege
        return flask.render_template('line_graph.html', **locals())

    @app.route('/recounted_data/<date_from>/<date_to>')
    @authorized_only('admin')
    def get_recounted(date_from, date_to):
        nonlocal has_privilege
        retval = {"data": []}
        data = manager.recount_pv(date_from, date_to)
        for dpt in data.keys():
            retval["data"].append({'parent': str(dpt)[
                0], 'dpt': '<a href="detail/' + dpt + '">' + dpt + '</a>', 'occupancy': round(data[dpt], 3)})
        return flask.jsonify(retval)

    @app.route('/recounted_graph_data/<date_from>/<date_to>')
    @authorized_only('admin')
    def get_recounted_datasets(date_from, date_to):
        nonlocal has_privilege
        retval = {'datasets': [
            {'data': [], 'backgroundColor': []}], 'labels': []}
        colors = ['#FFFF00', '#57EA00', '#1344C8',
                  '#8409C7', '#DD007D', '#FF2800', '#FFBB00']
        data = manager.recount_pv(date_from, date_to)
        root_dept_list = []
        for dpt in manager.dept_list:
            if len(dpt) == 1:
                root_dept_list.append(dpt)
        root_dept_list.sort()
        for dpt in root_dept_list:
            retval['datasets'][0]['data'].append(round(data[dpt], 3))
            retval['datasets'][0]['backgroundColor'].append(
                colors[root_dept_list.index(dpt)])
            retval['labels'].append(dpt)
        return flask.jsonify(retval)

    @app.route('/graph_data/<date_val>')
    @authorized_only('admin')
    def get_datasets(date_val):
        nonlocal has_privilege
        datasets = []
        date_split = date_val.split('-')
        p_date = date(int(date_split[2]), int(
            date_split[1]), int(date_split[0]))
        retval = {'labels': [], 'datasets': []}
        months = ['leden', 'únor', 'březen', 'duben', 'květen', 'červen',
                  'červenec', 'srpen', 'září', 'říjen', 'listopad', 'prosinec']
        colors = ['#FFFF00', '#57EA00', '#1344C8',
                  '#8409C7', '#DD007D', '#FF2800', '#FFBB00']
        for i in range(int(date_val.split('-')[1]), 13):
            retval['labels'].append(months[i-1] + ' ' + str(p_date.year))
        for i in range(1, int(date_val.split('-')[1])):
            retval['labels'].append(months[i-1] + ' ' + str(p_date.year+1))
        root_dept_list = []
        for dpt in manager.dept_list:
            if len(dpt) == 1:
                root_dept_list.append(dpt)
        root_dept_list.sort()
        for dpt in root_dept_list:
            dataset = {
                'label': dpt, 'backgroundColor': colors[root_dept_list.index(dpt)], 'data': []}
            datasets.append(dataset)
        dates = []
        for i in range(0, 12):
            future_p_date = p_date + relativedelta(months=i)
            dates.append(str(future_p_date.day) + '-' +
                         str(future_p_date.month) + '-' + str(future_p_date.year))
        future_month = 0
        for future_date in dates:
            total_sum = 0
            for dpt in root_dept_list:
                sum_val = 0.0
                for pv in manager.filter_by_presence(future_date, manager.filter_by_time(future_date, future_date, manager.filter_by_dept(dpt, ""))):
                    if pv.occupancy != "DPČ/DPP":
                        sum_val = sum_val + float(pv.occupancy)
                total_sum = total_sum + sum_val
                for dataset in datasets:
                    if str(dataset['label']) == str(dpt):
                        dataset['data'].append(round(sum_val, 2))
            retval['labels'][future_month] = retval['labels'][future_month] + \
                ' - {}'.format(round(total_sum, 2))
            future_month = future_month + 1
        for i in range(1, len(root_dept_list)+1):
            for dataset in datasets:
                if dataset['label'] == str(i):
                    retval['datasets'].append(dataset)
        return flask.jsonify(retval)

    @app.route('/line_data/<date_from>/<date_to>')
    @authorized_only('admin')
    def get_line_datasets(date_from, date_to):
        nonlocal has_privilege
        datasets = []
        date_split_f = date_from.split('-')
        date_split_t = date_to.split('-')
        p_date_f = date(int(date_split_f[2]), int(
            date_split_f[1]), int(date_split_f[0]))
        p_date_t = date(int(date_split_t[2]), int(
            date_split_t[1]), int(date_split_t[0]))
        retval = {'labels': [], 'datasets': []}
        months = ['leden', 'únor', 'březen', 'duben', 'květen', 'červen',
                  'červenec', 'srpen', 'září', 'říjen', 'listopad', 'prosinec']
        colors = ['#FFFF00', '#57EA00', '#1344C8',
                  '#8409C7', '#DD007D', '#FF2800', '#FFBB00']
        i = p_date_f
        dates = []
        while i <= p_date_t:
            retval['labels'].append(months[(i.month - 1)] + ' ' + str(i.year))
            dates.append(str(i.day) + '-' + str(i.month) + '-' + str(i.year))
            i += relativedelta(months=1)
        root_dept_list = []
        for dpt in manager.dept_list:
            if len(dpt) == 1:
                root_dept_list.append(dpt)
        root_dept_list.sort()
        for dpt in root_dept_list:
            dataset = {
                'label': dpt, 'backgroundColor': colors[root_dept_list.index(dpt)], 'borderColor': colors[root_dept_list.index(dpt)], 'data': [], 'fill': 'false'}
            datasets.append(dataset)
        future_month = 0
        for future_date in dates:
            total_sum = 0
            for dpt in root_dept_list:
                sum_val = 0.0
                for pv in manager.filter_by_presence(future_date, manager.filter_by_time(future_date, future_date, manager.filter_by_dept(dpt, ""))):
                    if pv.occupancy != "DPČ/DPP":
                        sum_val = sum_val + float(pv.occupancy)
                total_sum = total_sum + sum_val
                for dataset in datasets:
                    if str(dataset['label']) == str(dpt):
                        dataset['data'].append(round(sum_val, 2))
            retval['labels'][future_month] = retval['labels'][future_month] + \
                ' - {}'.format(round(total_sum, 2))
            future_month = future_month + 1
        for i in range(0, len(root_dept_list)):
            for dataset in datasets:
                if dataset['label'] == str(i+1):
                    retval['datasets'].append(dataset)
        return flask.jsonify(retval)

    @app.route('/detail_data/<date_val>', defaults={'dept': None})
    @app.route('/detail_data/<date_val>/<dept>')
    @authorized_only('admin')
    def get_details(date_val, dept):
        nonlocal has_privilege
        retval = {'data': []}
        if dept == None:
            pvs = manager.filter_by_time(date_val, date_val)
        else:
            pvs = manager.filter_by_time(
                date_val, date_val, manager.filter_by_dept(dept, ""))
        split_date = date_val.split('-')
        given_date = date(int(split_date[2]), int(
            split_date[1]), int(split_date[0]))
        for pv in pvs:
            vacancy_end = 'Není'
            for vacancy in pv.vd:
                if vacancy[0] != '' and vacancy[0] <= given_date and vacancy[1] >= given_date:
                    vacancy_end = vacancy[1].strftime('%d-%m-%Y')
            retval['data'].append({'oscpv': pv.oscpv, 'dept': pv.department, 'name': pv.name, 'surname': pv.surname,
                                   'start_of_employment': pv.soe.strftime('%d-%m-%Y'),
                                   'end_of_employment': 'Na dobu neurčitou' if pv.eoe.strftime('%d-%m-%Y') == '03-03-3333' else pv.eoe.strftime('%d-%m-%Y'),                                       'occupancy': pv.occupancy, 'vacancy_end': vacancy_end})
        return flask.jsonify(retval)

    @app.route('/occupancy_by_dept/<date_val>')
    @authorized_only('admin')
    def get_data(date_val):
        nonlocal has_privilege
        retval = {"data": []}
        for dpt in manager.dept_list:
            sum_val = 0.0
            for pv in manager.filter_by_presence(date_val, manager.filter_by_time(date_val, date_val, manager.filter_by_dept(dpt, ""))):
                sum_val += float(pv.occupancy)
            if sum_val != 0:
                retval["data"].append({'parent': str(dpt)[
                                      0], 'dpt': '<a href="detail/' + dpt + '">' + dpt + '</a>', 'occupancy': round(sum_val, 2)})
        return flask.jsonify(retval)

    @app.route('/changes_data/<date_from>/<date_to>')
    @authorized_only('admin')
    def get_changes(date_from, date_to):
        nonlocal has_privilege
        retval = {"data": []}
        for change in manager.filter_by_changes(date_from, date_to):
            pv = change[0]
            retval['data'].append({'oscpv': pv.oscpv, 'dept': pv.department, 'name': pv.name, 'surname': pv.surname,
                                   'occupancy': pv.occupancy, 'type_of_change': change[1], 'date_of_change': change[2].strftime('%d-%m-%Y')})
        return flask.jsonify(retval)

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        manager.db.rollback()

    return app


# vim:set sw=4 ts=4 et:
# -*- coding: utf-8 -*-
