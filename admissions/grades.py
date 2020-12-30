import numpy as np
import pandas
import scipy.interpolate

import requests
from html.parser import HTMLParser


def scrapegradedata(URL="http://gpa.eng.uci.edu/"):
    page = requests.get(URL)

    class GradeHTMLParser(HTMLParser):
        def __init__(self):
            HTMLParser.__init__(self)
            self.intr = False
            self.intd = False
            self.ina = False
            self.currattr = ""
            self.titles = []
            self.countries = []
            self.intlgpas = []
            self.usgpas = []

        def handle_starttag(self, tag, attrs):
            if tag == "tr":
                self.intr = True

            if tag == "td":
                self.intd = True
                self.currattr = attrs[0][1]

            if tag == "a":
                self.ina = True

        def handle_endtag(self, tag):
            if tag == "tr":
                self.intr = False

            if tag == "td":
                self.intd = False

            if tag == "a":
                self.ina = False

        def handle_data(self, data):
            if self.intd:
                if self.currattr == "views-field views-field-title":
                    if self.ina:
                        self.titles.append(data.strip())
                elif self.currattr == "views-field views-field-field-country":
                    self.countries.append(data.strip())
                elif self.currattr == "views-field views-field-field-intl-gpa":
                    self.intlgpas.append(data.strip())
                elif self.currattr == "views-field views-field-field-us-gpa":
                    self.usgpas.append(data.strip())
                else:
                    pass
            # end HTMLParser

    parser = GradeHTMLParser()
    _ = parser.feed(page.text)

    np.savez(
        "grade_data",
        titles=parser.titles,
        countries=parser.countries,
        intlgpas=parser.intlgpas,
        usgpas=parser.usgpas,
    )


def gengradedicts(grade_data="grade_data.xlsx"):
    # generate school and country grade dictionaries
    tmp = pandas.ExcelFile(grade_data, engine="openpyxl")
    grades = tmp.parse("grades")
    tmp.close()

    defaults = np.array(["DEFAULT" in n for n in grades["Name"].values])

    countrygrades = {}
    for row in grades[defaults].iterrows():
        countrygrades[
            "{} - {}".format(row[1]["Country"], row[1]["GPAScale"])
        ] = scipy.interpolate.interp1d(
            np.array(row[1]["SchoolGPA"].split("/")).astype(float),
            np.array(row[1]["4ptGPA"].split("/")).astype(float),
            kind="linear",
        )

    schoolgrades = {}
    for row in grades[~defaults].iterrows():
        schoolgrades[
            "{} - {} - {}".format(row[1]["Name"], row[1]["Country"], row[1]["GPAScale"])
        ] = scipy.interpolate.interp1d(
            np.array(row[1]["SchoolGPA"].split("/")).astype(float),
            np.array(row[1]["4ptGPA"].split("/")).astype(float),
            kind="linear",
        )

    return countrygrades, schoolgrades
