import os
from flask import Flask, render_template, request, url_for
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms.validators import ValidationError
from wtforms import StringField
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
import csv
from flask_bootstrap import Bootstrap5
from transformation import process_csv_file
import geojson

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret_key"
app.config["UPLOAD_FOLDER"] = "upload"
app.config["DOWNLOAD_FOLDER"] = "download"

bootstrap = Bootstrap5(app)

if not os.path.exists(app.config["UPLOAD_FOLDER"]):
    os.makedirs(app.config["UPLOAD_FOLDER"])

if not os.path.exists(app.config["DOWNLOAD_FOLDER"]):
    os.makedirs(app.config["DOWNLOAD_FOLDER"])

class UploadForm(FlaskForm):
    file = FileField(validators=[FileRequired(),
                                 FileAllowed(['csv'], 'Only CSV allowed')])
    message = StringField("Chat")

    def validate_file(self, field):
        if not (isinstance(field.data, FileStorage) and field.data):
            return

        stream = field.data.stream
        stream.seek(0)  # Move the stream cursor to the beginning of the file
        reader = csv.reader(stream.read().decode("utf-8").splitlines())
        for row in reader:
            if len(row) != 8:
                raise ValidationError("CSV must have 8 columns")


@app.route('/', methods=['GET', 'POST'])
def upload():
    form = UploadForm()

    if form.validate_on_submit():
        f = form.file.data
        filename = secure_filename(f.filename)
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        f.save(file_path)

        osm_data = process_csv_file(file_path)
        osm_file_path = os.path.join(app.config["DOWNLOAD_FOLDER"], "osm_data.geojson")
        with open(osm_file_path, "w") as osm_file:
            geojson.dump(osm_data, osm_file)

    
    return render_template('index.html', form=form)


# @app.route("/", methods=["GET", "POST"])
# def index():
#     form = UploadForm()
#     if form.validate_on_submit():
#         filename = secure_filename(form.file.data.filename)
#         file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
#         form.file.data.save(file_path)
#         # file.save(file_path)

#         osm_data = process_csv_file(file_path)
#         osm_file_path = os.path.join(app.config["DOWNLOAD_FOLDER"], "osm_data.geojson")
#         with open(osm_file_path, "w") as osm_file:
#             geojson.dump(osm_data, osm_file)

#         # Provide a download link for the transformed OSM data
#         download_link = url_for("download_file", filename="osm_data.geojson")

#         return render_template("index.html", form=form, download_link=download_link)
#     return render_template("index.html", form=form)


if __name__ == "__main__":
    app.run(debug=True)
