import discord
from discord.ext import commands
from tinydb import TinyDB, where


class Stats(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db: TinyDB = bot.db

    @commands.command()
    async def stats(self, ctx: commands.Context):
        db_size = len(str(self.db.storage.read())) / 2**20  # bytes -> mb
        chains = len(self.db.table("chains"))
        users = len(set(i['user'] for i in self.db.table('chains').all()))
        channels = len(set(i['channel'] for i in self.db.table('chains').all()))
        user_chains = len(self.db.table('chains').search(where('user') == ctx.author.id))
        channel_chains = len(self.db.table('chains').search(where('channel') == ctx.channel.id))
        embed = discord.Embed(
            color=0xff5757,
            title='Data',
            description=(
                f'`db.json` has {db_size:.2f}mb of data\n'
                f'There are `{chains}` chains stored from `{users}` users and `{channels}` channels\n'
                f'Of these, `{user_chains}` are from you and `{channel_chains}` are from this channel'
            )
        )

        await ctx.send(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(Stats(bot))
