import discord
from discord.ext import commands, tasks
from PIL import Image, ImageDraw, ImageFont
import requests

# ===============================
def get_furigana_via_api(sentence: str):
    url = "https://api.mygo.page/api/MarkAccent/"  # 替換成實際 API
    try:
        resp = requests.post(url, json={"text": sentence})
        if resp.status_code == 200:
            data = resp.json()
            if data["status"] == 200 and data["result"]:
                return [(item["surface"], item["furigana"], item["accent"]) for item in data["result"]]
    except Exception as e:
        print("API error:", e)
    return []

# 新增函數：把 API accent 轉成每個假名的 accent type
def convert_accent_per_kana(furigana, word_accent):
    """
    furigana: str, e.g., "てんき"
    word_accent: int, e.g., 1 (-1 = 無accent)
    return: list[int], 每個假名的 accent type
    """
    result = []
    for i, _ in enumerate(furigana):
        if word_accent == -1:
            result.append(0)
        elif word_accent == 0:
            # 0號音，第一音節低，其餘高
            result.append(0 if i == 0 else 1)
        else:
            # word_accent > 0
            if i + 1 == word_accent:
                result.append(2)  # 高音下降
            else:
                result.append(0)  # 其他低音
    return result

def is_kanji(char):
    return '\u4e00' <= char <= '\u9fff'

def calc_accent(word_index, char_index, word_surface, word_accent, new_words):
    monosyllabic = len(word_surface) == 1
    prev_accent = new_words[word_index - 1]["accent"] if word_index > 0 else -1
    case_particles = ['は', 'が', 'を', 'に', 'で', 'と', 'へ', 'から', 'まで', 'より']
    after_particle = word_index > 0 and new_words[word_index-1]["surface"] in case_particles

    is_drop = (char_index + 1 == word_accent)
    if word_accent == -1:
        return 0
    if word_accent == 0:
        if char_index > 0:
            return 1
        if monosyllabic:
            return 1
        if prev_accent == 0:
            return 0 if after_particle else 1
        return 0
    return 2 if is_drop else 0
    
# accent rendering
def draw_accent(d, x, y, width, furiHeight, accentType):
    """
    d: ImageDraw
    x, y: 左上角位置
    width: 該文字區域寬度
    furiHeight: 振假名高度 (用來估算線的垂直位置)
    accentType: 0,1,2
    """
    lineY = y - 45  # 線畫在文字上方一點點
    if accentType == 1:
        # 高音，畫一條橫線
        d.line((x, lineY, x + width, lineY), fill=(255, 0, 0), width=2)
    elif accentType == 2:
        # 高音下降，畫橫線 + 向下折線
        d.line((x, lineY, x + width, lineY), fill=(255, 0, 0), width=2)
        d.line((x + width, lineY, x + width, lineY + furiHeight), fill=(255, 0, 0), width=2)

# ===============================

