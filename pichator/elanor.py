#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

from twisted.python import log
from datetime import date
import xml.etree.ElementTree as ET

__all__ = ['Elanor']


def oracle_date_to_date(O_date):
    if O_date and O_date != 'None':
        split_string = O_date.split('-')
        return date(int(split_string[0]), int(split_string[1]), int(split_string[2]))
    else:
        return ""


class Elanor:
    def __init__(self, db):
        self.elanor_db = db

    def get_pvs(self, emp_no):
        query_text = f"select * from pv where oscpv like '{emp_no}.%'"
        pvs = self.elanor_db.execute(query_text)
        retval = []

        for pv in pvs:
            xml = ET.fromstring(pv.dalsi1_xml)

            for pv_item in xml.findall('.//uv_sjed_tyd'):
                date_from = oracle_date_to_date(pv_item.attrib['datum_od'])
                date_to = oracle_date_to_date(pv_item.attrib['datum_do'])
                occupancy = round(float(pv_item.attrib['hodnota']) / 40, 2)

                retval.append({
                    'pvid': pv.oscpv,
                    'occupancy': occupancy,
                    'department': pv.kod,
                    'validity': (max(oracle_date_to_date(pv.dat_nast), date_from),
                                 min(oracle_date_to_date(pv.dat_ukon), date_to)),
                    'emp_no': emp_no
                })

        return retval
