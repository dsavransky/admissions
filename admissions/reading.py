import pandas
import numpy as np
from cornellGrading import cornellQualtrics
import os


def validateReadingAssignment(out, candidates, nreaders):

    # final consistency check
    asslist = []
    for key, val in out.items():
        assert np.unique(val).size == val.size, "{} has non-unique list.".format(key)
        asslist = np.hstack((asslist, val))

    assert len(set(asslist) - set(candidates)) == 0, "Not all candidates assigned."
    for c in candidates:
        assert (
            np.where(asslist == c)[0].size == nreaders
        ), "{} not assigned twice.".format(c)


def genReadingAssignmentsHelper(readers, candidates, nreaders):

    # Each person needs to be read by 2 readers
    nperreader = int(np.round(len(candidates) * nreaders / len(readers)))

    clist = np.hstack((candidates.copy(), candidates.copy()))
    np.random.shuffle(clist)

    out = {}
    for reader in readers:
        tmp = clist[:nperreader]
        counter = 0
        while np.unique(tmp).size != tmp.size:
            counter += 1
            assert counter < 100, "Initial shuffling failed."
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

    validateReadingAssignment(out, candidates, nreaders)

    return out


def genReadingAssignments(infile, outfile, nreaders=2):
    # generate reading assignments
    # infile must be xlsx with two sheets (Readers & Canddiates)

    # grab all input data
    if isinstance(infile, str):
        tmp = pandas.ExcelFile(infile, engine="openpyxl")
        readers = tmp.parse("Readers")
        candidates = tmp.parse("Candidates")
        tmp.close()

        readers = readers["Reader Names"].values
        candidates = candidates["Candidate Names"].values.astype(str)
    else:
        readers = infile[0]
        candidates = infile[1]

    # shuffle candidates and split by readers
    # sometimes this process will fail so we just try from
    # scratch when that happens
    finished = False
    while not (finished):
        try:
            out = genReadingAssignmentsHelper(readers, candidates, nreaders)
            finished = True
        except AssertionError as e:
            print(e)

    # one final validation for paranoia
    validateReadingAssignment(out, candidates, nreaders)

    # write assignemnts out to disk
    outdf = pandas.DataFrame()
    for key, val in out.items():
        outdf = pandas.concat([outdf, pandas.DataFrame({key: val})], axis=1)

    with pandas.ExcelWriter(outfile) as writer:
        outdf.to_excel(writer, sheet_name="Assignments", index=False)


def genReadingAssignmentsConcs(readers, data):
    """
    readers (pandas dataframe)
    data (pandas dataframe)
    """

    from ortools.sat.python import cp_model

    # lets build a reward matrix
    rewards = {}
    for r in readers.index:
        print(r)
        for c in data["Full_Name"]:
            tmp = data.loc[
                data["Full_Name"] == c, ["Concentration_1", "Concentration_2"]
            ].values.squeeze()
            tmp = tmp[pandas.notnull(tmp)]
            tmp = tmp[tmp != "Undecided"]
            tmp = tmp[tmp != "Human Computer Interaction"]
            rewards[(r, c)] = readers.loc[r, tmp].sum()

    model = cp_model.CpModel()

    # all candidate/reader combinations
    assignments = {}
    for r in readers.index:
        for c in data["Full_Name"]:
            assignments[(r, c)] = model.NewBoolVar("{}_{}".format(r, c))

    # every candidate gets two readers
    for c in data["Full_Name"]:
        model.Add(sum(assignments[(r, c)] for r in readers.index) == 2)

    # Try to distribute assignments evenly
    min_candidates_per_reader = 2 * len(data) // len(readers.index)
    if min_candidates_per_reader * len(readers.index) < 2 * len(data):
        max_candidates_per_reader = min_candidates_per_reader + 1
    else:
        max_candidates_per_reader = min_candidates_per_reader

    for r in readers.index:
        num_reads = []
        for c in data["Full_Name"]:
            num_reads.append(assignments[(r, c)])
        model.Add(min_candidates_per_reader <= sum(num_reads))
        model.Add(sum(num_reads) <= max_candidates_per_reader)

    # Objective function based on rewards
    model.Maximize(
        sum(
            rewards[(r, c)] * assignments[(r, c)]
            for r in readers.index
            for c in data["Full_Name"]
        )
    )

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    res = np.zeros((len(readers.index), len(data["Full_Name"])))
    rewards2 = np.zeros((len(readers.index), len(data["Full_Name"])))

    for jj, r in enumerate(readers.index):
        for kk, c in enumerate(data["Full_Name"]):
            res[jj, kk] = solver.Value(assignments[(r, c)])
            rewards2[jj, kk] = rewards[(r, c)]

    return res, rewards2


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

    questionDef = {
        "QuestionText": surveyname,
        "DefaultChoices": False,
        "DataExportTag": "Q0",
        "QuestionType": "DB",
        "Selector": "TB",
        "Configuration": {"QuestionDescriptionOption": "UseText"},
        "QuestionDescription": surveyname,
        "ChoiceOrder": [],
        "Validation": {"Settings": {"Type": "None"}},
        "GradingData": [],
        "Language": [],
        "NextChoiceId": 4,
        "NextAnswerId": 1,
        "QuestionID": "QID0",
        "QuestionText_Unsafe": surveyname,
    }
    _ = c.addSurveyQuestion(surveyId, questionDef)

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
            "QuestionID": "QID%d" % (j + 1),
            "DataVisibility": {"Private": False, "Hidden": False},
            "QuestionText_Unsafe": desc,
        }
        c.addSurveyQuestion(surveyId, questionDef)

    questionDef = {
        "QuestionText": "Comments",
        "DefaultChoices": False,
        "DataExportTag": "Q%d" % (len(rubrics) + 2),
        "QuestionType": "TE",
        "Selector": "SL",
        "Configuration": {"QuestionDescriptionOption": "UseText"},
        "QuestionDescription": "Comments",
        "Validation": {
            "Settings": {
                "ForceResponse": "OFF",
                "ForceResponseType": "ON",
                "Type": "None",
            }
        },
        "GradingData": [],
        "Language": [],
        "NextChoiceId": 4,
        "NextAnswerId": 1,
        "SearchSource": {"AllowFreeResponse": "false"},
        "QuestionID": "QID%d" % (len(rubrics) + 2),
        "QuestionText_Unsafe": "Comments",
    }
    _ = c.addSurveyQuestion(surveyId, questionDef)

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