def text2png(query, drawBox=False):
    # Hyper parameters
    basefontSize = 40
    furifontSize = 20
    maxWordPerLine = 40
    spacing = 40
    boarderSize = 20
    furiRatio = 0.5
    font = ImageFont.truetype("./font/NotoSerifJP-Regular.otf", basefontSize)
    furifont = ImageFont.truetype("./font/NotoSerifJP-Regular.otf", furifontSize)
    
    # Initialize the image
    img = Image.new(mode="RGB", size=(100, 100), color=(255, 255, 255))
    draw = ImageDraw.ImageDraw(img)

    ## Change the input to multiple lines (add \n to the string) if needed
    if len(query) > maxWordPerLine:
        query = "\n".join([query[i:min(len(query), i+maxWordPerLine)] for i in range(0, len(query), maxWordPerLine)])
        linesNum, wordPerLine = len(query.split("\n")), maxWordPerLine
    else:
        linesNum, wordPerLine = 1, len(query)
    
    ## Get width and height of the image
    bbox = draw.multiline_textbbox((0, 0), query, font=font, spacing=spacing, align="left")
    furiHeight = int(spacing * furiRatio)
    emptySpace = spacing - furiHeight
    width = bbox[2] - bbox[0] + 2 * boarderSize
    height = bbox[3] - bbox[1] + spacing + 2 * boarderSize - emptySpace # Need to add one spacing for the first line
    furiWidth = (width - 2 * boarderSize) / wordPerLine # Should be rounded
    paddingHeight = (height - 2 * boarderSize + emptySpace) / linesNum
    kanjiHeight = paddingHeight - emptySpace
    
    ## Resize the background
    img = Image.new(mode="RGB", size=(width, height), color=(255, 255, 255))
    d = ImageDraw.Draw(img)

    # Remove "\n" from the query
    singleLineQuery = query.replace("\n", "")
    # Get the furigana
    result = get_furigana_via_api(singleLineQuery)

    # Draw the bounding box for each character where its furigana will be
    charCnt = 0
    current_line = 0
    for data in result:
        surface, furigana, accent = data
        # If an crossline pharase is detected, stop the process
        if charCnt + len(surface) > maxWordPerLine:
            charCnt = 0
            current_line += 1
        x = charCnt * furiWidth + boarderSize
        y = current_line * paddingHeight + boarderSize + emptySpace
        
        # Draw the bounding box for furi in red and kanji in blue
        if drawBox:
            # Draw the bounding box for furi in red
            d.rectangle((x, y, x+furiWidth*len(surface), y+furiHeight), outline=(255,0,0))            # Draw the bounding box for kanji in blue
            d.rectangle((x, y+furiHeight, x+furiWidth*len(surface), y+kanjiHeight), outline=(0,0,255))  # 漢字框
        
        # Draw the furigana aligned at the center
        if furigana and furigana != surface and any(is_kanji(c) for c in surface):
            centerX = int(x + furiWidth*len(surface)/2)
            d.text((centerX, y-20), furigana, fill=(0,0,0), font=furifont, anchor="mt")


        #Draw accent
# Convert word accent into per-kana accent
        accent_list = convert_accent_per_kana(furigana, accent)
        for idx, a in enumerate(accent_list):
            draw_accent(d, x + furiWidth*idx, y + furiHeight, furiWidth, furiHeight, a)

        # Update the character count
        charCnt += len(surface)

    ## Draw the text
    d.text((boarderSize, boarderSize+spacing-bbox[1] - emptySpace), query, fill=(0, 0, 0), spacing=spacing, font=font)
            
    # Save the image and send
    img.save("./images/furigana.png")
    return True

class Vocabulary(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    #文字
    @commands.command(brief="Append furigana to kanji", aliases=["f"])
    async def furigana(self, ctx: commands.Context):

        content = ctx.message.content.split(" ", 1)
        if len(content) < 2:
            await ctx.send("請輸入要加振假名的文字。")
            return
        query = content[1]

        result = get_furigana_via_api(query)
        hackmd_text = ""
        for surface, furigana, accent in result:
            if furigana and furigana != surface:
                hackmd_text += f"{surface}({furigana})"
            else:
                hackmd_text += surface
        await ctx.send(f"```\n{hackmd_text}\n```")

    #圖片
    @commands.command(brief="Generate furigana image", aliases=["p"])
    async def picture(self, ctx: commands.Context):
        content = ctx.message.content.split(" ", 1)
        if len(content) < 2:
            await ctx.send("請輸入要產生圖片的文字。")
            return
        query = content[1]

        success = text2png(query, drawBox=False)
        if success:
            await ctx.send(file=discord.File("./images/furigana.png"))
        else:
            await ctx.send("圖片生成失敗")
        

        
# Take action when load
async def setup(bot: commands.Bot):
    print("Vocabulary setup...")
    await bot.add_cog(Vocabulary(bot))
    
# Take action when reload
async def teardown(bot: commands.Bot):
    print("Vocabulary teardown...")


"""
TODO:
01. 對於全型還有半型混雜的情況，需要進行處理。可能一開始就要先算好全型還有半型的型狀，再去切bbox。 => 每次開始畫字的時候都要先計算一次?
02. 對於較長的輸入，可以考慮每行都重設一個定位點。 
03. 對フリガナ會重疊的問題進行處理。
04. 在畫字的時候，要考慮到如果一個詞被切到，需要提前進行換行。
05. 對於使用者修正原本的訊息可以進行rerender。
06. 對預先定好的字讀音可以複寫。
07. 加入音調功能。
08. 輸出成hackmd可以使用的格式。
09. 輸出成html檔。
10. 使用html2pdf的一些converter，可以得到匯出成pdf的功能。
"""