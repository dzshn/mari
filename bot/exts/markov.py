import collections
from typing import Optional, Deque

import discord
import markovify
from discord.ext import commands, tasks


class InformalText(markovify.Text):
    def test_sentence_input(self, sentence: str) -> bool:
        return bool(sentence.strip())

    def sentence_split(self, text: str) -> list[str]:
        sentences = []
        for line in text.splitlines():
            sentences += markovify.split_into_sentences(line)

        return sentences


class Markov(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.models: dict[int, InformalText] = {}
        self.tasks: Deque[tuple[int]] = collections.deque()

    @tasks.loop()
    async def collect_chains(self):
        channel, message = self.tasks.popleft()
        channel: discord.TextChannel = self.bot.get_channel(channel)
        message: discord.Message = await channel.fetch_message(message)

        corpuses: dict[int, list[str]] = collections.defaultdict(list)
        async for msg in channel.history(limit=None):
            if msg.author.bot:
                continue

            if msg.content:
                corpuses[msg.author.id].append(msg.content)

        for user, corpus in corpuses.items():
            model = InformalText('\n'.join(corpus), state_size=3)
            if user in self.models:
                self.models[user] = markovify.combine([self.models[user], model])
            else:
                self.models[user] = model

        await message.reply(
            f'Finished collecting {sum(map(len, corpuses.values()))} '
            f'messages from {len(corpuses.keys())} users!'
        )

        if not self.tasks:
            self.collect_chains.stop()

    @commands.command()
    async def collect(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Collect messages for later impersonation"""
        if channel is None:
            channel = ctx.channel

        self.tasks.append((channel.id, ctx.message.id))
        if not self.collect_chains.is_running():
            self.collect_chains.start()

        await ctx.send('Queued!')

    @commands.command()
    async def impersonate(
        self, ctx: commands.Context, whom: Optional[discord.User] = None, *, text: Optional[str] = None
    ):
        if whom is None:
            whom = ctx.author

        if whom.id not in self.models:
            await ctx.send('No data for that user!')
            return

        if text:
            generated = self.models[whom.id].make_sentence_with_start('text')
        else:
            generated = self.models[whom.id].make_sentence(tries=50)

        await ctx.send(generated)


def setup(bot: commands.Bot):
    bot.add_cog(Markov(bot))
