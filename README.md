# Rebiber: A tool for normalizing bibtex with official info.

We often cite papers using their arXiv info without noting that they are already __PUBLISHED__ in some conferences such as ACL, EMNLP, NAACL, ICLR or AAAI. These incorrect bib entries might violate rules about submissions or camera-ready versions for some conferences. __Rebiber__ is a simple tool in Python to fix them automatically, based on their official information from the full ACL anthology and DBLP (for ICLR and other conferences)! 

## Get started

```bash
git clone https://github.com/yuchenlin/rebiber.git
pip install bibtexparser
cd rebiber
```

Normalizing the bibtex entries to the official format.
```bash
python normalize.py -i example_input.bib -o example_output.bib -l bib_list.txt
```



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

The `bib_list.txt` contains a list of converted json files of the official bib data. In this repo, we now support the full ACL anthology, i.e., all papers that are published at *CL conferences (ACL, EMNLP, NAACL, etc.) as well as workshops.
Also, we support any conference proceedings that can be downloaded from DBLP, for example, ICLR2020.

These are current supported conferences in our `data` folder. 

| Name | Link |
| --- | ----------- |
| ACL anthology | https://www.aclweb.org/anthology/ |
| ICLR2020 | https://dblp.org/db/conf/iclr/iclr2020.html |
| ICLR2019 | https://dblp.org/db/conf/iclr/iclr2019.html |
| ICLR2018 | https://dblp.org/db/conf/iclr/iclr2018.html |
| AAAI2020 | https://dblp.org/db/conf/aaai/aaai2020.html |
| NeurIPS2020 | https://dblp.org/db/conf/nips/neurips2020.html |
| ICLR2017 | https://dblp.org/db/conf/iclr/iclr2017.html |
| ... | ... |

**Please feel free to create PR to add your conferences here following the next section!** 

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