def genRankSurvey(readername, candidates, binsize, surveyBaseName=None, shareWith=None):
    """
    readername (str)
    candidates (iterable)
    binsize (int)
    shareWith (str) optional
    surveyBaseName (str) optional
    """
    # connect and craete survey
    c = cornellQualtrics()
    surveyname = "Ranking Survey for {}".format(readername)
    if surveyBaseName:
        surveyname = "{} {}".format(surveyBaseName, surveyname)
    surveyId = c.createSurvey(surveyname)

    desc = (
        "This survey is for: {0}.\n\n"
        "Rank students into the top 50%-ile bins.  "
        "Put exactly {1} students in each bin.  "
        "All uncategorized students will automatically "
        "be placed in the bottom 50%-ile. Ordering within a bin "
        "does not matter.".format(readername, binsize)
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


def getRankSurveyRes(assignments, outfile, surveyBaseName=None, c=None):
    if c is None:
        c = cornellQualtrics()

    outdict = {}
    readersheets = []
    for readername in assignments.columns:
        surveyname = "Ranking Survey for {}".format(readername)
        if surveyBaseName:
            surveyname = "{} {}".format(surveyBaseName, surveyname)
        surveyId = c.getSurveyId(surveyname)
        tmpdir = c.exportSurvey(surveyId)
        tmpfile = os.path.join(tmpdir, surveyname + ".csv")
        assert os.path.isfile(tmpfile), "Survey results not where expected."
        res = pandas.read_csv(tmpfile, header=[0, 1, 2])

        if len(res) == 0:
            continue

        allnames = np.array([])
        readernames = []
        readerscores = []
        for j in range(5):
            gcolinds = np.array(
                ["Q1_{}_GROUP".format(j) in c for c in res.columns.get_level_values(0)]
            )
            gcols = res.columns.get_level_values(0)[gcolinds]
            names = res[gcols].iloc[-1].values
            names = names[names == names]
            assert len(names) == 3
            allnames = np.hstack((allnames, names))
            for n in names:
                if n in outdict:
                    outdict[n] += ((j + 1) * 10,)
                else:
                    outdict[n] = ((j + 1) * 10,)
                readernames.append(n)
                readerscores.append((j + 1) * 10)
        unranked = np.array(list(set(assignments[readername].values) - set(allnames)))
        unranked = unranked[unranked != "nan"]
        for n in unranked:
            if n in outdict:
                outdict[n] += (100,)
            else:
                outdict[n] = (100,)
            readernames.append(n)
            readerscores.append(100)

        readersheets.append(
            pandas.DataFrame({"Name": readernames, "Rank": readerscores})
        )

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
            "Last Name": outnames[:, 0],
            "First Name": outnames[:, 1],
            "Rank 1": outrank1,
            "Rank 2": outrank2,
        }
    )
    with pandas.ExcelWriter(outfile) as ew:
        out.to_excel(ew, sheet_name="Ranks", index=False)
        for j, r in enumerate(readersheets):
            r.to_excel(ew, sheet_name=assignments.columns[j], index=False)


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

    with pandas.ExcelWriter(outfile) as ew:
        out.to_excel(ew, sheet_name="Reader A Scores", index=False)
        out2.to_excel(ew, sheet_name="Reader A Raw Scores", index=False)
