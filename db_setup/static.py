import os, cv2, csv, json, sys, io
import operator, argparse, requests
import pandas as pd
import sqlite3
from datetime import datetime
import utils.db_utils as db_utils


def download_csv_from_google_drive(id):

    # Download the csv files stored in Google Drive with initial information about
    # the movies and the species

    URL = "https://docs.google.com/uc?export=download"

    session = requests.Session()

    response = session.get(URL, params={"id": id}, stream=True)
    token = get_confirm_token(response)

    if token:
        params = {"id": id, "confirm": token}
        response = session.get(URL, params=params, stream=True)

    return response


def get_confirm_token(response):
    for key, value in response.cookies.items():
        if key.startswith("download_warning"):
            return value

    return None

# TODO merge the get_fps and get_length function
def get_fps(video_file):
    if os.path.isfile(video_file):
        fps = int(cv2.VideoCapture(video_file).get(cv2.CAP_PROP_FPS))
    else:
        fps = None
    return fps

def get_length(video_file):
    if os.path.isfile(video_file):
        fps = int(cv2.VideoCapture(video_file).get(cv2.CAP_PROP_FPS))
        totalNoFrames = cv2.VideoCapture(video_file).get(cv2.CAP_PROP_FRAME_COUNT)
        length = float(totalNoFrames) / float(fps)
    else:
        length = None
    return length

def add_movies(movies_file_id, db_path, movies_path):

    # Download the csv with movies information from the google drive
    movies_csv_resp = download_csv_from_google_drive(movies_file_id)
    movies_df = pd.read_csv(io.StringIO(movies_csv_resp.content.decode("utf-8")))

    # Include server's path of the movie files
    movies_df["Fpath"] = movies_path + "/" + movies_df["FilenameCurrent"] + ".mov"

    # Standarise the filename
    movies_df["FilenameCurrent"] = movies_df["FilenameCurrent"].str.normalize("NFD")
    
    # Set up sites information
    sites_db = movies_df[
        ["SiteDecription", "CentroidLat", "CentroidLong"]
    ].drop_duplicates("SiteDecription")

    # Add values to sites table
    db_utils.add_to_table(
        db_path, "sites", [(None,) + tuple(i) + (None,) for i in sites_db.values], 5
    )

    # Update movies table
    conn = db_utils.create_connection(db_path)

    # Reference with sites table
    sites_df = pd.read_sql_query("SELECT id, name FROM sites", conn)
    sites_df = sites_df.rename(columns={"id": "Site_id"})

    movies_df = pd.merge(
        movies_df, sites_df, how="left", left_on="SiteDecription", right_on="name"
    )

    # Calculate the fps and length of the original movies
    movies_df["fps"] = movies_df["Fpath"].apply(get_fps, 1)
    movies_df["duration"] = movies_df["Fpath"].apply(get_length, 1)
    
    # Select only those fields of interest
    movies_db = movies_df[
        ["FilenameCurrent", "DateFull", "fps", "duration", "Author", "Site_id", "Fpath"]
    ]

    # Add values to movies table
    db_utils.add_to_table(
        db_path, "movies", [(None,) + tuple(i) for i in movies_db.values], 8
    )


def add_species(species_file_id, db_path):

    # Download the csv with species information from the google drive
    species_csv_resp = download_csv_from_google_drive(species_file_id)
    species_df = pd.read_csv(io.StringIO(species_csv_resp.content.decode("utf-8")))

    # Add values to species table
    db_utils.add_to_table(
        db_path, "species", [(None,) + tuple([i]) for i in species_df["Name"].values], 2
    )


def main():
    "Handles argument parsing and launches the correct function."
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--species_file_id",
        "-sp",
        help="Google drive id of species csv file",
        type=str,
        required=True,
    )
    parser.add_argument(
        "--movies_file_id",
        "-mov",
        help="Google drive id of movies csv file",
        type=str,
        required=True,
    )
    parser.add_argument(
        "-db",
        "--db_path",
        type=str,
        help="the absolute path to the database file",
        default=r"../koster_lab.db",
        required=True,
    )
    parser.add_argument(
        "-mp",
        "--movies_path",
        type=str,
        help="the absolute path to the movie files",
        default=r"/uploads",
    )

    args = parser.parse_args()

    add_movies(args.movies_file_id, args.db_path, args.movies_path)
    add_species(args.species_file_id, args.db_path)


if __name__ == "__main__":
    main()