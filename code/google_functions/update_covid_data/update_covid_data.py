"""
Gets the latest covid data from covid19.fetch.rest and uploads it to big query.

Also creates a csv file of all historic data and places it in the bucket.
"""
import io
import time
import requests

from google.cloud import bigquery
from google.cloud import storage

def main(request,context):


    # =======================================
    # SETTINGS
    # =======================================
    big_query_covid_table = "your_dataset.covid_cases"

    # BUCKET SETTINGS
    historic_data_bucket_name = "covid19lang"
    historic_csv_filepath = "historic_covid_data.csv"


    # =======================================
    # REMOTE CLIENTS
    # =======================================
    print("Connecting to big query client")
    bq_client = bigquery.Client()

    print("Connecting to google storage client")
    storage_client = storage.Client()


    # =======================================
    # GET LATEST DATA FROM FETCH.REST
    # =======================================
    print("Getting latest covid 19 data")
    url = "http://covid19.fetch.rest/v1/latest/all"

    # Try 3 times, sleeping for 10 seconds after each retry
    n_tries = 3
    delay_before_retry = 10
    for i in range(n_tries):
        r = requests.get(url, params={}, timeout=30)
        if (r.status_code != 200):
            if (i+1) < n_tries:
                time.sleep(delay_before_retry)
                continue
            else:
                r.raise_for_status()
        else:
            content = r.json()  # get content as JSON


    data = content["data"]
    latest_date = data[0]["date"]
    print(f"received data for {latest_date}")


    # =======================================================
    # CHECK THAT WE DONT ALREADY HAVE DATA FOR THIS SAME DATE
    # =======================================================
    print("Checking we dont already have this data")

    query = f"select count(*) as n from {big_query_covid_table} where date = '{latest_date}';"
    job_response = bq_client.query(query).result()
    n_matches = job_response.to_dataframe()["n"][0]

    if (n_matches > 0):
        raise AssertionError("We already have data for this date")



    # =======================================================
    # UPLOAD TO BIG QUERY
    # =======================================================
    print("filtering to only keep desired columns")
    desired_columns = ["date", "region", "cases", "deaths", "recovered"]
    for i in range(len(data)):
        row = data[i]
        # filter the desired columns using a dictionary comprehension
        row = {key:val for key,val in row.items() if key in desired_columns}
        data[i] = row # replace with new filtered row


    print("Uploading data to big query")
    errors = bq_client.insert_rows_json(big_query_covid_table, data)
    if len(errors) > 0:
        raise AssertionError("Failed to upload data to big query")



    # =======================================================
    # CREATE ALL HISTORIC DATA AS A CSV FILE
    # =======================================================
    print("getting all historical data")
    query = f"select * from {big_query_covid_table};"
    job_response = bq_client.query(query).result()
    df = job_response.to_dataframe()

    print("Creating csv string of all historical data")
    virtual_text_file = io.StringIO()
    df.to_csv(virtual_text_file, header=True, index=False)
    csv_string = virtual_text_file.getvalue()



    # =======================================================
    # SEND CSV FILE TO BUCKET
    # =======================================================
    print("Creating csv file in bucket")
    bucket = storage_client.bucket(historic_data_bucket_name)
    blob = bucket.blob(historic_csv_filepath)
    blob.upload_from_string(csv_string)

    print("DONE!")


if __name__ == '_main_':
    main()