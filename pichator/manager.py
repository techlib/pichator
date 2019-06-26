#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

__all__ = ['Manager']

from twisted.python import log
from twisted.internet.task import LoopingCall
from threading import Thread
from sqlalchemy import and_, or_
from sqlalchemy.dialects import postgresql
from sqlalchemy import types as sqltypes
from sqlalchemy.sql.expression import cast
from datetime import timedelta, datetime, date, time
from psycopg2.extras import DateRange, Range, register_range
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.exceptions import Forbidden, NotAcceptable, InternalServerError
from calendar import monthrange, monthlen

class TimeRange(Range):
    def len(self):
        # Returns number of minutes in timerange
        dt_from = datetime.combine(date.today(),self.lower)
        dt_to = datetime.combine(date.today(),self.upper)
        length = dt_to - dt_from
        total = length.total_seconds() / 60
        return total if total < 6 * 60 else total - 30


class TIMERANGE(postgresql.ranges.RangeOperators, sqltypes.UserDefinedType):
    def get_col_spec(self, **kw):
        return 'timerange'


def eng_to_symbol(mode, stamp):
    obj_mapping = {
        'Employer difficulties': 'C',
        'Vacation': 'D',
        'Vacation 0.5': '0,5D',
        'Presence': '/' if stamp else '/-',
        'Absence': 'A',
        'On call time': 'H',
        'Sickness': 'N',
        'Compensatory time off': 'NV',
        'Family member care': 'O',
        'Personal difficulties': 'P',
        'Bussiness trip': 'Sc+' if stamp else 'Sc',
        'Study': 'St',
        'Training': 'Šk' if stamp else 'Šk-',
        'Injury and disease from profession': 'Ú',
        'Unpaid leave': 'V',
        'Public interest': 'Z',
        'Sickday': 'ZV',
    }

    return obj_mapping[mode]


def eng_to_czech(mode):
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
        'Personal difficulties': 'Osobní překážky',
        'Bussiness trip': 'Služební cesta',
        'Study': 'Studium při zaměstnání',
        'Training': 'Školení',
        'Injury and disease from profession': 'Úraz/nemoc z povolání',
        'Unpaid leave': 'Neplacené volno',
        'Public interest': 'Obecný zájem',
        'Sickday': 'Zdravotní volno'
    }
    return obj_mapping[mode]


def get_dayname(number):
    return ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')[number]

