#!/usr/bin/python3
# -*- coding: utf-8 -*-

__all__ = ['make_site']

from werkzeug.exceptions import Unauthorized

import flask
import os


def make_site(manager, debug=False):
    app = flask.Flask('.'.join(__name__.split('.')[:-1]))
    app.secret_key = os.urandom(16)
    app.debug = debug

    @app.errorhandler(Unauthorized.code)
    def unauthorized(e):
        return flask.Response('Invalid or missing token', Unauthorized.code, {'WWW-Authenticate': 'Bearer'})

    @app.route('/', methods=['GET'])
    def info():
        return flask.render_template('index.html', **locals())

    @app.route('/api/incoming', methods=['POST'])
    def msg():
        result = manager.process_msg(flask.request.get_json(),
                                     flask.request.headers.get('Authentication'))
        if result:
            return flask.Response('OK', 200)
        else:
            return flask.Response('Internal server error', 500)

    @app.route('/report/<id>')
    def report(id):
        return flask.render_template('report.html', **locals())

    @app.route('/last_failed_plays')
    def data_fail_play():
        retval = {'data': []}
        fails = manager.get_last_failed()
        for fail in fails:
            retval['data'].append(
                {'name': fail['name'], 'time': fail['time'], 'host': fail['host']})
        return flask.jsonify(retval)

    @app.route('/host/<hostname>')
    def host_detail(hostname):
        return flask.render_template('host.html', **locals())

    @app.route('/host_data/<hostname>')
    def host_data(hostname):
        retval = {'data': []}
        plays = manager.get_host_history(hostname)
        for play in plays:
            retval['data'].append(
                {'play': play['name'], 'status': play['status'], 'time': play['time']})
        return flask.jsonify(retval)

    @app.route('/monitor/host')
    def get_hosts():
        data = manager.get_hosts()
        return flask.jsonify({'data': data})

    return app
