import argparse
import os
import sys
import time
import json
import calendar
import datetime

sys.path.append(os.path.join(sys.path[0], '../'))
from instabot import Bot, utils

from tqdm import tqdm
from pymongo import MongoClient

from config import (MONGO_DB_URL, MONGO_DB_NAME, TABLES)


HASH_MEDIA_COLL_NAME = "hashtag_media"
POTENTAIL_INFLUENCER = "potential_influencer"


def add_user_metadata(user_id, bot, pot_infl_coll):

	try:

		if pot_infl_coll.count_documents({"user_id": user_id}) > 0:
			# Record already present
			return

		data = {}

		data["user_id"] = user_id
		data["info_at_utc"] = calendar.timegm(time.gmtime())


		user_id_info = bot.get_user_info(user_id, use_cache=True)

		data["username"] = user_id_info["username"]
		data["following_count"] = user_id_info["following_count"]
		data["follower_count"] = user_id_info["follower_count"]

		pot_infl_coll.insert_one(data)

	except:
		print("Unexpected error for user_id : " + str(user_id))
		print(sys.exc_info()[0])




def main():
	parser = argparse.ArgumentParser(add_help=True)
	parser.add_argument('-u', type=str, help="username")
	parser.add_argument('-p', type=str, help="password")
	parser.add_argument('-proxy', type=str, help="proxy")
	parser.add_argument('-max_time', type=int, help="proxy")
	args = parser.parse_args()

	bot = Bot()
	bot.login(username=args.u, password=args.p
	          ,proxy=args.proxy)

	client = MongoClient(MONGO_DB_URL)
	db = client[MONGO_DB_NAME]

	hash_media_coll = db[HASH_MEDIA_COLL_NAME]
	pot_infl_coll = db[POTENTAIL_INFLUENCER]

	max_time = args.max_time
	i = 1

	while True:

		records = list(hash_media_coll.find({"info_at_utc": {"$gte": max_time}}).sort([("info_at_utc" , 1)]).limit(50))
		# records = list(hash_media_coll.find({}))

		for record in records:

			print(str(i) + " : " + str(record["media_id"]) + " : " + str(record["info_at_utc"]))
			print("Liker count: " + str(len(record["likers"])))
			print("Commenters count: " + str(len(record["commenters"])))

			i += 1

			for user_id in record["likers"]:
				add_user_metadata(user_id, bot, pot_infl_coll)

			for user_id in record["commenters"]:
				add_user_metadata(user_id, bot, pot_infl_coll)

			max_time = max(max_time, record["info_at_utc"])

		# break


if __name__ == '__main__':
	main()