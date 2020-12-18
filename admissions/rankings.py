import numpy as np
import re
from scipy.optimize import curve_fit
import country_converter as coco
import matplotlib.pyplot as plt

cc = coco.CountryConverter()


def parseusnwr(lines, hasreps=True):
    # For US News and World Report
    # expected format:
    # View all %d Photos\nName\nLoc\n\n#Rank\n...\nREPUTATION SCORE\nrep\n...Save to My Schools

    nump = re.compile(r"#(\d+)*")
    photp = re.compile(r"View all \d+ photos")

    ranks = []
    names = []
    reps = []

    while lines:
        # read lines until you hit a non-blank one
        l = lines.pop(0).strip()
        while not l:
            l = lines.pop(0).strip()
        # this is either the 'view photos line, a blank, or the school name
        # if it's the photos line, read until the next non-blank
        if photp.match(l):
            l = lines.pop(0).strip()
            while not l:
                l = lines.pop(0).strip()

        # we've got to be at the name by now
        names.append(l.strip(" 1"))

        # next look for the ranking match
        l = lines.pop(0).strip()
        while (nump.match(l) is None) & ("Unranked" not in l):
            l = lines.pop(0).strip()
        if "Unranked" in l:
            ranks.append(np.max(ranks) + 1)
        else:
            ranks.append(int(nump.match(l).groups()[0]))

        if hasreps:
            # next look for rep scores
            while not ("REPUTATION SCORE" in l):
                l = lines.pop(0).strip()
            # grab next non blank line
            l = lines.pop(0).strip()
            while not l:
                l = lines.pop(0).strip()
            if l == "N/A":
                reps.append(np.nan)
            else:
                reps.append(float(l))

        while not ("Save to My Schools" in l):
            l = lines.pop(0).strip()

    names = np.array(names)
    ranks = np.array(ranks)
    reps = np.array(reps)

    if hasreps:
        return ranks, names, reps
    else:
        return ranks, names


# various fit functions
def linfit(x, m, b):
    return m * x + b


def sqfit(x, a, b, c):
    return a * x ** 2 + b * x + c


def expfit(x, a, b, c):
    return a * np.exp(-b * x) + c


def sfit(x, a, b, c):
    return a / (b + np.exp(-c * x))


def sfit2(x, a, b, c):
    return a + b/ (1 + np.exp(-x/c))

def tanhfit(x, a, b, c):
    return a + b*np.tanh(x/c)


# PCA
def dopca(x, y):
    R = np.array([x - np.mean(x), y - np.mean(y)])
    S = R.dot(R.transpose()) / (len(x) - 1)
    w, v = np.linalg.eig(S)
    v = v.transpose()[0]
    ft = [v[1] / v[0], np.mean(y) - v[1] / v[0] * np.mean(x)]
    return ft


