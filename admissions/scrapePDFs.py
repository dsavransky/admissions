import io
import string
import pdfminer
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.pdfpage import PDFPage
import glob
import numpy as np


def scrapePDFs(ids, profs, facconsulted):

    # gather PDF files and ensure we have all we need
    files = glob.glob("Candidates/*.pdf")
    havefiles = [int(f.split("_")[-1].split(".")[0]) for f in files]

    assert len(set(ids) - set(havefiles)) == 0, "Missing files for: {}".format(
        set(ids) - set(havefiles)
    )

    # align files with ids
    inds = np.array([np.where(havefiles == n)[0][0] for n in ids])

    havefiles = np.array(havefiles)[inds]
    files = np.array(files)[inds]

    # allocate outputs
    out = np.zeros(files.shape, dtype=object)
    badpages = []

    # split compund last names
    allprofs = []
    allprofssplit = []
    for p in profs:
        if (" " in p) and ("van der" not in p):
            tmp = p.split(" ")
            for t in tmp:
                allprofs.append(p)
                allprofssplit.append(t)
        else:
            allprofs.append(p)
            allprofssplit.append(p)

    # define text translation
    trans = str.maketrans(
        string.punctuation + "’\n", " " * (len(string.punctuation) + 2)
    )
    profstrans = np.array(
        [" {} ".format(prof.lower().translate(trans)) for prof in allprofssplit]
    )

    facconsulted = facconsulted.astype(str)
    facconsulted[facconsulted == "nan"] = ""

    # Perform layout analysis for all text
    laparams = pdfminer.layout.LAParams()
    setattr(laparams, "all_texts", True)

    for ii, fname in enumerate(files):
        print("%d/%d: %s" % (ii, len(files), fname))

        rsrcmgr = PDFResourceManager()
        outfp = io.StringIO("")
        device = TextConverter(rsrcmgr, outfp, laparams=laparams)

        with open(fname, "rb") as fp:
            interpreter = PDFPageInterpreter(rsrcmgr, device)
            for j, page in enumerate(PDFPage.get_pages(fp, check_extractable=True)):
                try:
                    interpreter.process_page(page)
                except: # noqa
                    print("Unparsable page encountered.")
                    if fname not in badpages:
                        badpages.append(fname)

        txt = outfp.getvalue()
        device.close()
        outfp.close()
        txt = txt + " " + facconsulted[ii] + " "

        tmp = []
        for jj, prof in enumerate(profstrans):
            if prof in txt.lower().translate(trans):
                tmp.append(allprofs[jj])

        out[ii] = ", ".join(np.unique(tmp))

    return out
