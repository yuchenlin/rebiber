conf_name=$1
shift
for year in "$@"
do
	echo "$conf_name-$year"
	python bib2json.py \
	-i raw_data/$conf_name$year.bib \
	-o data/$conf_name$year.bib.json
	echo "data/$conf_name$year.bib.json" >> bib_list.txt
done
