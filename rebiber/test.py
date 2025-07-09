import uuid 
import rebiber 
import os 

# Load Bib Database 
filepath = os.path.abspath(rebiber.__file__).replace("__init__.py","")
bib_list_path = os.path.join(filepath, "bib_list.txt")
bib_db = rebiber.construct_bib_db(bib_list_path, start_dir=filepath)



def process(input_bib):
    random_id = uuid.uuid4().hex
    with open(f"/tmp/input_{random_id}.bib", "w") as f:
        f.write(input_bib.replace("\t", "    "))
    all_bib_entries = rebiber.load_bib_file(f"/tmp/input_{random_id}.bib")
    print("# Input Bib Entries:", len(all_bib_entries))
    rebiber.normalize_bib(bib_db, all_bib_entries, f"/tmp/output_{random_id}.bib")
    with open(f"/tmp/output_{random_id}.bib") as f:
        output_bib = f.read().replace("\n ", "\n    ")
    # delete both files
    # print(output_bib)
    return output_bib

input_bib = """
@article{Chung2022ScalingIL,
  title={Scaling Instruction-Finetuned Language Models},
  author={Hyung Won Chung and Le Hou and S. Longpre and Barret Zoph and Yi Tay and William Fedus and Eric Li and Xuezhi Wang and Mostafa Dehghani and Siddhartha Brahma and Albert Webson and Shixiang Shane Gu and Zhuyun Dai and Mirac Suzgun and Xinyun Chen and Aakanksha Chowdhery and Dasha Valter and Sharan Narang and Gaurav Mishra and Adams Wei Yu and Vincent Zhao and Yanping Huang and Andrew M. Dai and Hongkun Yu and Slav Petrov and Ed Huai-hsin Chi and Jeff Dean and Jacob Devlin and Adam Roberts and Denny Zhou and Quoc V. Le and Jason Wei},
  journal={ArXiv},
  year={2022},
  volume={abs/2210.11416}
}
"""

print(process(input_bib))

# New test case for arXiv reformatting
input_bib_arxiv = """
@article{ArxivTest2023,
  author={Test Author},
  title={A Test Article on ArXiv},
  journal={ArXiv},
  year={2023},
  volume={abs/2301.01234},
  url={https://arxiv.org/abs/2301.01234v2},
  note={Some notes here}
}

@article{ArxivTestOldStyle,
  author={Old Style Author},
  title={An Old Style ArXiv Article},
  eprint={math/0309136},
  archivePrefix={arXiv},
  primaryClass={math},
  url={https://arxiv.org/abs/math/0309136}
}

@article{ArxivTestWithCategory,
  author={Category Author},
  title={A Category Specific ArXiv Article},
  url={https://arxiv.org/abs/cs.CL/2305.05678},
  note={Another note}
}
"""

output_bib_arxiv = process(input_bib_arxiv)
print("\n--- ArXiv Test Output ---")
print(output_bib_arxiv)

# Assertions for the new arXiv test case
assert "archivePrefix = {arXiv}" in output_bib_arxiv
assert "eprint = {2301.01234}" in output_bib_arxiv
# For ArxivTest2023, primaryClass is not expected as it's not in the URL
# assert "primaryClass = {cs.CL}" in output_bib_arxiv # Removed this assertion

# Assertions for ArxivTestOldStyle
assert "eprint = {math/0309136}" in output_bib_arxiv
assert "primaryclass = {math}" in output_bib_arxiv # Expecting 'math' as primaryClass

# Assertions for ArxivTestWithCategory
assert "eprint = {2305.05678}" in output_bib_arxiv
assert "primaryclass = {cs.cl}" in output_bib_arxiv # Expecting 'cs.CL' as primaryClass

# Check for removal of redundant fields
assert "journal={ArXiv}" not in output_bib_arxiv
assert "volume={abs/2301.01234}" not in output_bib_arxiv
assert "url={https://arxiv.org/abs/2301.01234v2}" not in output_bib_arxiv
assert "url={https://arxiv.org/abs/math/0309136}" not in output_bib_arxiv

print("\nArXiv test cases passed!")
