from flask import Flask, render_template, url_for, request, redirect, send_from_directory, send_file
import os
from werkzeug.utils import secure_filename
import rebiber


app = Flask(__name__)
filepath = os.path.dirname(os.path.abspath(__file__)) + '/'
app.config["UPLOAD_FOLDER"] = filepath + "static/uploads"
app.config["ALLOWED_EXTENSIONS"] = ["bib"]


def process_file(input_file_path):
    all_bib_entries = rebiber.load_bib_file(input_file_path)
    filepath = os.path.abspath(rebiber.__file__).replace("__init__.py","")
    bib_list_path = os.path.join(filepath, "bib_list.txt")
    bib_db = rebiber.construct_bib_db(bib_list_path, start_dir=filepath)
    rebiber.normalize_bib(bib_db, all_bib_entries, "output.bib") 


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
                return redirect(request.url)

            if allowed_file(bib_file.filename):
                filename = secure_filename(bib_file.filename)
                bib_file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                print("File uploaded successfully")
                process_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                return redirect('/downloadfile/'+ 'output.bib')
            
            else:
                print("That file extension is not allowed")
                return redirect(request.url)

    return render_template("index.html")


# Download API
@app.route("/downloadfile/<filename>", methods = ['GET'])
def download_file(filename):
    return render_template('download.html',value=filename)


@app.route('/return-files/<filename>')
def return_files_tut(filename):
    file_path = app.config['UPLOAD_FOLDER'] + '/output.bib'
    return send_file(file_path, as_attachment=True, attachment_filename='')


if __name__ == "__main__":
    app.run(debug=True)
