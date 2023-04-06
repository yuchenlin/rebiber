conf_name=$1
shift
for year in "$@"
do
	# check if raw_data/$conf_name$year.bib exists, if not we might have to concatenate partial files
	if [ ! -f raw_data/$conf_name$year.bib ]; then
		echo "raw_data/$conf_name$year.bib does not exist, trying to concatenate partial files:"
		echo raw_data/${conf_name}${year}_*.bib
		cat raw_data/${conf_name}${year}_*.bib > raw_data/$conf_name$year.bib
	fi
	echo "$conf_name-$year"
	python bib2json.py \
	-i raw_data/$conf_name$year.bib \
	-o data/$conf_name$year.bib.json
	echo "data/$conf_name$year.bib.json" >> bib_list.txt
done
