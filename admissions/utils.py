import numpy as np
import pandas
import scipy.interpolate
from scipy.optimize import curve_fit
from scipy.stats import norm
import country_converter as coco
from fuzzywuzzy import process
from shutil import copyfile
from admissions.rankings import tfit


class utils:
    def __init__(
        self,
        utilfile,
        rankfile="university_rankings.xlsx",
        aliasfile="university_aliases.xlsx",
        gradefile="grade_data.xlsx",
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
        tmp = pandas.ExcelFile(self.gradefile, engine="openpyxl")
        grades = tmp.parse("grades")
        tmp.close()

        interps = []
        for row in grades.iterrows():
            xgpa = np.array(row[1]["SchoolGPA"].split("/")).astype(float)
            ygpa = np.array(row[1]["4ptGPA"].split("/")).astype(float)
            if (xgpa.min() != 0) & (ygpa.min() != 0):
                xgpa = np.hstack([xgpa, 0])
                ygpa = np.hstack([ygpa, 0])
            interps.append(scipy.interpolate.interp1d(xgpa, ygpa, kind="linear"))
        grades["Interp"] = interps
        self.grades = grades

        self.cc = coco.CountryConverter()

        # create fit function
        x = np.array([9, 50])
        y = np.array([3.3, 3.5])
        ftrank, _ = curve_fit(tfit, x, y, [-0.5, 2.5])

        self.rankfit = lambda x: tfit(x, ftrank[0], ftrank[1])

    def readFiles(self):
        tmp = pandas.ExcelFile(self.rankfile, engine="openpyxl")
        self.lookup = tmp.parse("lookup")
        tmp.close()
        tmp = pandas.ExcelFile(self.aliasfile, engine="openpyxl")
        self.aliases = tmp.parse("aliases")
        self.ignore = tmp.parse("ignore")
        tmp.close()
        tmp = pandas.ExcelFile(self.utilfile, engine="openpyxl")
        self.renames = tmp.parse("rename")
        self.schoolmatches = tmp.parse("schools")
        tmp.close()

    def __del__(self):
        self.updateFiles()

    def isknownschool(self, name):
        # try main list
        if name in self.lookup["Name"].values:
            return True
        if name in self.aliases["Alias"].values:
            return True

        return False

    def matchschool(self, name, country, city=None):
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
            if city:
                qstr = "I think {} in {}, {} is {}. [accept]/enter alias/[r]ename/[n]ew/[s]kip ".format(
                    name, city, country, res[0]
                )

            else:
                qstr = "I think {} in {} is {}. [accept]/enter alias/[r]ename/[n]ew/[s]kip ".format(
                    name, country, res[0]
                )

            instr = input(qstr)
            if instr:
                if instr == "r":
                    newname = input("Official Name: ")
                    if newname not in self.lookup["Name"].values:
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
                    if instr not in self.lookup["Name"].values:
                        print(
                            "I don't know the school you just entered.  Trying again."
                        )
                        return self.matchschool(name, country, city=city)
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
            with pandas.ExcelWriter(self.rankfile) as ew:
                self.lookup.to_excel(ew, sheet_name="lookup", index=False)

        if self.aliasup:
            with pandas.ExcelWriter(self.aliasfile) as ew:
                self.aliases.to_excel(ew, sheet_name="aliases", index=False)
                self.ignore.to_excel(ew, sheet_name="ignore", index=False)

        if self.gradeup:
            grades = self.grades.copy()
            grades = grades.drop(["Interp"], axis=1)
            with pandas.ExcelWriter(self.gradefile) as ew:
                grades.to_excel(ew, sheet_name="grades", index=False)

        if self.utilup:
            renames = self.renames.copy()
            schoolmatches = self.schoolmatches.copy()
            schoolmatches = schoolmatches.sort_values(by=["Full_Name"]).reset_index(
                drop=True
            )
            with pandas.ExcelWriter(self.utilfile) as ew:
                renames.to_excel(ew, sheet_name="rename", index=False)
                schoolmatches.to_excel(ew, sheet_name="schools", index=False)

        # flush all the update bools
        self.rankup = False
        self.aliasup = False
        self.gradeup = False
        self.utilup = False

    def calc4ptGPA(self, school, country, gpascale, gpa):
        """Convert GPA to 4 point scale"""

        if gpascale == 4.0:
            return gpa

        if (gpascale == 4.3) | (gpascale == 4.33) | (gpascale == 4.2):
            if gpa > 4.0:
                return 4.0
            else:
                return gpa

        # first try to match the school
        mtch = (
            (self.grades.Name == school)
            & (self.grades.Country == country)
            & (self.grades.GPAScale == gpascale)
        )
        if mtch.any():
            return self.grades.loc[mtch, "Interp"].values[0](gpa)

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
        action = input("What would you like to do? [manual entry]/[n]ew ")
        if action:
            newname = input("New Entry:  [DEFAULT country]/[s] School Name ")
            if newname:
                newname = school
            else:
                newname = "DEFAULT {}".format(country)
            xgpastr = input("New Entry GPAs: gpascale/.../min ")
            ygpastr = input("New Entry 4pt GPAs: 4.0/.../min ")
            xgpa = np.array(xgpastr.split("/")).astype(float)
            ygpa = np.array(ygpastr.split("/")).astype(float)
            if (xgpa.min() != 0) & (ygpa.min() != 0):
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
                        "Interp": [
                            scipy.interpolate.interp1d(xgpa, ygpa, kind="linear")
                        ],
                    }
                ),
                ignore_index=True,
            )
            self.gradeup = True
        else:
            return None

        return self.grades.loc[self.grades.Name == newname, "Interp"].values[0](gpa)

    def assignschools(self, data):
        """Determine undergrad and grad institutions for all students

        data - main data table
        """

        for row in data.itertuples():
            fullname = row.Full_Name
            if fullname in self.schoolmatches["Full_Name"].values:
                redo = False
                ugj = self.schoolmatches.loc[
                    self.schoolmatches["Full_Name"] == fullname, "UG_School"
                ].values[0]
                if not (
                    self.isknownschool(
                        row.__getattribute__("School_Name_{}".format(int(ugj)))
                    )
                ):
                    redo = True

                gj = self.schoolmatches.loc[
                    self.schoolmatches["Full_Name"] == fullname, "GR_School"
                ].values[0]
                if not (np.isnan(gj)):
                    if not (
                        self.isknownschool(
                            row.__getattribute__("School_Name_{}".format(int(gj)))
                        )
                    ):
                        redo = True

                if redo:
                    self.schoolmatches = self.schoolmatches[
                        self.schoolmatches["Full_Name"] != fullname
                    ].reset_index(drop=True)
                else:
                    continue

            print("\n")
            print(fullname)

            schools = []
            degreetypes = []
            countries = []
            earneddegs = []
            gpas = []
            snums = []

            for j in range(1, 4):
                s = row.__getattribute__("School_Name_{}".format(j))
                if s == s:
                    country = self.cc.convert(
                        names=row.__getattribute__("School_Country_{}".format(j)),
                        to="name_short",
                    )
                    c = row.__getattribute__("School_City_{}".format(j))
                    res = self.matchschool(s, country, city=c)

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
                    gpas.append(row.__getattribute__("GPA_School_{}".format(j)))
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
                            "{}: {}, {}, Earned: {}, GPA:{}".format(
                                kk,
                                schools[kk],
                                degreetypes[kk],
                                earneddegs[kk],
                                gpas[kk],
                            )
                        )
                    waitingForResponse = True
                    while waitingForResponse:
                        try:
                            ug = int(input("Pick UNDERgrad school index (from 0) "))
                            assert ug in range(len(schools))
                            waitingForResponse = False
                        except (ValueError, AssertionError):
                            print("I need a valid integer from the list.")
                else:
                    ug = inds[0]

                inds = np.where(
                    [
                        (("under" not in d.lower()) | ("combined" in d.lower()))
                        & (d != "")
                        for d in degreetypes
                    ]
                )[0]
                # throw away any matches of ugrad institution
                inds[inds != ug]
                if len(inds) == 0:
                    pass
                elif len(inds) > 1:
                    for kk in range(len(schools)):
                        print(
                            "{}: {}, {}, Earned: {}, GPA:{}".format(
                                kk,
                                schools[kk],
                                degreetypes[kk],
                                earneddegs[kk],
                                gpas[kk],
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
                            "GR_School": [np.nan],
                        }
                    ),
                    ignore_index=True,
                )
                self.utilup = True

    def fillSchoolData(self, data):
        for row in data.itertuples():
            fullname = row.Full_Name
            print(fullname)

            # get ugrad gpa
            j = int(
                self.schoolmatches.loc[
                    self.schoolmatches["Full_Name"] == fullname, "UG_School"
                ].values[0]
            )
            s = row.__getattribute__("School_Name_{}".format(j))
            country = self.cc.convert(
                names=row.__getattribute__("School_Country_{}".format(j)),
                to="name_short",
            )
            school = self.matchschool(s, country)
            gpa = row.__getattribute__("GPA_School_{}".format(j))
            gpascale = row.__getattribute__("GPA_Scale_School_{}".format(j))
            country = self.cc.convert(
                names=row.__getattribute__("School_Country_{}".format(j)),
                to="name_short",
            )

            data.at[row.Index, "UGrad_School"] = school
            data.at[row.Index, "UGrad_GPA"] = gpa
            newgpa = self.calc4ptGPA(school, country, gpascale, gpa)
            # check for rename request:
            if newgpa is None:
                newgpa = input("GPA: ")
                newgpascale = input("GPA Scale: ")
                self.renames = self.renames.append(
                    pandas.DataFrame(
                        {
                            "Full_Name": [fullname, fullname],
                            "Field": [
                                "GPA_School_{}".format(j),
                                "GPA_Scale_School_{}".format(j),
                            ],
                            "Value": [float(newgpa), float(newgpascale)],
                        }
                    ),
                    ignore_index=True,
                )
                self.utilup = True
                continue

            data.at[row.Index, "UGrad_GPA_4pt"] = newgpa

            rank = self.lookup.loc[self.lookup["Name"] == school, "Rank"].values[0]
            medgpa = self.rankfit(rank)
            uggpa = norm.cdf(2 * (newgpa - medgpa))
            data.at[row.Index, "UGrad_Rank"] = rank
            data.at[row.Index, "UGrad_GPA_Norm"] = uggpa

            # get grad school gpa if it exists
            if (
                self.schoolmatches.loc[
                    self.schoolmatches["Full_Name"] == fullname, "GR_School"
                ]
                .notnull()
                .values[0]
            ):
                j = int(
                    self.schoolmatches.loc[
                        self.schoolmatches["Full_Name"] == fullname, "GR_School"
                    ].values[0]
                )

                s = row.__getattribute__("School_Name_{}".format(j))
                country = self.cc.convert(
                    names=row.__getattribute__("School_Country_{}".format(j)),
                    to="name_short",
                )
                school = self.matchschool(s, country)
                data.at[row.Index, "Grad_School"] = school
                gpa = row.__getattribute__("GPA_School_{}".format(j))
                if np.isfinite(gpa):
                    gpascale = row.__getattribute__("GPA_Scale_School_{}".format(j))
                    country = self.cc.convert(
                        names=row.__getattribute__("School_Country_{}".format(j)),
                        to="name_short",
                    )

                    data.at[row.Index, "Grad_GPA"] = gpa
                    newgpa = self.calc4ptGPA(school, country, gpascale, gpa)
                    data.at[row.Index, "Grad_GPA_4pt"] = newgpa

                    rank = self.lookup.loc[
                        self.lookup["Name"] == school, "Rank"
                    ].values[0]
                    medgpa = self.rankfit(rank)
                    grgpa = norm.cdf(2 * (newgpa - medgpa))
                    data.at[row.Index, "Grad_Rank"] = rank
                    data.at[row.Index, "Grad_GPA_Norm"] = grgpa

        return data

    def readData(self, fname):
        data = pandas.read_csv(fname, header=[0, 1])
        data.columns = data.columns.droplevel(-1)
        data.drop(data[data["Field Admission Decision"] == "ADMT"].index, inplace=True)
        data.reset_index(drop=True, inplace=True)

        data = data.drop(
            columns=[
                "Assigned",
                "In Progress",
                "Completed",
                "Tags",
                "Field Admission Decision",
                "Admit Term (requested)",
                "Admit Term (offered)",
                "Application Date Submitted",
                "Application Status",
                "Applicant Decision",
                "CollegeNET ID",
                "Admit Program (offered)"
            ],
            errors="ignore",
        )

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

        # make sure that numeric cols remain numeric
        numcols = [
            "Verbal_GRE_Unofficial",
            "Quantitative_GRE_Unofficial",
            "GRE_Analytical_Writing_GRE_Unofficial",
            "UGrad_GPA_4pt",
            "Grad_GPA_4pt",
        ]
        for j in range(1, 4):
            numcols.append("GPA_School_{}".format(j))
            numcols.append("GPA_Scale_School_{}".format(j))

        for col in numcols:
            if col in data:
                data[col] = data[col].astype(float)

        return data
