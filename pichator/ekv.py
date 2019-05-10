#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-

__all__ = ['Ekv']


class Ekv:
    def __init__(self, db):
        self.db = db

    def get_arrival(self, date, ID):
        ms_date = date.strftime("%Y-%m-%d")
        query = f'''
                SELECT MIN([Time])
                FROM [ASSET].[dbo].[EFI_EKV_ValidPass]
                WHERE [AssetUID]='I1.{ID}'
                AND [Time] between '{ms_date} 00:00:00' and '{ms_date} 23:59:59'
                '''
        try:
            return self.db.execute(query).one()[0]
        except:
            self.db.connect()
            return self.db.execute(query).one()[0]

    def get_departure(self, date, ID):
        ms_date = date.strftime("%Y-%m-%d")
        query = f'''
                SELECT MAX([Time])
                FROM [ASSET].[dbo].[EFI_EKV_ValidPass]
                WHERE [AssetUID]='I1.{ID}'
                AND [Time] between '{ms_date} 00:00:00' and '{ms_date} 23:59:59'
                '''
        try:
            return self.db.execute(query).one()[0]
        except:
            self.db.connect()
            return self.db.execute(query).one()[0]
