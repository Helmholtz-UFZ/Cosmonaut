import os
from flask import Flask, render_template, request
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from wtforms import StringField, ValidationError
from werkzeug.utils import secure_filename
import csv
from flask_bootstrap import Bootstrap5

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret_key"
app.config["UPLOAD_FOLDER"] = "upload"

bootstrap = Bootstrap5(app)

if not os.path.exists(app.config["UPLOAD_FOLDER"]):
    os.makedirs(app.config["UPLOAD_FOLDER"])


class CsvValidator(object):
    """
    Validates that a file uploaded via a Flask-WTF FileField is a CSV file with a specified number of columns.

    Args:
        num_columns (int): The expected number of columns in the CSV file.

    Raises:
        ValidationError: If the uploaded file is not a CSV file or does not have the expected number of columns.
    """

    def __init__(self, num_columns):
        self.num_columns = num_columns

    def __call__(self, form, field):
        if not field.data:
            raise ValidationError("No file uploaded")

        filename = secure_filename(field.data.filename)
        if not filename.endswith(".csv"):
            raise ValidationError("File must be a CSV")

        stream = field.data.stream
        stream.seek(0)  # Move the stream cursor to the beginning of the file
        try:
            reader = csv.reader(stream.read().decode("utf-8").splitlines())
            for row in reader:
                if len(row) != self.num_columns:
                    raise ValidationError(f"CSV must have {self.num_columns} columns")
        except csv.Error:
            raise ValidationError("File is corrupted")


class UploadForm(FlaskForm):
    file = FileField(validators=[FileRequired(), CsvValidator(8)])
    message = StringField("Chat")


@app.route("/", methods=["GET", "POST"])
def index():
    """
    Renders the index.html template and handles file uploads.

    Returns:
        If the form is submitted and valid, returns a success message with the file path.
        Otherwise, returns the rendered index.html template with an UploadForm instance.
    """
    form = UploadForm()
    if form.validate_on_submit():
        file = form.file.data
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)
        return f"File uploaded successfully! Path: {file_path}"
    return render_template("index.html", form=form)


if __name__ == "__main__":
    app.run(debug=True)
