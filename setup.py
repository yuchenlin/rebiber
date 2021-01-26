import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="rebiber", 
    version="0.0.1",
    description="A tool for normalizing bibtex with official info.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yuchenlin/rebiber",
    py_modules=["bib2json", "normalize"],
    packages=setuptools.find_packages(),
    install_requires=['argparse',
                      'bibtexparser',
                    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)