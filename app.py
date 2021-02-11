from flask import Flask, render_template, url_for, request, redirect, send_from_directory, send_file
import os
from werkzeug.utils import secure_filename
import rebiber
import boto3


app = Flask(__name__)
filepath = os.path.dirname(os.path.abspath(__file__)) + '/'
app.config["UPLOAD_FOLDER"] = filepath
app.config["ALLOWED_EXTENSIONS"] = ["bib"]
# BUCKET = "rebiber"
# os.environ['AWS_PROFILE'] = "Profile1"


def upload_file(file_name, bucket):
    """
    Function to upload a file to an S3 bucket
    """
    object_name = file_name
    s3_client = boto3.client('s3')
    response = s3_client.upload_file(file_name, bucket, object_name)

    return response


def download_bib(file_name, bucket):
    """
    Function to download a given file from an S3 bucket
    """
    s3 = boto3.resource('s3')
    s3.Bucket(bucket).download_file(file_name, file_name)
    return file_name


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
                # upload_file(f"output.bib", BUCKET)
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
    # output = download_bib(f"{filename}", BUCKET)
    # return send_file(output, as_attachment=True)
    return send_file(f"{filename}", as_attachment=True)


@app.route('/back')
def back():
    return redirect(url_for('index'))


if __name__ == "__main__":
    app.run(debug=True)
