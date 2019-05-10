#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

__all__ = ['Manager']

from sqlalchemy import and_
from datetime import timedelta
from psycopg2.extras import Range


class Manager(object):
    def __init__(self, pich_db):
        self.pich_db = pich_db

    def get_emp_no(self, username):
        return self.pich_db.employee().filter_by(username=username).one().emp_no

    def get_timetables(self, emp_no):
        payload = {'data': []}
        pvs = self.pich_db.session.query(self.pich_db.employee,
                                         self.pich_db.pv, self.pich_db.timetable).join(
            self.pich_db.pv).join(self.pich_db.timetable).filter_by(emp_no=emp_no).fetch_all()
        for pv in pvs:
            payload['data'].append({'PV': pv.pvid, 'days': [pv.monday.lower, pv.monday.upper, pv.tuesday.lower, pv.tuesday.upper,
                                                            pv.wedensday.lower, pv.wedensday.upper, pv.thursday.lower,
                                                            pv.thursday.upper, pv.friday.lower, pv.friday.upper]})
        return payload

    def update_presence(self, date, source):
        for employee in self.pich_db.employee().fetchall():
            arrival = source.get_arrival(date, employee.uid)
            departure = source.get_departure(date, employee.uid)
            length = (departure - arrival).seconds / 3600
            presence_mode = 'Presence' if length >= 6 else 'Presence -'
            if not self.pich_db.presence().filter_by(
                    and_(uid_employee=employee.uid, date=date)).first():
                self.pich_db.presence().insert().values(date=date, arrival=arrival,
                                                        departure=departure,
                                                        presence_mode=presence_mode,
                                                        uid_employee=employee.uid)
            else:
                presence = self.pich_db.presence().filter_by(
                    and_(uid_employee=employee.uid, date=date)).one()
                if presence.arrival > arrival:
                    presence.update().values(arrival=arrival)
                if presence.departure < departure:
                    presence.update().values(departure=departure)
        self.pich_db.commit()
