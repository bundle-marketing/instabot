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

AMNT_HASHTAG = 500



def main():
	parser = argparse.ArgumentParser(add_help=True)
	parser.add_argument('-u', type=str, help="username")
	parser.add_argument('-p', type=str, help="password")
	parser.add_argument('-proxy', type=str, help="proxy")
	parser.add_argument('--target_hashtags', type=str, nargs='+', help='List of hashtags to target')
	args = parser.parse_args()

	bot = Bot()
	bot.login(username=args.u, password=args.p
	          ,proxy=args.proxy)

	client = MongoClient(MONGO_DB_URL)
	db = client[MONGO_DB_NAME]

	hash_media_coll = db[HASH_MEDIA_COLL_NAME]

	input_hashtags = list(set(map( lambda x: x.lstrip('#') , args.target_hashtags)))

	for hashtag in input_hashtags:

		print("Getting media of hashtag " + hashtag)

		medias = bot.get_total_hashtag_medias(hashtag, amount=AMNT_HASHTAG)

		for media_id in medias:

			try:
				info = bot.get_media_info(media_id)[0]

				to_add = {}
				to_add["media_id"] = info["pk"]
				to_add["hashtag"] = hashtag
				to_add["owner"] = info["user"]["pk"]

				# try:
				# 	to_add["media_created_at_utc"] = info["caption"]["created_at_utc"] # 1540188551
				# finally:
				# 	to_add["media_created_at_utc"] = None


				to_add["info_at_utc"] = calendar.timegm(time.gmtime())

				to_add["likers"] = bot.get_media_likers(media_id)
				to_add["commenters"] = bot.get_media_commenters(media_id)

				hash_media_coll.insert_one(to_add)

			except:
				pass

			
			finally:
				pass

if __name__ == '__main__':
	main()