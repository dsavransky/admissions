#%pylab --no-import-all
from admissions.rankings import *
import pandas
from fuzzywuzzy import fuzz, process

# Here we are going to create our university lookup list
#-------------------------------------

#scrape these:
#https://www.usnews.com/best-colleges/rankings/engineering-doctorate
#https://www.usnews.com/best-colleges/rankings/engineering-overall
#https://www.usnews.com/best-colleges/rankings/national-liberal-arts-colleges
#https://www.usnews.com/best-colleges/rankings/national-universities
#https://www.usnews.com/best-colleges/rankings/hbcu

#https://www.topuniversities.com/university-rankings/university-subject-rankings/2020/engineering-technology
#https://www.topuniversities.com/university-rankings/world-university-rankings/2021

#https://www.timeshighereducation.com/world-university-rankings/2021/subject-ranking/engineering-and-IT#!/page/0/length/25/sort_by/rank/sort_order/asc/cols/stats
#https://www.timeshighereducation.com/world-university-rankings/2021/world-ranking#!/page/0/length/25/sort_by/rank/sort_order/asc/cols/stats

# We start with the US News and World Report data to generate the US list
usnames, usranks = genuslist()

# QS World list
names, ranks, countries = genqslist()

# we're going to merge the us and qs lists now

#look at US school subset with continuous ranks
#we should have all of these in our US list already
usn = names[(countries == 'United States') & (ranks < 400)]
usr = ranks[(countries == 'United States') & (ranks < 400)]
#this one is ambiguous:
usn[usn=='Pennsylvania State University'] = 'Pennsylvania State University--University Park'

nomatch = list(set(usn) - set(usnames))
for n in nomatch:
    res = process.extractOne(n,usnames)
    if res[1] >= 90:
        usn[usn == n] = res[0]
        print("Replacing {} : {}".format(n,res[0]))

#missed these:
usn[usn == 'Virginia Polytechnic Institute and State University'] = 'Virginia Tech'
usn[usn == 'The Ohio State University'] = 'Ohio State University--Columbus'

indsus = np.hstack([np.where(usnames == n)[0] for n in usn])

#linear fit works well here too
ftusqs,ftusqscov = curve_fit(linfit,usr,usranks[indsus])

plt.figure(6)
plt.clf()
plt.scatter(usr,usranks[indsus])
plt.plot([1,max(usr)],linfit(np.array([1,max(usr)]),ftusqs[0],ftusqs[1]))
plt.xlabel('World Rank')
plt.ylabel('US Rank')
plt.title('Qs Engineering and Technology Ranking Model')

#lets take a look at the above 400s
usn2 = names[(countries == 'United States') & (ranks > 400)]
usr2 = ranks[(countries == 'United States') & (ranks > 400)]
# again, ambiguity:
usn2[usn2 == 'City University of New York'] = "CUNY--City College"

nomatch = list(set(usn2) - set(usnames))
for n in nomatch:
    res = process.extractOne(n,usnames)
    if res[1] >= 90:
        usn2[usn2 == n] = res[0]
        print("Replacing {} : {}".format(n,res[0]))

# missed this:
usn2[usn2 == "Stony Brook University, State University of New York"] = 'Stony Brook University--SUNY'

blks = np.unique(ranks)[np.unique(ranks) > 400]
eranks = []
for b in blks:
    tmpi = usn2[usr2 == b]
    if len(tmpi)>0:
        inds = np.hstack([np.where(usnames == n)[0] for n in tmpi])
        eranks.append(np.median(usranks[inds]))
    else:
        eranks.append(np.nan)
eranks = np.array(eranks)
# this ends up being non-monotonic, so we'll force some smoothness to it
eranks = np.round(linfit(np.hstack([blks[:-1]+np.diff(blks)/2,550]),ftusqs[0],ftusqs[1]))

# convert to our ranking scale
ranksb = np.round(linfit(ranks,ftusqs[0],ftusqs[1]))
for j,b in enumerate(blks):
    ranksb[ranks == b] = eranks[j]

# drop US from list
inds = (countries != 'United States')
worldnames = names[inds]
worldranks = ranksb[inds]
worldcountries = countries[inds]

