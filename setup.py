import setuptools
import os

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

about = {}
with open("rebiber/_version.py") as f:
    exec(f.read(), about)
os.environ["PBR_VERSION"] = about["__version__"]

setuptools.setup(
    name="rebiber", 
    version=about["__version__"],
    author='Bill Yuchen Lin',
    author_email='yuchen.lin@usc.edu',
    description="A tool for normalizing bibtex with official info.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yuchenlin/rebiber",
    py_modules=["bib2json", "normalize"],
    packages=setuptools.find_packages(),
    install_requires=['argparse',
                      'bibtexparser',
                      'tqdm',
                    ],
    entry_points = {
        'console_scripts': ['rebiber=rebiber.normalize:main'],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    package_data={'rebiber': ['data/*.json', 'bib_list.txt', 'example_input.bib', 'example_output.bib']},
)
