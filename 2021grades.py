from admissions.grades import *

# scrape website
scrapegradedata()

# grab parsed website data
gradedat = np.load('grade_data.npz')
names = gradedat['titles']
countries = gradedat['countries']
intlgpas = gradedat['intlgpas']
usgpas = gradedat['usgpas']

# grab our university list
tmp = pandas.ExcelFile('university_rankings.xlsx')
lookup = tmp.parse('lookup')
tmp.close()
lnames = lookup['Name'].values
lcountries = lookup['Country'].values

# some initial corrections
names[names == 'Northeastern University'] = 'Northeastern University (China)'
countries[names == "Xi'an Jiaotong-Liverpool University"] = 'China'
countries[names == "University of Macau"] = 'Macau'
countries[names == "Macau University of Science and Technology"] = 'Macau'
countries[names == "University of Waterloo"] = 'Canada'
countries[countries == 'Scotland'] = 'United Kingdom'
names[names == 'DEFAULT Great Britain'] = 'DEFAULT United Kingdom'
names[names == 'National Institute of Technology'] = 'National Institute of Technology, Tiruchirappalli'
countries = np.array(cc.convert(names = list(countries), to = 'name_short'))

# remove any entries without data (and the redundant default Scotland)
# also remove the 'before' entries'
bad = (intlgpas == '') | (usgpas == '') | (names == 'DEFAULT Scotland') | \
    (names == 'Shanghai Jiaotong University - Before 2004') |\
    (names == 'Shanghai Normal University - Before 2013') |\
    (names == 'Xiamen University - Between 2002 and 2012') |\
    (names == 'Indian Institute of Technology')
names = names[~bad]
countries = countries[~bad]
intlgpas = intlgpas[~bad]
usgpas = usgpas[~bad]

# there are also some duplicates
dups = np.unique(names, return_counts=True)
dups = dups[0][dups[1]>1]
for d in dups:
    ind = np.where(names == d)[0].max()
    names = np.delete(names,ind)
    countries = np.delete(countries,ind)
    intlgpas = np.delete(intlgpas,ind)
    usgpas = np.delete(usgpas,ind)

#now lets build up the final list
#first, clean up all the defaults 'DEFAULTS'
defaults = np.array(['DEFAULT' in n for n in names])
names[names == 'DEFAULT Argetina'] = 'Argentina'
names[defaults] = np.array(['DEFAULT '+c for c in cc.convert(names = list(names[defaults]), to = 'name_short')])

#load known aliases and apply
tmp = pandas.ExcelFile('grades_aliases.xlsx')
aliases = tmp.parse('aliases')
tmp.close()

for k,v in zip(aliases['Alias'].values, aliases['Standard Name'].values):
    names[names == k] = v

#check that the matching ones are in the correct countries
match = list(set(names).intersection(set(lnames)))
inds = np.array([n in match for n in names])
chk1 = np.hstack([countries[names == m] == lcountries[lnames ==m] for m in match])
assert np.all(chk1), "Some country matches failed"
#bad = np.array(match)[~chk1]
#[(countries[names == m],lcountries[lnames ==m]) for m in bad]

#now lets clean up all the after, percentage and scale cruft
#should already have removed all the before and between
assert np.where(['Before' in n for n in names])[0].size == 0
assert np.where(['Between' in n for n in names])[0].size == 0

afterp = re.compile(r'([\s\S]*) - After \d+[\s\S]*')
for j,n in enumerate(names):
    if afterp.match(n):
        print("{} : '{}'".format(n,afterp.match(n).groups()[0]))
        names[j] = afterp.match(n).groups()[0]

percentagep = re.compile(r'([\s\S]*) - Percent[\s\S]*')
for j,n in enumerate(names):
    if percentagep.match(n):
        print("{} : '{}'".format(n,percentagep.match(n).groups()[0]))
        names[j] = percentagep.match(n).groups()[0]

scalep = re.compile(r'([\s\S]*) - \d+[\s\S]* [s|S]cale')
for j,n in enumerate(names):
    if scalep.match(n):
        print("{} : '{}'".format(n,scalep.match(n).groups()[0]))
        names[j] = scalep.match(n).groups()[0]


#update lookup table with new universities
nomatch = list(set(names) - set(lnames) - set(names[defaults]))
inds = np.hstack([np.where(names == n)[0] for n in nomatch])

tmp = pandas.DataFrame({'Name':names[inds],
                        'Rank':np.array([200]*len(inds)),
                        'Country':countries[inds]})

tmp= tmp.iloc[np.unique(tmp['Name'].values,return_index=True)[1]]
lookup = lookup.append(tmp)
lookup = lookup.sort_values(by=['Rank']).reset_index(drop=True)

ew = pandas.ExcelWriter('university_rankings.xlsx',options={'encoding':'utf-8'})
lookup.to_excel(ew,sheet_name='lookup',index=False)
ew.save()
ew.close()


#some more data cleanup
intlgpas[names == 'Ganpat University'] = '10/9/8/7/6/5/0'
usgpas[names == 'Ganpat University'] = '4.0/3.6/3.3/3.0/2.3/2.0/0'

#establish gpa scale for each entry and save updated data
gpascale = []
for i in intlgpas:
    gpascale.append(np.array(i.split('/')).astype(float).max())
gpascale = np.array(gpascale)


names = np.hstack([names,'Massachusetts Institute of Technology'])
countries = np.hstack([countries,'United States'])
gpascale = np.hstack([gpascale,5])
intlgpas = np.hstack([intlgpas,'5/4/3/2/0'])
usgpas = np.hstack([usgpas,'4/3/2/1/0'])

pout = pandas.DataFrame({'Name':names,
                         'Country':countries,
                         'GPAScale':gpascale,
                         'SchoolGPA':intlgpas,
                         '4ptGPA':usgpas})

ew = pandas.ExcelWriter('grade_data.xlsx',options={'encoding':'utf-8'})
pout.to_excel(ew,sheet_name='grades',index=False)
ew.save()
ew.close()



#------------------------------------------------------
#original machinery for getting aliases
rndict = {}
rndict['Manipal University'] = 'Manipal Academy of Higher Education, Manipal, Karnataka, India'

newnames = []
newcountries = []

for n in nomatch:
    if (n in rndict) or (n in newnames):
        continue
    currc = countries[names == n]
    tmp = lnames[lcountries == currc]
    if len(tmp) > 0:
        res = process.extractOne(n,tmp)
        if res[1] >= 98:
            rndict[n] = res[0]
            print("{} {} {} : {}?  ".format(currc,res[1],n,res[0]))
        else:
            instr = input("{} {} {} : {}?  ".format(currc,res[1],n,res[0]))
            if instr:
                if instr == 'n':
                    newnames.append(n)
                    newcountries.append(currc)
                else:
                    rndict[n] = instr
            else:
                rndict[n] = res[0]
    else:
        newnames.append(n)
        newcountries.append(countries[names == n])


vals = []
valo = []
for key, val in rndict.items():
    vals.append(val)
    valo.append(key)
    names[names == key] = val

aliasesout = pandas.DataFrame({'Alias':valo,
                            'Standard Name':vals})
aliasesout = aliasesout.iloc[np.unique(aliasesout['Alias'].values,return_index=True)[1]]
aliasesout = aliasesout.sort_values(by=['Standard Name']).reset_index(drop=True)

#write utils
ew = pandas.ExcelWriter('grades_aliases.xlsx',options={'encoding':'utf-8'})
aliasesout.to_excel(ew,sheet_name='aliases',index=False)
ew.save()
ew.close()



