from flask import Flask, render_template, url_for, request, redirect, send_from_directory, send_file
import os
from werkzeug.utils import secure_filename
import rebiber
import boto3


app = Flask(__name__)
filepath = os.path.dirname(os.path.abspath(__file__)) + '/'
app.config["UPLOAD_FOLDER"] = filepath
app.config["ALLOWED_EXTENSIONS"] = ["bib"]


def process_file(input_file_path, deduplicate, removed_value_names):
    all_bib_entries = rebiber.load_bib_file(input_file_path)
    filepath = os.path.abspath(rebiber.__file__).replace("__init__.py","")
    bib_list_path = os.path.join(filepath, "bib_list.txt")
    bib_db = rebiber.construct_bib_db(bib_list_path, start_dir=filepath)
    rebiber.normalize_bib(bib_db, all_bib_entries, "output.bib", deduplicate=deduplicate, removed_value_names=removed_value_names) 


def allowed_file(filename):
    # We only want files with a . in the filename
    if not "." in filename:
        return False

    # Split the extension from the filename
    ext = filename.rsplit(".", 1)[1]

    # Check if the extension is in ALLOWED_IMAGE_EXTENSIONS
    if ext.lower() in app.config["ALLOWED_EXTENSIONS"]:
        return True
    else:
        return False


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        
        if request.files:
            bib_file = request.files["bib"]

            if bib_file.filename == "":
                print("No filename")
                error = "File not found."
                return render_template("index.html", error=error, version=rebiber.__version__)

            if allowed_file(bib_file.filename):
                filename = secure_filename(bib_file.filename)
                bib_file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                print("File uploaded successfully")

                # check if any checkbox is selected
                deduplicate = True
                if request.form.get('duplicate'):
                    print('keep duplicate is selected')
                    deduplicate = False

                value_names = ['pages','editor','volume','month','url','biburl','address','publisher','bibsource','timestamp','doi']
                removed_value_names=[]
                
                for value in value_names:
                    if request.form.get(value):
                        removed_value_names.append(value)
                        print(value + ' is selected')

                process_file(os.path.join(app.config['UPLOAD_FOLDER'], filename), deduplicate, removed_value_names)
                return redirect('/downloadfile/'+ 'output.bib')
            
            else:
                print("That file extension is not allowed")
                error = "Invalid file extension. Please upload a bib file."
                return render_template("index.html", error=error, version=rebiber.__version__)

    return render_template("index.html", version=rebiber.__version__)


# Download API
@app.route("/downloadfile/<filename>", methods = ['GET'])
def download_file(filename):
    return render_template('download.html',value=filename, version=rebiber.__version__)


@app.route('/return-files/<filename>')
def return_files_tut(filename):
    return send_file(f"{filename}", as_attachment=True, cache_timeout=-1)


if __name__ == "__main__":
    app.run(debug=True)
