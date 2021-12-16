import io
import string
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.pdfpage import PDFPage
import os
import glob
import re
import numpy as np


def scrapePDFs(fullnames, profs):
    files = glob.glob("Candidates/*.pdf")
    havefiles = [",".join(os.path.split(f)[1].split("_")[:2]) for f in files]
    needfiles = [re.sub(r"[\s']", "", n) for n in fullnames]
    assert len(set(needfiles) - set(havefiles)) == 0

    needfiles = np.array(needfiles)
    havefiles = np.array(havefiles)
    inds = np.array([np.where(havefiles == n)[0][0] for n in needfiles])

    havefiles = havefiles[inds]
    files = np.array(files)[inds]

    out = np.zeros(files.shape, dtype=object)
    badpages = []
    trans = str.maketrans(
        string.punctuation + "’\n", " " * (len(string.punctuation) + 2)
    )
    for i, fname in enumerate(files):
        print("%d/%d: %s" % (i, len(files), fname))

        rsrcmgr = PDFResourceManager()
        outfp = io.StringIO("")
        device = TextConverter(rsrcmgr, outfp)

        with open(fname, "rb") as fp:
            interpreter = PDFPageInterpreter(rsrcmgr, device)
            for j, page in enumerate(PDFPage.get_pages(fp, check_extractable=True)):
                try:
                    interpreter.process_page(page)
                except:
                    print("Unparsable page encountered.")
                    if fname not in badpages:
                        badpages.append(fname)

        txt = outfp.getvalue()
        device.close()
        outfp.close()

        tmp = []
        for prof in profs:
            if " " + prof.lower().translate(trans) + " " in txt.lower().translate(
                trans
            ):
                tmp.append(prof)
        out[i] = ", ".join(tmp)

    return out
