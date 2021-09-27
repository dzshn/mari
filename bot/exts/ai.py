import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from discord.ext import commands

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
logging.basicConfig(level=logging.FATAL)


class AI(commands.Cog):
    def __init__(self, bot: commands.Bot):
        try:
            import transformers
        except ImportError:
            bot.remove_cog('AI')

        self.bot = bot
        self.gpt2pipeline = transformers.pipeline('text-generation', model='gpt2')

    @commands.command()
    async def gpt2(self, ctx: commands.Context, max_words: Optional[int], *, text: str):
        result = None

        def _():
            nonlocal result
            result = self.gpt2pipeline(text, max_length=50)

        async with ctx.channel.typing():
            with ThreadPoolExecutor() as pool:
                await self.bot.loop.run_in_executor(pool, _)

        await ctx.send(result[0]['generated_text'][:2000])


def setup(bot: commands.Bot):
    bot.add_cog(AI(bot))
