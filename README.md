# Rebiber: A tool for normalizing bibtex with official info.

Normalizing the bibtex entries to the official ACL Anthology format.

https://www.aclweb.org/anthology/anthology.bib.gz

Example input:
```bib
@article{lin2020birds,
	title={Birds have four legs?! NumerSense: Probing Numerical Commonsense Knowledge of Pre-trained Language Models},
	author={Lin, Bill Yuchen and Lee, Seyeon and Khanna, Rahul and Ren, Xiang},
	journal={arXiv preprint arXiv:2005.00683},
	year={2020}
}

```

Birds have four legs?! NumerSense: Probing Numerical Commonsense Knowledge of Pre-trained Language Models
---> "birdshavefourlegsnumersenseprobingnumericalcommonsenseknowledgeofpretrainedlanguagemodels"
---> "lin-etal-2020-birds" in anthology.bib

Example output:
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