def genuslist(
    engugradwphd="usnwr_engineering_ugrad_w_phd.txt",
    engugradwophd="usnwr_engineering_ugrad_wo_phd.txt",
    natnllibarts="usnwr_national_liberal_arts.txt",
    natnlunivs="usnwr_national_universities.txt",
    hbcus="usnwr_hbcus.txt",
):
    # Generate list of US schools and ranks

    # engineering undergrad with PhD:
    with open(engugradwphd) as f:
        lines = f.readlines()
        ranks1, names1, reps1 = parseusnwr(lines)

    # engineering undergrad without PhD:
    with open(engugradwophd) as f:
        lines = f.readlines()
        ranks2, names2, reps2 = parseusnwr(lines)

    # national liberal arts schools:
    with open(natnllibarts) as f:
        lines = f.readlines()
        ranks3, names3 = parseusnwr(lines, hasreps=False)

    # national universities:
    with open(natnlunivs) as f:
        lines = f.readlines()
        ranksn, namesn = parseusnwr(lines, hasreps=False)

    # hbcus
    with open(hbcus) as f:
        lines = f.readlines()
        ranksh, namesh = parseusnwr(lines, hasreps=False)

    # first find a suitable fit to w/ phd ranks/reps - exponential works best
    inds = ~np.isnan(reps1)
    ft1, ft1cov = curve_fit(linfit, reps1[inds], ranks1[inds])
    ft2, ft2cov = curve_fit(sqfit, reps1[inds], ranks1[inds])
    ft3, ft3cov = curve_fit(expfit, reps1[inds], ranks1[inds])

    plt.figure(1)
    plt.clf()
    plt.scatter(reps1[inds], ranks1[inds], label="Data")
    plt.plot(reps1[inds], linfit(reps1[inds], ft1[0], ft1[1]), label="Linear Fit")
    plt.plot(
        reps1[inds], sqfit(reps1[inds], ft2[0], ft2[1], ft2[2]), label="Square Fit"
    )
    plt.plot(reps1[inds], expfit(reps1[inds], ft3[0], ft3[1], ft3[2]), label="Exp Fit")
    plt.legend()
    plt.xlabel("Reputation Scores")
    plt.ylabel("Rank")
    plt.title("USNWR Engineering w/ PhD Rank vs. Rep Model")

    # merge w and wo phd ranks based on rep score fit +6 spots
    ranks2b = expfit(reps2, ft3[0], ft3[1], ft3[2]) + 6
    ranks2b[np.isnan(reps2)] = np.max(ranks1) + 7
    ranks2b = np.round(ranks2b)

    # find the intersection of w/out phd and liberal arts schools:
    tmp = list(set(names2).intersection(set(names3)))
    inds2 = np.hstack([np.where(names2 == n)[0] for n in tmp])
    inds3 = np.hstack([np.where(names3 == n)[0] for n in tmp])

    # linear fit works well here
    ft4, ft4cov = curve_fit(linfit, ranks3[inds3], ranks2b[inds2])

    plt.figure(2)
    plt.clf()
    plt.scatter(ranks3[inds3], ranks2b[inds2])
    plt.plot([1, max(ranks3)], linfit(np.array([1, max(ranks3)]), ft4[0], ft4[1]))
    plt.xlabel("Liberal Arts Ranks")
    plt.ylabel("Converted Engineering w/out PhD Rank")
    plt.title("USNWR Liberal Arts Ranking Model")

    # need to get rid of the intersections from the 3rd group:
    dropinds = np.array([n not in names2 for n in names3])
    names3b = names3[dropinds]
    ranks3b = linfit(ranks3[dropinds], ft4[0], ft4[1]) + 7
    ranks3b = np.round(ranks3b)

    # join us institution names
    usnames = np.hstack((names1, names2, names3b))
    usranks = np.hstack((ranks1, ranks2b, ranks3b))
    usranks[usranks > 200] = 200

    # lets get intersection of all the stuff so far with the national universities
    tmp = list(set(usnames).intersection(set(namesn)))
    indsn = np.hstack([np.where(namesn == n)[0] for n in tmp])
    indsu = np.hstack([np.where(usnames == n)[0] for n in tmp])

    # lets look at some partitioned linear fits (going to use the 150 one)
    ft7, ft7cov = curve_fit(linfit, ranksn[indsn], usranks[indsu])
    tmp1 = ranksn[indsn]
    tmp2 = usranks[indsu]
    ft8, ft8cov = curve_fit(linfit, tmp1[tmp1 < 200], tmp2[tmp1 < 200])
    ft9, ft9cov = curve_fit(linfit, tmp1[tmp1 < 150], tmp2[tmp1 < 150])

    plt.figure(3)
    plt.clf()
    plt.scatter(ranksn[indsn], usranks[indsu], label="data")
    plt.plot(
        [1, max(ranksn)],
        linfit(np.array([1, max(ranksn)]), ft7[0], ft7[1]),
        label="Fit all data",
    )
    plt.plot(
        [1, max(ranksn)],
        linfit(np.array([1, max(ranksn)]), ft8[0], ft8[1]),
        label="Fit < 200",
    )
    plt.plot(
        [1, max(ranksn)],
        linfit(np.array([1, max(ranksn)]), ft9[0], ft9[1]),
        label="Fit < 150",
    )
    plt.legend()
    plt.xlabel("National Universities Ranks")
    plt.ylabel("Eng+Liberal Arts Ranks")
    plt.title("USNWR National Universities Ranking Model")

    # now grab all that remains
    newinds = np.array([n not in usnames for n in namesn])
    newnames = namesn[newinds]
    newranks = ranksn[newinds] * ft9[0] + ft9[1]
    newranks = np.round(newranks)
    newranks[newranks > 200] = 200

    usnames = np.hstack((usnames, newnames))
    usranks = np.hstack((usranks, newranks))

    # let's see if we missed any HBCUs
    tmp = list(set(usnames).intersection(set(namesh)))
    indsh = np.hstack([np.where(namesh == n)[0] for n in tmp])
    indsu = np.hstack([np.where(usnames == n)[0] for n in tmp])

    # lets look at some fits (but going with linear fit)
    ft10, ft10cov = curve_fit(linfit, ranksh[indsh], usranks[indsu])
    ft11, ft11cov = curve_fit(expfit, ranksh[indsh], usranks[indsu])
    ft12, ft12cov = curve_fit(sqfit, ranksh[indsh], usranks[indsu])

    plt.figure(4)
    plt.clf()
    plt.scatter(ranksh[indsh], usranks[indsu], label="data")
    plt.plot(
        [1, max(ranksh)],
        linfit(np.array([1, max(ranksh)]), ft10[0], ft10[1]),
        label="lin fit",
    )
    plt.plot(
        np.linspace(1, max(ranksh)),
        expfit(np.linspace(1, max(ranksh)), ft11[0], ft11[1], ft11[2]),
        label="exp fit",
    )
    plt.plot(
        np.linspace(1, max(ranksh)),
        sqfit(np.linspace(1, max(ranksh)), ft12[0], ft12[1], ft12[2]),
        label="sq fit",
    )
    plt.legend()
    plt.xlabel("HBCU Ranks")
    plt.ylabel("Eng+Liberal Arts+National Ranks")
    plt.title("USNWR HBCU Ranking Model")

    # now grab all that remains
    newinds = np.array([n not in usnames for n in namesh])
    newnames = namesh[newinds]
    newranks = ranksh[newinds] * ft10[0] + ft10[1]
    newranks = np.round(newranks)
    newranks[newranks > 200] = 200

    usnames = np.hstack((usnames, newnames))
    usranks = np.hstack((usranks, newranks))

    inds = np.argsort(usranks)
    usnames = usnames[inds]
    usranks = usranks[inds]

    return usnames, usranks