# put everyting together
allnames = np.hstack((usnames,worldnames))
allranks = np.hstack((usranks,worldranks))
allcountries = np.hstack((['United States']*len(usnames),worldcountries))

#------------------------------
# list from THE - this one has a much shorter linear regime overlap with US schools
# so we'll match it against our full list to date

wnames, wranks, wcountries = genthelist()

#grab existing alias list
tmp = pandas.ExcelFile('university_aliases.xlsx')
aliases = tmp.parse('aliases')
tmp.close()

rndict = {}
for k,v in zip(aliases['Alias'].values, aliases['Standard Name'].values):
    rndict[k] = v
    wnames[wnames == k] = v

#remaining US schools are medical schools so lets get rid of them
nomatch = list(set(wnames) - set(allnames))
inds = np.hstack([np.where(wnames == n)[0] for n in nomatch])
tmp = wnames[inds][wcountries[inds] == 'United States']
inds2 = np.hstack([np.where(wnames == n)[0] for n in tmp])
wnames = np.delete(wnames,inds2)
wranks = np.delete(wranks,inds2)
wcountries = np.delete(wcountries,inds2)


# find intersection with all schools so far
tmp = list(set(wnames[wranks<101]).intersection(set(allnames)))
indsall = np.hstack([np.where(allnames == n)[0] for n in tmp])
indsworld = np.hstack([np.where(wnames == n)[0] for n in tmp])
ft6,ft6cov = curve_fit(linfit,wranks[indsworld],allranks[indsall])
ft6b = dopca(wranks[indsworld],allranks[indsall])

plt.figure(8)
plt.clf()
plt.scatter(wranks[indsworld],allranks[indsall])
plt.plot([1,max(wranks[indsworld])],linfit(np.array([1,max(wranks[indsworld])]),ft6[0],ft6[1]))
plt.plot([1,max(wranks[indsworld])],linfit(np.array([1,max(wranks[indsworld])]),ft6b[0],ft6b[1]))
plt.xlabel('THE World Rank')
plt.ylabel('US+QS Rank')
plt.title('THE Conversion Model')

wranks2 = wranks.copy().astype(float)
wranks2[wranks2 < 101] = np.round(linfit(wranks2[wranks2 < 101] ,ft6[0],ft6[1]))

# now lets see what the lower blocks map to
blks = np.unique(wranks)[np.unique(wranks) > 100]
eranks = []
for b in blks:
    tmpi = list(set(wnames[wranks==b]).intersection(set(allnames)))
    if tmpi:
        indsalli = np.hstack([np.where(allnames == n)[0] for n in tmpi])
        eranks.append(np.median(allranks[indsalli]))
    else:
        eranks.append(np.nan)
eranks = np.round(np.array(eranks))
#want to enforce a monotonic sequence
eranks = np.round(linfit(np.hstack([blks[:-1]+np.diff(blks)/2,1500]),ft6[0],ft6[1]))
for j in range(len(blks)):
    wranks2[wranks2 == blks[j]] = eranks[j]


#throw out matches
nomatch = list(set(wnames) - set(allnames))
inds = np.hstack([np.where(wnames == n)[0] for n in nomatch])
wnames = wnames[inds]
wranks2 = wranks2[inds]
wcountries = wcountries[inds]

#put everything together again and sort
allnames = np.hstack((allnames,wnames))
allranks = np.hstack((allranks,wranks2))
allcountries = np.hstack((allcountries,wcountries))

inds = np.argsort(allranks)
allnames = allnames[inds]
allranks = allranks[inds]
allcountries = allcountries[inds]
allranks[allranks > 200] = 200

#write to spreadsheet
pout = pandas.DataFrame({'Name':allnames,
                         'Rank':allranks,
                         'Country':allcountries})

ew = pandas.ExcelWriter('university_rankings.xlsx',options={'encoding':'utf-8'})
pout.to_excel(ew,sheet_name='lookup',index=False)
ew.save()
ew.close()






