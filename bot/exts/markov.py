import collections
from typing import Optional

import discord
import markovify
from tinydb import TinyDB, where
from discord.ext import commands, tasks

Task = collections.namedtuple('Task', 'channel message users')
Task.channel: discord.TextChannel
Task.message: discord.Message
Task.users: list[discord.User]


class InformalText(markovify.Text):
    def test_sentence_input(self, sentence: str) -> bool:
        return bool(sentence.strip())

    def sentence_split(self, text: str) -> list[str]:
        sentences = []
        for line in text.splitlines():
            sentences += markovify.split_into_sentences(line)

        return sentences


class BrokenChain(Exception):
    pass


class Markov(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db: TinyDB = bot.db
        self.tasks: collections.deque[Task] = collections.deque()

    @tasks.loop()
    async def collect_chains(self):
        channel, message, users = self.tasks.popleft()

        corpuses: dict[discord.User, list[str]] = collections.defaultdict(list)
        async for msg in channel.history(limit=None):
            if msg.author.bot:
                continue

            if users is not None and msg.author not in users:
                continue

            if msg.content:
                corpuses[msg.author].append(msg.content)

        for user, corpus in corpuses.items():
            self.db.table('chains').upsert({
                'channel': channel.id,
                'user': user.id,
                'model': InformalText('\n'.join(corpus), state_size=3).to_dict()
            }, (where('channel') == channel.id) & (where('user') == user.id))

        await message.reply(
            f'Finished collecting {sum(map(len, corpuses.values()))} '
            f'messages from {len(corpuses.keys())} users!'
        )

        if not self.tasks:
            self.collect_chains.stop()

    @commands.command()
    async def collect(
        self,
        ctx: commands.Context,
        users: commands.Greedy[discord.Member],
        channel: Optional[discord.TextChannel] = None
    ):
        """Collect messages for later impersonation"""
        if channel is None:
            channel = ctx.channel

        self.tasks.append(Task(channel=channel, message=ctx.message, users=users or None))
        if not self.collect_chains.is_running():
            self.collect_chains.start()

        await ctx.send('Queued!')

    @commands.command()
    async def impersonate(
        self,
        ctx: commands.Context,
        users: commands.Greedy[discord.Member],
        channels: commands.Greedy[discord.TextChannel],
        *,
        text: Optional[str] = None
    ):
        """Generate some text based off a user's messages

        Optionally provide:
            Users: whose messages to use (default: command author)
            Channels: which channels to use chains from (default: current channel)
            Text: what should the message start with"""
        models: list[InformalText] = []
        if not users:
            users = [ctx.author]
        if not channels:
            channels = [ctx.channel]

        for channel in channels:
            for user in users:
                query = (where('user') == user.id) & (where('channel') == channel.id)
                if self.db.table('chains').contains(query):
                    models.append(InformalText.from_dict(self.db.table('chains').get(query)['model']))

        if not models:
            await ctx.send('No data!')
            return

        model = markovify.combine(models)

        try:
            if text:
                generated = model.make_sentence_with_start(text, strict=False, tries=500)
            else:
                generated = model.make_sentence(tries=500)

            if generated is None or not generated.strip():
                raise ValueError('Failed to generate message')

        except (KeyError, ValueError, markovify.text.ParamError) as e:
            raise BrokenChain from e

        await ctx.send(generated)

    @commands.command()
    async def hivemind(
        self,
        ctx: commands.Context,
        channels: commands.Greedy[discord.TextChannel] = None,
        text: Optional[str] = None
    ):
        """Generate some text based off users in the server

        Optionally provide:
            Channels: which channels to use (default: current channel)
            Text: what should the message start with"""
        models: list[InformalText] = []
        if not channels:
            channels = [ctx.channel]

        for channel in channels:
            for data in self.db.table('chains').search(where('channel') == channel.id):
                models.append(InformalText.from_dict(data['model']))

        if not models:
            await ctx.send('No data!')
            return

        model = markovify.combine(models)

        try:
            if text:
                generated = model.make_sentence_with_start(text, strict=False, tries=500)
            else:
                generated = model.make_sentence(tries=500)

            if generated is None or not generated.strip():
                raise ValueError('Failed to generate message')

        except (KeyError, ValueError, markovify.text.ParamError) as e:
            raise BrokenChain from e

        await ctx.send(generated)

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandInvokeError) and isinstance(error.original, BrokenChain):
            await ctx.send("I couldn't come up with anything!")

        else:
            raise error


def setup(bot: commands.Bot):
    bot.add_cog(Markov(bot))
