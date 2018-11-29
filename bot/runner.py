import argparse
import os
import sys
import time
import json
import calendar
import datetime
import random

from tqdm import tqdm
from pymongo import MongoClient

from bson.objectid import ObjectId

from config import (MONGO_DB_URL, MONGO_DB_NAME, TABLES)

sys.path.append(os.path.join(sys.path[0], '../'))
from instabot import Bot, utils



## Setting up Database connection ##

client = MongoClient(MONGO_DB_URL)
db = client[MONGO_DB_NAME]

#### Setting up Bot #####

bot = Bot(filter_private_users=False,
	stop_words=(),
	blacklist_hashtags=[])



## ENV variables ###

USER_MEDIA_HISTORY = 10
USER_MAX_FOLLOWERS = 100000

UNFOLLOW_DELAY = 3 * 24 * 60 * 60
MAX_AMT_MEDIA_FOLLOW = 3


def get_current_time():
	return calendar.timegm(time.gmtime())


def get_user_target_media(user_id, media_config):
	to_return = []

	media_history = USER_MEDIA_HISTORY

	if "count" in media_config:
		media_history = min(media_history, media_config["count"]) 

	if media_history < 1:
		return []

	medias = bot.get_user_medias(user_id=user_id, filtration=False, is_comment=False)
	if len(medias):
		for i in range(min(media_history,len(medias))):

			media_info = bot.get_media_info(medias[i])[0]

			data = {}
			data["media_id"] = medias[i]
			data["timestamp"] = get_current_time()
			data["taken_at"] = media_info["taken_at"]

			data["caption"] = {}

			data["caption"]["created_at"] = media_info["caption"]["created_at_utc"]
			data["caption"]["text"] = media_info["caption"]["text"]

			if "likers" in media_config and media_config["likers"] == True:
				data["likers"] = bot.get_media_likers(medias[i])
				data["like_count"] = len(data["likers"])

			if "comment" in media_config and media_config["comment"] == True:

				comments = bot.get_media_comments_all(data["media_id"], only_text=False, count=False)

				data["comments"] = []

				for comm in comments:
					comment_data = {}

					comment_data["id"] = comm["pk"]
					comment_data["created_at"] = comm["created_at_utc"]

					comment_data["text"] = comm["text"]
					comment_data["user_id"] = comm["user_id"]

					data["comments"].append(comment_data)

				data["comment_count"] = len(data["comments"])


			to_return.append(data)

	return to_return


def get_user_metadata(target_username=None, target_user_id=None, media_config=None):

	data = {}	
	data["info_at_utc"] = get_current_time()

	if target_username == None:
		if target_user_id == None:
			return None
		else:
			data["user_id"] = target_user_id
			
	else:
		data["ig_username"] = target_username

		if target_user_id == None:
			data["user_id"] = bot.convert_to_user_id(data["ig_username"])
		else:
			data["user_id"] = target_user_id

	data["following"] = bot.get_user_following(user_id=data["user_id"], nfollows=USER_MAX_FOLLOWERS)
	data["following_count"] = len(data["following"])

	data["follower"] = bot.get_user_followers(user_id=data["user_id"], nfollows=USER_MAX_FOLLOWERS)
	data["follower_count"] = len(data["follower"])

	if media_config != None:
		data["media"] = get_user_target_media(user_id=data["user_id"], media_config=media_config)

	return data


def get_job_record(job_id):
	job_config_coll = db[TABLES["JOB_CONFIG"]]


	key = {"_id" : job_id}

	records = list(job_config_coll.find(key))

	if len(records) != 1 :
		return None

	return records[0]

def update_job_record(data):
	job_config_coll = db[TABLES["JOB_CONFIG"]]

	key = {"_id" : data["_id"]}
	job_config_coll.replace_one(key, data)


def add_user_record(data):
	infl_data_coll = db[TABLES["INFLUENCER_DATA"]]

	infl_data_coll.insert_one(data)

def get_config(id, table_name):
	config_coll = db[table_name]


	key = {"_id" : id}

	records = list(config_coll.find(key))

	if len(records) != 1 :
		return None

	return records[0]

def get_people_to_follow(count=50):

	user_follow_coll = db[TABLES["USER_FOLLOW"]]

	key = { "status" : -1 }
	sort_key = [ ("weight" , -1) ]

	return list(user_follow_coll.find(key).sort(sort_key).limit(count))


