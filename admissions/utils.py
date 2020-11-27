import numpy as np
import re
import pandas
import scipy.interpolate
from scipy.optimize import curve_fit
import os,glob
import country_converter as coco
from fuzzywuzzy import fuzz, process
from shutil import copyfile

class utils:
    def __init__(
        self,
        rankfile = 'university_rankings.xlsx',
        aliasfile = 'university_aliases.xlsx'
    ):

        self.rankfile = rankfile
        self.aliasfile = aliasfile

        copyfile(rankfile,rankfile+".bck")
        copyfile(aliasfile,aliasfile+".bck")
        self.readFiles()

    def readFiles(self):
        tmp = pandas.ExcelFile(self.rankfile)
        self.lookup = tmp.parse('lookup')
        tmp.close()
        tmp = pandas.ExcelFile(self.aliasfile)
        self.aliases = tmp.parse('aliases')
        self.ignore = tmp.parse('ignore')
        tmp.close()

    def __del__(self):
        self.updateFiles()

    def matchschool(self,name,country):
        #check ignores first
        if (name in self.ignore['Name'].values) and \
            (self.ignore.loc[self.ignore.Name == name,'Country'].values[0] == country):
                return ("skip", )

        #try main list
        if (name in self.lookup['Name'].values) and \
            (self.lookup.loc[self.lookup.Name == name,'Country'].values[0] == country):
                return name

        #try aliases
        if name in self.aliases['Alias'].values:
            return self.aliases.loc[self.aliases['Alias'] == name,'Standard Name'].values[0]

        #try fuzzy match against main list
        res = process.extractOne(name,self.lookup.loc[self.lookup['Country'] == country,'Name'].values)
        if res[1] == 100:
            self.updateAliases(name,res[0])
            return res[0]
        else:
            instr = input("I think {} in {} is {}. [accept]/enter alias/[r]ename/[n]ew/[s]kip ".format(name, country, res[0]))
            if instr:
                if instr == 'r':
                    newname = input("Official Name: ")
                    return "rename",newname
                elif instr == 'n':
                    newname = input("Official Name: [accept]")
                    if not(newname):
                        newname = name
                    newrank = input("Rank: [200] ")
                    if not(newrank):
                        newrank = 200
                    self.updateRankings(newname,newrank,country)
                    if newname != name:
                        self.updateAliases(name,newname)
                    return newname
                elif instr == 's':
                    self.updateIgnores(name,country)
                    return ("skip", )
                else:
                    self.updateAliases(name,instr)
                    return instr
            else:
                self.updateAliases(name,res[0])
                return res[0]


    def updateAliases(self,alias,standard_name):
        self.aliases = self.aliases.append(pandas.DataFrame({'Alias':[alias],'Standard Name':[standard_name]}))
        self.aliases = self.aliases.sort_values(by=['Standard Name']).reset_index(drop=True)

    def updateIgnores(self,name,country):
        self.ignore = self.ignore.append(pandas.DataFrame({'Name':[name],'Country':[country]})).reset_index(drop=True)

    def updateRankings(self,name,rank,country):
        self.lookup = self.lookup.append(pandas.DataFrame({'Name':[name],'Rank':[rank],'Country':[country]}))
        self.lookup = self.lookup.sort_values(by=['Rank']).reset_index(drop=True)

    def updateFiles(self):

        ew = pandas.ExcelWriter(self.rankfile,options={'encoding':'utf-8'})
        self.lookup.to_excel(ew,sheet_name='lookup',index=False)
        ew.save()
        ew.close()

        ew = pandas.ExcelWriter(self.aliasfile,options={'encoding':'utf-8'})
        self.aliases.to_excel(ew,sheet_name='aliases',index=False)
        self.ignore.to_excel(ew,sheet_name='ignore',index=False)
        ew.save()
        ew.close()



