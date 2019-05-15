#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

__all__ = ['Manager']

from twisted.python import log
from twisted.internet.task import LoopingCall
from sqlalchemy import and_
from datetime import timedelta, datetime, date
from psycopg2.extras import DateRange
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.exceptions import Forbidden


class Manager(object):
    def __init__(self, pich_db):
        self.pich_db = pich_db

    def get_emp_no(self, username):
        emp_t = self.pich_db.employee
        try:
            return emp_t.filter(emp_t.username == username).one().emp_no
        except NoResultFound:
            log.msg(f'User not found. Supplied username: {username}')
            raise Forbidden

    def get_timetables(self, emp_no):
        payload = {'data': []}
        emp_t = self.pich_db.employee
        time_t = self.pich_db.timetable
        pv_t = self.pich_db.pv
        today = date.today()
        pvs = self.pich_db.session.query(emp_t,
                                         pv_t, time_t).join(
            pv_t).join(time_t).filter(emp_t.emp_no == emp_no).all()
        # no timetables yet
        if pvs == []:
            pv_only = self.pich_db.session.query(emp_t, pv_t).join(
                pv_t).filter(emp_t.emp_no == emp_no).all()
            for pv in pv_only:
                if today in pv[1].validity:
                    payload["data"].append({"PV": pv[1].pvid, "occupancy": str(
                        pv[1].occupancy), "department": pv[1].department, "days": ['08:00', '16:30', '08:00',
                                                                                   '16:30', '08:00', '16:30',
                                                                                   '08:00', '16:30', '08:00',
                                                                                   '16:30']})
        else:
            for pv in pvs:
                work_rel = pv[1]
                tt = pv[2]
                if today in work_rel.validity:
                    payload["data"].append({"PV": work_rel.pvid, "occupancy": str(work_rel.occupancy),
                                            "department": work_rel.department,
                                            "days": [tt.monday.lower, tt.monday.upper, tt.tuesday.lower, tt.tuesday.upper,
                                                     tt.wedensday.lower, tt.wedensday.upper, tt.thursday.lower,
                                                     tt.thursday.upper, tt.friday.lower, tt.friday.upper]})
        return payload

    def update_presence(self, date, source):
        pres_t = self.pich_db.presence
        emp_t = self.pich_db.employee
        for employee in emp_t.all():
            log.msg(
                f'Processing employee {employee.first_name} {employee.last_name}')
            arriv = source.get_arrival(date, employee.uid)
            depart = source.get_departure(date, employee.uid)
            length = (depart - arriv).seconds / 3600
            presence_mode = 'Presence' if length >= 6 else 'Presence-'
            log.msg(
                f'Current record: arrival: {arriv}, departure: {depart}, length: {length}, presence_mode: {presence_mode}')
            if not pres_t.filter(
                    and_(pres_t.uid_employee == employee.uid, pres_t.date == date)).first():
                pres_t.insert(date=date, arrival=arriv.time(),
                              departure=depart.time(),
                              presence_mode=presence_mode,
                              uid_employee=employee.uid)

            else:
                presence_s = pres_t.filter(
                    and_(pres_t.uid_employee == employee.uid, pres_t.date == date))
                presence = presence_s.one()
                if presence.arrival > arriv.time():
                    presence_s.update({'arrival': arriv.time()})

                if presence.departure < depart.time():
                    presence_s.update({'departure': depart.time()})

        self.pich_db.commit()

    def sync(self, date, source, src_name, elanor):
        self.check_loop = LoopingCall(
            self.update_presence, date=date, source=source)
        self.check_loop_2 = LoopingCall(self.update_pvs, elanor=elanor)
        log.msg(f'Syncing presence from {src_name}')
        self.check_loop.start(3600)
        log.msg(f'Syncing pvs from elanor')
        self.check_loop_2.start(3600)

    def update_pvs(self, elanor):
        pv_t = self.pich_db.pv
        emp_t = self.pich_db.employee
        for employee in emp_t.all():
            for pv in elanor.get_pvs(employee.emp_no):
                uid_emp = emp_t.filter(
                    emp_t.emp_no == pv['emp_no']).first().uid
                valid = DateRange(
                    lower=pv['validity'][0], upper=pv['validity'][1], bounds='[]')

                if not pv_t.filter(and_(pv_t.pvid == pv['pvid'], pv_t.occupancy == pv['occupancy'],
                                        pv_t.department == pv['department'], pv_t.validity == valid, pv_t.uid_employee == uid_emp)).first():
                    log.msg(
                        f'Inserting pv: {pv["pvid"]} of employee {employee.first_name} {employee.last_name}')
                    pv_t.insert(pvid=pv['pvid'], occupancy=pv['occupancy'],
                                department=pv['department'], validity=valid, uid_employee=uid_emp)

        self.pich_db.commit()
