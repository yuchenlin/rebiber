# Rebiber: A tool for normalizing bibtex with official info.

We often cite papers using their arXiv versions without noting that they are already **PUBLISHED** in some conferences. These unofficial bib entries might violate rules about submissions or camera-ready versions for some conferences.
We introduce **Rebiber**, a simple tool in Python to fix them automatically. It is based on the official conference information from the [DBLP](https://dblp.org/) or [the ACL anthology](https://www.aclweb.org/anthology/) (for NLP confernces)! You can check the list of supported conferences [here](#supported-conferences).
Apart from handling outdated arXiv citations, **Rebiber** also normalizes citations in a unified way (DBLP-style), supporting abbreviation and value selection.

You can use [this google colab notebook](https://colab.research.google.com/drive/12oQcLs25CFjI4evsFlWfKD1DfTEiqyCN?usp=sharing) as a simple web demo.
And [this](https://rebiber.herokuapp.com/) is a beta version of our web app for Rebiber (still under development).

## Changelogs

- **2021.02.08**
  We now support multiple useful feaures: 1) turning off some certain values, e.g., "-r url,pages,address" for removing the values from the output, 2) using abbr. to shorten the booktile values, e.g., `Proceedings of the .* Annual Meeting of the Association for Computational Linguistics` --> `Proc. of ACL`. More examples are [here.](https://github.com/yuchenlin/rebiber/blob/main/rebiber/abbr.tsv)
- **2021.01.30**
  We build a colab notebook as a simple web demo. [link](https://colab.research.google.com/drive/12oQcLs25CFjI4evsFlWfKD1DfTEiqyCN?usp=sharing)

## Installation

```bash
pip install rebiber -U
rebiber --update  # update the bib data and the abbr. info
```

OR

```bash
git clone https://github.com/yuchenlin/rebiber.git
cd rebiber/
pip install -e .
```

If you would like to use the latest github version with more bug fixes, please use the second installation method.

## Usage（v1.1.1）

Normalize your bibtex file with the official converence information:

```bash
rebiber -i /path/to/input.bib -o /path/to/output.bib
```

You can find a pair of example input and output files in `rebiber/example_input.bib` and `rebiber/example_output.bib`.

| argument | usage                                                                                                                                                                                            |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `-i`     | or `--input_bib`. The path to the input bib file that you want to update                                                                                                                         |
| `-o`     | or `--output_bib`. The path to the output bib file that you want to save. If you don't specify any `-o` then it will be the same as the `-i`.                                                    |
| `-r`     | or `--remove`. A comma-seperated list of value names that you want to remove, such as "-r pages,editor,volume,month,url,biburl,address,publisher,bibsource,timestamp,doi". Empty by **default**. |
| `-s`     | or `--shorten`. A bool argument that is `"False"` by **default**, used for replacing `booktitle` with abbreviation in `-a`. Used as `-s True`.                                                   |
| `-d`     | or `--deduplicate`. A bool argument that is `"True"` by **default**, used for removing the duplicate bib entries sharing the same key. Used as `-d True`.                                        |
| `-l`     | or `--bib_list`. The path to the list of the bib json files to be loaded. Check [rebiber/bib_list.txt](rebiber/bib_list.txt) for the default file. Usually you don't need to set this argument.  |
| `-a`     | or `--abbr_tsv`. The list of conference abbreviation data. Check [rebiber/abbr.tsv](rebiber/abbr.tsv) for the default file. Usually you don't need to set this argument.                         |
| `-u`     | or `--update`. Update the local bib-related data with the lateset Github version.                                                                                                                |
| `-v`     | or `--version`. Print the version of current Rebiber.                                                                                                                                            |

<!-- Or
```bash
python rebiber/normalize.py \
  -i rebiber/example_input.bib \
  -o rebiber/example_output.bib \
  -l rebiber/bib_list.txt
``` -->

## Non-destructive Un-arXiver

For some users, replacing entire bibliography entries may be inconvient.
An alternative is to use the the unarxiver tool to detect outdated bibliography entries and print them to the terminal so the user can fix them. To do this, you can run:

```bash
python rebiber/arxiv.py mybibfile.bib
```

NOTE: unarxiver has to build a cache first, which can take quite a while. By default, the script parallelizes across all cores. You might also find pypy faster than regular python. After running it, you should see output like:

```
Original entry:
@article{miller2017parlai,
 author = {{Miller}, A.~H. and {Feng}, W. and {Fisch}, A. and {Lu}, J. and {Batra}, D. and {Bordes}, A. and {Parikh},
D. and {Weston}, J.},
 eprint = {arXiv:1705.06476},
 journal = {arXiv:1705.06476},
 title = {Parl{AI}: A Dialog Research Software Platform},
 url = {https://arxiv.org/abs/1705.06476},
 year = {2017}
}


New Entry:
@inproceedings{miller-etal-2017-parlai,
    title = "{P}arl{AI}: A Dialog Research Software Platform",
    author = "Miller, Alexander  and
      Feng, Will  and
      Batra, Dhruv  and
      Bordes, Antoine  and
      Fisch, Adam  and
      Lu, Jiasen  and
      Parikh, Devi  and
      Weston, Jason",
    booktitle = "Proceedings of the 2017 Conference on Empirical Methods in Natural Language Processing: System
Demonstrations",
    month = sep,
    year = "2017",
    address = "Copenhagen, Denmark",
    publisher = "Association for Computational Linguistics",
    url = "https://www.aclweb.org/anthology/D17-2014",
    doi = "10.18653/v1/D17-2014",
    pages = "79--84",
}
```

## Example Input and Output

An example input entry with the arXiv information (from Google Scholar or somewhere):

```bib
@article{lin2020birds,
	title={Birds have four legs?! NumerSense: Probing Numerical Commonsense Knowledge of Pre-trained Language Models},
	author={Lin, Bill Yuchen and Lee, Seyeon and Khanna, Rahul and Ren, Xiang},
	journal={arXiv preprint arXiv:2005.00683},
	year={2020}
}

```

An example normalized output entry with the official information:

```bib
@inproceedings{lin2020birds,
    title = "{B}irds have four legs?! {N}umer{S}ense: {P}robing {N}umerical {C}ommonsense {K}nowledge of {P}re-{T}rained {L}anguage {M}odels",
    author = "Lin, Bill Yuchen  and
      Lee, Seyeon  and
      Khanna, Rahul  and
      Ren, Xiang",
    booktitle = "Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing (EMNLP)",
    month = nov,
    year = "2020",
    address = "Online",
    publisher = "Association for Computational Linguistics",
    url = "https://www.aclweb.org/anthology/2020.emnlp-main.557",
    doi = "10.18653/v1/2020.emnlp-main.557",
    pages = "6862--6868",
}
```

## Supported Conferences

The `bib_list.txt` contains a list of converted json files of the official bib data. In this repo, we now support the full [ACL anthology](https://www.aclweb.org/anthology/), i.e., all papers that are published at \*CL conferences (ACL, EMNLP, NAACL, etc.) as well as workshops.
Also, we support any conference proceedings that can be downloaded from DBLP, for example, ICLR2020.

The following conferences are supported and their bib/json files are in our `data` folder. You can turn each item on/off in `bib_list.txt`. **Please feel free to create PR for adding new conferences following [this](#adding-a-new-conference)!**

| Name               | Years           |
| ------------------ | --------------- |
| ACL Anthology      | (until 2021-01) |
| AAAI               | 2010 -- 2020    |
| AISTATS            | 2013 -- 2020    |
| ALENEX             | 2010 -- 2020    |
| ASONAM             | 2010 -- 2019    |
| BigDataConf        | 2013 -- 2019    |
| BMVC               | 2010 -- 2020    |
| CHI                | 2010 -- 2020    |
| CIDR               | 2009 -- 2020    |
| CIKM               | 2010 -- 2020    |
| COLT               | 2000 -- 2020    |
| CVPR               | 2000 -- 2020    |
| ICASSP             | 2015 -- 2020    |
| ICCV               | 2003 -- 2019    |
| ICLR               | 2013 -- 2020    |
| ICML               | 2000 -- 2020    |
| IJCAI              | 2011 -- 2020    |
| KDD                | 2010 -- 2020    |
| MLSys              | 2019 -- 2020    |
| MM                 | 2016 -- 2020    |
| NeurIPS            | 2000 -- 2020    |
| RECSYS             | 2010 -- 2020    |
| SDM                | 2010 -- 2020    |
| SIGIR              | 2010 -- 2020    |
| SIGMOD             | 2010 -- 2020    |
| SODA               | 2010 -- 2020    |
| STOC               | 2010 -- 2020    |
| UAI                | 2010 -- 2020    |
| WSDM               | 2008 -- 2020    |
| WWW (The Web Conf) | 2001 -- 2020    |

**Thanks for [Anton Tsitsulin](http://tsitsul.in/)'s great work on collecting such a complete set bib files!**

<!--
python bib2json.py -i data/iclr2020.bib -o data/iclr2020.json
python bib2json.py -i data/iclr2019.bib -o data/iclr2019.json
python bib2json.py -i data/iclr2018.bib -o data/iclr2018.json
python bib2json.py -i data/aaai2020.bib -o data/aaai2020.json
 -->

## Adding a new conference

You can manually add any conferences from DBLP by downloading their bib files to our `raw_data` folder, and run a prepared script `add_conf.sh`.

Take ICLR2020 and ICLR2019 as an example:

- Step 1: Go to [DBLP](https://dblp.org/db/conf/iclr/iclr2020.html)
- Step 2: Download the bib files, and put them here as `raw_data/iclr2020.bib` and `raw_data/iclr2019.bib` (name should be in the format as {conf_name}{year}.bib)
- Step 3: Run script

```bash
bash add_conf.sh iclr 2019 2020
```

## Contact

Please email yuchen.lin@usc.edu or create Github issues here if you have any questions or suggestions.
