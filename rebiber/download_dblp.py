# download bib files for major conferences for previous years till the current year from dblp
# please add conference short name below if it is missing

import os.path
import requests
import time
import datetime

confs = [
    "neurips",
    "nips",
    "icml",
    "iclr",
    # "eccv", #eccv does not work since it has different storing way
    "iccv",
    "bmvc",
    "cvpr",
    "accv",
    "miccai",
    # "ecml", #ecml does not work since it has different storing way
    "aaai",
    "ijcai",
    "kdd",
    "interspeech",
    "icassp",
    "chi",
    "sigir",
    "sigmod",
    "aistats",
    "uai",
    "www"
]
short_conf_names = {
    "neurips": "nips"
}
latest_year = datetime.date.today().year
years = list(range(2020, latest_year + 1))
max_try = 10
num_trials = 0
max_step = 5

for conf in confs:
    for year in years:
        cites = ""
        jsonfilename = f"./data/{conf}{year}.bib.json"
        bibfilename = f"./raw_data/{conf}{year}.bib"
        if os.path.isfile(jsonfilename) or os.path.isfile(bibfilename):
            # file already exist, no need to download
            print(f"Skipping {conf} {year} since it already exists")
            continue
        conf_short = short_conf_names.get(conf, conf)
        query_string = f"toc:db/conf/{conf_short}/{conf}{year}.bht:"
        step = 0        
        while step < max_step:
            print(f"Processing {conf} {year} at step {step} * 1000")
            # https://dblp.org/search/publ/api?q=toc%3Adb/conf/nips/neurips2024.bht%3A&h=1000&f=1000
            query_params = {
                "q": query_string,
                "h": 1000,
                "f": step * 1000,
                "format": "bib"
            }
            # s = f"https://dblp.org/search/publ/api?q=conf/{conf}/{year}&h=1000&f={step*1000}&format=bib"
            query_url = "https://dblp.org/search/publ/api"
            res = requests.get(query_url, params=query_params)
            time.sleep(5)
            if res.status_code != requests.codes.ok or "Too Many Requests" in res.text:
                print("Timeout! Sleep for one minute!")
                time.sleep(60)
                num_trials += 1
                if num_trials > max_try:
                    cites = ""
                    break
                else:
                    continue
            else:
                step += 1
                num_trials = 0
                if res.text == "":
                    print("stop")
                    break
                cites += res.text
        if cites == "":
            # skip this conference for this year
            print(f"No entries! Skipping {conf} {year}")
            continue
        with open(bibfilename, "w") as f:
            f.write(cites)
            time.sleep(15)