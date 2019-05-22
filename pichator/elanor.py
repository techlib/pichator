#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

from twisted.python import log
from datetime import date
import re

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
            regex_occupancy = r"<uv_sjed_tyd hodnota=\"([0-9]+\.[0-9]+)\" id=\"[0-9]+\" datum_od=\"([0-9]+-[0-9]+-[0-9]+)\" datum_do=\"([0-9]+-[0-9]+-[0-9]+)\" "
            matches = re.finditer(regex_occupancy, pv.dalsi1_xml, re.MULTILINE)
            for matchNum, match in enumerate(matches):
                matchNum = matchNum + 1
                retval.append({'pvid': pv.oscpv, 'occupancy': round(float(match.group(1))/40, 2), 'department': pv.kod, 'validity': (max(
                    oracle_date_to_date(pv.dat_nast), oracle_date_to_date(match.group(2))), min(oracle_date_to_date(pv.dat_ukon), oracle_date_to_date(match.group(3)))), 'emp_no': pv.oscpv.split('.')[0]})
        return retval
