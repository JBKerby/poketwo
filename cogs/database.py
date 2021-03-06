import discord
import pymongo
from bson.objectid import ObjectId
from discord.ext import commands


class Database(commands.Cog):
    """For database operations."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def fetch_member_info(self, member: discord.Member):
        return await self.bot.mongo.Member.find_one(
            {"id": member.id}, {"pokemon": 0, "pokedex": 0}
        )

    async def fetch_next_idx(self, member: discord.Member, reserve=1):
        result = await self.bot.mongo.db.member.find_one_and_update(
            {"_id": member.id}, {"$inc": {"next_idx": reserve}}
        )
        return result["next_idx"]

    async def reset_idx(self, member: discord.Member, value):
        result = await self.bot.mongo.db.member.find_one_and_update(
            {"_id": member.id}, {"$set": {"next_idx": value}}
        )
        return result["next_idx"]

    async def fetch_pokedex(self, member: discord.Member, start: int, end: int):

        filter_obj = {}

        for i in range(start, end):
            filter_obj[f"pokedex.{i}"] = 1

        return await self.bot.mongo.Member.find_one({"id": member.id}, filter_obj)

    async def fetch_market_list(self, skip: int, limit: int, aggregations=[]):
        return await self.bot.mongo.db.listing.aggregate(
            [*aggregations, {"$skip": skip}, {"$limit": limit}], allowDiskUse=True
        ).to_list(None)

    async def fetch_market_count(self, aggregations=[]):

        result = await self.bot.mongo.db.listing.aggregate(
            [*aggregations, {"$count": "num_matches"}], allowDiskUse=True
        ).to_list(None)

        if len(result) == 0:
            return 0

        return result[0]["num_matches"]

    async def fetch_pokemon_list(
        self, member: discord.Member, skip: int, limit: int, aggregations=[]
    ):
        return await self.bot.mongo.db.pokemon.aggregate(
            [
                {"$match": {"owner_id": member.id}},
                {"$sort": {"idx": 1}},
                {"$project": {"pokemon": "$$ROOT", "idx": "$idx"}},
                *aggregations,
                {"$skip": skip},
                {"$limit": limit},
            ],
            allowDiskUse=True,
        ).to_list(None)

    async def fetch_pokemon_count(self, member: discord.Member, aggregations=[]):

        result = await self.bot.mongo.db.pokemon.aggregate(
            [
                {"$match": {"owner_id": member.id}},
                {"$project": {"pokemon": "$$ROOT"}},
                *aggregations,
                {"$count": "num_matches"},
            ],
            allowDiskUse=True,
        ).to_list(None)

        if len(result) == 0:
            return 0

        return result[0]["num_matches"]

    async def fetch_pokedex_count(self, member: discord.Member, aggregations=[]):

        result = await self.bot.mongo.db.member.aggregate(
            [
                {"$match": {"_id": member.id}},
                {"$project": {"pokedex": {"$objectToArray": "$pokedex"}}},
                {"$unwind": {"path": "$pokedex"}},
                {"$replaceRoot": {"newRoot": "$pokedex"}},
                *aggregations,
                {"$group": {"_id": "count", "result": {"$sum": 1}}},
            ],
            allowDiskUse=True,
        ).to_list(None)

        if len(result) == 0:
            return 0

        return result[0]["result"]

    async def fetch_pokedex_sum(self, member: discord.Member, aggregations=[]):

        result = await self.bot.mongo.db.member.aggregate(
            [
                {"$match": {"_id": member.id}},
                {"$project": {"pokedex": {"$objectToArray": "$pokedex"}}},
                {"$unwind": {"path": "$pokedex"}},
                {"$replaceRoot": {"newRoot": "$pokedex"}},
                *aggregations,
                {"$group": {"_id": "sum", "result": {"$sum": "$v"}}},
            ],
            allowDiskUse=True,
        ).to_list(None)

        if len(result) == 0:
            return 0

        return result[0]["result"]

    async def update_member(self, member, update):
        if hasattr(member, "id"):
            member = member.id
        return await self.bot.mongo.db.member.update_one({"_id": member}, update)

    async def update_pokemon(self, pokemon, update):
        if hasattr(pokemon, "id"):
            pokemon = pokemon.id
        if hasattr(pokemon, "_id"):
            pokemon = pokemon._id
        if isinstance(pokemon, dict) and "_id" in pokemon:
            pokemon = pokemon["_id"]
        return await self.bot.mongo.db.pokemon.update_one({"_id": pokemon}, update)

    async def fetch_pokemon(self, member: discord.Member, idx: int):

        if isinstance(idx, ObjectId):
            result = await self.bot.mongo.db.pokemon.find_one({"_id": idx})
        elif idx == -1:
            count = await self.fetch_pokemon_count(member)
            result = await self.bot.mongo.db.pokemon.aggregate(
                [
                    {"$match": {"owner_id": member.id}},
                    {"$sort": {"idx": 1}},
                    {"$project": {"pokemon": "$$ROOT", "idx": "$idx"}},
                    {"$skip": count - 1},
                    {"$limit": 1},
                ],
                allowDiskUse=True,
            ).to_list(None)

            if len(result) == 0 or "pokemon" not in result[0]:
                result = None
            else:
                result = result[0]["pokemon"]
        else:
            result = await self.bot.mongo.db.pokemon.find_one(
                {"owner_id": member.id, "idx": idx}
            )

        if result is None:
            return None

        return self.bot.mongo.Pokemon.build_from_mongo(result)

    async def fetch_guild(self, guild: discord.Guild):
        g = await self.bot.mongo.Guild.find_one({"id": guild.id})
        if g is None:
            g = self.bot.mongo.Guild(id=guild.id)
            await g.commit()
        return g

    async def update_guild(self, guild: discord.Guild, update):
        return await self.bot.mongo.db.guild.update_one(
            {"_id": guild.id}, update, upsert=True
        )

    async def fetch_channel(self, channel: discord.TextChannel):
        c = await self.bot.mongo.Channel.find_one({"id": channel.id})
        if c is None:
            c = self.bot.mongo.Channel(id=channel.id)
            await c.commit()
        return c

    async def update_channel(self, channel: discord.TextChannel, update):
        return await self.bot.mongo.db.channel.update_one(
            {"_id": channel.id}, update, upsert=True
        )


def setup(bot: commands.Bot):
    bot.add_cog(Database(bot))
