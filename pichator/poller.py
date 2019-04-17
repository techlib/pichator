#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

from datetime import date, datetime
from sqlalchemy import and_
from xml.etree import cElementTree as ET
import requests

__all__ = ['Poller']
class Passage:
    def __init__(self, ID, date):
        self.ID = ID
        self.date = date

class Poller:
    def __init__(self, pich_db, ekv_user, ekv_pass):
        self.pich_db = pich_db
        self.ekv_user = ekv_user
        self.ekv_pass = ekv_pass

    def update_presence(self):
        '''
        poll EKV and save processed information to DB
        '''
        today = date.today()
        passages = []
        last_ID = self.pich_db.helpler_variables.one().last_ekv_id
        response = self.get_history(last_ID)
        response_tree = ET.parse(response)
        root = response_tree.getroot()
        max_id = 0
        for record in root.iter('AssetHistoryEntry'):
            pass_date = datetime(record.find('Time').text).date()
            pass_ID = record.find('UID').text
            pass_UID = int(record.find('ID').text)
            if today == pass_date and not '_' in pass_ID:
                max_id = max([max_id, pass_UID])
                passages.append(Passage(pass_ID, pass_date))
        self.pich_db.helpler_variables.update().values(last_ekv_id = max_id)
        missing = self.pich_db.session.query(self.pich_db.employee).join(
            self.pich_db.presence).filter_by(and_(Date=today, Presence=False)).fetchall()
        for employee in missing:
            for passage in passages:
                if employee.EKV_ID == passage.ID:
                    day = datetime(passage.date).weekday()
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
    
    def get_history(self, start_ID):
        url = 'https://fides1.ntkcz.cz/AssetWebService.asmx'
        
        headers = {'Content-Type': 'text/xml; charset=utf-8', 'Authorization': f'Basic {self.ekv_user} {self.ekv_pass}', 'SOAPAction': 'http://fides.cz/getHistoryEntries'}
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
        
        response = requests.post(url, data = body,  headers = headers)
        if response.code == 200:
            return response.content
        else:
            raise Exception(f'Asset server responded with code: {response.code} and says: {response.text}')