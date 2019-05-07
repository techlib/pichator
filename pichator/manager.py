#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

__all__ = ['Manager']


class Manager(object):
    def __init__(self, pich_db):
        self.pich_db = pich_db

    def get_emp_no(self, username):
        return self.pich_db.employee().filter_by(username=username).one().emp_no

    def get_timetables(self, emp_no):
        payload = {'data': []}
        pvs = self.pich_db.session.query(self.pich_db.employee, self.pich_db.pv, self.pich_db.timetable).join(
            self.pich_db.pv).join(self.pich_db.timetable).filter_by(emp_no=emp_no).fetch_all()
        for pv in pvs:
            payload['data'].append({'PV': pv.pvid, 'days': [pv.monday_from, pv.monday_to, pv.tuesday_from, pv.tuesday_to,
                                                            pv.wedensday_from, pv.wedensday_to, pv.thursday_from, pv.thursday_to, pv.friday_from, pv.friday_to]})
        return payload
