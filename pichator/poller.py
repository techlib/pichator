#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

from datetime import date, datetime
from sqlalchemy import and_
from xml.etree import cElementTree as ET
import re
import requests

__all__ = ['Poller']


def oracle_date_to_date(O_date):
    if O_date and O_date != 'None':
        split_string = O_date.split('-')
        return date(int(split_string[0]), int(split_string[1]), int(split_string[2]))
    else:
        return ""


class Passage:
    def __init__(self, UID, date):
        self.UID = UID
        self.date = date


class Poller:
    def __init__(self, pich_db, elanor_db, ekv_user, ekv_pass):
        self.pich_db = pich_db
        self.elanor_db = elanor_db
        self.ekv_user = ekv_user
        self.ekv_pass = ekv_pass

    def update_presence(self):
        '''
        poll EKV and save processed information to DB
        '''
        passages = []
        last_id = self.pich_db.helpler_variables.one().last_ekv_id
        response = self.get_history(last_id)
        response_tree = ET.parse(response)
        root = response_tree.getroot()
        for record in root.iter('AssetHistoryEntry'):
            pass_date = datetime(record.find('Time').text).date()
            pass_uid = record.find('UID').text
            pass_id = int(record.find('ID').text)
            if not '_' in pass_uid:
                last_id = pass_id
                passages.append(Passage(pass_uid, pass_date))
        self.pich_db.helpler_variables.update().values(last_ekv_id=last_id)
        missing = self.pich_db.session.query(self.pich_db.pv, self.pich_db.presence, self.pich_db.employee).join(
            self.pich_db.presence).join(self.pich_db.employee).filter_by(and_(Presence=False)).fetchall()
        for pv in missing:
            for passage in passages:
                if pv.ekv_id == passage.UID:
                    day = datetime(passage.date).weekday()
                    timetables = self.pich_db.session.query(self.pich_db.employee, self.pich_db.pv, self.pich_db.timetable).join(
                        self.pich_db.pv).join(self.pich_db.timetable).filter_by(pv_fk=pv.pvid).fetchall()
                    for timetable in timetables:
                        timetable_days = [timetable.MONDAY, timetable.TUESDAY,
                                          timetable.WEDENSDAY, timetable.THURSDAY, timetable.FRIDAY, timetable.SATURDAY, timetable.SUNDAY]
                        shift = timetable_days[day]
                        if passage.date in timetable.validity:
                            self.pich_db.presence.filter_by(and_(PVID_PV=timetable.pvid, Date=passage.date)).update(
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

    def get_history(self, start_ID):
        url = 'https://fides1.ntkcz.cz/AssetWebService.asmx'

        headers = {'Content-Type': 'text/xml; charset=utf-8',
                   'Authorization': f'Basic {self.ekv_user} {self.ekv_pass}', 'SOAPAction': 'http://fides.cz/getHistoryEntries'}
        body = f"""
                <?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                  <soap:Body>
                    <getHistoryEntries xmlns="http://fides.cz/">
                      <firstHistoryId>{start_ID}</firstHistoryId>
                      <maxCount>1000</maxCount>
                    </getHistoryEntries>
                  </soap:Body>
                </soap:Envelope>
                """

        response = requests.post(url, data=body,  headers=headers)
        if response.code == 200:
            return response.content
        else:
            raise Exception(
                f'Asset server responded with code: {response.code} and says: {response.text}')

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
