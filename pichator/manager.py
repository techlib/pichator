#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

__all__ = ['Manager']

from twisted.python import log
from twisted.internet.task import LoopingCall
from sqlalchemy import and_
from sqlalchemy.dialects import postgresql
from sqlalchemy import types as sqltypes
from datetime import timedelta, datetime, date
from psycopg2.extras import DateRange, Range, register_range
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.exceptions import Forbidden, ImATeapot


class TimeRange(Range):
    pass


class TIMERANGE(postgresql.ranges.RangeOperators, sqltypes.UserDefinedType):
    def get_col_spec(self, **kw):
        return 'timerange'


class Manager(object):
    def __init__(self, pich_db):
        self.pich_db = pich_db
        register_range('timerange', TimeRange,
                       self.pich_db.engine.raw_connection().cursor(), globally=True)

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
            pv_t).join(time_t, isouter=True).filter(emp_t.emp_no == emp_no).all()
        for pv in pvs:
            work_rel = pv[1]
            if pv[2]:
                tt = pv[2]
                if today in work_rel.validity and today in tt.validity:
                    payload["data"].append({"PV": work_rel.pvid, "occupancy": str(work_rel.occupancy),
                                            "department": work_rel.department,
                                            "days": [str(tt.monday.lower), str(tt.monday.upper), str(tt.tuesday.lower), str(tt.tuesday.upper),
                                                     str(tt.wedensday.lower), str(
                                                         tt.wedensday.upper), str(tt.thursday.lower),
                                                     str(tt.thursday.upper), str(tt.friday.lower), str(tt.friday.upper)]})
            else:
                if today in pv[1].validity:
                    payload["data"].append({"PV": work_rel.pvid, "occupancy": str(
                        pv[1].occupancy), "department": work_rel.department, "days": ['08:00', '16:30', '08:00',
                                                                                   '16:30', '08:00', '16:30',
                                                                                   '08:00', '16:30', '08:00',
                                                                                   '16:30']})
        return payload

    def set_timetables(self, data):
        # returns True if commit succeeds, False otherwise
        pv_t = self.pich_db.pv
        timetable_t = self.pich_db.timetable
        today = date.today()
        maxdate = date.max
        log.msg(f'data recieved: {data}')
        monday_v = TimeRange(data['monF'], data['monT'])
        tuesday_v = TimeRange(data['tueF'], data['tueT'])
        wedensday_v = TimeRange(data['wedF'], data['wedT'])
        thursday_v = TimeRange(data['thuF'], data['thuT'])
        friday_v = TimeRange(data['friF'], data['friT'])
        validity_v = DateRange(today, maxdate)
        pvid_v = data['pvs']
        if not monday_v and tuesday_v and wedensday_v and thursday_v and friday_v and validity_v and pvid_v:
            raise ImATeapot
        pvs = pv_t.filter(pv_t.pvid == pvid_v).all()
        for pv in pvs:
            if today in pv.validity:
                valid_pv_uid = pv.uid
                break
        if not valid_pv_uid:
            raise ImATeapot
        pv_w_tt = self.pich_db.session().query(
            timetable_t, pv_t).join(pv_t).filter(pv_t.pvid == pvid_v).all()
        for pv_w_tt_it in pv_w_tt:
            if today in pv_w_tt_it[0].validity and today in pv_w_tt_it[1].validity:
                tt_timeid = pv_w_tt_it[0].timeid
                cur_tt = timetable_t.filter(timetable_t.timeid == tt_timeid)
                validity_from = cur_tt.one().validity.lower
                new_validity = DateRange(validity_from, today)
                cur_tt.update({'validity': new_validity})
                break

        try:
            timetable_t.insert(monday=monday_v, tuesday=tuesday_v, wedensday=wedensday_v,
                               thursday=thursday_v, friday=friday_v, validity=validity_v, uid_pv=valid_pv_uid)
            self.pich_db.commit()
        except Exception as e:
            log.err(e)
            self.pich_db.rollback()
            raise ImATeapot

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
                    if pv_t.filter(and_(pv_t.pvid == pv['pvid'], pv_t.occupancy == pv['occupancy'],
                                        pv_t.department == pv['department'], pv_t.uid_employee == uid_emp)).first():
                        pv_t.filter(and_(pv_t.pvid == pv['pvid'], pv_t.occupancy == pv['occupancy'],
                                         pv_t.department == pv['department'], pv_t.uid_employee == uid_emp)).one().update().values({'validity': valid})
                    else:
                        pv_t.insert(pvid=pv['pvid'], occupancy=pv['occupancy'],
                                    department=pv['department'], validity=valid, uid_employee=uid_emp)

        self.pich_db.commit()
