from google.cloud import storage
from google.cloud import bigquery
from apiclient import discovery
import httplib2
from oauth2client import client
from flask import jsonify
from flask import Flask, redirect, url_for,request, render_template,session
import datetime

# Google Storage Setup
storage_client = storage.Client()

# Google BigQuery Setup
client_bq = bigquery.Client() 

# Universal variables 
app = Flask(__name__)

today_date_sql = 'select max(date) as today from your_dataset.covid_cases;'
query_result_today = client_bq.query(today_date_sql).result()
record_today = [dict(row) for row in query_result_today]
today_date = record_today[0]['today']
today_date_str = today_date.strftime("%Y-%m-%d")


@app.route('/mood')
def mood():
    # Display tweet sentiments
    
    #Retrieve the latest data from a sentiment
    mood_sql = ("""select date, score from covid19-274903.your_dataset.sentiment
              ORDER BY date asc; """)
    query_result_mood= client_bq.query(mood_sql).result()   
    results = [[row["date"], row["score"]] for row in query_result_mood ]
    return render_template('mood.html', results = results)

  
@app.route('/')
def worldPage():
    # Retreive all data of the world, including confirmed cases, deaths and recovered.
    world_sql = ("""select sum(cases) as total_confirmedCases, sum(deaths) as total_deaths, 
                    sum(recovered) as total_recovered from your_dataset.covid_cases 
                    where date = '{}';""").format(today_date)
    query_job_world = client_bq.query(world_sql)
    query_result_world = query_job_world.result()
    records_world = [dict(row) for row in query_result_world] 
    confrimedCases = records_world[0]['total_confirmedCases']
    deaths = records_world[0]['total_deaths']
    recovered = records_world[0]['total_recovered']

    #Retrieve the rank for cs, deaths, recovered for the whole world
    world_rank_sql = ("""select region,cases,deaths, recovered from your_dataset.covid_cases 
                 where date ='{}'group by region,cases,deaths, recovered; """).format(today_date)
    query_result_world_rank = client_bq.query(world_rank_sql).result()
    record_world_rank = [dict(row) for row in query_result_world_rank]

    world_sql = ("""select region,cases,deaths, recovered from your_dataset.covid_cases 
                 where date ='{}'group by region,cases,deaths, recovered; """).format(today_date)
    result_world = client_bq.query(world_sql).result()
    

    latestWorldData = [[row["region"].replace("_", " ").title(), row["cases"], 
                        row["deaths"], row["recovered"]] for row in result_world]
    
    return render_template('world.html',cs=confrimedCases,
                            deaths = deaths, recovered = recovered,
                            world_rank = record_world_rank,
                            latestWorldData=latestWorldData)

@app.route('/country/<string:country_id>')
def countryPage(country_id):
    country=country_id.title()
    # Retrieve all data from a country
    country_sql = ("""  select region, cases, deaths,recovered from covid19-274903.your_dataset.covid_cases
                  where region = @country
                  ORDER BY cases desc; """)
    job_config = bigquery.QueryJobConfig(
    query_parameters=[
        bigquery.ScalarQueryParameter("country", "STRING", country_id),]
)
    query_result_country = client_bq.query(country_sql,job_config=job_config).result()
    record_country = [dict(row) for row in query_result_country ] 


    #Retrieve the latest data from a country
    country_sql_latest = ("""  select region, cases, deaths,recovered from covid19-274903.your_dataset.covid_cases
                  where region = @country_id and date = @today
                  ORDER BY cases desc limit 10; """)
    job_config_latest = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("country_id", "STRING", country_id),
            bigquery.ScalarQueryParameter("today", "STRING", today_date_str),        
        ]
    )
    query_result_country_latest = client_bq.query(country_sql_latest,job_config = job_config_latest).result()
    record_country_latest = [dict(row) for row in query_result_country_latest ]
    cs_latest = record_country_latest[0]['cases']
    deaths_latest = record_country_latest[0]['deaths']
    recovered_latest = record_country_latest[0]['recovered']

    #Retrieve the latest data from a country
    sql = ("""  select date, cases from covid19-274903.your_dataset.covid_cases
                  where region = @country_id
                  ORDER BY date asc; """)
    job_config_latest = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("country_id", "STRING", country_id),
                  
        ]
    )
    results = client_bq.query(sql,job_config = job_config_latest).result()    
    results = [[row["date"], row["cases"]] for row in results ]

    return render_template('country.html',cs_latest=cs_latest,
                            deaths_latest=deaths_latest,
                            recovered_latest=recovered_latest,
                            results=results,country=country)
                            
                                                
if __name__ == '__main__':
    app.run(host="0.0.0.0",
        debug = True)

