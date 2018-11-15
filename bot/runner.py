import argparse
import os
import sys
import time
import json
import calendar
import datetime

from tqdm import tqdm
from pymongo import MongoClient

from config import (MONGO_DB_URL, MONGO_DB_NAME, TABLES)

sys.path.append(os.path.join(sys.path[0], '../'))
from instabot import Bot, utils



## Setting up Database connection ##

client = MongoClient(MONGO_DB_URL)
db = client[MONGO_DB_NAME]




#### Setting up Bot #####

bot = Bot()
bot.login(username=os.environ['USERNAME'], 
	password=os.environ['PASSWORD'],
	proxy=os.environ['PROXY'],
	filter_private_users=False,
	stop_words=(),
	blacklist_hashtags=[])



## ENV variables ###

USER_MEDIA_HISTORY = 10
USER_MAX_FOLLOWERS = 100000


def get_user_target_media(user_id, media_history=USER_MEDIA_HISTORY):
	to_return = []

	if media_history < 1:
		return []

	medias = bot.get_user_medias(user_id=user_id, filtration=False, is_comment=False)
	if len(medias):
		for i in range(min(media_history,len(medias))):

			media_info = bot.get_media_info(data["media_id"])[0]

			data = {}
			data["media_id"] = medias[i]
			data["timestamp"] = calendar.timegm(time.gmtime())
			data["taken_at"] = media_info["taken_at"]

			data["caption"] = {}

			data["caption"]["created_at"] = media_info["caption"]["created_at_utc"]
			data["caption"]["text"] = media_info["caption"]["text"]

			data["likers"] = bot.get_media_likers(medias[i])
			data["like_count"] = len(data["likers"])

			to_return.append(data)

	return to_return


def get_user_metadata(config):#, melrose_coll):

	data = {}	
	data["info_at_utc"] = calendar.timegm(time.gmtime())

	if "target_ig_username" not in config :
		if "target_ig_user_id" not in config:
			return None
		else:
			data["user_id"] = config["target_ig_user_id"]
			
	else:
		data["ig_username"] = config["target_ig_username"]
		data["user_id"] = bot.convert_to_user_id(data["ig_username"])
	

	data["following"] = bot.get_user_following(user_id=data["user_id"], nfollows=USER_MAX_FOLLOWERS)
	data["following_count"] = len(data["following"])

	data["follower"] = bot.get_user_followers(user_id=data["user_id"], nfollows=USER_MAX_FOLLOWERS)
	data["follower_count"] = len(data["follower"])

	data["media"] = get_user_target_media(user_id=data["user_id"], media_history=USER_MEDIA_HISTORY)

	return data


def get_job_record(job_id):
	job_config_coll = db[TABLES["JOB_CONFIG"]]


	key = {"_id" : job_id}

	records = list(pot_infl_coll.find(key))

	if len(records) != 1 :
		return None

	return records[0]

def update_job_record(data):
	job_config_coll = db[TABLES["JOB_CONFIG"]]

	key = {"_id" : data["_id"]}
	job_config_coll.update(key, data)


def add_user_record(data):
	infl_data_coll = db[TABLES["INFLUENCER_DATA"]]

	infl_data_coll.insert_one(data)


def main():
	job_record = get_job_record(os.environ['JOB_ID'])

	if job_record == None:
		return


	if job_record["type"] == "get_data":

		data = get_user_metadata(job_record)

		if data == None:
			return

		add_user_record(data)

	else:
		return



	job_record["completion_time"] = calendar.timegm(time.gmtime())
	update_job_record(job_record)


	# time.sleep(60)



	











if __name__ == '__main__':
	main()