class Manager(object):
    def __init__(self, db):
        self.db = db
        register_range('timerange', TimeRange,
                       self.db.engine.raw_connection().cursor(),
                       globally=True)
        self.depts = []

    def get_emp_no(self, username):
        emp_t = self.db.employee
        try:
            return emp_t.filter(emp_t.username == username).one().emp_no
        except NoResultFound:
            log.err(f'User not found. Supplied username: {username}')
            raise NotAcceptable

    def get_acl(self, username):
        emp_t = self.db.employee
        try:
            return emp_t.filter(emp_t.username == username).one().acl
        except NoResultFound:
            log.err(f'User not found. Supplied username: {username}')
            raise NotAcceptable

    def get_depts(self, username):
        emp_t = self.db.employee
        pv_t = self.db.pv
        try:
            emp_uid = emp_t.filter(
                emp_t.emp_no == self.get_emp_no(username)).one().uid
            today = date.today()
            pvs = pv_t.filter(and_(pv_t.uid_employee == emp_uid,
                                   pv_t.validity.contains(today))).all()

            return [pv.department for pv in pvs]
        except Exception as e:
            log.err(e)
            return []
        
    def get_all_depts(self):
        return self.depts
    
    def get_all_employees(self):
        retval = []
        for emp in self.db.employee.all():
            retval.append({
                'first_name': emp.first_name,
                'last_name': emp.last_name,
                'uid': emp.uid,
                'acl': emp.acl,
                    })
        return retval

    def month_range(self, year, month):
        days = monthlen(year, month)
        return DateRange(date(year, month, 1), date(year, month, days), '[]')

    def daterange_iter(self, dr):
        for n in range(int((dr.upper - dr.lower).days)):
            yield dr.lower + timedelta(n)

    def get_employees(self, dept, month, year):
        retval = []

        emp_t = self.db.employee
        pv_t = self.db.pv

        employees_with_pvs = self.db.session \
            .query(emp_t, pv_t) \
            .join(pv_t) \
            .filter(pv_t.validity.overlaps(self.month_range(year, month))) \
            .filter(cast(pv_t.department, sqltypes.String).startswith(dept))

        for employee, pv in employees_with_pvs.all():
            retval.append({
                'first_name': employee.first_name,
                'last_name': employee.last_name,
                'PV': pv.pvid,
                'dept': pv.department,
                'username': employee.username
            })

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

        time_t = self.db.timetable
        pv_t = self.db.pv

        pvs = self.db.session.query(pv_t, time_t) \
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
                for day in ('monday', 'tuesday', 'wednesday', 'thursday', 'friday'):
                    pv_data['days'].append(
                        tt.__getattribute__(day).lower.strftime('%H:%M'))
                    pv_data['days'].append(
                        tt.__getattribute__(day).upper.strftime('%H:%M'))

            else:
                pv_data['days'] = ['08:00', '16:30'] * 5

            payload['data'].append(pv_data)

        return payload
    
    def get_dept_mode(self, dept):
        acls_t = self.db.acls
        mode_row = acls_t.filter(acls_t.dept == str(dept)).first()
        if not mode_row:
            return
        else:
            return mode_row.acl
        
    def set_dept_mode(self, dept, mode):
        acls_t = self.db.acls
        prev_mode_row = acls_t.filter(acls_t.dept == dept)
        if prev_mode_row.first():
            acl = prev_mode_row.first().acl
            if mode == acl:
                return
            else:
                prev_mode_row.update({'acl': mode})
        else:
            acls_t.insert(dept = dept, acl = mode)
            
        self.db.commit()
            
    def set_timetables(self, data):
        # returns True if commit succeeds, False otherwise
        pv_t = self.db.pv
        timetable_t = self.db.timetable
        maxdate = date.max
        start_date = date.today()
        
        if data['date']:
            start_date = datetime.strptime(data['date'],'%d-%m-%Y').date()
            
        valid_mon = data['monF'] and data['monT']
        valid_tue = data['tueF'] and data['tueT']
        valid_wed = data['wedF'] and data['wedT']
        valid_thu = data['thuF'] and data['thuT']
        valid_fri = data['friF'] and data['friT']
        valid = valid_mon and valid_tue and valid_wed and valid_thu and valid_fri
        if not valid:
            log.err('Attempt to upsert timetable without all days periods filled-in.\n\
                    To signify free day, please set start and end of workday to 00:00')
            raise NotAcceptable
        mon_time_f, mon_time_t = datetime.strptime(data['monF'], '%H:%M').time(), datetime.strptime(data['monT'], '%H:%M').time()
        tue_time_f, tue_time_t = datetime.strptime(data['tueF'], '%H:%M').time(), datetime.strptime(data['tueT'], '%H:%M').time()
        wed_time_f, wed_time_t = datetime.strptime(data['wedF'], '%H:%M').time(), datetime.strptime(data['wedT'], '%H:%M').time()
        thu_time_f, thu_time_t = datetime.strptime(data['thuF'], '%H:%M').time(), datetime.strptime(data['thuT'], '%H:%M').time()
        fri_time_f, fri_time_t = datetime.strptime(data['friF'], '%H:%M').time(), datetime.strptime(data['friT'], '%H:%M').time()
        
        monday_v = TimeRange(mon_time_f, mon_time_t)
        tuesday_v = TimeRange(tue_time_f, tue_time_t)
        wednesday_v = TimeRange(wed_time_f, wed_time_t)
        thursday_v = TimeRange(thu_time_f, thu_time_t)
        friday_v = TimeRange(fri_time_f, fri_time_t)

        hours_in_week = (monday_v.len() + tuesday_v.len() +
                         wednesday_v.len() + thursday_v.len() + friday_v.len()) / 60
        validity_v = DateRange(start_date, maxdate)
        pvid_v = data['f_pvs']
        pv = pv_t.filter(pv_t.pvid == pvid_v).filter(
            pv_t.validity.contains(start_date)).first()
        if not pv:
            log.err('Attempt to upsert timetable for user who doesn\'t have valid PV')
            raise NotAcceptable

        valid_pv_uid = pv.uid
        occupancy = pv.occupancy

        if not hours_in_week == 40 * occupancy:
            # Filled in hours are not matching occupancy
            return False

        query = self.db.session().query(pv_t, timetable_t).join(pv_t)
        pv_with_timetable = query.filter(and_(pv_t.pvid == pvid_v), pv_t.validity.contains(
            start_date), timetable_t.validity.contains(start_date)).first()

        if pv_with_timetable:
            pv, timetable = pv_with_timetable
            # Timetable already exist so we end its validty before new timetable is valid
            tt_timeid = timetable.timeid
            cur_tt = timetable_t.filter(timetable_t.timeid == tt_timeid)
            validity_from = cur_tt.one().validity.lower
            new_validity = DateRange(validity_from, start_date)
            cur_tt.update({'validity': new_validity})

        try:
            # Insert new timetable
            timetable_t.insert(monday=monday_v, tuesday=tuesday_v,
                               wednesday=wednesday_v, thursday=thursday_v,
                               friday=friday_v, validity=validity_v,
                               uid_pv=valid_pv_uid)
            self.db.commit()
            return True
        except Exception as e:
            log.err(e)
            self.db.rollback()
            raise InternalServerError

    def get_pvs(self, emp_uid, month, year):
        retval = []

        pv_t = self.db.pv

        pvs = self.db.session \
            .query(pv_t) \
            .filter(pv_t.uid_employee == emp_uid) \
            .filter(pv_t.validity.overlaps(self.month_range(year, month)))

        for pv in pvs.all():
            retval.append({
                'pvid': pv.pvid,
                'department': pv.department
            })

        return retval

    def get_attendance2(self, uid, pvid, month, year, username):
        result = {}
        days = monthlen(year, month)

        time_t = self.db.timetable
        pres_t = self.db.presence
        pv_t   = self.db.pv

        month_range = self.month_range(year, month)
        today = date.today()

        # generate empty month with no presence
        for day in range(1, days + 1):
            result[day] = {
                'day': day,
                'mode': None,
                'timetable': None,
                'date': date(year, month, day),
                'arrival': None,
                'departure': None,
            }

        # fill in actual presence
        presence = pres_t \
            .filter(pres_t.date >= month_range.lower) \
            .filter(pres_t.date <= month_range.upper) \
            .filter(pres_t.uid_employee == uid)

        for p in presence.all():
            result[p.date.day] = {**result[p.date.day], **{
                'mode':  p.presence_mode,
                'arrival': p.arrival,
                'departure': p.departure
            }}

        # add timetable information
        timetables = time_t \
            .join(pv_t) \
            .filter(pv_t.pvid == pvid) \
            .filter(time_t.validity.overlaps(month_range))

        all_timetables = timetables.all()
        for _, day in result.items():
            for timetable in all_timetables:
                weekday = day['date'].weekday()
                if day['date'] in timetable.validity and weekday < 5:
                    day['timetable'] = getattr(timetable, get_dayname(weekday))
                    day['mode'] = day['mode'] or ('absence' if day['timetable'] and day['date'] <= today else None)
                    break

        return result

    def set_acls(self, datadict):
        emp_t = self.db.employee
        for emp_uid in datadict.keys():
            emp_t.filter(emp_t.uid == emp_uid).update({'acl': datadict[emp_uid]})
        self.db.commit()
    
    def get_attendance(self, uid, pvid, period, username):
        WEEKDAYS = ['Pondělí', 'Úterý', 'Středa',
                    'Čtvrtek', 'Pátek', 'Sobota', 'Neděle']
        retval = {'data': []}
        per_year = int(period.split('-')[1])
        per_month = int(period.split('-')[0])
        per_range = monthrange(per_year, per_month)
        per_range_list = [i for i in range(1, per_range[1] + 1)]
        pv_t = self.db.pv
        emp_t = self.db.employee
        pres_t = self.db.presence
        time_t = self.db.timetable
        emp_no = self.get_emp_no(username)
        uid = emp_t.filter(emp_t.emp_no == emp_no).one().uid
        pvs = pv_t.filter(pv_t.pvid == pvid).all()
        uid_pv = ''

        for day in per_range_list:
            curr_time = ''
            day_date = date(per_year, per_month, day)
            weekday = day_date.weekday()
            for pv in pvs:
                # Get pv valid for the date
                if day_date in pv.validity:
                    uid_pv = pv.uid
                    break
            # If there's no valid pv for date, continue to next day
            if not uid_pv:
                continue
            # Get timetable corresponding to the date
            curr_time = time_t.filter(
                time_t.uid_pv == uid_pv, time_t.validity.contains(day_date)).first()
            if curr_time:
                timetable_list = [
                    curr_time.monday,
                    curr_time.tuesday,
                    curr_time.wednesday,
                    curr_time.thursday,
                    curr_time.friday,
                    TimeRange('00:00', '00:00'),
                    TimeRange('00:00', '00:00')
                ]
            else:
                timetable_list = [TimeRange('00:00', '00:00')] * 7
            attend = pres_t.filter(
                and_(pres_t.date == day_date, pres_t.uid_employee == uid)
            ).first()


            if timetable_list[weekday].lower == timetable_list[weekday].upper:
                mode = 'Presence'
            elif attend:
                mode = eng_to_czech(attend.presence_mode)
            else:
                mode = 'Absence'
            if attend:
                retval['data'].append({
                    'day': f'{day}. ',
                    'start': f'{attend.arrival}',
                    'end': f'{attend.departure}',
                    'mode': mode,
                    'stamp': 'Ano' if attend.food_stamp else 'Ne',
                    'timetable': f'{timetable_list[weekday].lower} - {timetable_list[weekday].upper}',
                    'weekday': WEEKDAYS[weekday]
                })
            else:
                retval['data'].append({
                    'day': f'{day}. ',
                    'start': '00:00',
                    'end': '00:00',
                    'mode': mode,
                    'stamp': 'Ne',
                    'timetable': f'{timetable_list[weekday].lower} - {timetable_list[weekday].upper}',
                    'weekday': WEEKDAYS[weekday]
                })
        return retval

    def pvid_to_username(self, pvid):
        emp_no = pvid.split('.')[0]
        emp_t = self.db.employee
        try:
            return emp_t.filter(emp_t.emp_no == emp_no).one().username
        except Exception as e:
            log.err(e)
            log.err(f'User belonging to pvid {pvid} not found.')
            raise NotAcceptable
        return ''

    def is_supervisor(self, user_uid, employee_uid):
        emp_t = self.db.employee

        acl = emp_t.get(user_uid).acl
        user = emp_t.filter(emp_t.uid == employee_uid).one().username

        for dept in self.get_depts(user):
            if str(dept).startswith(acl):
                return True

        return False

    def set_attendance(self, date, employee_uid, start, end, mode):
        pres_t = self.db.presence

        length = datetime.strptime(start, "%H:%M") - datetime.strptime(end, "%H:%M")
        duration = length.seconds / 3600

        # If attendance is longer than 6 hours (or 4 on business trip) employee can haz food stamp
        food_stamp = duration >= 6 or (mode == 'Business trip' and duration >= 4)

        presence = pres_t \
            .filter(pres_t.uid_employee == employee_uid) \
            .filter(pres_t.date == date)

        if presence.first():
            presence.update({
                'arrival': start,
                'departure': end,
                'food_stamp': food_stamp,
                'presence_mode': mode,
            })
        else:
            pres_t.insert(**{
                'arrival': start,
                'departure': end,
                'food_stamp': food_stamp,
                'presence_mode': mode,
                'uid_employee': employee_uid,
                'date': date,
            })

        self.db.commit()

    def get_dept(self, pvid, date):
        pv_t = self.db.pv
        pv = pv_t.filter(and_(pv_t.pvid == pvid, pv_t.validity.contains(date))).first()
        if not pv:
            log.msg(f'PV {pvid} is not valid at {date}. Cannot return department.')
            return
        return pv.department
    
    def get_department(self, dept, month, year):
        retval = {'data': []}
        gen_mode = self.get_dept_mode(dept)
        found = False
        
        emp_t = self.db.employee
        pv_t = self.db.pv
        pres_t = self.db.presence
        timetable_t = self.db.timetable

        per_range = monthrange(year, month)
        query = self.db.session.query(pv_t, emp_t, timetable_t)\
        .join(emp_t)\
        .outerjoin(timetable_t)
        
        month_period = DateRange(date(year, month, 1), date(
            year, month, per_range[1]), '[]')

        pv_with_emp = query \
            .filter(and_(pv_t.validity.overlaps(month_period), timetable_t.validity.overlaps(month_period))) \
            .filter(cast(pv_t.department, sqltypes.String).startswith(dept)).all()
            
        if not pv_with_emp:
            log.msg(f'No valid employees with timetable for period {month_period.lower} - {month_period.upper}')
            return retval
        
        for _, employee, timetable in pv_with_emp:
            # Select pvs in the department itself or subordinate departments
            retval_dict = {
                'name': f'{employee.first_name} {employee.last_name}'}
            for day in range(per_range[1]):
                curr_date = date(year, month, day + 1)
                
                if timetable and curr_date in timetable.validity:
                    timetable_list = [
                        timetable.monday,
                        timetable.tuesday,
                        timetable.wednesday,
                        timetable.thursday,
                        timetable.friday,
                        None,
                        None
                    ]
                else:
                    timetable_list = [None] * 7
                
                presence = pres_t.filter(
                    and_(pres_t.uid_employee ==
                         employee.uid, pres_t.date == curr_date)
                ).first()
                # Weekend
                if curr_date.isoweekday() in [6, 7]:
                    symbol = 'S'
                    
                # This timetable is not valid on this day,
                # it is non working day for the employee or the day is in future
                elif timetable_list[curr_date.weekday()] == None or curr_date > date.today():
                    symbol = '-'
                
                # Employee has valid timetable for the day and should have been in workplace but was not present    
                elif not presence:
                    # Automatically generated presence
                    if gen_mode == 'auto':
                        if timetable_list[curr_date.weekday()].len() >= 6*60:
                            symbol = '/'
                        else:
                            symbol = '/-'
                    else:
                        symbol = 'A'
                        
                # Employee was present or was on vacation, business trip etc.
                else:
                    symbol = eng_to_symbol(
                        presence.presence_mode, presence.food_stamp
                    )
                    # If employee was present for shorter time and presence is automatically generated fill in presence acording timetable
                    if symbol == '/-' and gen_mode == 'auto' and timetable_list[curr_date.weekday()].len() >= 6*60:
                        symbol = '/'
                retval_dict[str(day+1)] = symbol
            # If there exist record for this employee in this month with different timetable - merge them
            for record in retval['data']:
                if record['name'] == f'{employee.first_name} {employee.last_name}':
                    found = True
                    for key in record.keys():
                        if record[key] == '-' and retval_dict[key]:
                            record[key] = retval_dict[key]
            if not found:
                retval['data'].append(retval_dict)
        log.msg(retval)
        return retval

    def init_presence(self, period, source):
        pres_t = self.db.presence
        emp_t = self.db.employee
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
                    and_(pres_t.uid_employee == employee.uid,
                         pres_t.date == date)
                ).first():
                    pres_t.insert(
                        date=date,
                        arrival=arriv.time(),
                        departure=depart.time(),
                        presence_mode=presence_mode,
                        uid_employee=employee.uid,
                        food_stamp=food_stamp
                    )

                else:
                    presence_s = pres_t.filter(
                        and_(pres_t.uid_employee ==
                             employee.uid, pres_t.date == date)
                    )
                    presence = presence_s.one()
                    if presence.arrival > arriv.time():
                        presence_s.update(
                            {'arrival': arriv.time(), 'food_stamp': food_stamp})

                    if presence.departure < depart.time():
                        presence_s.update(
                            {'departure': depart.time(), 'food_stamp': food_stamp})

        self.db.commit()
        
        

    def update_presence(self, date, source):
        pres_t = self.db.presence
        emp_t = self.db.employee
        for employee in emp_t.all():
            arriv = source.get_arrival(date, employee.uid)
            depart = source.get_departure(date, employee.uid)
            if not arriv:
                continue
            length = (depart - arriv).seconds / 3600
            presence_mode = 'Presence'
            food_stamp = length >= 6
            if not pres_t.filter(
                    and_(pres_t.uid_employee == employee.uid, pres_t.date == date)
            ).first():
                pres_t.insert(
                    date=date,
                    arrival=arriv.time(),
                    departure=depart.time(),
                    presence_mode=presence_mode,
                    uid_employee=employee.uid,
                    food_stamp=food_stamp
                )
            else:
                presence_s = pres_t.filter(
                    and_(pres_t.uid_employee == employee.uid, pres_t.date == date)
                )
                presence = presence_s.one()
                if presence.arrival > arriv.time():
                    presence_s.update({
                        'arrival': arriv.time(),
                        'food_stamp': food_stamp
                    })
                if presence.departure < depart.time():
                    presence_s.update({
                        'departure': depart.time(),
                        'food_stamp': food_stamp
                    })

        self.db.commit()

    def sync(self, date, source, src_name, elanor):
        self.check_loop = LoopingCall(
            self.update_presence, date=date, source=source)
        self.check_loop_2 = LoopingCall(self.update_pvs, elanor=elanor)
        log.msg(f'Syncing presence from {src_name}')
        self.check_loop.start(3600)
        log.msg(f'Syncing pvs from elanor')
        self.check_loop_2.start(3600)

    def update_pvs(self, elanor):
        pv_t = self.db.pv
        emp_t = self.db.employee
        departments = []
        for employee in emp_t.all():
            for pv in elanor.get_pvs(employee.emp_no):
                uid_emp = emp_t.filter(
                    emp_t.emp_no == pv['emp_no']).first().uid
                if pv['department'] not in departments:
                    departments.append(pv['department'])
                valid = DateRange(
                    lower=pv['validity'][0], upper=pv['validity'][1], bounds='[]')

                if not pv_t.filter(
                    and_(pv_t.pvid == pv['pvid'],
                         pv_t.occupancy == pv['occupancy'],
                         pv_t.department == pv['department'],
                         pv_t.validity == valid,
                         pv_t.uid_employee == uid_emp)
                ).first():
                    if pv_t.filter(
                        and_(pv_t.pvid == pv['pvid'],
                             pv_t.occupancy == pv['occupancy'],
                             pv_t.department == pv['department'],
                             pv_t.uid_employee == uid_emp)
                    ).first():
                        pv_t.filter(
                            and_(pv_t.pvid == pv['pvid'],
                                 pv_t.occupancy == pv['occupancy'],
                                 pv_t.department == pv['department'],
                                 pv_t.uid_employee == uid_emp
                                 )
                        ).update({'validity': valid})
                    else:
                        pv_t.insert(
                            pvid=pv['pvid'],
                            occupancy=pv['occupancy'],
                            department=pv['department'],
                            validity=valid,
                            uid_employee=uid_emp
                        )      
        self.depts = departments
        self.depts.sort()
        self.db.commit()