#--------------------------------------
#this is all machinery for the initial THE-QS alias list
# orig manual matches
rndict = {}
rndict['Miami University'] = 'Miami University--Oxford'
rndict['Indiana University'] = 'Indiana University--Bloomington'
rndict['Ohio State University (Main campus)'] = 'Ohio State University--Columbus'
rndict['Florida Agricultural and Mechanical University'] = 'Florida A&M University -- Florida State University'
rndict['Penn State (Main campus)'] = 'Pennsylvania State University--University Park'
rndict['Binghamton University, State University of New York'] = 'Binghamton University--SUNY'
rndict['Virginia Polytechnic Institute and State University'] = 'Virginia Tech'
rndict['Rutgers, the State University of New Jersey'] = 'Rutgers University--New Brunswick'
rndict['Pontifical Catholic University of Rio de Janeiro (PUC-Rio)'] = 'Pontifícia Universidade Católica do Rio de Janeiro'
rndict['University of São Paulo']='Universidade de São Paulo'
rndict['Federal University of Rio Grande do Sul']='Universidade Federal do Rio Grande Do Sul'
rndict['Federal University of Minas Gerais']='Universidade Federal de Minas Gerais'
rndict['Federal University of Santa Catarina']='Universidade Federal de Santa Catarina'
rndict['Federal University of São Carlos']='Universidade Federal de São Carlos (UFSCar)'
rndict['Federal University of Rio de Janeiro']='Universidade Federal do Rio de Janeiro'
rndict['University of Campinas']='Universidade Estadual de Campinas (Unicamp)'
rndict['University of Chile']='Universidad de Chile'
rndict['University of Concepción'] = 'Universidad de Concepción'
rndict['University of Santiago, Chile (USACH)'] = 'Universidad de Santiago de Chile (USACH)'
rndict['University of Antioquia'] = 'Universidad de Antioquia'
rndict['University of the Andes, Colombia'] = 'Universidad de los Andes'
rndict['University of Lorraine']='Université de Lorraine'
rndict['Paris Sciences et Lettres – PSL Research University Paris']='Université PSL'
rndict['University of Strasbourg']='Université de Strasbourg'
rndict['University of Lille']='Université de Lille'
rndict['University of Lorraine']='Université de Lorraine'
rndict['University of Technology of Compiègne'] = 'Université de Technologie de Compiègne (UTC)'
rndict['University of Malaya'] = 'Universiti Malaya (UM)'
rndict['National Polytechnic University (IPN)'] = 'Instituto Politécnico Nacional (IPN)'
rndict['National Autonomous University of Mexico'] = 'Universidad Nacional Autónoma de México  (UNAM)'
rndict['Polytechnic University of Bucharest'] = 'University POLITEHNICA of Bucharest'
rndict['École Polytechnique Fédérale de Lausanne'] = 'EPFL'
rndict['Pontifical Catholic University of Chile'] = 'Pontificia Universidad Católica de Chile (UC)'
rndict['State University of New York Albany'] = 'University at Albany--SUNY'
rndict['National University of Córdoba'] = 'Universidad Nacional de Córdoba - UNC'
rndict['University of Liège'] = 'Université de Liège'
rndict['Federal University of São Paulo (UNIFESP)'] = 'Universidade Federal de São Paulo'
rndict['University of Montreal'] = 'Université de Montréal'
rndict['University of the Andes, Chile'] = 'Universidad de los Andes - Chile'
rndict['Pontifical Catholic University of Valparaíso'] = 'Pontificia Universidad Católica de Valparaíso'
rndict['Pontifical Javeriana University'] = 'Pontificia Universidad Javeriana'
rndict['University of Havana'] = 'Universidad de La Habana'
rndict['University of Rennes 1'] = 'Université de Rennes 1'
rndict['University of Paris'] = 'Université de Paris'
rndict['Technical University of Berlin'] = 'Technische Universität Berlin (TU Berlin)'
rndict['University of Hamburg']='Universität Hamburg'
rndict['University of Potsdam']='Universität Potsdam'
rndict['University of Stuttgart']='Universität Stuttgart'
rndict['University of Mannheim']='Universität Mannheim'
rndict['University of Indonesia']='University of Indonesia'
rndict['Padjadjaran University'] = 'Universitas Padjadjaran'
rndict['Universitas Gadjah Mada']='Gadjah Mada University'
rndict['Université Saint-Joseph de Beyrouth'] = 'Saint Joseph University of Beirut (USJ)'
rndict['Metropolitan Autonomous University']='Universidad Autónoma Metropolitana (UAM)'
rndict['Monterrey Institute of Technology']='Tecnológico de Monterrey'
rndict['University of Guadalajara']='Universidad de Guadalajara (UDG)'
rndict['Pontifical Catholic University of Peru'] = 'Pontificia Universidad Católica del Perú'
rndict['Cracow University of Technology']='Cracow University of Technology (Politechnika Krakowska)'
rndict['Catholic University of Portugal']= 'Universidade Católica Portuguesa - UCP'
rndict['NOVA University of Lisbon']='Universidade Nova de Lisboa'
rndict['National Technical University of Ukraine National Technical University of Ukraine "Igor Sik']='National Technical University of Ukraine National Technical University of Ukraine "Igor Sikorsky Kyiv Polytechnic Institute"'
rndict['National Technical University Kharkiv Polytechnic Institute']='National Technical University  National Technical University "Kharkiv Polytechnic Institute"'
rndict['Simón Bolívar University'] = 'Universidad Simón Bolívar (USB)'
rndict['Vietnam National University (Ho Chi Minh City)'] = 'Viet Nam National University Ho Chi Minh City (VNU-HCM)'

