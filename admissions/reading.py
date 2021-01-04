import pandas
import numpy as np
from cornellGrading import cornellQualtrics
import os


def genReadingAssignments(infile, outfile):
    # generate reading assignments
    # infile must be xlsx with two sheets (Readers & Canddiates)

    # grab all input data
    tmp = pandas.ExcelFile(infile, engine="openpyxl")
    readers = tmp.parse("Readers")
    candidates = tmp.parse("Candidates")
    tmp.close()

    readers = readers["Reader Names"].values
    candidates = candidates["Candidate Names"].values

    # Each person needs to be read by 2 readers
    nperreader = int(np.round(len(candidates) * 2 / len(readers)))

    # shuffle candidates and split by readers
    clist = np.hstack((candidates.copy(), candidates.copy()))
    np.random.shuffle(clist)

    out = {}
    for reader in readers:
        tmp = clist[:nperreader]
        while np.unique(tmp).size != tmp.size:
            np.random.shuffle(clist)
            tmp = clist[:nperreader]
        out[reader] = tmp
        clist = clist[nperreader:]

    # check for unassigned
    if len(clist) > 0:
        for c in clist:
            r = np.random.choice(readers, size=1)[0]
            while c in out[r]:
                r = np.random.choice(readers, size=1)[0]
            out[r] = np.hstack((out[r], c))

    # final consistency check
    asslist = []
    for key, val in out.items():
        assert np.unique(val).size == val.size, "{} has non-unique list.".format(key)
        asslist = np.hstack((asslist, val))

    assert np.all(
        np.unique(asslist) == np.sort(candidates)
    ), "Not all candidates assigned."
    for c in candidates:
        assert np.where(asslist == c)[0].size == 2, "{} not assigned twice.".format(c)

    # write assignemnts out to disk
    outdf = pandas.DataFrame()
    for key, val in out.items():
        outdf = pandas.concat([outdf, pandas.DataFrame({key: val})], axis=1)

    ew = pandas.ExcelWriter(outfile, options={"encoding": "utf-8"})
    outdf.to_excel(ew, sheet_name="Assignments", index=False)
    ew.save()
    ew.close()


def genRubricSurvey(surveyname, candidates, rubrics, scoreOptions, shareWith=None):
    """
    surveyname (str)
    candidates (iterable)
    rubrics (iterable)
    scoreOptions (iterable)
    shareWith (str) optional
    """

    # connect and craete survey
    c = cornellQualtrics()
    surveyId = c.createSurvey(surveyname)

    # candidate dropdown
    desc = "Select Candidate Name"
    choices = {}
    for j, choice in enumerate(candidates):
        choices[str(j + 1)] = {"Display": choice}
    choiceOrder = list(range(1, len(choices) + 1))
    questionDef = {
        "QuestionText": desc,
        "DefaultChoices": False,
        "DataExportTag": "Q1",
        "QuestionType": "MC",
        "Selector": "DL",
        "Configuration": {"QuestionDescriptionOption": "UseText"},
        "QuestionDescription": desc,
        "Choices": choices,
        "ChoiceOrder": choiceOrder,
        "Validation": {
            "Settings": {
                "ForceResponse": "ON",
                "ForceResponseType": "ON",
                "Type": "None",
            }
        },
        "Language": [],
        "QuestionID": "QID1",
        "QuestionText_Unsafe": desc,
    }
    qid1 = c.addSurveyQuestion(surveyId, questionDef)

    # rubric multiple choice
    choices = {}
    for j, choice in enumerate(scoreOptions):
        choices[str(j + 1)] = {"Display": str(choice)}
    choiceOrder = list(range(1, len(choices) + 1))

    for j in range(1, len(rubrics) + 1):
        desc = rubrics[j - 1]
        questionDef = {
            "QuestionText": desc,
            "DataExportTag": "Q%d" % (j + 1),
            "QuestionType": "MC",
            "Selector": "SAVR",
            "SubSelector": "TX",
            "Configuration": {"QuestionDescriptionOption": "UseText"},
            "QuestionDescription": desc,
            "Choices": choices,
            "ChoiceOrder": choiceOrder,
            "Validation": {
                "Settings": {
                    "ForceResponse": "ON",
                    "ForceResponseType": "ON",
                    "Type": "None",
                }
            },
            "Language": [],
            "QuestionID": "QID%d" % (j + 3),
            "DataVisibility": {"Private": False, "Hidden": False},
            "QuestionText_Unsafe": desc,
        }
        c.addSurveyQuestion(surveyId, questionDef)

    # generate quotas
    quotaGroupName = "q1quotas"
    quotaGroupId = c.addSurveyQuotaGroup(surveyId, quotaGroupName)

    quotas = []
    for j, s in enumerate(candidates):
        quotaDef = {
            "Name": "name{}quota".format(j + 1),
            "Occurrences": 1,
            "Logic": {
                "0": {
                    "0": {
                        "LogicType": "Question",
                        "QuestionID": "QID1",
                        "QuestionIsInLoop": "no",
                        "ChoiceLocator": "q://QID1/SelectableChoice/{}".format(j + 1),
                        "Operator": "Selected",
                        "QuestionIDFromLocator": "QID1",
                        "LeftOperand": "q://QID1/SelectableChoice/{}".format(j + 1),
                        "Type": "Expression",
                        "Description": "",
                    },
                    "Type": "If",
                },
                "Type": "BooleanExpression",
            },
            "LogicType": "Simple",
            "QuotaAction": "ForBranching",
            "ActionInfo": {
                "0": {
                    "0": {
                        "ActionType": "ForBranching",
                        "Type": "Expression",
                        "LogicType": "QuotaAction",
                    },
                    "Type": "If",
                },
                "Type": "BooleanExpression",
            },
            "QuotaRealm": "Survey",
            "Count": 0,
        }
        quotas.append(c.addSurveyQuota(surveyId, quotaDef))

    # and now we can update Q1 with the quotas
    desc = "Select Candidate Name"
    choices = {}
    for j, choice in enumerate(candidates):
        choices[str(j + 1)] = {
            "Display": choice,
            "DisplayLogic": {
                "0": {
                    "0": {
                        "LogicType": "Quota",
                        "QuotaID": quotas[j],
                        "QuotaType": "Simple",
                        "Operator": "QuotaNotMet",
                        "LeftOperand": "qo://{}/QuotaNotMet".format(quotas[j]),
                        "QuotaName": "name{}quota".format(j + 1),
                        "Type": "Expression",
                        "Description": "",
                    },
                    "Type": "If",
                },
                "Type": "BooleanExpression",
                "inPage": False,
            },
        }
    choiceOrder = list(range(1, len(choices) + 1))
    questionDef = {
        "QuestionText": desc,
        "DefaultChoices": False,
        "DataExportTag": "Q1",
        "QuestionType": "MC",
        "Selector": "DL",
        "Configuration": {"QuestionDescriptionOption": "UseText"},
        "QuestionDescription": desc,
        "Choices": choices,
        "ChoiceOrder": choiceOrder,
        "Validation": {
            "Settings": {
                "ForceResponse": "ON",
                "ForceResponseType": "ON",
                "Type": "None",
            }
        },
        "Language": [],
        "QuestionID": "QID1",
        "QuestionText_Unsafe": desc,
    }

    c.updateSurveyQuestion(surveyId, qid1, questionDef)

    if shareWith:
        c.shareSurvey(surveyId, shareWith)

    # publish & activate
    c.publishSurvey(surveyId)
    c.activateSurvey(surveyId)

    link = "https://cornell.qualtrics.com/jfe/form/%s" % surveyId

    return link


