"""
Script to get twitter comments for today, calcualte the sentiment score,
and upload the score to big query
"""
import os
import json
import datetime

import google
from google.cloud import bigquery
from google.cloud import storage
from google.cloud import language
from google.cloud.language import enums
from google.cloud.language import types

import tweepy

def main(request,context):
    # =====================================
    # SETTINGS
    # =====================================
    bq_sentiment_table = "your_dataset.sentiment"

    # TWEEPY SETTINGS
    

    # # access the components of the credentials file
    ACCESS_TOKEN="########################"
    ACCESS_TOKEN_SECRET="#####################"
    CONSUMER_KEY="##########################"
    CONSUMER_SECRET="#########################"


    # Entities to extract for sentiment analysis
    desired_entity_names = ["covid19", "pandemic", "virus", "quarantine", "lockdown", "stayathome"]


    # DATE SETTINGS
    # is called just after midnight (UTC), so get day before
    date = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    date_str = date.strftime("%Y-%m-%d")# string representation of date YYYY-MM-DD


    # =====================================
    # CONNECT TO REMOTE CLIENTS
    # =====================================
    print("Connecting to remote clients")

    # TWITTER CLIENT
    try:
        auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
        auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
        api = tweepy.API(auth,wait_on_rate_limit=True,wait_on_rate_limit_notify=True,retry_count=2,retry_delay=5)

    except:
        raise Exception("Error: Authentication Failed")


    # CONNECT TO BIG QUERY
    bqclient = bigquery.Client()

    # CONNECT TO NATURAL LANGUAGE CLIENT
    nlp_client = language.LanguageServiceClient()

    # CONNECT TO GOOGLE CLOUD STORAGE
    storage_client = storage.Client()


    # =====================================
    # GET TODAYS COMMENTS FROM TWITTER
    # =====================================
    print("Getting twitter comments")
    def get_tweets_for_date(start_date,search_keywords,n):
        """ function to retrieve tweets with a given date"""

        SEARCH_KEYWORDS = search_keywords
        start_date=start_date
        date_format = "%Y-%m-%d"
        end_date=datetime.datetime.strptime(start_date, date_format) + datetime.timedelta(days=1)
        end_date = end_date.strftime(date_format)

        statuses_json = []
        statuses = tweepy.Cursor(api.search,q=SEARCH_KEYWORDS,since=start_date,until=end_date, lang="en").items(n)

        if statuses:
            for item in statuses:
                # Process each status retrieved
                statuses_json.append(item._json)
        return statuses_json


    print("Processing twitter comments")
    # Tweets as a list of dictionaries
    tweets = get_tweets_for_date(date_str,"#covid19 ",300)

    # =====================================
    # CACHING TWITTER COMMENTS DATA TO BUCKET
    # =====================================
    print("caching twitter comments to bucket")
    file_content = json.dumps(tweets, indent=4) # storing tweets as a JSON string
    file_name = f"tweets_{date_str}.json" # saved as tweets_YYYY-MM-DD.json

    tweets_subdirectory = "tweets"
    file_path = os.path.join(tweets_subdirectory, file_name)  # full file path of filename in bucket

    # upload tweets to bucket file
    def upload_string(destination_blob_name,tweets_string):
        "Upload a given string as a given blob name to the bucket"
        bucket_name = "covid19chenlang"
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_string(tweets_string)

    upload_string(file_path,file_content)



    # =====================================
    # FUNCTIONS FOR SENTIMENT ANALYSIS OF TWEETS
    # =====================================
    def get_entity_level_sentiment(nlp_client, s):
        """ Given a string, it performs entity level sentiment analysis.
            Returns a list of dictionaries with following items
            - name:         name of entity
            - magnitude:    sentiment magnitude
            - score:        sentiment score
            - salience:     how salient is the entity
        """
        document = language.types.Document(
            content=s,
            language="en",
            type="PLAIN_TEXT"
            )
        response = nlp_client.analyze_entity_sentiment(document=document, encoding_type='UTF32')

        entities = []
        for entity in response.entities:
            processed_entity = dict(name=entity.name,
                                    magnitude=entity.sentiment.magnitude,
                                    score=entity.sentiment.score,
                                    salience=entity.salience)
            entities.append(processed_entity)

        return entities


    def concatenate_all_twitter_messages(tweets):
        """ Takes a list of dictionaries of tweets from tweepy
            and concatenates all the message content into a single string.
            Each tweet is separated by a newline.
        """
        messages = []
        for tweet in tweets:
            msg = tweet["text"]
            # Ensure all tweets end with a full stop
            if not msg.endswith("."):
                msg += "."
            messages.append(msg)

        # convert to string, each tweet separated by a newline
        messages = "\n".join(messages)
        return messages


    # =====================================
    # GET SENTIMENT SCORE OF THE TWEETS
    # =====================================
    print("Calculating sentiment of comments")
    # ENTITY LEVEL SENTIMENT ANALYSIS
    concatenated_tweets = concatenate_all_twitter_messages(tweets)
    all_entities = get_entity_level_sentiment(nlp_client, concatenated_tweets)

    desired_entities = [entity for entity in all_entities if entity["name"].lower().replace("#","") in desired_entity_names]

    # AVERAGE OUT THE SCORE OVER THE DESIRED NAMED ENTITIES
    total_score = 0
    for entity in desired_entities:
        total_score += entity["score"]
    sentiment_score = total_score/len(all_entities)
    print(sentiment_score)
    print("Date: "+ date_str)


    # =====================================
    # PUSH THE SENTIMENT SCORE TO BIG QUERY
    # =====================================
    print("Pushing sentiment score to big query")
    rows = [dict(date=date_str, score=sentiment_score)]
    bqclient.insert_rows_json(bq_sentiment_table, rows)
    print("DONE!")
    
if __name__ == '_main_':
    main()