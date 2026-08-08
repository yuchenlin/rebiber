# Rebiber: A tool for normalizing bibtex with official info.

<p>
<a href="https://huggingface.co/spaces/yuchenlin/Rebiber">
    <img src="https://img.shields.io/badge/🤗 Web%20Demo--red?style=flat_square">
  </a>

<a href="https://colab.research.google.com/drive/12oQcLs25CFjI4evsFlWfKD1DfTEiqyCN?usp=sharing">
    <img src="https://img.shields.io/badge/Colab%20Notebook--green?style=flat_square&logo=googlecolab">
     <!-- <img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/, width=150, height=150/></a> -->
  </a>

<a href="https://twitter.com/billyuchenlin/status/1353850378438070272?s=20">
    <img src="https://img.shields.io/badge/Tweet--blue?style=flat_square&logo=twitter">
  </a>
</p>

We often cite papers using their arXiv versions without noting that they are already __PUBLISHED__ in some conferences. These unofficial bib entries might violate rules about submissions or camera-ready versions for some conferences. 
We introduce __Rebiber__, a simple tool in Python to fix them automatically. It is based on the official conference information from the [DBLP](https://dblp.org/) or [the ACL anthology](https://www.aclweb.org/anthology/) (for NLP conferences)! You can check the list of supported conferences [here](#supported-conferences).
Apart from handling outdated arXiv citations, __Rebiber__ also normalizes citations in a unified way (DBLP-style), supporting abbreviation and value selection.



<!-- ***Web demo:*** [https://rebiber.herokuapp.com/](https://rebiber.herokuapp.com/) (recommended). -->

***Demo on Huggingface Space [https://huggingface.co/spaces/yuchenlin/Rebiber](https://huggingface.co/spaces/yuchenlin/Rebiber) (recommended)***

***Colab notebook:*** [here](https://colab.research.google.com/drive/12oQcLs25CFjI4evsFlWfKD1DfTEiqyCN?usp=sharing) 

## Changelog

- **2026.08** Version **1.3.0**. Safer title matching (author-overlap guard so a "Deep Learning" book/Nature paper is not replaced by an unrelated KDD talk); official arXiv fields (`eprint`, `archivePrefix`, `primaryClass`); do not rewrite already-published papers just because an abstract mentions arXiv; do not silently drop unparsed entries; `--format-only` / `--dry-run` / `--no-check-authors`; batch inputs (`rebiber -i *.bib`); conference data through 2025–2026 (AAAI, ICLR, ICML, NeurIPS, CVPR, ICCV, CHI, WWW, SIGIR, IJCAI, KDD, Interspeech, ICASSP, AISTATS, UAI, BMVC, ACL Anthology); monthly GitHub Action to refresh DBLP + ACL anthology; more `booktitle` abbreviations (COLM, WACV, ECCV, ICCV, NAACL, Findings, TACL, JMLR).

- **2024.7** Version 1.2.0. added automatic script to download bib files for recent conferences from dblp. 

- **2023.06.01** New demo ready to use on Huggingface's Space via Gradio. Also, a few conferences are added.

- **2021.09.06** We fixed a few minor bugs and added features such as sorting and urls to arXiv (if the paper is not in any conferences; thanks to [@nicola-decao](https://github.com/nicola-decao)). We also updated the ACL anthology bib/json to the latest version as well as other conferences.

- **2021.05.30** 
We build a [beta version](https://rebiber.herokuapp.com/) of our **web app for Rebiber**; add new conferences to our dataset; fix a few minor bugs. (It is not working anymore. Please use the new huggingface space demo.)
- **2021.02.08** 
We now support multiple useful features: 1) turning off some certain values, e.g., "-r url,pages,address" for removing the values from the output, 2) using abbr. to shorten the booktitle values, e.g., `Proceedings of the .* Annual Meeting of the Association for Computational Linguistics` --> `Proc. of ACL`. More examples are [here.](https://github.com/yuchenlin/rebiber/blob/main/rebiber/abbr.tsv)
- **2021.01.30** 
We build a colab notebook as a simple web demo. [link](https://colab.research.google.com/drive/12oQcLs25CFjI4evsFlWfKD1DfTEiqyCN?usp=sharing)



## Installation

```bash
git clone https://github.com/yuchenlin/rebiber.git
cd rebiber/
pip install -e .
# optional: pip install -e ".[dev]"   # pytest
```

OR

```bash
uv tool install https://github.com/yuchenlin/rebiber
```

OR from a local checkout with uv:

```bash
uv tool install .
```

The editable / GitHub install is recommended if you want the latest conference data and bug fixes.

## Usage (v1.3.0)

Normalize your bibtex file(s) with the official conference information:

```bash
rebiber -i input.bib [more.bib ...] [-o out.bib|outdir]
```

Examples:

```bash
# single file (writes back to input.bib if -o is omitted)
rebiber -i examples/input.bib -o examples/output.bib

# batch: multiple files or a glob; -o can be a directory
rebiber -i *.bib
rebiber -i paper1.bib paper2.bib -o ./normalized/

# pretty-print only (no official-info replacement; useful for diffs)
rebiber -i input.bib -o pretty.bib --format-only

# report what would change without writing
rebiber -i input.bib --dry-run
```

You can find a pair of example input and output files in [`examples/input.bib`](examples/input.bib) and [`examples/output.bib`](examples/output.bib).

```
rebiber -i input.bib [more.bib ...] [-o out.bib|outdir]
  -r/--remove comma fields
  -s/--shorten True|False   (default False)
  -d/--deduplicate True|False (default True)
  -st/--sort True|False (default False)
  --format-only   # pretty-print only, for diffs (issue 66)
  --dry-run       # report without writing
  --no-check-authors  # disable author-overlap guard (issue 50)
  -u/--update
  -v/--version
  -l/--bib_list
  -a/--abbr_tsv
```

| argument | usage|
| ----------- | ----------- |
| `-i` | or `--input_bib`. One or more input `.bib` files (shell globs like `*.bib` work). |
| `-o` | or `--output_bib`. Output `.bib` path, or a directory when normalizing multiple files. If omitted, each input is overwritten in place. |
| `-r` | or `--remove`. A comma-separated list of value names that you want to remove, such as `-r pages,editor,volume,month,url,biburl,address,publisher,bibsource,timestamp,doi`. Empty by __default__.  |
| `-s` | or `--shorten`. `True`/`False`, **False** by default. Replace `booktitle`/`journal` with abbreviations from `-a`. Used as `-s True`. |
| `-d` | or `--deduplicate`. `True`/`False`, **True** by default. Remove duplicate bib entries that share the same key. Used as `-d True`. |
| `-st` | or `--sort`. `True`/`False`, **False** by default. Keep the input order unless set to `True` (then entries are ordered alphabetically). Used as `-st True`. |
| `--format-only` | Pretty-print / normalize formatting only. Do not replace entries with official DBLP/ACL records. Handy for reviewing diffs. |
| `--dry-run` | Report conversions and issues without writing output files. |
| `--no-check-authors` | Disable the author-overlap guard (see below). |
| `-l` | or `--bib_list`. The list of bib json files to load. Default: [rebiber/bib_list.txt](rebiber/bib_list.txt). |
| `-a` | or `--abbr_tsv`. Conference abbreviation table. Default: [rebiber/abbr.tsv](rebiber/abbr.tsv). |
| `-u` | or `--update`. Update the local bib-related data with the latest GitHub version. |
| `-v` | or `--version`. Print the version of current Rebiber. |

### Matching behavior (v1.3.0)

- **Author-overlap guard.** A title-only match is not enough when the candidate official record looks like a different paper. Rebiber will not replace a "Deep Learning" book or *Nature* article with an unrelated KDD talk that happens to share a short/generic title. Use `--no-check-authors` only if you want the old title-only behavior.
- **ArXiv official fields.** Unofficial arXiv preprints are rewritten with standard fields (`eprint`, `archivePrefix`, `primaryClass`) instead of a free-form `journal = {arXiv preprint ...}` string.
- **Published papers stay published.** Rebiber will not rewrite an already-published entry just because the abstract (or another field) mentions arXiv.
- **Unparsed entries are kept.** Entries that fail to parse are not silently dropped from the output.

Convert a raw BibTeX dump to the internal JSON index:

```bash
python -m rebiber.bib2json -i path/to/conf.bib -o path/to/conf.json
# or: bib2json -i path/to/conf.bib -o path/to/conf.json
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

The `bib_list.txt` contains a list of converted json files of the official bib data. In this repo, we now support the full [ACL anthology](https://www.aclweb.org/anthology/), i.e., all papers that are published at *CL conferences (ACL, EMNLP, NAACL, etc.) as well as workshops.
Also, we support any conference proceedings that can be downloaded from DBLP, for example, ICLR2020.

A monthly GitHub Action refreshes DBLP dumps and the ACL anthology automatically. You can also update a single conference locally (see [Adding a new conference](#adding-a-new-conference)).

The following conferences are supported and their bib/json files are in our `data` folder. You can turn each item on/off in `bib_list.txt`. **Please feel free to create PR for adding new conferences following [this](#adding-a-new-conference)!** 

| Name | Years |
| --- | ----------- |
| ACL Anthology | current (2026; split JSON files) |
| AAAI | 2010 -- 2026 |
| AISTATS | 2013 -- 2025 |
| ALENEX | 2010 -- 2020 |
| ASONAM | 2010 -- 2019 |
| BigDataConf | 2013 -- 2019 |
| BMVC | 2010 -- 2024 |
| CHI | 2010 -- 2026 |
| CIDR | 2009 -- 2020 |
| CIKM | 2010 -- 2020 |
| COLT | 2000 -- 2020 |
| CVPR | 2000 -- 2025 |
| ICASSP | 2015 -- 2025 |
| ICCV | 2003 -- 2025 |
| ICLR | 2013 -- 2025 |
| ICML | 2000 -- 2025 |
| IJCAI | 2011 -- 2025 |
| INTERSPEECH | 2016 -- 2025 |
| KDD | 2010 -- 2024 |
| MLSys | 2019 -- 2020 |
| MM | 2016 -- 2020 |
| NeurIPS | 2000 -- 2025 |
| RECSYS | 2010 -- 2020 |
| SDM | 2010 -- 2020 |
| SIGIR | 2010 -- 2026 |
| SIGMOD | 2010 -- 2022 (2023 and after changed to journal) |
| SODA | 2010 -- 2020 |
| STOC | 2010 -- 2020 |
| UAI | 2010 -- 2025 |
| WSDM | 2008 -- 2020 |
| WWW (The Web Conf) | 2001 -- 2026 |


**Thanks for [Anton Tsitsulin](http://tsitsul.in/)'s great work on collecting such a complete set bib files!**

<!-- 
python -m rebiber.bib2json -i data/iclr2020.bib -o data/iclr2020.json
python -m rebiber.bib2json -i data/iclr2019.bib -o data/iclr2019.json
python -m rebiber.bib2json -i data/iclr2018.bib -o data/iclr2018.json
python -m rebiber.bib2json -i data/aaai2020.bib -o data/aaai2020.json
 -->


## Adding a new conference

A monthly GitHub Action refreshes DBLP + the ACL anthology. To add or update a conference yourself:

```bash
python -m rebiber.download_dblp --confs iclr --start-year 2026
```

`--confs` accepts a conference short name (DBLP key, e.g. `iclr`, `neurips`, `cvpr`). Repeat or pass a comma-separated list if the downloader supports multiple names. Then convert any remaining raw `.bib` files if needed:

```bash
python -m rebiber.bib2json -i raw_data/iclr2026.bib -o rebiber/data/iclr2026.bib.json
```

And add the new JSON path to `rebiber/bib_list.txt` if it is not already listed.

Alternatively, you can still download bib files from DBLP by hand into `raw_data/` (name them `{conf}{year}.bib`) and run `bash scripts/add_conf.sh iclr 2019 2020`.

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=yuchenlin/rebiber&type=Date)](https://star-history.com/#yuchenlin/rebiber&Date)

## Contact

Please email [billyuchenlin@gmail.com](mailto:billyuchenlin@gmail.com) or [i@yuchenlin.xyz](mailto:i@yuchenlin.xyz), or open a [GitHub issue](https://github.com/yuchenlin/rebiber/issues) if you have any questions or suggestions.
(USC: yuchen.lin@usc.edu)
