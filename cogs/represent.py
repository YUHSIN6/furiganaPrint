from ast import arg
import dis
from unittest import result
import discord
from discord.ext import commands, tasks
from datetime import date, datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from table2ascii import Alignment, table2ascii as t2a, PresetStyle

# channel IDs
testChannel = 1033739167743606847
practiceRoomChannel = 1025050215499190306
# The IDs used to tag
name2Id = {
    "宇昕": 468711293264855052,
    "冠霆": 701401037621166169,
    "禾堃": 561559537539088385,
    "致越": 615891322804371485,
    "陳曦": 917446775873343600,
    "振君": 796434960256991262,
    "瑋棻": 987612507738877972
}
id2Name = {
    468711293264855052: "宇昕",
    701401037621166169: "冠霆",
    561559537539088385: "禾堃",
    615891322804371485: "致越",
    917446775873343600: "陳曦",
    796434960256991262: "振君",
    987612507738877972: "瑋棻"
}
enterDay = {
    "宇昕": "01/01",
    "冠霆": "01/01",
    "禾堃": "01/01",
    "致越": "01/01",
    "陳曦": "01/01",
    "振君": "01/01",
    "瑋棻": "04/29"
}
# The id of the bot
botId = 1196679798525808720
# The name of admin
admin = ["冠霆", "禾堃"]

# reminderScheduler
remindScheduler: AsyncIOScheduler
noReminderToday = False
todayReminderIDs = []

