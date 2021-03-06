#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

__all__ = ['Ekv']

from datetime import datetime
from twisted.python import log

class Ekv:
    def __init__(self, db):
        self.db = db

    def get_arrival(self, date, ID):
        ms_date = date.strftime("%Y-%m-%d")
        query = '''
                SELECT MIN([Time])
                FROM [ASSET].[dbo].[EFI_EKV_ValidPass]
                WHERE [AssetUID]='I1.{}'
                AND [Time] between '{} 00:00:00' and '{} 23:59:59'
                '''.format(ID, ms_date, ms_date)
        return self.db.execute(query).fetchall()[0][0]

    def get_departure(self, date, ID):
        ms_date = date.strftime("%Y-%m-%d")
        query = '''
                SELECT MAX([Time])
                FROM [ASSET].[dbo].[EFI_EKV_ValidPass]
                WHERE [AssetUID]='I1.{}'
                AND [Time] between '{} 00:00:00' and '{} 23:59:59'
                '''.format(ID, ms_date, ms_date)
        return self.db.execute(query).fetchall()[0][0]