def parseqs(lines):
    # parse scrape from QS World Universities
    ranks = []
    names = []
    countries = []

    nump2 = re.compile(r"[=]?(\d+)")
    namep = re.compile(r"([\s\S]+) Logo[\s\S]+\t([\s\S]+)")
    namep2 = re.compile(r"([\s\S]+)More\t([\s\S]+)")

    while lines:
        r = int(nump2.match(lines.pop(0).strip()).groups()[0])
        if ranks:
            if r < ranks[-1]:
                r = int(nump2.match(lines.pop(0).strip()).groups()[0])
        ranks.append(r)
        l = lines.pop(0).strip()
        tmp = namep.match(l)
        if not tmp:
            tmp = namep2.match(l)
        names.append(tmp.groups()[0].strip())
        countries.append(tmp.groups()[1].strip())

    countries = np.array(cc.convert(names=countries, to="name_short"))

    ranks = np.array(ranks)
    names = np.array(names)
    countries = np.array(countries)

    return names, ranks, countries


def genqslist(
    wengtech="qs_world_universities_engineering_and_technology.txt",
    worldu="qs_world_universities.txt",
):
    # create merged QS top universities list

    # let's take a look at the top universities engineering & tech degree ranking
    with open(wengtech) as f:
        lines = f.readlines()
        names, ranks, countries = parseqs(lines)

    with open(worldu) as f:
        lines = f.readlines()
        names2, ranks2, countries2 = parseqs(lines)

    # find overlap in lists
    tmp = list(set(names).intersection(set(names2)))
    inds1 = np.hstack([np.where(names == n)[0] for n in tmp])
    inds2 = np.hstack([np.where(names2 == n)[0] for n in tmp])

    r1 = ranks[inds1]
    r2 = ranks2[inds2]
    ii = (r1 < 400) & (r2 < 500)
    r1 = r1[ii]
    r2 = r2[ii]

    ftqs, ftqscov = curve_fit(linfit, r2, r1)
    ftqs2 = dopca(r2, r1)

    plt.figure(5)
    plt.clf()
    plt.scatter(ranks2[inds2], ranks[inds1])
    plt.scatter(r2, r1)
    plt.plot([1, max(ranks2)], linfit(np.array([1, max(ranks2)]), ftqs[0], ftqs[1]))
    plt.plot([1, max(ranks2)], linfit(np.array([1, max(ranks2)]), ftqs2[0], ftqs2[1]))
    plt.xlabel("QS World Ranks All")
    plt.ylabel("QS World Ranks Engineering and Technology")
    plt.title("Qs World to Engineering and Technology Ranking Model")

    inds2comp = list(set(range(len(ranks2))) - set(inds2))
    names2 = names2[inds2comp]
    ranks2 = ranks2[inds2comp]
    countries2 = countries2[inds2comp]
    ranks2 = np.round(linfit(ranks2, ftqs[0], ftqs[1]))

    names = np.hstack([names, names2])
    countries = np.hstack([countries, countries2])
    ranks = np.hstack([ranks, ranks2])

    inds = np.argsort(ranks)
    names = names[inds]
    ranks = ranks[inds]
    countries = countries[inds]

    return names, ranks, countries