def genRankSurvey(readername, candidates, binsize, shareWith=None):
    """
    readername (str)
    candidates (iterable)
    binsize (int)
    shareWith (str) optional
    """
    # connect and craete survey
    c = cornellQualtrics()
    surveyname = "Ranking Survey for {}".format(readername)
    surveyId = c.createSurvey(surveyname)

    desc = (
        u"This survey is for: {0}.\n\n"
        u"Rank students into the top 50%-ile bins.  "
        u"Put exactly {1} students in each bin.  "
        u"All uncategorized students will automatically "
        u"be placed in the bottom 50%-ile. Ordering within a bin "
        u"does not matter.".format(readername, binsize)
    )

    choices = {}
    for j, choice in enumerate(candidates):
        choices[str(j + 1)] = {"Display": choice}
    choiceOrder = list(range(1, len(choices) + 1))

    questionDef = {
        "QuestionText": desc,
        "DefaultChoices": False,
        "DataExportTag": "Q1",
        "QuestionID": "QID1",
        "QuestionType": "PGR",
        "Selector": "DragAndDrop",
        "SubSelector": "Columns",
        "Configuration": {
            "QuestionDescriptionOption": "UseText",
            "Stack": False,
            "StackItemsInGroups": False,
        },
        "QuestionDescription": desc,
        "Choices": choices,
        "ChoiceOrder": choiceOrder,
        "Validation": {
            "Settings": {
                "ForceResponse": "ON",
                "Type": "GroupChoiceRange",
                "MinChoices": "{}".format(binsize),
                "MaxChoices": "{}".format(binsize),
            }
        },
        "GradingData": [],
        "Language": [],
        "NextChoiceId": len(choices) + 1,
        "NextAnswerId": 6,
        "Groups": ["Top 10%", "Top 20%", "Top 30%", "Top 40%", "Top 50%"],
        "NumberOfGroups": 5,
        "QuestionText_Unsafe": desc,
    }

    c.addSurveyQuestion(surveyId, questionDef)

    if shareWith:
        c.shareSurvey(surveyId, shareWith)

    c.publishSurvey(surveyId)
    c.activateSurvey(surveyId)

    link = "https://cornell.qualtrics.com/jfe/form/%s" % surveyId
    return link