nomatch = list(set(wnames) - set(allnames))
skipped = []
nocountry = []


for n in nomatch:
    if (n in rndict) or (n in skipped):
        continue
    tmp = allnames[allcountries == wcountries[wnames == n]]
    if len(tmp) > 0:
        res = process.extractOne(n,tmp)
        if res[1] >= 98:
            rndict[n] = res[0]
            print("{} {} : {}?  ".format(res[1],n,res[0]))
        elif res[1] >= 90:
            instr = input("{} {} : {}?  ".format(res[1],n,res[0]))
            if instr:
                if instr == 'n':
                    skipped.append(n)
                else:
                    rndict[n] = instr
            else:
                rndict[n] = res[0]
    else:
        nocountry.append(n)



nomatch1 = list(set(wnames[wcountries == 'Ukraine']) - set(allnames))
for n in nomatch1:
    tmp = allnames[allcountries == wcountries[wnames == n]]
    if len(tmp) > 0:
        res = process.extractOne(n.lower(),tmp)
        #if res[1] >= 80:
        print("{}  rndict['{}']='{}'".format(res[1],n,res[0]))


vals = []
valo = []
for key, val in rndict.items():
    vals.append(val)
    valo.append(key)
    wnames[wnames == key] = val

aliasesout = pandas.DataFrame({'Alias':valo,
                            'Standard Name':vals})
aliasesout = aliasesout.iloc[np.unique(aliasesout['Alias'].values,return_index=True)[1]]
aliasesout = aliasesout.sort_values(by=['Standard Name']).reset_index(drop=True)
#write utils
ew = pandas.ExcelWriter('university_aliases.xlsx',options={'encoding':'utf-8'})
aliasesout.to_excel(ew,sheet_name='aliases',index=False)
ew.save()
ew.close()

#remaining US schools are medical schools so lets get rid of them
nomatch = list(set(wnames) - set(allnames))
inds = np.hstack([np.where(wnames == n)[0] for n in nomatch])
tmp = wnames[inds][wcountries[inds] == 'United States']
inds2 = np.hstack([np.where(wnames == n)[0] for n in tmp])
wnames = np.delete(wnames,inds2)
wranks = np.delete(wranks,inds2)
wcountries = np.delete(wcountries,inds2)

#lets see if we missed anymore
nomatch = set(wnames) - set(allnames)
nomatch = list(nomatch - set(nocountry))
inds = np.hstack([np.where(wnames == n)[0] for n in nomatch])
ucs = np.unique(wcountries[inds])
for c in ucs:
    print(c)
    print(np.sort(wnames[inds][wcountries[inds] == c]))
    print(np.sort(allnames[allcountries == c]))

