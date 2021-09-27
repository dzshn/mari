from typing import Optional

import discord
import markovify
from tinydb import TinyDB, where
from discord.ext import commands


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
            for user, corpus in self.db.table('collects').get(where('channel') == channel.id):
                if user in users:
                    models.append(InformalText('\n'.join(corpus)))

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