def parsethe(lines):
    # parse scrape from Times Higher Education
    wranks = []
    wnames = []
    wcountries = []

    lparse = re.compile(r"[=]?(\d+)[-]?[\s\S]*\t([\s\S]+)")

    while lines:
        l = lines.pop(0).strip()
        tmp = lparse.match(l)
        wranks.append(int(tmp.groups()[0]))
        wnames.append(tmp.groups()[1])
        wcountries.append(lines.pop(0).strip())
        lines.pop(0)

    wranks = np.array(wranks).astype(float)
    wnames = np.array(wnames)
    wcountries = np.array(cc.convert(names=wcountries, to="name_short"))

    wnames[
        (wnames == "Northeastern University") & (wcountries == "China")
    ] = "Northeastern University (China)"

    return wnames, wranks, wcountries


def genthelist(
    wengtech="the_world_universities_engineering.txt",
    worldu="the_world_universities_all.txt",
):

    with open(wengtech) as f:
        lines = f.readlines()
        wnames, wranks, wcountries = parsethe(lines)

    with open(worldu) as f:
        lines = f.readlines()
        wnames2, wranks2, wcountries2 = parsethe(lines)

    # find overlap in lists
    tmp = list(set(wnames).intersection(set(wnames2)))
    inds1 = np.hstack([np.where(wnames == n)[0] for n in tmp])
    inds2 = np.hstack([np.where(wnames2 == n)[0] for n in tmp])

    r1 = wranks[inds1]
    r2 = wranks2[inds2]
    ii = (r1 < 100) & (r2 < 100)
    r1 = r1[ii]
    r2 = r2[ii]

    ftthe, ftthecov = curve_fit(linfit, r2, r1)
    ftthe2 = dopca(r2, r1)

    plt.figure(7)
    plt.clf()
    plt.scatter(wranks2[inds2], wranks[inds1])
    plt.scatter(r2, r1)
    plt.plot([1, max(wranks2)], linfit(np.array([1, max(wranks2)]), ftthe[0], ftthe[1]))
    plt.plot(
        [1, max(wranks2)], linfit(np.array([1, max(wranks2)]), ftthe2[0], ftthe2[1])
    )
    plt.xlabel("THE World Ranks All")
    plt.ylabel("THE World Ranks Engineering and Technology")
    plt.title("THE World to Engineering and Technology Ranking Model")

    inds2comp = list(set(range(len(wranks2))) - set(inds2))
    wnames2 = wnames2[inds2comp]
    wranks2 = wranks2[inds2comp]
    wcountries2 = wcountries2[inds2comp]
    wranks2 = np.round(linfit(wranks2, ftthe2[0], ftthe2[1])) + 10

    wnames = np.hstack([wnames, wnames2])
    wcountries = np.hstack([wcountries, wcountries2])
    wranks = np.hstack([wranks, wranks2])

    inds = np.argsort(wranks)
    wnames = wnames[inds]
    wranks = wranks[inds]
    wcountries = wcountries[inds]

    return wnames, wranks, wcountries
