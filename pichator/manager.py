#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

__all__ = ['Manager']

from twisted.python import log
from twisted.internet.task import LoopingCall
from threading import Thread
from sqlalchemy import and_
from sqlalchemy.dialects import postgresql
from sqlalchemy import types as sqltypes
from datetime import timedelta, datetime, date, time
from psycopg2.extras import DateRange, Range, register_range
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.exceptions import Forbidden, NotAcceptable, InternalServerError
from calendar import monthrange


class TimeRange(Range):
    def len(self):
        # Returns number of minutes in timerange
        overflow = False
        split_from = self.lower.split(':')
        split_to = self.upper.split(':')
        h_from = int(split_from[0])
        m_from = int(split_from[1])
        h_to = int(split_to[0])
        m_to = int(split_to[1])
        m_len = m_to - m_from
        if m_len < 0:
            m_len = 60 - m_len
            overflow = True
        h_len = h_to - h_from if not overflow else h_to - h_from - 1
        total = h_len * 60 + m_len
        return total if total < 6 * 60 else total - 30


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
            log.err(f'User not found. Supplied username: {username}')
            raise NotAcceptable
        
    def get_acl(self, username):
        emp_t = self.pich_db.employee
        try:
            return emp_t.filter(emp_t.username == username).one().acl
        except NoResultFound:
            log.err(f'User not found. Supplied username: {username}')
            raise NotAcceptable
        
    def get_depts(self, username):
        emp_t = self.pich_db.employee
        pv_t = self.pich_db.pv
        try:
            emp_uid = emp_t.filter(emp_t.emp_no == self.get_emp_no(username)).one().uid
            return [i.dept for i in pv_t.filter(and_(pv_t.uid_employee == emp_uid, datetime.today().date() in pv_t.validity))]
        except Exception as e:
            log.err(e)
            return []
        
    def get_employees(self, dept, period):
        retval = []
        emp_t = self.pich_db.employee
        pv_t = self.pich_db.pv
        per_range = monthrange(
            int(period.split('-')[1]), int(period.split('-')[0]))
        per_start = datetime.strptime(
            period + f'-{per_range[0] + 1}', '%m-%Y-%d').date()
        per_end = datetime.strptime(
            period + f'-{per_range[1]}', '%m-%Y-%d').date()

        for employee in self.pich_db.session.query(pv_t, emp_t).join(emp_t).all():
            if str(employee[0].department)[0] == str(dept)[0] and (per_start in employee[0].validity or per_end in employee[0].validity):
                retval.append({'first_name': employee[1].first_name, 'last_name': employee[1].last_name, 'PV':employee[0].pvid, 'dept': employee[0].department, 'username': employee[1].username})
        return retval
        
    def threaded_init(self, period, source):
        th_init = Thread(target=self.init_presence, args=(period, source))
        th_init.start()

    def threaded_update_presence(self, date, source):
        th_up_pres = Thread(target=self.update_presence, args=(date, source))
        th_up_pres.start()

    def threaded_update_pv(self, elanor):
        th_up_pv = Thread(target=self.update_pvs, args=(elanor, ))
        th_up_pv.start()

    def get_timetables(self, emp_uid):
        payload = {'data': []}
        today = date.today()

        time_t = self.pich_db.timetable
        pv_t = self.pich_db.pv

        pvs = self.pich_db.session.query(pv_t, time_t) \
            .outerjoin(time_t, and_(time_t.uid_pv == pv_t.uid, time_t.validity.contains(today))) \
            .filter(pv_t.validity.contains(today)) \
            .filter(pv_t.uid_employee == emp_uid)

        for item in pvs.all():
            pv, tt = item

            pv_data = {
                'PV': pv.pvid,
                'occupancy': str(pv.occupancy),
                'department': pv.department,
                'days': [],
            }

            if tt:
                for day in ('monday', 'tuesday', 'wedensday', 'thursday', 'friday'):
                    pv_data['days'].append(
                        tt.__getattribute__(day).lower.strftime('%H:%M'))
                    pv_data['days'].append(
                        tt.__getattribute__(day).upper.strftime('%H:%M'))

            else:
                pv_data['days'] = ['08:00', '16:30'] * 5

            payload['data'].append(pv_data)

        return payload

    def set_timetables(self, data):
        # returns True if commit succeeds, False otherwise
        pv_t = self.pich_db.pv
        timetable_t = self.pich_db.timetable
        today = date.today()
        maxdate = date.max
        if not (data['monF'] and data['monT'] and data['tueF'] and data['tueT'] and data['wedF'] and data['wedT'] and data['thuF'] and data['thuT'] and data['friF'] and data['friT']):
            log.err('Attempt to upsert timetable without all days periods filled-in.\n\
                    To signify free day, please set start and end of workday to 00:00')
            raise NotAcceptable
        monday_v = TimeRange(data['monF'], data['monT'])
        tuesday_v = TimeRange(data['tueF'], data['tueT'])
        wedensday_v = TimeRange(data['wedF'], data['wedT'])
        thursday_v = TimeRange(data['thuF'], data['thuT'])
        friday_v = TimeRange(data['friF'], data['friT'])
        hours_in_week = (monday_v.len() + tuesday_v.len() +
                         wedensday_v.len() + thursday_v.len() + friday_v.len()) / 60
        validity_v = DateRange(today, maxdate)
        pvid_v = data['f_pvs']
        pvs = pv_t.filter(pv_t.pvid == pvid_v).all()
        for pv in pvs:
            if today in pv.validity:
                valid_pv_uid = pv.uid
                occupancy = pv.occupancy
                break
        if not hours_in_week == 40 * occupancy:
            return False
        if not valid_pv_uid:
            log.err('Attempt to upsert timetable for user who doesn\'t have valid PV')
            raise NotAcceptable
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
            timetable_t.insert(monday=monday_v, tuesday=tuesday_v,
                               wedensday=wedensday_v, thursday=thursday_v,
                               friday=friday_v, validity=validity_v,
                               uid_pv=valid_pv_uid)
            self.pich_db.commit()
            return True
        except Exception as e:
            log.err(e)
            self.pich_db.rollback()
            raise InternalServerError

    def get_pvs(self, emp_no, period):
        retval = {'data': []}
        per_range = monthrange(
            int(period.split('-')[1]), int(period.split('-')[0]))
        per_start = datetime.strptime(
            period + f'-{per_range[0] + 1}', '%m-%Y-%d').date()
        per_end = datetime.strptime(
            period + f'-{per_range[1]}', '%m-%Y-%d').date()
        pv_t = self.pich_db.pv
        emp_t = self.pich_db.employee
        pvs = self.pich_db.session.query(emp_t,
                                         pv_t).join(
            pv_t).filter(emp_t.emp_no == emp_no).all()
        for pv in pvs:
            work_rel = pv[1]
            if per_start in work_rel.validity or per_end in work_rel.validity:
                retval['data'].append(
                    {'PV': work_rel.pvid, 'dept': work_rel.department})
        return retval

    def get_attendance(self, uid, pvid, period, username):
        WEEKDAYS = ['Pondělí', 'Úterý', 'Středa',
                    'Čtvrtek', 'Pátek', 'Sobota', 'Neděle']
        retval = {'data': []}
        per_year = int(period.split('-')[1])
        per_month = int(period.split('-')[0])
        per_range = monthrange(per_year, per_month)
        per_range_list = [i for i in range(1, per_range[1] + 1)]
        pv_t = self.pich_db.pv
        emp_t = self.pich_db.employee
        pres_t = self.pich_db.presence
        time_t = self.pich_db.timetable
        emp_no = self.get_emp_no(username)
        uid = emp_t.filter(emp_t.emp_no == emp_no).one().uid
        pvs = pv_t.filter(pv_t.pvid == pvid).all()
        uid_pv = ''
        for day in per_range_list:
            curr_time = ''
            day_date = date(per_year, per_month, day)
            weekday = day_date.weekday()
            for pv in pvs:
                if day_date in pv.validity:
                    uid_pv = pv.uid
                    break
            if not uid_pv:
                return {'data': []}
            timetables = time_t.filter(time_t.uid_pv == uid_pv).all()
            for timetable in timetables:
                if day_date in timetable.validity:
                    curr_time = timetable
                    break
            if curr_time:
                timetable_list = [curr_time.monday, curr_time.tuesday,
                                  curr_time.wedensday, curr_time.thursday, curr_time.friday, TimeRange('00:00', '00:00'), TimeRange('00:00', '00:00')]
            else:
                timetable_list = [TimeRange('00:00', '00:00')] * 7
            attend = pres_t.filter(
                and_(pres_t.date == day_date, pres_t.uid_employee == uid)).first()
            if attend:
                retval['data'].append({'day': f'{day}. ', 'start': f'{attend.arrival}', 'end': f'{attend.departure}',
                                       'mode': attend.presence_mode, 'stamp': 'Ano' if attend.food_stamp else 'Ne',
                                       'timetable': f'{timetable_list[weekday].lower} - {timetable_list[weekday].upper}',
                                       'weekday': WEEKDAYS[weekday]})
            else:
                retval['data'].append({'day': f'{day}. ', 'start': '00:00', 'end': '00:00',
                                       'mode': 'Absence', 'stamp': 'Ne',
                                       'timetable': f'{timetable_list[weekday].lower} - {timetable_list[weekday].upper}',
                                       'weekday': WEEKDAYS[weekday]})
        return retval

    def set_attendance(self, day, period, username, start, end, mode):
        pres_t = self.pich_db.presence
        emp_t = self.pich_db.employee
        per_year = int(period.split('-')[1])
        per_month = int(period.split('-')[0])
        day_no = int(day.replace('.', ''))
        emp_no = self.get_emp_no(username)
        start_t = datetime(per_year, per_month, day_no, int(
            start.split(':')[0]), int(start.split(':')[1]))
        end_t = datetime(per_year, per_month, day_no, int(
            end.split(':')[0]), int(end.split(':')[1]))
        date = start_t.date()
        length = (end_t - start_t).seconds / 3600
        food_stamp = length >= 6
        employee = emp_t.filter(emp_t.emp_no == emp_no).one()
        if not pres_t.filter(
                and_(pres_t.uid_employee == employee.uid, pres_t.date == date)).first():
            pres_t.insert(date=date, arrival=start_t,
                          departure=end_t,
                          presence_mode=mode,
                          uid_employee=employee.uid, food_stamp=food_stamp)
        else:
            presence_s = pres_t.filter(
                and_(pres_t.uid_employee == employee.uid, pres_t.date == date))
            presence_s.update({'arrival': start_t, 'departure': end_t,
                               'food_stamp': food_stamp, 'presence_mode': mode})

        self.pich_db.commit()

    def get_department(self, dept, period):
        emp_t = self.pich_db.employee
        
    
    def init_presence(self, period, source):
        pres_t = self.pich_db.presence
        emp_t = self.pich_db.employee
        per_year = int(period.split('-')[1])
        per_month = int(period.split('-')[0])
        per_range = monthrange(per_year, per_month)
        per_range_list = [i for i in range(1, per_range[1] + 1)]
        for employee in emp_t.all():
            for day in per_range_list:
                datetm = datetime.strptime(
                    f'{day}-{per_month}-{per_year}', '%d-%m-%Y')
                date = datetm.date()
                arriv = source.get_arrival(date, employee.uid)
                depart = source.get_departure(date, employee.uid)
                if not arriv:
                    continue
                length = (depart - arriv).seconds / 3600
                presence_mode = 'Presence'
                food_stamp = length >= 6
                if not pres_t.filter(
                        and_(pres_t.uid_employee == employee.uid, pres_t.date == date)).first():
                    pres_t.insert(date=date, arrival=arriv.time(),
                                  departure=depart.time(),
                                  presence_mode=presence_mode,
                                  uid_employee=employee.uid, food_stamp=food_stamp)

                else:
                    presence_s = pres_t.filter(
                        and_(pres_t.uid_employee == employee.uid, pres_t.date == date))
                    presence = presence_s.one()
                    if presence.arrival > arriv.time():
                        presence_s.update(
                            {'arrival': arriv.time(), 'food_stamp': food_stamp})

                    if presence.departure < depart.time():
                        presence_s.update(
                            {'departure': depart.time(), 'food_stamp': food_stamp})

        self.pich_db.commit()

    def update_presence(self, date, source):
        pres_t = self.pich_db.presence
        emp_t = self.pich_db.employee
        for employee in emp_t.all():
            arriv = source.get_arrival(date, employee.uid)
            depart = source.get_departure(date, employee.uid)
            if not arriv:
                continue
            length = (depart - arriv).seconds / 3600
            presence_mode = 'Presence'
            food_stamp = length >= 6
            if not pres_t.filter(
                    and_(pres_t.uid_employee == employee.uid, pres_t.date == date)).first():
                pres_t.insert(date=date, arrival=arriv.time(),
                              departure=depart.time(),
                              presence_mode=presence_mode,
                              uid_employee=employee.uid, food_stamp=food_stamp)
            else:
                presence_s = pres_t.filter(
                    and_(pres_t.uid_employee == employee.uid, pres_t.date == date))
                presence = presence_s.one()
                if presence.arrival > arriv.time():
                    presence_s.update(
                        {'arrival': arriv.time(), 'food_stamp': food_stamp})
                if presence.departure < depart.time():
                    presence_s.update(
                        {'departure': depart.time(), 'food_stamp': food_stamp})

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
                                        pv_t.department == pv['department'], pv_t.validity == valid,
                                        pv_t.uid_employee == uid_emp)).first():
                    if pv_t.filter(and_(pv_t.pvid == pv['pvid'], pv_t.occupancy == pv['occupancy'],
                                        pv_t.department == pv['department'], pv_t.uid_employee == uid_emp)).first():
                        pv_t.filter(and_(pv_t.pvid == pv['pvid'], pv_t.occupancy == pv['occupancy'],
                                         pv_t.department == pv['department'], pv_t.uid_employee == uid_emp
                                         )).update({'validity': valid})
                    else:
                        pv_t.insert(pvid=pv['pvid'], occupancy=pv['occupancy'],
                                    department=pv['department'], validity=valid, uid_employee=uid_emp)

        self.pich_db.commit()
