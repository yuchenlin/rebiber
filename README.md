# Rebiber: A tool for normalizing bibtex with official info.

We often cite papers using their arXiv versions without noting that they are already __PUBLISHED__ in some conferences such as ACL, EMNLP, NAACL, ICLR or AAAI. These unofficial bib entries might violate rules about submissions or camera-ready versions for some conferences. 
We introduce __Rebiber__, a simple tool in Python to fix them automatically. It is on their official conference information from the DBLP or the ACL anthology (for NLP confernces)! You can check the list of suported conferences [here](#supported-conferences).


## Installation

```bash
pip install rebiber -U
```

OR 

```bash
git clone https://github.com/yuchenlin/rebiber.git
cd rebiber/
pip install -e .
```


## Usage
To normalize your bibtex file with the official converence information.

```bash 
rebiber -i /path/to/input.bib -o /path/to/output.bib
```
You can find a pair of example input and output files in `rebiber/example_input.bib` and `rebiber/example_output.bib`.
You can also specify your own bib list files by `-l /path/to/bib_list.txt`. If you don't specify any `-o` then it will be the same as the `-i`.
<!-- Or 
```bash
python rebiber/normalize.py \
  -i rebiber/example_input.bib \
  -o rebiber/example_output.bib \
  -l rebiber/bib_list.txt
``` -->


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

The `bib_list.txt` contains a list of converted json files of the official bib data. In this repo, we now support the full [ACL anthology](https://www.aclweb.org/anthology/), i.e., all papers that are published at *CL conferences (ACL, EMNLP, NAACL, etc.) as well as workshops.
Also, we support any conference proceedings that can be downloaded from DBLP, for example, ICLR2020.

The following conferences are supported and their bib/json files are in our `data` folder. You can turn each item on/off in `bib_list.txt`. **Please feel free to create PR for adding new conferences following [this](#adding-a-new-conference)!** 

| Name | Years |
| --- | ----------- |
| ACL Anthology |  (until 2021-01) |
| AAAI | 2010 -- 2020 |
| AISTATS | 2013 -- 2020 |
| ALENEX | 2010 -- 2020 |
| ASONAM | 2010 -- 2019 |
| BigDataConf | 2013 -- 2019 |
| BMVC | 2010 -- 2020 |
| CHI | 2010 -- 2020 |
| CIDR | 2009 -- 2020 |
| CIKM | 2010 -- 2020 |
| COLT | 2000 -- 2020 |
| CVPR | 2000 -- 2020 |
| ICASSP | 2015 -- 2020 |
| ICCV | 2003 -- 2019 |
| ICLR | 2013 -- 2020 |
| ICML | 2000 -- 2020 |
| IJCAI | 2011 -- 2020 |
| KDD | 2010 -- 2020 |
| NeurIPS | 2000 -- 2020 |
| RECSYS | 2010 -- 2020 |
| SDM | 2010 -- 2020 |
| SIGIR | 2010 -- 2020 |
| SIGMOD | 2010 -- 2020 |
| SODA | 2010 -- 2020 |
| STOC | 2010 -- 2020 |
| UAI | 2010 -- 2020 |
| WSDM | 2008 -- 2020 |
| WWW (The Web Conf) | 2001 -- 2020 |


**Thanks for [Anton Tsitsulin](http://tsitsul.in/)'s great work on collecting such a complete set bib files!**

<!-- 
python bib2json.py -i data/iclr2020.bib -o data/iclr2020.json
python bib2json.py -i data/iclr2019.bib -o data/iclr2019.json
python bib2json.py -i data/iclr2018.bib -o data/iclr2018.json
python bib2json.py -i data/aaai2020.bib -o data/aaai2020.json
 -->


## Adding a new conference

You can manually add any conferences from DBLP by downloading its bib file to our `data` folder, then convert the conference bib file to the json format, and finally add its path to the `bib_list.txt`.

Take ICLR2020 as an example:

- Step 1: Go to https://dblp.org/db/conf/iclr/iclr2020.html 
- Step 2: Download the bib file, and put it here as `data/iclr2020.bib` 
- Step 3: Convert it to the json format.
```bash
python bib2json.py -i data/iclr2020.bib -o data/iclr2020.json
```
- Step 4: Add its path to `bib_list.txt`.

## Contact

Please email yuchen.lin@usc.edu or create Github issues here if you have any questions or suggestions. 