def update_people_to_follow(data):

	user_follow_coll = db[TABLES["USER_FOLLOW"]]

	key = { "_id" : data["_id"]}

	user_follow_coll.replace_one(key, data)


def get_people_to_unfollow(count=50):

	user_follow_coll = db[TABLES["USER_FOLLOW"]]

	key = { "status" : 0, "unfollowed_time" : {"$lt": get_current_time()} }
	sort_key = [ ("weight" , -1) ]

	return list(user_follow_coll.find(key).sort(sort_key).limit(count))


def add_job_comment(job_record, comment):

	if "runtime_comment" in job_record:

		job_record["runtime_comment"] += ('\n' + comment)

	else:

		job_record["runtime_comment"] = comment

	update_job_record(job_record)

def main():

	# Getting job details
	
	job_id = ObjectId(os.environ['JOB_ID'])
	job_record = get_job_record(job_id)

	if job_record == None:
		return

	# Bot login

	try:

		cred_username = os.environ['USERNAME']
		cred_passwd = os.environ['PASSWORD']

	except:

		add_job_comment(job_record, "ABORT: Username/Password not provided")
		return


	cred_proxy = None

	try:
		cred_proxy = os.environ['PROXY']

	except:

		add_job_comment(job_record, "CAUTION: Proxy not provided.")


	login_success = bot.login(username=cred_username, password=cred_passwd, proxy=cred_proxy)

	if login_success == False:

		job_record["login_issue"] = True
		job_record["login_username"] = cred_username
		job_record["login_issue_solved"] = False

		add_job_comment(job_record, "ABORT: Unable to login.")

		return

	job_record["ran_once"] = True
	update_job_record(job_record)

	job_record["success"] = False
	job_record["start_time"] = get_current_time()

	target_username = None
	target_user_id = None
	media_config = None

	if job_record["type"] == "get_data":

		config_record = get_config(job_record["linked_job_id"], TABLES["INFLUENCER_CONFIG"])
		
		if config_record != None:

			if "ig_username" in config_record:
				target_username = config_record["ig_username"]

			if "user_id" in config_record:
				target_user_id = config_record["user_id"]

			if "media" in config_record:
				media_config = config_record["media"]
			
			data = get_user_metadata(target_username=target_username, target_user_id=target_user_id, media_config=media_config)

			if data != None:
				add_user_record(data)
				job_record["success"] = True

	elif job_record["type"] == "update_follow":
		
		config_record = get_config(job_record["linked_job_id"], TABLES["UPDATE_FOLLOW_CONFIG"])
		
		if config_record != None:

			if "target_ig_username" in config_record:
				target_username = config_record["target_ig_username"]

			if "media" in config_record:
				media_config = config_record["media"]

			
			data = get_user_metadata(target_username=target_username, target_user_id=target_user_id, media_config=media_config)

			if data != None:
				add_user_record(data)
				job_record["success"] = True

	elif job_record["type"] == "follow":

		print("Running job of type follow")
		for user_record in get_people_to_follow(count=10):

			ret_code = bot.follow(user_id=user_record["target_user_id"])

			if ret_code == False:

				print("This user was skipped")

				user_record["status"] = 1
				user_record["skipped"] = 1

				update_people_to_follow(user_record)

			else:

				print("This user was followed")

				bot.like_user(user_id=user_record["target_user_id"], amount= random.randint(1, MAX_AMT_MEDIA_FOLLOW), filtration=False)


				user_record["status"] = 0
				user_record["followed_time"] = get_current_time()
				user_record["unfollowed_time"] = user_record["followed_time"] + UNFOLLOW_DELAY

				update_people_to_follow(user_record)

				job_record["success"] = True

				break

	elif job_record["type"] == "unfollow":
		print("Running job of type follow")

		for user_record in get_people_to_unfollow(count=10):

			ret_code = bot.unfollow(user_id=user_record["target_user_id"])

			user_record["status"] = 1
			update_people_to_follow(user_record)

			if ret_code == True:

				print("This user was unfollowed")


				job_record["success"] = True
				break

	else:

		## TODO: Better solution?
		job_record["ran_once"] = False


	# TODO

	# elif job_record["type"] == "like_hashtag":
	# 	pass



	job_record["completion_time"] = get_current_time()
	update_job_record(job_record)


if __name__ == '__main__':
	main()