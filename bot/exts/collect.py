import collections

import discord
from tinydb import TinyDB, where
from discord.ext import commands, tasks

CollectionTask = collections.namedtuple('Task', 'channel message')
CollectionTask.channel: discord.TextChannel
CollectionTask.message: discord.Message


class Collect(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db: TinyDB = bot.db
        self.tasks: collections.deque[CollectionTask] = collections.deque()

    @tasks.loop()
    async def collect_messages(self):
        channel, message = self.tasks.popleft()
        export = []
        async for msg in channel.history(limit=None):
            if msg.author.bot:
                continue

            if msg.content:
                export.append([msg.author.id, msg.content])

        self.db.table('collects').upsert({
            'channel': channel.id,
            'data': export
        }, where('channel') == channel.id)

        await message.reply(
            f'Finished collecting {len(export)} messages!'
        )

        if not self.tasks:
            self.collect_messages.stop()

    @commands.command()
    async def collect(
        self,
        ctx: commands.Context,
        channels: commands.Greedy[discord.TextChannel]
    ):
        """Collect messages for later impersonation"""
        if not channels:
            channels = [ctx.channel]

        await ctx.send('Queued!')

        for ch in channels:
            self.tasks.append(CollectionTask(channel=ch, message=ctx.message))

        if not self.collect_messages.is_running():
            self.collect_messages.start()


def setup(bot: commands.Bot):
    bot.add_cog(Collect(bot))
