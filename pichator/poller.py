#!/usr/bin/python3

from datetime import date, datetime
from sqlalchemy import and_


class Poller:
    def __init__(self, pich_db):
        self.pich_db = pich_db

    def update_presence(self):
        '''
        poll EKV and save processed information to DB
        '''
        today = date.today()
        passages = []  # filter only results from today
        missing = self.pich_db.session.query(self.pich_db.employee).join(
            self.pich_db.presence).filter_by(and_(Date=today, Presence=False)).fetchall()
        for employee in missing:
            for passage in passages:
                if employee.EKV_ID == passage.ID:
                    day = datetime(passage.time).weekday()
                    timetables = self.pich_db.session.query(self.pich_db.employee, self.pich_db.pv, self.pich_db.timetable).join(
                        self.pich_db.pv).join(self.pich_db.timetable).filter_by(Empid=employee.EMPID).fetchall()
                    for timetable in timetables:
                        timetable_days = [timetable.MONDAY, timetable.TUESDAY,
                                          timetable.WEDENSDAY, timetable.THURSDAY, timetable.FRIDAY, timetable.SATURDAY, timetable.SUNDAY]
                        shift = timetable_days[day]
                        if today in timetable.validity:
                            self.pich_db.presence.filter_by(and_(PVID_PV=timetable.pvid, Date=today)).update(
                            ).values(Presence=True, Presence_mode='Presence' if shift >= 6 else 'Presence-')
        self.pich_db.commit()

    def init_presence(self):
        employees = self.pich_db.employee.all()
        today = date.today()
        for employee in employees:
            PVs = self.pich_db.session.query(self.pich_db.employee, self.pich_db.pv).join(
                self.pich_db.pv).filter_by(Empid=employee.EMPID).fetchall()
            validPVs = [i for i in PVs if today in i.Validity]
            for PV in validPVs:
                if not self.pich_db.presence.filter_by(and_(Date=today, PVID_PV=PV.PVID)).first():
                    self.pich_db.presence.insert().values(Date=today, PVID_PV=PV.PVID,
                                                          Presence=False, Presence_mode='Absence')
        self.pich_db.commit()