def getRankSurveyRes(assignments, outfile):
    c = cornellQualtrics()

    outdict = {}
    for readername in assignments.columns:
        surveyname = "Ranking Survey for {}".format(readername)
        surveyId = c.getSurveyId(surveyname)
        tmpdir = c.exportSurvey(surveyId)
        tmpfile = os.path.join(tmpdir, surveyname + ".csv")
        assert os.path.isfile(tmpfile), "Survey results not where expected."
        res = pandas.read_csv(tmpfile, header=[0, 1, 2])

        if len(res) == 0:
            continue

        allnames = np.array([])
        for j in range(5):
            gcolinds = np.array(
                ["Q1_{}_GROUP".format(j) in c for c in res.columns.get_level_values(0)]
            )
            gcols = res.columns.get_level_values(0)[gcolinds]
            names = res[gcols].values
            names = names[names == names]
            assert len(names) == 3
            allnames = np.hstack((allnames, names))
            for n in names:
                if n in outdict:
                    outdict[n] += ((j + 1) * 10,)
                else:
                    outdict[n] = ((j + 1) * 10,)
        unranked = np.array(list(set(assignments[readername].values) - set(allnames)))
        unranked = unranked[unranked != "nan"]
        for n in unranked:
            if n in outdict:
                outdict[n] += (100,)
            else:
                outdict[n] = (100,)

    # build output
    outnames = []
    outrank1 = []
    outrank2 = []
    for key, val in outdict.items():
        outnames.append(key.split(", "))
        outrank1.append(val[0])
        if len(val) == 2:
            outrank2.append(val[1])
        else:
            outrank2.append(np.nan)
    outnames = np.array(outnames)
    out = pandas.DataFrame(
        {
            "First Name": outnames[:, 0],
            "Lat Name": outnames[:, 1],
            "Rank 1": outrank1,
            "Rank 2": outrank2,
        }
    )
    ew = pandas.ExcelWriter(outfile, options={"encoding": "utf-8"})
    out.to_excel(ew, sheet_name="Ranks", index=False)
    ew.save()
    ew.close()


def genRankDragSurvey(surveyname, candidates, shareWith=None):
    """
    surveyname (str)
    candidates (iterable)
    shareWith (str) optional
    """

    # connect and craete survey
    c = cornellQualtrics()
    surveyId = c.createSurvey(surveyname)

    desc = "Drag Students into your preferred rank order.  Note that the bottom half is undifferentiated."
    choices = {}
    for j, choice in enumerate(candidates):
        choices[str(j + 1)] = {"Display": choice}
    choiceOrder = list(range(1, len(choices) + 1))
    questionDef = {
        "QuestionText": desc,
        "DefaultChoices": False,
        "DataExportTag": "Q1",
        "QuestionType": "RO",
        "Selector": "DND",
        "SubSelector": "TX",
        "Configuration": {"QuestionDescriptionOption": "UseText"},
        "QuestionDescription": desc,
        "Choices": choices,
        "ChoiceOrder": choiceOrder,
        "Validation": {"Settings": {"ForceResponse": "OFF", "Type": "None"}},
        "Language": [],
        "QuestionID": "QID1",
        "QuestionText_Unsafe": desc,
    }
    c.addSurveyQuestion(surveyId, questionDef)

    if shareWith:
        c.shareSurvey(surveyId, shareWith)

    c.publishSurvey(surveyId)
    c.activateSurvey(surveyId)

    link = "https://cornell.qualtrics.com/jfe/form/%s" % surveyId

    return link


def binRubricSurveyResults(surveyname, outfile):

    c = cornellQualtrics()
    surveyId = c.getSurveyId(surveyname)
    tmpdir = c.exportSurvey(surveyId)
    tmpfile = os.path.join(tmpdir, surveyname + ".csv")
    assert os.path.isfile(tmpfile), "Survey results not where expected."

    res = pandas.read_csv(tmpfile, header=[0, 1, 2])

    namecol = res.columns.get_level_values(0)[
        np.array(
            ["Select Candidate Name" in c for c in res.columns.get_level_values(1)]
        )
    ]

    names = np.array([n[0] for n in res[namecol].values])

    # calculate total scores
    quescolinds = np.array(
        ["Rubric" in c and "Score" in c for c in res.columns.get_level_values(1)]
    )
    quescols = res.columns.get_level_values(0)[quescolinds]
    quesnames = res.columns.get_level_values(1)[quescolinds]
    scores = res[quescols].values.sum(axis=1)
    inds = np.argsort(scores)[::-1]
    names = names[inds]
    binsize = int(np.round(len(names) * 0.1))
    bins = np.zeros(names.size)
    for j in range(5):
        bins[j * binsize : (j + 1) * binsize] = (j + 1) * 10
    bins[bins == 0] = 100

    rawscores = res[quescols].values

    out = pandas.DataFrame({"Candidate": names, "Bin": bins})
    ew = pandas.ExcelWriter(outfile, options={"encoding": "utf-8"})
    out2 = pandas.DataFrame(
        {
            "Candidate": names,
            "s1": rawscores[:, 0],
            "s2": rawscores[:, 1],
            "s3": rawscores[:, 2],
            "s4": rawscores[:, 3],
            "s5": rawscores[:, 4],
        }
    )
    out.to_excel(ew, sheet_name="Reader A Scores", index=False)
    out2.to_excel(ew, sheet_name="Reader A Raw Scores", index=False)
    ew.save()
    ew.close()
