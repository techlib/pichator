#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

from datetime import date, datetime
from sqlalchemy import and_
from xml.etree import cElementTree as ET
import re
import requests

__all__ = ['Poller']


def oracle_date_to_date(o_date):
    try:
        return date(*[int(i) for i in o_date.split('-')])
    except ValueError:
        return ''

class Poller:
    def __init__(self, pich_db, elanor_db, ekv_user, ekv_pass):
        self.pich_db = pich_db
        self.elanor_db = elanor_db
        self.ekv_user = ekv_user
        self.ekv_pass = ekv_pass

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

    def sync_pv(self):
        pvs = self.elanor_db.pv.fetch_all()
        for pv in pvs:
            regex_occupancy = r"<uv_sjed_tyd hodnota=\"([0-9]+\.[0-9]+)\" id=\"[0-9]+\" datum_od=\"([0-9]+-[0-9]+-[0-9]+)\" datum_do=\"([0-9]+-[0-9]+-[0-9]+)\" "
            matches = re.finditer(regex_occupancy, pv.dalsi1_xml, re.MULTILINE)
            for matchNum, match in enumerate(matches):
                matchNum = matchNum + 1
                if not self.pich_db.pv.filter_by(and_(pvid=pv.oscpv, occupancy=round(float(match.group(1))/40, 2), department=pv.kod, validity=(oracle_date_to_date(match.group(2)), oracle_date_to_date(match.group(3))))).first():
                    self.pich_db.pv.insert().values(pvid=pv.oscpv, emp_no_employee=pv.oscpv//1,
                                                    occupancy=round(float(match.group(1))/40, 2), department=pv.kod, validity=(oracle_date_to_date(match.group(2)), oracle_date_to_date(match.group(3))))
