from string import ascii_uppercase
for j,c in enumerate(ascii_uppercase):
    print("Reader {}".format(c))
    if j == 19:
        break

from faker import Faker
fake = Faker()

for _ in range(200):
    tmp = fake.name()
    while ("DDS" in tmp) or ("PhD" in tmp) or ("MD" in tmp) or \
            ("DVM" in tmp) or ("Dr." in tmp):
        tmp = fake.name()

    print(tmp)



############## generate some fake survey response data for testing purposes
#submit one real entry first

surveyname = "Astro Initial Read Survey for Reader A"
surveyId = c.getSurveyId(surveyname)
tmpdir = c.exportSurvey(surveyId)
tmpfile = os.path.join(tmpdir, surveyname + ".csv")
assert os.path.isfile(tmpfile), "Survey results not where expected."

res = pandas.read_csv(tmpfile, header=[0, 1, 2])
row = res.copy(deep=True)

scoreOptions = [1, 2, 3, 4]
ss2 = np.array(list(set(np.arange(len(ss))) - set(np.where(ss ==  res['Q1'].values[0][0])[0])))+1
for j,s in enumerate(ss2):
    row['Q1'] = s
    row['Q2'] = np.random.choice(scoreOptions)
    row['Q3'] = np.random.choice(scoreOptions)
    row['Q4'] = np.random.choice(scoreOptions)
    row['Q5'] = np.random.choice(scoreOptions)
    row['Q6'] = np.random.choice(scoreOptions)
    if j == 0:
        out = row.copy(deep=True)
    else:
        out = out.append(row,ignore_index=True)

out.to_csv('fake_data.csv',index=False)

#import with legacy importer

