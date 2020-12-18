import numpy as np
import re
import pandas
import scipy.interpolate
from scipy.optimize import curve_fit
import os, glob
import country_converter as coco
from fuzzywuzzy import fuzz, process
from shutil import copyfile


class utils:
    def __init__(
        self,
        rankfile="university_rankings.xlsx",
        aliasfile="university_aliases.xlsx",
        gradefile="grade_data.xlsx",
        utilfile="utils2021.xlsx",
    ):

        self.rankfile = rankfile
        self.aliasfile = aliasfile
        self.gradefile = gradefile
        self.utilfile = utilfile

        self.rankup = False
        self.aliasup = False
        self.gradeup = False
        self.utilup = False

        copyfile(rankfile, rankfile + ".bck")
        copyfile(aliasfile, aliasfile + ".bck")
        copyfile(gradefile, gradefile + ".bck")
        copyfile(utilfile, utilfile + ".bck")
        self.readFiles()

        # generate grade interpolants
        tmp = pandas.ExcelFile(self.gradefile)
        grades = tmp.parse("grades")
        tmp.close()

        interps = []
        for row in grades.iterrows():
            xgpa = np.array(row[1]["SchoolGPA"].split("/")).astype(float)
            ygpa = np.array(row[1]["4ptGPA"].split("/")).astype(float)
            if xgpa.min() != 0:
                xgpa = np.hstack([xgpa, 0])
                ygpa = np.hstack([ygpa, 0])
            interps.append(scipy.interpolate.interp1d(xgpa, ygpa, kind="linear"))
        grades["Interp"] = interps
        self.grades = grades

        self.cc = coco.CountryConverter()

    def readFiles(self):
        tmp = pandas.ExcelFile(self.rankfile)
        self.lookup = tmp.parse("lookup")
        tmp.close()
        tmp = pandas.ExcelFile(self.aliasfile)
        self.aliases = tmp.parse("aliases")
        self.ignore = tmp.parse("ignore")
        tmp.close()
        tmp = pandas.ExcelFile(self.utilfile)
        self.renames = tmp.parse("rename")
        self.schoolmatches = tmp.parse("schools")
        tmp.close()

    def __del__(self):
        self.updateFiles()

    def matchschool(self, name, country):
        # check ignores first
        if (name in self.ignore["Name"].values) and (
            self.ignore.loc[self.ignore.Name == name, "Country"].values[0] == country
        ):
            return ("skip",)

        # try main list
        if (name in self.lookup["Name"].values) and (
            self.lookup.loc[self.lookup.Name == name, "Country"].values[0] == country
        ):
            return name

        # try aliases
        if name in self.aliases["Alias"].values:
            return self.aliases.loc[
                self.aliases["Alias"] == name, "Standard Name"
            ].values[0]

        if country not in self.lookup["Country"].values:
            instr = input(
                "{0}: I don't know any schools in {1}. [new]/[s]kip ".format(
                    name, country
                )
            )
            if instr:
                self.updateIgnores(name, country)
                return ("skip",)
            else:
                newname = input("Official Name: [{}] ".format(name))
                if not (newname):
                    newname = name
                newrank = input("Rank: [200] ")
                if not (newrank):
                    newrank = 200
                self.updateRankings(newname, newrank, country)
                return newname

        # try fuzzy match against main list
        res = process.extractOne(
            name, self.lookup.loc[self.lookup["Country"] == country, "Name"].values
        )
        if res[1] == 100:
            self.updateAliases(name, res[0])
            return res[0]
        else:
            instr = input(
                "I think {} in {} is {}. [accept]/enter alias/[r]ename/[n]ew/[s]kip ".format(
                    name, country, res[0]
                )
            )
            if instr:
                if instr == "r":
                    newname = input("Official Name: ")
                    if (newname not in self.lookup["Name"].values):
                        print("This is a new school.")
                        newrank = input("Rank: [200] ")
                        if not (newrank):
                            newrank = 200
                        self.updateRankings(newname, int(newrank), country)
                    return "rename", newname
                elif instr == "n":
                    newname = input("Official Name: [accept]")
                    if not (newname):
                        newname = name
                    newrank = input("Rank: [200] ")
                    if not (newrank):
                        newrank = 200
                    self.updateRankings(newname, int(newrank), country)
                    if newname != name:
                        self.updateAliases(name, newname)
                    return newname
                elif instr == "s":
                    self.updateIgnores(name, country)
                    return ("skip",)
                else:
                    if (instr not in self.lookup["Name"].values):
                        print("I don't know the school you just entered.  Trying again.")
                        return self.matchschool(name, country)
                    self.updateAliases(name, instr)
                    return instr
            else:
                self.updateAliases(name, res[0])
                return res[0]

    def updateAliases(self, alias, standard_name):
        self.aliasup = True
        self.aliases = self.aliases.append(
            pandas.DataFrame({"Alias": [alias], "Standard Name": [standard_name]})
        )
        self.aliases = self.aliases.sort_values(by=["Standard Name"]).reset_index(
            drop=True
        )

    def updateIgnores(self, name, country):
        self.aliasup = True
        self.ignore = self.ignore.append(
            pandas.DataFrame({"Name": [name], "Country": [country]})
        ).reset_index(drop=True)

    def updateRankings(self, name, rank, country):
        self.rankup = True
        self.lookup = self.lookup.append(
            pandas.DataFrame({"Name": [name], "Rank": [rank], "Country": [country]})
        )
        self.lookup = self.lookup.sort_values(by=["Rank"]).reset_index(drop=True)

    def updateFiles(self):

        if self.rankup:
            ew = pandas.ExcelWriter(self.rankfile, options={"encoding": "utf-8"})
            self.lookup.to_excel(ew, sheet_name="lookup", index=False)
            ew.save()
            ew.close()

        if self.aliasup:
            ew = pandas.ExcelWriter(self.aliasfile, options={"encoding": "utf-8"})
            self.aliases.to_excel(ew, sheet_name="aliases", index=False)
            self.ignore.to_excel(ew, sheet_name="ignore", index=False)
            ew.save()
            ew.close()

        if self.gradeup:
            grades = self.grades.copy()
            grades = grades.drop(["Interp"], axis=1)
            ew = pandas.ExcelWriter(self.gradefile, options={"encoding": "utf-8"})
            grades.to_excel(ew, sheet_name="grades", index=False)
            ew.save()
            ew.close()

        if self.utilup:
            renames = self.renames.copy()
            schoolmatches = self.schoolmatches.copy()
            ew = pandas.ExcelWriter(self.utilfile, options={"encoding": "utf-8"})
            renames.to_excel(ew, sheet_name="rename", index=False)
            schoolmatches.to_excel(ew, sheet_name="schools", index=False)
            ew.save()
            ew.close()

        # flush all the update bools
        self.rankup = False
        self.aliasup = False
        self.gradeup = False
        self.utilup = False

    def calc4ptGPA(self, school, country, gpascale, gpa):
        """Convert GPA to 4 point scale"""

        if gpascale == 4.0:
            return gpa

        if gpascale == 4.3:
            if gpa > 4.0:
                return 4.0
            else:
                return gpa

        # first try to match the school
        if (
            (school in self.grades["Name"].values)
            and (
                self.grades.loc[self.grades.Name == school, "Country"].values[0]
                == country
            )
            and (
                self.grades.loc[self.grades.Name == school, "GPAScale"].values[0]
                == gpascale
            )
        ):
            return self.grades.loc[self.grades.Name == school, "Interp"].values[0](gpa)

        # if that doesn't work, lets try to match the country
        if (
            (self.grades["Name"] == "DEFAULT {}".format(country))
            & (self.grades["GPAScale"] == gpascale)
        ).any():
            return self.grades.loc[
                (self.grades["Name"] == "DEFAULT {}".format(country))
                & (self.grades["GPAScale"] == gpascale),
                "Interp",
            ].values[0](gpa)

        # if we're here, nothing worked, so lets ask for help
        print(
            "No matches for {} in {} with {} GPA scale.".format(
                school, country, gpascale
            )
        )
        newname = input("New Entry:  [DEFAULT country]/[s] School Name ")
        if newname:
            newname = school
        else:
            newname = "DEFAULT {}".format(country)
        xgpastr = input("New Entry GPAs: gpascale/.../min ")
        ygpastr = input("New Entry 4pt GPAs: 4.0/.../min ")
        xgpa = np.array(xgpastr.split("/")).astype(float)
        ygpa = np.array(ygpastr.split("/")).astype(float)
        if xgpa.min() != 0:
            xgpa = np.hstack([xgpa, 0])
            ygpa = np.hstack([ygpa, 0])

        self.grades = self.grades.append(
            pandas.DataFrame(
                {
                    "Name": [newname],
                    "Country": [country],
                    "GPAScale": [gpascale],
                    "SchoolGPA": [xgpastr],
                    "4ptGPA": [ygpastr],
                    "Interp": [scipy.interpolate.interp1d(xgpa, ygpa, kind="linear")],
                }
            ),
            ignore_index=True,
        )
        self.gradeup = True

        return self.grades.loc[self.grades.Name == newname, "Interp"].values[0](gpa)

    def assignschools(self, data):
        """Determine undergrad and grad institutions for all students

        data - main data table
        """

        for row in data.itertuples():
            fullname = row.Full_Name
            if fullname in self.schoolmatches["Full_Name"].values:
                continue

            print("\n")
            print(fullname)

            schools = []
            degreetypes = []
            countries = []
            earneddegs = []
            snums = []

            for j in range(1, 4):
                s = row.__getattribute__("School_Name_{}".format(j))
                if s == s:
                    country = self.cc.convert(
                        names=row.__getattribute__("School_Country_{}".format(j)),
                        to="name_short",
                    )
                    res = self.matchschool(s, country)

                    if isinstance(res, tuple):
                        if res[0] == "skip":
                            continue
                        elif res[0] == "rename":
                            self.renames = self.renames.append(
                                pandas.DataFrame(
                                    {
                                        "Full_Name": [fullname],
                                        "Field": ["School_Name_{}".format(j)],
                                        "Value": [res[1]],
                                    }
                                ),
                                ignore_index=True,
                            )
                            self.utilup = True
                            n = res[1]
                    else:
                        n = res

                    schools.append(n)
                    countries.append(country)
                    tmp = row.__getattribute__("Degree_level_School_{}".format(j))
                    if tmp != tmp:
                        tmp = ""
                    degreetypes.append(tmp)
                    earneddegs.append(
                        row.__getattribute__("Earned_a_degree_School_{}".format(j))
                    )
                    snums.append(j)

            hasgr = False
            if len(schools) == 1:
                ug = 0
                gr = None
            else:
                inds = np.where(["under" in d.lower() for d in degreetypes])[0]
                if len(inds) != 1:
                    for kk in range(len(schools)):
                        print(
                            "{}: {}, {}, Earned: {}".format(
                                kk, schools[kk], degreetypes[kk], earneddegs[kk]
                            )
                        )
                    ug = int(input("Pick UNDERgrad school index (from 0) "))
                else:
                    ug = inds[0]

                inds = np.where(
                    [
                        ("under" not in d.lower()) | ("combined" in d.lower())
                        for d in degreetypes
                    ]
                )[0]
                if len(inds) == 0:
                    pass
                elif len(inds) > 1:
                    for kk in range(len(schools)):
                        print(
                            "{}: {}, {}, Earned: {}".format(
                                kk, schools[kk], degreetypes[kk], earneddegs[kk]
                            )
                        )
                    gr = input("Pick GRAD school index (from 0) or enter for none ")
                    if gr:
                        gr = int(gr)
                        hasgr = True
                else:
                    gr = inds[0]
                    hasgr = True

            if hasgr:
                self.schoolmatches = self.schoolmatches.append(
                    pandas.DataFrame(
                        {
                            "Full_Name": [fullname],
                            "UG_School": [snums[ug]],
                            "GR_School": [snums[gr]],
                        }
                    ),
                    ignore_index=True,
                )
                self.utilup = True
            else:
                self.schoolmatches = self.schoolmatches.append(
                    pandas.DataFrame(
                        {
                            "Full_Name": [fullname],
                            "UG_School": [snums[ug]],
                            "GR_School": [None],
                        }
                    ),
                    ignore_index=True,
                )
                self.utilup = True

        return data

    def readData(self, fname):
        data = pandas.read_csv(fname, header=[0, 1])
        data.columns = data.columns.droplevel(-1)
        data = data.drop(
            columns=[
                "Assigned",
                "In Progress",
                "Completed",
                "Tags",
                "Field Admission Decision",
            ],
            errors="ignore",
        )

        # retain only our concentrations
        # concentrations = np.unique(np.hstack([data['Concentration 1'][data['Concentration 1'].notnull()].unique(),data['Concentration 2'][data['Concentration 2'].notnull()].unique(),data['Concentration 3'][data['Concentration 3'].notnull()].unique()]))
        # ourconcs = ['Aerodynamics','Aerospace Systems','Dynamics and Control','Dynamics and Space Mechanics','Propulsion']
        # inds = (data['Concentration 1'] == ourconcs[0]) | (data['Concentration 2'] == ourconcs[0]) | (data['Concentration 3'] == ourconcs[0])
        # for j in range(1,len(ourconcs)):
        #    inds = inds | ((data['Concentration 1'] == ourconcs[j]) | (data['Concentration 2'] == ourconcs[j]) | (data['Concentration 3'] == ourconcs[j]))
        #
        # data = data.loc[inds]
        # data = data.reset_index(drop=True)

        # make sure that numeric cols remain numeric
        numcols = [
            "Verbal GRE (Unofficial)",
            "Quantitative GRE (Unofficial)",
            "GRE Analytical Writing GRE (Unofficial)",
        ]
        for j in range(1, 4):
            numcols.append("GPA (School {})".format(j))
            numcols.append("GPA Scale (School {})".format(j))

        for col in numcols:
            data[col] = data[col].astype(float)

        # add some new columns
        data["UGrad School"] = None
        data["UGrad GPA"] = None
        data["Grad School"] = None
        data["Grad GPA"] = None
        data["UGrad GPA 4pt"] = None
        data["Grad GPA 4pt"] = None
        data["UGrad GPA Norm"] = None
        data["Grad GPA Norm"] = None
        data["UGrad Rank"] = None
        data["Grad Rank"] = None
        data["URM"] = None
        data["Total"] = None

        # remove all column name spaces and special chars
        data.columns = data.columns.str.strip()
        data.columns = data.columns.str.replace(" ", "_")
        data.columns = data.columns.str.replace("?", "")
        data.columns = data.columns.str.replace("(", "")
        data.columns = data.columns.str.replace(")", "")
        data.columns = data.columns.str.replace('"', "")

        # add full name col
        fullname = [
            "{}, {}".format(row.Last_Name, row.First_Name) for row in data.itertuples()
        ]
        data["Full_Name"] = fullname

        # overwrite all fields as needed
        for row in self.renames.itertuples():
            data.loc[data["Full_Name"] == row.Full_Name, row.Field] = row.Value

        return data