daysOfMonth = [0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

# Utility functions

def half2full(s: str) -> str:
    result = ''
    for c in s:
        result += chr(ord(c)+65248)
    return result

def full2half(s: str) -> str:
    result = ''
    for c in s:
        result += chr(ord(c)-65248)
    return result

def date2week(m, d):
    """
    Transferring dates to week. Input should be month and day.    
    """
    date = sum(daysOfMonth[0:m]) + d
    return (date-1) // 7 + 1

def week2date(week):
    """
    Transferring week to date (date for sectionA and sectionC),
    it should be smaller than 52.    
    """
    assert(week <= 52)
    sectionA, sectionB, sectionC = [1, 2], [1, 5], [1, 7]
    for i in range(week-1):
        sectionA[1] += 7
        if sectionA[1] > daysOfMonth[sectionA[0]]:
            sectionA = [sectionA[0] + 1, sectionA[1] - daysOfMonth[sectionA[0]]]
        sectionB[1] += 7
        if sectionB[1] > daysOfMonth[sectionB[0]]:
            sectionB = [sectionB[0] + 1, sectionB[1] - daysOfMonth[sectionB[0]]]
        sectionC[1] += 7
        if sectionC[1] > daysOfMonth[sectionC[0]]:
            sectionC = [sectionC[0] + 1, sectionC[1] - daysOfMonth[sectionC[0]]]
    return f"{sectionA[0]:02d}/{sectionA[1]:02d}", f"{sectionB[0]:02d}/{sectionB[1]:02d}", f"{sectionC[0]:02d}/{sectionC[1]:02d}"

grammarSection = "A"
def scheduleOneDay(member, init, futsugou, lastDone, section, date):
    """
    Input the `member` dict and `init`, `futsugou` data, and who had represented last time(`lastDone`). \n
    Then it will return the people for the representation of the day (and update member dict)
    """
    if init != None:
        # Use initial data
        if init[0] == "中止":
            return "中止"
        elif init[0] == "文法":
            return "文法"
        else:
            if init[0][0] not in  ["*", "-"]:
                member[init[0]] += 1
            if init[1][0] not in  ["*", "-"]:
                member[init[1]] += 1
            return init
    else:
        if len(futsugou) >= 4:
            return "中止"
        if grammarSection == section and datetime.strptime(f'2024/{date}', "%Y/%m/%d").date() > datetime.strptime(f'2024/02/27', "%Y/%m/%d").date():
            return "文法"
        # List of member, for sorting
        cnt = []
        for v in member.keys():
            # Dont use the member to schedule if the one hasn't entered yet
            if datetime.strptime(f'2024/{enterDay[v]}', "%Y/%m/%d").date() > datetime.strptime(f'2024/{date}', "%Y/%m/%d").date():
                continue
            cnt.append([v, member[v]])
        cnt.sort(key=lambda mem: mem[1])
        
        ans = []
        # Choose from the member list
        for m, _ in cnt:
            if (m not in lastDone) and (m not in futsugou) and (len(ans) < 2):  
                member[m] += 1
                ans.append(m)
        # All members have tried but not available
        # Use members in lastDone
        for m in lastDone:
            if (futsugou != None and m not in futsugou) and (len(ans) < 2):
                member[m] += 1
                ans.append(m)
        # Still can not find enough people
        if len(ans) < 2:
            for m in ans:
                member[m] -= 1
            return "中止"
        elif len(ans) == 2:
            return ans     
        else:
            return "中止"

def scheduler(end=None):
    """
    Generate scheduler from the first week to last week.
    Return a list of scheduler based on week number `end`.
    If `end` was not given, it will generate schedule until today.
    """
    # Handle if end is not given
    if end == None:
        end = date2week(datetime.today().month, datetime.today().day) - 1
    
    # Init member dict
    member = {
        "冠霆": 0,
        "禾堃": 0,
        "致越": 0,
        "宇昕": 0,
        "陳曦": 0,
        "振君": 0,
        "瑋棻": 0
    }
    
    # First read in futsugou
    with open('./data/futsugou.txt', 'r') as f:
        temp = f.readlines()
        futsugou = {}
        for t in temp:
            d = t[:-1].split(' ') if t[-1] == "\n" else t.split(' ')
            futsugou.update({d[0]: d[1:]})

    # Second read in initialization
    with open('./data/init.txt', 'r') as f:
        temp = f.readlines()
        init = {}
        for t in temp:
            d = t[:-1].split(' ') if t[-1] == "\n" else t.split(' ')
            init.update({d[0]: d[1:]})

    # Generate schedule
    result = []
    lastDone = []
    for w in range(1, end+1):
        sectionAdate, sectionBdate, sectionCdate = week2date(w)
        print("Week", w, ":", sectionAdate, sectionBdate, sectionCdate)

        # Process section A
        _init = init.get(sectionAdate)
        _futsugou = futsugou.get(sectionAdate)
        if _futsugou == None: _futsugou = []
        sectionAmember = scheduleOneDay(member, _init, _futsugou, lastDone, "A", sectionAdate)
        print(sectionAmember)
        if sectionAmember != "中止" and sectionAmember != "文法":
            lastDone = sectionAmember

        # print(sectionAmember)
        # Process section B
        _init = init.get(sectionBdate)
        _futsugou = futsugou.get(sectionBdate)
        if _futsugou == None: _futsugou = []
        sectionBmember = scheduleOneDay(member, _init, _futsugou, lastDone, "B", sectionBdate)
        print(sectionBmember)
        if sectionBmember != "中止" and sectionBmember != "文法":
            lastDone = sectionBmember

        # print(sectionBmember)
        # Process section C
        _init = init.get(sectionCdate)
        _futsugou = futsugou.get(sectionCdate)
        if _futsugou == None: _futsugou = []
        sectionCmember = scheduleOneDay(member, _init, _futsugou, lastDone, "C", sectionCdate)
        print(sectionCmember)
        if sectionCmember != "中止" and sectionCmember != "文法":
            lastDone = sectionCmember

        # print(sectionCmember)
        result.append([sectionAdate, sectionAmember, sectionBdate, sectionBmember, sectionCdate, sectionCmember])

    print(result)

    # Return result
    return result, member

def generateTableSchedule(result, old: bool=True):
    """
    Transform data `result` into the format of table.
    If `old` is `True`, then the old schedule will be printed.
    """
    header = ['wk', 'Section A', 'Section B', 'Section C']
    thisWeek = date2week(datetime.today().month, datetime.today().day)
    body = []
    for w, data in enumerate(result, 1):
        if old or w >= thisWeek:
            sectionAdate, sectionAmember, sectionBdate, sectionBmember, sectionCdate, sectionCmember = data

            if sectionAmember in ["中止", "文法"]:
                sectionAtext = f"{sectionAmember}　　 "
            else:
                member = ""
                for mem in sectionAmember:
                    if mem[0] not in ["-", "*"]: member += mem + " "

                    else: member += "　　"
                sectionAtext = f"{member}"

            if sectionBmember in ["中止", "文法"]:
                sectionBtext = f"{sectionBmember}　　 "
            else:
                member = ""
                for mem in sectionBmember:
                    if mem[0] not in ["-", "*"]: member += mem + " "
                    else: member += "　　"
                sectionBtext = f"{member}"

            if sectionCmember in ["中止", "文法"]:
                sectionCtext = f"{sectionCmember}　　 "
            else:
                member = ""
                for mem in sectionCmember:
                    if mem[0] not in ["-", "*"]: member += mem + " "
                    else: member += "　　"
                sectionCtext = f"{member}"

            body.append([f"{w:02d}({sectionAdate},{sectionBdate[-2:]},{sectionCdate[-2:]})", sectionAtext, sectionBtext, sectionCtext])

    output = t2a(
        header=header,
        body=body,
        style=PresetStyle.plain,
        alignments=Alignment.CENTER,
        first_col_heading=True,
    )

    return f'```\n{output}\n```'

def generateTableMember(member):
    # Remove 振君 from dict member
    member.pop("振君")

    header = list(member.keys())
    body = [[half2full(f'{member[m]:02d}') for m in member.keys()]]


    output = t2a(
            header=header,
            body=body,
            style=PresetStyle.minimalist,
            cell_padding=2,
            number_alignments=Alignment.CENTER,
            alignments= Alignment.CENTER,
            first_col_heading=False,
        )

    return f'```\n{output}   　　　　\n```'

class Represent(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.question = [] # Store the question data
        # Zero means not in session
        self.uploadSession = {
            "冠霆": 0, "禾堃": 0, "致越": 0,
            "宇昕": 0, "陳曦": 0, "振君": 0, "瑋棻": 0
        }
        self.uploadData = {
            "冠霆": [], "禾堃": [], "致越": [],
            "宇昕": [], "陳曦": [], "振君": [], "瑋棻": []
        }
        self.replySession = {
            "冠霆": 0, "禾堃": 0, "致越": 0,
            "宇昕": 0, "陳曦": 0, "振君": 0, "瑋棻": 0
        }
        self.removeSession = {
            "冠霆": [], "禾堃": [], "致越": [],
            "宇昕": [], "陳曦": [], "振君": [], "瑋棻": []
        }
        self.adminOperate = False
        self.adminTarget = ""
    
    # Commands
    
    listHelp = """
List out the schedule from the first week to the this week.
There are three arguments can be used:

  `past` or `p`：past schedule
  `future` or `f`：future schedule
  `all` or `a`：all schedule

If no argument is given, then it will list out the schedule in the next 3 weeks.
"""
    @commands.command(brief="List out the schedule.", aliases=["ls", "listSchedule"], help=listHelp)
    async def schedule(self, ctx: commands.Context):
        # Parse args
        mode = "future"
        if len(ctx.message.content.split(" ")) == 2:
            arg = ctx.message.content.split(" ")[1]
            if arg in ["past", "p"]:
                mode = "past"
            elif arg in ["future", "f"]:
                mode = "future"
            elif arg in ["all", "a"]:
                mode = "all"
            else:
                await ctx.send("引数が間違っています。以下の引数が使えます：\n`p`：過去のスケジュール\n`f`：未来のスケジュール\n`a`：全てのスケジュール")
                return
        elif len(ctx.message.content.split(" ")) > 2:
            await ctx.send("引数が間違っています。以下の引数が使えます：\n`p`：過去のスケジュール\n`f`：未来のスケジュール\n`a`：全てのスケジュール")
            return

        # Generate table
        thisweek = date2week(datetime.today().month, datetime.today().day)  
        if mode == "future": # List out the schedule in the next five weeks
            result, _ = scheduler(thisweek + 3)     
            table = generateTableSchedule(result, old=False)
            title = "今週から 4 週間内のスゲジュウル："
        elif mode == "past":
            result, _ = scheduler()
            table = generateTableSchedule(result, old=True)
            # table = table + "\n\*が付いてる人は、その日の発表をすっぽかした。😐" 
            title = "過去のスゲジュウル："
        elif mode == "all":
            result, _ = scheduler(thisweek + 3)        
            table = generateTableSchedule(result, old=True)
            # table = table + "\n\*が付いてる人は、その日の発表をすっぽかした。😐" 
            title = "全てのスゲジュウル："
        
        # Send embed
        embed = discord.Embed(
            title=title,
            description=table, 
            color=discord.Color.blue()
        )
        # Count the number of representation until today
        thisWeek = date2week(datetime.today().month, datetime.today().day)
        result, member = scheduler(thisWeek)
        weekdays = [1, 4, 6]
        for idx, w in enumerate(weekdays):
            if type(result[-1][idx*2+1]) != list: 
                continue
            if datetime.today().weekday() < w or (datetime.today().weekday() == w and datetime.today().hour < 22):
                for mem in result[-1][idx*2+1]:
                    if mem[0] not in ["*", "-"]:
                        member[mem] -= 1
            # else:
            #     for mem in result[-1][idx*2+1]:
            #         if mem[0] == "*": # The guy doesn't present at that day
            #             member[mem] -= 1
        embed.add_field(name="皆の発表回数：", value=generateTableMember(member), inline=False)
        await ctx.send(embed=embed)

    dataHelp = """
List out the data of the representation.

Arguments:

    `me` or `m`: List out the data of the user.
    `all` or `a`: List out the data of all users.
    name: List out the data of the user.

If the argument is not given, then it will list out the data of all users.
"""
    @commands.command(brief="List out the data.", aliases=["ld", "listData"], help=dataHelp)
    async def data(self, ctx: commands.Context):
        mode = "all"
        name = "皆"
        if len(ctx.message.content.split(" ")) == 2:
            arg = ctx.message.content.split(" ")[1]
            mode = "name"
            if arg in ["me", "m"]:
                name = id2Name.get(ctx.author.id)
                if name == None:
                    await ctx.send(f"{name}さんは日本語練習のメンバーではないので、この機能が使えません。")
                    return
            elif arg in ["all", "a"]:
                mode = "all"
                name = "皆"
            else:
                name = arg
                if name not in name2Id.keys():
                    await ctx.send(f"{name}さんは日本語練習のメンバーではないので、この機能が使えません。")
                    return
        elif len(ctx.message.content.split(" ")) > 2:
            await ctx.send("引数が間違っています。以下の引数が使えます：\n`[me|m]`：自分のデータ\n名前：その人のデータ\n`[all|a]`：全てのデータ")
            return

        record = []
        with open('./data/represent_data.txt', 'r') as f:
            temp = f.readlines()
            for t in temp:
                d = t[:-1].split(' ') if t[-1] == "\n" else t.split(' ')
                if mode == "all":
                    # If last person shares the same title, then they did the representation together and its section C
                    if len(record) and record[-1][3] == d[3] and d[2] == "C":
                        record[-1][0] += f' {d[0]}'
                    else:
                        record.append(d)
                else: # mode == "name"
                    # Represent time
                    rtime = datetime.strptime(f'2024/{d[1]}/22', "%Y/%m/%d/%H")
                    # Current time
                    ctime = datetime.now()
                    if d[0] == name and rtime < ctime:
                        record.append(d)

        pages = []
        num_pages = len(record) // 10 + 1 if len(record) % 10 else len(record) // 10
        for i in range(0, len(record), 10): # Every page has 10 records
            embed = discord.Embed(
                title=f"{name}さんの発表記録：",
                description=f"Page {i//10+1} / {num_pages}",
                color=discord.Color.blue()
            )
            for r in record[i:i+10]:
                if len(r) == 6:
                    embed.add_field(name=f"{r[0]} {r[1]} Section {r[2]}： {r[3]}", value=f"[pptリンク]({r[4]}) [録画リンク]({r[5]})", inline=False)
                elif len(r) == 5:
                    embed.add_field(name=f"{r[0]} {r[1]} Section {r[2]}： {r[3]}", value=f"[pptリンク]({r[4]})", inline=False)

            pages.append(embed)

        message = await ctx.send(embed = pages[-1])

        if num_pages > 1:
            await message.add_reaction('⏮')
            await message.add_reaction('◀')
            await message.add_reaction('▶')
            await message.add_reaction('⏭')

            def check(reaction, user):
                return user == ctx.author

            i = 0
            reaction = None

            while True:
                if str(reaction) == '⏮':
                    i = 0
                    await message.edit(embed = pages[i])
                elif str(reaction) == '◀':
                    if i > 0:
                        i -= 1
                        await message.edit(embed = pages[i])
                elif str(reaction) == '▶':
                    if i < len(pages)-1:
                        i += 1
                        await message.edit(embed = pages[i])
                elif str(reaction) == '⏭':
                    i = len(pages)-1
                    await message.edit(embed = pages[i])
                
                try:
                    reaction, user = await self.bot.wait_for('reaction_add', timeout = 30.0, check = check)
                    print(reaction, user)
                    await message.remove_reaction(reaction, user)
                    print("remove action done")
                except:
                    break

            await message.clear_reactions()

    inconvHelp="""
Check or choose the inconvenience time of the user.

Arguments:
    
    `check` or `c`: Display the inconvenience time of the user.
    `add` or `a`: Display the inconvenience time of the user and let the user choose the inconvenience time.
    `remove` or `r`: Display the inconvenience time of the user and let the user remove the inconvenience time.

If no argument is given, then it will behave as passing argument `add`.
When admin use `in+`, he can adjust the time schedule of all members by appending the name of the user at the end of the instruction.
"""
    @commands.command(brief="Check or choose the inconvenience time of the user.", aliases=["in", "incon", "inconvenience", "in+"], help=inconvHelp)
    async def inconv(self, ctx: commands.Context):
        # When admin use `in+`, to regard it as a superior command
        if ctx.message.content.split(" ")[0] == "$in+":
            if id2Name.get(ctx.author.id) not in admin:
                await ctx.send("あなたは管理者ではないので、この機能が使えません。")
                return
            if len(ctx.message.content.split(" ")) == 2:
                arg = ctx.message.content.split(" ")[1]
                if arg in name2Id.keys():
                    mode = "view+"
                    name = arg
                else:
                    await ctx.send("その名前は日本語練習のメンバーではありません。")
                    return
            elif len(ctx.message.content.split(" ")) == 3:
                arg1, arg2 = ctx.message.content.split(" ")[1], ctx.message.content.split(" ")[2]
                if arg2 not in name2Id.keys():
                    await ctx.send("その名前は日本語練習のメンバーではありません。")
                    return
                name = arg2
                if arg1 in ["check", "c"]:
                    mode = "view+"
                elif arg1 in ["add", "a"]:
                    mode = "add+"
                elif arg1 in ["remove", "r"]:
                    mode = "remove+"
                else:
                    await ctx.send("引数が間違っています。以下の引数が使えます：\n`check` or `c`：不都合時間を表示\n`add` or `a`：不都合時間を選ぶ\n`remove` or `r`：不都合時間を削除")
                    return
        else:
            mode = "add"
            if len(ctx.message.content.split(" ")) == 2:
                arg = ctx.message.content.split(" ")[1]
                if arg in ["check", "c"]:
                    mode = "view"
                elif arg in ["add", "a"]:
                    mode = "add"
                elif arg in ["remove", "r"]:
                    mode = "remove"
                else:
                    await ctx.send("引数が間違っています。以下の引数が使えます：\n`check` or `c`：不都合時間を表示\n`add` or `a`：不都合時間を選ぶ\n`remove` or `r`：不都合時間を削除")
                    return

            # First print the inconvenience time of the query user
            name = id2Name.get(ctx.author.id)
            if name == None:
                await ctx.send("あなたは日本語練習のメンバーではないので、この機能が使えません。")
                return
            
        futsugouDates = ''
        futsugou = {}
        with open('./data/futsugou.txt') as f:
            temp = f.readlines()
            for t in temp:
                d = t[:-1].split(' ') if t[-1] == "\n" else t.split(' ')
                inputdate = datetime.strptime(f'2024/{d[0]}', "%Y/%m/%d").date()
                if inputdate >= datetime.now().date():
                    if (name in d[1:]):
                        futsugouDates += f'{d[0]} '
                    futsugou.update({d[0]: d[1:]})

        embed = discord.Embed(
            title=f"{name}さんの不都合時間は：",
            description=futsugouDates,
            color=discord.Color.blue()
        )
        # Send inconvenience message
        inconvenience = await ctx.send(embed=embed)
        
        if mode in ["view", "view+"]:
            return

        # Then print the questionnaire
        thisweek = date2week(datetime.today().month, datetime.today().day)
        result, _ = scheduler(thisweek + 3)

        if mode in ["add", "add+"]:
            text = "新たな不都合時間を選んでください："
        else:
            text = "削除したい不都合時間を選んでください："

        embed = discord.Embed(
            title=text,
            color=discord.Color.blue()
        )
        Icon = ['1️⃣','2️⃣','3️⃣','4️⃣','5️⃣','6️⃣','7️⃣','8️⃣','9️⃣','🔟', '🆗']
        
        cnt = 0
        dates = []
        futsugouDates = futsugouDates.strip().split(' ') if futsugouDates else []
        if mode in ["remove", "remove+"]:
            for d in futsugouDates:
                inputdate = datetime.strptime(f'2024/{d}', "%Y/%m/%d").date()
                if inputdate < datetime.now().date(): continue
                embed.add_field(name=f'{Icon[cnt]} {d}', value='')
                dates.append(d)
                cnt += 1
                if cnt >= 10: break
        else:
            for data in result:
                if cnt >= 10: break
                _dates = [data[0], data[2], data[4]]

                for d in _dates:
                    inputdate = datetime.strptime(f'2024/{d}', "%Y/%m/%d").date()
                    if inputdate < datetime.now().date(): continue
                    if d not in futsugouDates:
                        embed.add_field(name=f'{Icon[cnt]} {d}', value='')
                        dates.append(d)
                        cnt += 1
                        if cnt >= 10: break

        embed.add_field(name=f'{Icon[10]} 完成', value='')

        if cnt == 0:
            if mode in ["add", "add+"]:
                await ctx.send("もう選びすぎました。今週から 4 週間内の時間しか選べません。")
            else:
                await ctx.send("もう不都合な時間がありません。")
            return

        message = await ctx.send(embed=embed)

        # Store the question data
        self.question.append([message, name, dates, [0]*10, inconvenience, mode])

        # Add reactions
        for i in range(cnt):
            await message.add_reaction(Icon[i])
        await message.add_reaction(Icon[10])
    
    uploadHelp="""
Upload the data for representation.

Arguments:

    None

If admin use `up+`, he can upload other's data by appending the name of the user at the end of the instruction.
"""
    @commands.command(brief="Upload the data for representation.", aliases=["up", "uploadData", "up+"], help=uploadHelp)
    async def upload(self, ctx: commands.Context):
        if ctx.message.content.split(" ")[0] == "$up+":
            if id2Name.get(ctx.author.id) not in admin:
                await ctx.send("あなたは管理者ではないので、この機能が使えません。")
                return
            if len(ctx.message.content.split(" ")) == 2:
                arg = ctx.message.content.split(" ")[1]
                if arg in name2Id.keys():
                    name = arg
                else:
                    await ctx.send("その名前は日本語練習のメンバーではありません。")
                    return
            else:
                await ctx.send("直したい人の名前を教えてください。")
                return
            self.adminOperate = True
            self.adminTarget = name
        else: 
            name = id2Name.get(ctx.author.id)
            if name == None:
                await ctx.send("あなたは日本語練習のメンバーではないので、この機能が使えません。")
                return
    
        # Calculate the date and section the user should upload
        thisweek = date2week(datetime.today().month, datetime.today().day)
        result, _ = scheduler(thisweek)
        sectionAdate, sectionAmember, sectionBdate, sectionBmember, sectionCdate, sectionCmember = result[-1]
        
        sectionAtime = datetime.strptime(f'2024/{sectionAdate}/23/59', "%Y/%m/%d/%H/%M")
        sectionBtime = datetime.strptime(f'2024/{sectionBdate}/23/59', "%Y/%m/%d/%H/%M")
        sectionCtime = datetime.strptime(f'2024/{sectionCdate}/23/59', "%Y/%m/%d/%H/%M")

        if datetime.now() <= sectionAtime and sectionAmember != "中止" and sectionAmember != "文法" and name in sectionAmember:
            section = "A"
            sectionDate = sectionAdate
        elif datetime.now() <= sectionBtime and sectionBmember != "中止" and sectionBmember != "文法" and name in sectionBmember:
            section = "B"
            sectionDate = sectionBdate
        elif datetime.now() <= sectionCtime and sectionCmember != "中止" and sectionCmember != "文法" and name in sectionCmember:
            section = "C"
            sectionDate = sectionCdate
        else:
            await ctx.send("今週は発表がないので、アップロードする必要がありません。")
            return 
        
        # From `represent_data.txt` to check if the user has uploaded
        uploaded = False
        with open('./data/represent_data.txt', 'r') as f:
            temp = f.readlines()
            for t in temp:
                d = t[:-1].split(' ') if t[-1] == "\n" else t.split(' ')
                if d[0] == name and d[1] == sectionDate:
                    uploaded = True
                    title = d[3]
                    pptLink = d[4]

        # Check if the time is already passed
        if datetime.now() >= datetime.strptime(f'2024/{sectionDate}/22/00', "%Y/%m/%d/%H/%M"):
            # Maybe need to upload the record link, check whether
            if uploaded:
                if len(ctx.message.content.split(" ")) != 3:
                    await ctx.send("リンクを教えてください。")
                else:
                    link = ctx.message.content.split(" ")[2]
                    self.uploadRecord(ctx, name, link)
            else:
                await ctx.send(f"{name}は今日の発表をすっぽかした。故に録画をアプロードしなくてもいいです。")


        self.uploadSession[name] = 1 # Enter the upload session
        
        # First store the date and section
        self.uploadData[name].append(sectionDate)
        self.uploadData[name].append(section)

        if uploaded:
            self.uploadSession[name] = -1 # Enter the reupload check session
            text = "すでにアップロードしました。以下は元のデータですが、内容を更新したいですか？(y/n)（このメッセージをリプライしてください）"
            embed = discord.Embed(
                title="発表のデータ：",
                color=discord.Color.orange()
            )
            embed.add_field(name="日にち：", value=sectionDate)
            embed.add_field(name="セクション：", value=section)
            embed.add_field(name="テーマ：", value=title)
            embed.add_field(name="pptのリンク：", value=pptLink)
            # Send the message
            message = await ctx.send(text, embed=embed)
            # Store the messageID
            self.replySession[name] = message.id
            self.removeSession[name].append(message.id)
        else:
            message = await ctx.send("まずは発表のテーマを教えてください：（このメッセージをリプライしてください）")
            # Store the messageID
            self.replySession[name] = message.id
            self.removeSession[name].append(message.id)
    
    @commands.command(brief="Upload the link of the representation", aliases=["ur"])
    async def uploadRecord(self, ctx: commands.Context, name: str="", rdate: str="", link: str=""):
        # Check if the name and date are given
        if name == "" or rdate == "":
            await ctx.send("Please enter the name and date.")
            return

        # Check if the link is given
        if link == "":
            await ctx.send("Please enter the link.")
            return

        with open('./data/represent_data.txt', 'r') as f:
            data = f.readlines()
            for i in range(len(data)):
                d = data[i][:-1].split(' ') if data[i][-1] == "\n" else data[i].split(' ')
                if d[0] == name and d[1] == rdate:
                    data[i] = ' '.join(d[:5]) + f' {link}\n'
                    
        with open('./data/represent_data.txt', 'w') as f:
            f.writelines(data)

    # Events
        
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if id2Name.get(message.author.id) in admin and self.adminOperate:
            thisUserName = self.adminTarget
        else:
            thisUserName = id2Name.get(message.author.id)
        if thisUserName == None:
            return
        # The message must reply to the correct message
        if message.reference == None or message.reference.message_id != self.replySession[thisUserName]:
            return
        # Store this messageID
        self.removeSession[thisUserName].append(message.id)

        # Only use data to the first '/n' to prevent the user from sending too much data
        message.content = message.content.split('\n')[0]

        if self.uploadSession[thisUserName] == 1:
            # Store the theme
            self.uploadData[thisUserName].append(message.content)
            # Ask for the link to the ppt
            self.uploadSession[thisUserName] = 2
            message = await message.channel.send("次に、pptのリンクを教えてください：（このメッセージをリプライしてください）")
            # Store the messageID
            self.replySession[thisUserName] = message.id
            self.removeSession[thisUserName].append(message.id)

        elif self.uploadSession[thisUserName] == 2:
            # Store the ppt link
            self.uploadData[thisUserName].append(message.content)
            # Append the data to the file
            with open('./data/represent_data.txt', 'a') as f:
                # Then write the data of this user
                f.write(f'{thisUserName} {self.uploadData[thisUserName][0]} {self.uploadData[thisUserName][1]} {self.uploadData[thisUserName][2]} {self.uploadData[thisUserName][3]}\n')

            text = "了解しました。以下はアップロードしたデータです："
            # Send the data back
            embed = discord.Embed(
                title="発表のデータ：",
                color=discord.Color.orange()
            )
            embed.add_field(name="日にち：", value=self.uploadData[thisUserName][0])
            embed.add_field(name="セクション：", value=self.uploadData[thisUserName][1])
            embed.add_field(name="テーマ：", value=self.uploadData[thisUserName][2])
            embed.add_field(name="pptのリンク：", value=self.uploadData[thisUserName][3])
            await message.channel.send(text, embed=embed)
            # Remove the message of the question
            for m in self.removeSession[thisUserName]:
                msg = await message.channel.fetch_message(m)
                await msg.delete()
            # If the session is activated by admin
            if self.adminOperate:
                self.adminOperate = False
                self.adminTarget = ""
            # Reset the session
            self.uploadSession[thisUserName] = 0
            self.uploadData[thisUserName] = []
            self.replySession[thisUserName] = 0
            self.removeSession[thisUserName] = []

        elif self.uploadSession[thisUserName] == -1:
            # Check if the user want to reupload
            if message.content == 'y':
                self.uploadSession[thisUserName] = 1
                message = await message.channel.send("まずは発表のテーマを教えてください：（このメッセージをリプライしてください）")
                # Store the messageID
                self.replySession[thisUserName] = message.id
                self.removeSession[thisUserName].append(message.id)
            else:
                self.uploadSession[thisUserName] = 0
                self.replySession[thisUserName] = 0
                self.removeSession[thisUserName] = []
                self.uploadData[thisUserName] = []
                # If the session is activated by admin
                if self.adminOperate:
                    self.adminOperate = False
                    self.adminTarget = ""
                await message.channel.send("了解しました。変更はしません。")
        
    def processInconv(self, i):
        name = self.question[i][1]
        mode = self.question[i][-1]
        userAnswerDates = []
        userInconvDates = []
        for j in range(10):
            if self.question[i][3][j]:
                userAnswerDates.append(self.question[i][2][j])

        futsugou = []
        existsDates = []
        with open('./data/futsugou.txt', 'r') as f:
            temp = f.readlines()
            for t in temp:
                d = t[:-1].split(' ') if t[-1] == "\n" else t.split(' ')
                mem = d[1:]
                if (name in mem) and (d[0] in userAnswerDates) and mode in ["remove", "remove+"]:
                    mem.remove(name)
                elif (name not in mem) and (d[0] in userAnswerDates) and mode in ["add", "add+"]:
                    mem.append(name)    
                
                if mem:     
                    mem = ' '.join(mem)
                    futsugou.append(f'{d[0]} {mem}\n')
                    existsDates.append(d[0])

                if name in mem and datetime.strptime(f'2024/{d[0]}', "%Y/%m/%d").date() >= datetime.now().date():
                    userInconvDates.append(d[0])

        # Process the query that specified by `special_process_delta`
        special_process_delta = 2 # Today and tomorrow
        special_dates = [datetime.today().date() + timedelta(days=i) for i in range(special_process_delta)]
        print(special_dates)
        print(userAnswerDates)

        for date in special_dates:
            if date.strftime("%m/%d") not in userAnswerDates:
                continue

            if mode in ["add", "add+"]:
                # If found in init, add -
                found = False
                with open('./data/init.txt', 'r') as f:
                    temp = f.readlines()
                    for i, t in enumerate(temp):
                        d = t[:-1].split(' ') if t[-1] == "\n" else t.split(' ')
                        if d[0] == date.strftime("%m/%d") and d[1] != "中止":
                            if d[1] == name:
                                d[1], d[2] = d[2], f'-{name}'
                            elif d[2] == name:
                                d[2] = f'-{name}'

                            if d[1][0] == '-' and d[2][0] == '-':
                                temp[i] = ' '.join([d[0], "中止"]) + '\n' if t[-1] == "\n" else ' '.join([d[0], "中止"])
                            else:
                                temp[i] = ' '.join(d) + '\n' if t[-1] == "\n" else ' '.join(d)
                            found = True
                            break

                print(f"Find done, result = {found}")
                # If not found, add the date to the init        
                if not found:
                    thisweek = date2week(datetime.today().month, datetime.today().day)
                    result, _ = scheduler(thisweek)
                    _, _, sectionBdate, sectionBmember, sectionCdate, sectionCmember = result[-1]
                    member = sectionBmember if date == datetime.strptime(f'2024/{sectionBdate}', "%Y/%m/%d").date() else sectionCmember
                    
                    if member != "中止": 
                        another_mem = member[0] if member[0] != name else member[1]
                        temp.append(f'\n{date.strftime("%m/%d")} {another_mem} -{name}')
                
            elif mode in ["remove", "remove+"]:
                # Fetch the line and remove the dash
                with open('./data/init.txt', 'r') as f:
                    temp = f.readlines()
                    for i, t in enumerate(temp):
                        d = t[:-1].split(' ') if t[-1] == "\n" else t.split(' ')
                        if d[0] == date.strftime("%m/%d") and d[1] != "中止":
                            if d[1] == f'-{name}':
                                d[1] = name
                            elif d[2] == f'-{name}':
                                d[2] = name
                            temp[i] = ' '.join(d) + '\n' if t[-1] == "\n" else ' '.join(d)
                            break

            print("===============================================")
            print(temp)
            print("===============================================")

            # Write back to the file
            with open('./data/init.txt', 'w') as f:
                f.writelines(temp)

        if mode in ["add", "add+"]: # Add those dates that are not in the file
            for d in userAnswerDates:
                if d not in existsDates:
                    futsugou.append(f'{d} {name}\n')
                    userInconvDates.append(d)

        futsugou.sort()
        userInconvDates.sort()

        with open('./data/futsugou.txt', 'w') as f:
            f.writelines(futsugou)

        return discord.Embed(
            title="あなたの不都合時間は：",
            description=' '.join(userInconvDates),
            color=discord.Color.blue()
        )
        
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        icon2idx = {'1️⃣': 0,'2️⃣': 1,'3️⃣': 2,'4️⃣': 3,'5️⃣': 4,'6️⃣': 5,'7️⃣': 6,'8️⃣': 7,'9️⃣': 8,'🔟': 9, '🆗': 10}
        if payload.user_id != botId:
            global noReminderToday
            if (payload.emoji.name == "wakattatteba") and (not noReminderToday) and (payload.message_id in todayReminderIDs):
                noReminderToday = True
                channel = self.bot.get_channel(practiceRoomChannel)          
                await channel.send("わかった。今日のリマインダーはオフになります。")
                
            idx = -1
            for i in range(len(self.question)): 
                if self.question[i][0].id == payload.message_id: 
                    idx = i
            if idx != -1 and (id2Name.get(payload.user_id) == self.question[idx][1] or id2Name.get(payload.user_id) in admin):
                iconIdx = icon2idx[payload.emoji.name]
                # If Ok is pressed, list and delete the message and remove messageID and update to hackmd
                if iconIdx == 10:
                    # Process the query
                    embed = self.processInconv(idx)
                    # Update the inconvenience data
                    await self.question[idx][4].edit(embed=embed)
                    # Remove the questionnaire
                    await self.question[idx][0].delete()
                    # Remove from question list
                    self.question.pop(idx)
                    # Remind everyone
                    await reminder3(self.bot, False)
                else:
                    print(f'Icon {iconIdx + 1} is pressed by {self.question[idx][1]}')
                    self.question[idx][3][iconIdx] = 1

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        icon2idx = {'1️⃣': 0,'2️⃣': 1,'3️⃣': 2,'4️⃣': 3,'5️⃣': 4,'6️⃣': 5,'7️⃣': 6,'8️⃣': 7,'9️⃣': 8,'🔟': 9, '🆗': 10}
        if payload.user_id != botId:
            idx = -1
            for i in range(len(self.question)): 
                if self.question[i][0].id == payload.message_id: 
                    idx = i
            if idx != -1 and (id2Name.get(payload.user_id) == self.question[idx][1] or id2Name.get(payload.user_id) in admin):
                iconIdx = icon2idx[payload.emoji.name]
                if iconIdx == 10:
                    # Don't do anything, this won't happen.
                    pass
                else:
                    print(f'Icon {iconIdx + 1} is unpressed by {self.question[idx][1]}')
                    self.question[idx][3][iconIdx] = 0

async def reminder1(bot, test: bool=False):
    """
    Remind the people who will represent in today. And call everyone to the voice channel.
    """
    if test:
        channel = bot.get_channel(testChannel)          
    else:
        channel = bot.get_channel(practiceRoomChannel)
    thisweek = date2week(datetime.today().month, datetime.today().day)
    result, _ = scheduler(thisweek)
    sectionAdate, sectionAmember, sectionBdate, sectionBmember, sectionCdate, sectionCmember = result[-1]
    
    sectionAdate = datetime.strptime(f'2024/{sectionAdate}', "%Y/%m/%d").date()
    sectionBdate = datetime.strptime(f'2024/{sectionBdate}', "%Y/%m/%d").date()
    sectionCdate = datetime.strptime(f'2024/{sectionCdate}', "%Y/%m/%d").date()
    today = datetime.today().date()
    if sectionAdate == today:
        section = "A"
        date = sectionAdate
        member = sectionAmember
    elif sectionBdate == today:
        section = "B"
        date = sectionBdate
        member = sectionBmember
    elif sectionCdate == today:
        section = "C"
        date = sectionCdate
        member = sectionCmember
    else:
        await channel.send("今日は発表の日ではありません。")
        return
    
    # Send message to channel
    if member == "中止":
        embed = discord.Embed(
            title=f"{date} Section {section}",
            description=f'今天練習暫停一次！大家辛苦了！',
            color=discord.Color.red()
        )
        await channel.send(embed=embed)
    elif member == "文法":
        embed = discord.Embed(
            title=f"{date} Section {section}",
            description=f'今天是文法練習！大家記得上線！',
            color=discord.Color.red()
        )
        await channel.send(embed=embed)
    else:
        embed = discord.Embed(
            title=f"{date} Section {section}",
            description=f'今天発表する人は：<@{name2Id[member[0]]}> と <@{name2Id[member[1]]}>',
            color=discord.Color.red()
        )
        # Fetch represent data
        with open('./data/represent_data.txt', 'r') as f:
            temp = f.readlines()
            for t in temp:
                d = t[:-1].split(' ') if t[-1] == "\n" else t.split(' ')
                if d[0] == member[0] and d[1] == date.strftime("%m/%d"):
                    embed.add_field(name=f"{member[0]}", value=f"テーマ：{d[3]}\nppt：[リンク]({d[4]})", inline=False)
                elif d[0] == member[1] and d[1] == date.strftime("%m/%d"):
                    embed.add_field(name=f"{member[1]}", value=f"テーマ：{d[3]}\nppt：[リンク]({d[4]})", inline=False)
        # Send to chat room
        await channel.send(embed=embed)

async def reminder2(bot, test: bool=False):
    if noReminderToday:
        return

    if test:
        channel = bot.get_channel(testChannel)          
    else:
        channel = bot.get_channel(practiceRoomChannel)
    # Notice those who will represent today but haven't upload the data
    thisweek = date2week(datetime.today().month, datetime.today().day)
    result, _ = scheduler(thisweek)
    sectionAdate, sectionAmember, sectionBdate, sectionBmember, sectionCdate, sectionCmember = result[-1]
    today = datetime.today().date()
    if datetime.strptime(f'2024/{sectionAdate}', "%Y/%m/%d").date() == today:
        member = sectionAmember
    elif datetime.strptime(f'2024/{sectionBdate}', "%Y/%m/%d").date() == today:
        member = sectionBmember
    elif datetime.strptime(f'2024/{sectionCdate}', "%Y/%m/%d").date() == today:
        member = sectionCmember
    else:
        await channel.send("今日は発表の日ではありません。")
        return
    
    if member in ["中止", "文法"]:
        return
    
    # Fetch represent data
    Uploaded = []
    with open('./data/represent_data.txt', 'r') as f:
        temp = f.readlines()
        for t in temp:
            d = t[:-1].split(' ') if t[-1] == "\n" else t.split(' ')
            if d[0] == member[0] and d[1] == today.strftime("%m/%d"):
                Uploaded.append(member[0])
            elif d[0] == member[1] and d[1] == today.strftime("%m/%d"):
                Uploaded.append(member[1])
    
    global todayReminderIDs
    # Tag those who haven't upload to remind them
    if member[0] not in Uploaded:
        message = await channel.send(f"<@{name2Id[member[0]]}> さん、まだ発表のデータをアップロードしていません。`$upload`を使って、アップロードしてください。")
        todayReminderIDs.append(message.id)
    if member[1] not in Uploaded:
        message = await channel.send(f"<@{name2Id[member[1]]}> さん、まだ発表のデータをアップロードしていません。`$upload`を使って、アップロードしてください。")
        todayReminderIDs.append(message.id)

async def reminder3(bot, regular: bool=True, test: bool=False):
    """
    Remind everyone that the schedule is updated.
    If regular is `True`, then it will send the message since the scheduler calls it.
    If regular is `False`, then it will send the message since someone fill the questionnarie.
    """
    thisweek = date2week(datetime.today().month, datetime.today().day)
    table = generateTableSchedule(scheduler(thisweek + 3)[0], old=False)
    embed = discord.Embed(
        title="今週から 4 週間内のスゲジュウル：",
        description=table,
        color=discord.Color.green()
    )

    # Send to chat room
    if test:
        channel = bot.get_channel(testChannel)          
    else:
        channel = bot.get_channel(practiceRoomChannel)
    if regular:
        content = "**[注意]**：スゲジュウルを注意してください。"  
    else:
        content = "**[注意]**：スゲジュウルが更新されました。"

    await channel.send(content=content, embed=embed)

async def reminder4(bot, test: bool=False):
    
    if test:
        channel = bot.get_channel(testChannel)
    else:
        channel = bot.get_channel(practiceRoomChannel)
    # Reset noRemindToday
    global noReminderToday
    global todayReminderIDs
    noReminderToday = False
    todayReminderIDs = []

    # Remind the admin to upload record
    thisweek = date2week(datetime.today().month, datetime.today().day)
    result, _ = scheduler(thisweek)
    sectionAdate, sectionAmember, sectionBdate, sectionBmember, sectionCdate, sectionCmember = result[-1]
    today = datetime.today().date()
    if datetime.strptime(f'2024/{sectionAdate}', "%Y/%m/%d").date() == today:
        member = sectionAmember
    elif datetime.strptime(f'2024/{sectionBdate}', "%Y/%m/%d").date() == today:
        member = sectionBmember
    elif datetime.strptime(f'2024/{sectionCdate}', "%Y/%m/%d").date() == today:
        member = sectionCmember
    else:
        await channel.send("今日は発表の日ではありません。")
        return
    
    if member in ["中止", "文法"]:
        return
    
    # Fetch represent data
    notUploaded = []
    with open('./data/represent_data.txt', 'r') as f:
        temp = f.readlines()
        for t in temp:
            d = t[:-1].split(' ') if t[-1] == "\n" else t.split(' ')
            if d[1] == today.strftime("%m/%d") and len(d) == 5:
                notUploaded.append(d[0])
    
    # Remind the admin
    if len(notUploaded) > 0:
        await channel.send(f"<@701401037621166169>今日の発表録画がアップロードされていない人は：{', '.join(notUploaded)}")
    else:
        return

def add_scheduler(bot):
    """
    Add three jobs to the scheduler.
    (Currently only two of them are added.)
    """
    # Remind at the beggining of the practice (22:00)
    remindScheduler.add_job(func = reminder1, args=[bot], \
        trigger = CronTrigger(day_of_week="tue, fri, sun", hour=22, minute=0, second=0))

    # Remind at the end of the practice (23:30)
    remindScheduler.add_job(func = reminder4, args=[bot], \
        trigger = CronTrigger(day_of_week="tue, fri, sun", hour=23, minute=30, second=0))

    # Remind at days we will practice 17:00 18:00 19:00 20:00 21:00
    remindScheduler.add_job(func = reminder2, args=[bot], \
        trigger = CronTrigger(day_of_week="tue, fri, sun", hour="17-21", minute=0, second=0))
      
    # Remind at monday 00:00
    remindScheduler.add_job(func = reminder3, args=[bot], \
        trigger = CronTrigger(day_of_week="mon", hour=0, minute=0, second=0))

# Take action when load
async def setup(bot: commands.Bot):
    global remindScheduler
    remindScheduler = AsyncIOScheduler()
    add_scheduler(bot)
    remindScheduler.start()
    print("Scheduler created")
    await bot.add_cog(Represent(bot))
    
# Take action when reload
async def teardown(bot: commands.Bot):
    remindScheduler.remove_all_jobs()
    remindScheduler.shutdown()
    print("Scheduler removed")
