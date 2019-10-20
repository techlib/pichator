#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

from twisted.python import log
from datetime import date, datetime
import xml.etree.ElementTree as ET

__all__ = ['Elanor']


def parse_date(date_str):
    return datetime.strptime(date_str, '%Y-%m-%d').date()


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
                date_from = parse_date(pv_item.attrib['datum_od'])
                date_to = parse_date(pv_item.attrib['datum_do'])
                occupancy = round(float(pv_item.attrib['hodnota']) / 40, 2)

                dat_nast = parse_date(pv.dat_nast)
                dat_ukon = parse_date(pv.dat_ukon)

                item = {
                    'pvid': pv.oscpv,
                    'occupancy': occupancy,
                    'department': pv.kod,
                    'validity': (max(dat_nast, date_from),
                                 min(dat_ukon, date_to)),
                    'emp_no': emp_no
                }

                if item['validity'][0] > item['validity'][1]:
                    log.msg('Ignoring {} (valid_from:{} < valid_to:{})'.format(
                        pv.oscpv, item['validity'][0], item['validity'][1]))
                    continue

                retval.append(item)

        return retval

