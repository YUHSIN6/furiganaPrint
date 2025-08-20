import requests
import discord
from bs4 import BeautifulSoup
import random
from discord.ext import commands, tasks


def askRandomGrammar(level: int = 3):
    """
    The possible levels are 0, 1, 2, 3.
    """
    assert level >= 0 and level <= 3
    # Send a POST and receive the website html code
    url=f"https://nani-blog.com/category/n{level}/"
    website = requests.get(url).text
    soup = BeautifulSoup(website, "html.parser")

    # Fetch the required tags, which are phrasing_text and phrasing_subscript 
    postsList = soup.find("div", attrs={"class": "textwidget custom-html-widget"})
    posts = postsList.findAll("a")

    # Generate random number within the range of the list
    rand = random.randint(0, len(posts)-1)

    # Return the random post and its link
    return posts[rand].get_text(), posts[rand]['href']

class Grammar(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(brief="Send question to all member.", aliases=["sgq"])
    async def sendGrammarQuestion(self, ctx: commands.Context, difficulties: str = "3"):
        """
        Send a random grammar question to all members in the voice room.
        """
        # First get the list of member in the voice channel
        members = ctx.author.voice.channel.members    
        await ctx.send(f"Sending N{difficulties} grammar to {len(members)} members...")

        # Send the question to all members through private message
        for member in members:
            question, link = askRandomGrammar(int(difficulties))
            await member.send(f"**お題**：[{question}]({link})")
        await ctx.send(f"Done!")


# Take action when load
async def setup(bot: commands.Bot):
    print("Grammar setup...")
    await bot.add_cog(Grammar(bot))
    
# Take action when reload
async def teardown(bot: commands.Bot):
    print("Grammar teardown...")

