import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import sqlite3
import yfinance as yf
from datetime import datetime

# Server setup
load_dotenv()
token = os.getenv("DISCORD_TOKEN")
intents = discord.Intents.all()
intents.members = True
bot = commands.Bot(command_prefix='$', intents=intents)

# On ready
@bot.event
async def on_ready():
    connection = sqlite3.connect('portfolio.db')
    cursor = connection.cursor()
    curr_time = datetime.now()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stats(ID, Date, Cash)
        ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio(ID, Ticker, Unit)
        ''')
    guild = bot.get_guild(1051270024796586088)
    for member in guild.members:
        if not member.bot:
            cursor.execute("SELECT 1 FROM stats WHERE ID=? LIMIT 1", (member.id,))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO stats(ID, Date, Cash) VALUES (?,?,?)", (member.id, curr_time, float(1000000),))
    print("Bot is active!")
    connection.commit()
    connection.close()

# New member joins
@bot.event
async def on_member_join(member):
    connection = sqlite3.connect('portfolio.db')
    cursor = connection.cursor()
    curr_time = datetime.now()
    cursor.execute("INSERT INTO stats(ID, Date, Cash) VALUES (?,?,?)", (member.id, curr_time, float(1000000),))
    await member.send(f"Welcome, {member.name}. You have joined Stock Simulator and have been given USD$ 1,000,000.00 to invest. Have fun!")
    connection.commit()
    connection.close()

# Stock Info
@bot.command()
async def info(ctx, arg):
    stock = yf.Ticker(str(arg))
    await ctx.send("Ticker: " + str(arg)
                 + ". Last Price: "  + str(stock.info.get("regularMarketPrice"))
                 + ". Market Cap: " + str(stock.info.get("marketCap"))
                 + ". PE Ratio: " + str(stock.info.get("trailingPE"))
                 + ". Dividend Yield: " + str(stock.info.get("dividendRate")))

# Buy stock
@bot.command()
async def buy(ctx, arg1, arg2):
    connection = sqlite3.connect('portfolio.db')
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM stats")
    all_users = cursor.fetchall()
    for user in all_users:
        if user[0] == ctx.author.id:
            cash_amount = user[2]
    buying_cost = int(arg2)*price(str(arg1))
    if cash_amount >= buying_cost:
        cursor.execute("SELECT 1 FROM portfolio WHERE Ticker=? AND ID=? LIMIT 1", (arg1,ctx.author.id,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO portfolio(ID, Ticker, Unit) VALUES (?,?,?)", (ctx.author.id, arg1, int(arg2),))
            connection.commit()
            cursor.execute("UPDATE stats SET Cash=? WHERE ID=?", (cash_amount-buying_cost, ctx.author.id,))
            connection.commit()
        else:
            cursor.execute("SELECT Unit FROM portfolio WHERE Ticker=? AND ID=?", (arg1,ctx.author.id,))
            unit = cursor.fetchone()[0]
            cursor.execute("UPDATE portfolio SET Unit=? WHERE Ticker=? AND ID=?", (unit+int(arg2), arg1, ctx.author.id,))
            connection.commit()
            cursor.execute("UPDATE stats SET Cash=? WHERE ID=?", (cash_amount-buying_cost, ctx.author.id,))
            connection.commit()
    else:
        await ctx.send("Cash balance not enough.")

    connection.close()

# Sell stock
@bot.command()
async def sell(ctx, arg1, arg2):
    connection = sqlite3.connect('portfolio.db')
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM stats")
    all_users = cursor.fetchall()
    for user in all_users:
        if user[0] == ctx.author.id:
            cash_amount = user[2]
    cursor.execute("SELECT 1 FROM portfolio WHERE Ticker=? AND ID=? LIMIT 1", (arg1, ctx.author.id, ))
    if cursor.fetchone():
        cursor.execute("SELECT Unit FROM portfolio WHERE Ticker=? AND ID=?", (arg1, ctx.author.id,))
        unit = cursor.fetchone()[0]
        if unit > int(arg2):
            selling_cost = price(str(arg1))*int(arg2)
            cursor.execute("UPDATE portfolio SET Unit=? WHERE Ticker=? AND ID=?", (unit-int(arg2),arg1,ctx.author.id,))
            connection.commit()
            cursor.execute("UPDATE stats SET Cash=? WHERE ID=?", (cash_amount+selling_cost, ctx.author.id,))
            connection.commit()
        elif unit == int(arg2):
            selling_cost = price(str(arg1))*int(arg2)
            cursor.execute("DELETE FROM portfolio WHERE Ticker=? AND ID=?", (arg1, ctx.author.id,))
            connection.commit()
            cursor.execute("UPDATE stats SET Cash=? WHERE ID=?", (cash_amount+selling_cost, ctx.author.id,))
            connection.commit()
        else:
            await ctx.send("Cannot sell more than stock being owned.")
    else:
        await ctx.send("Stock not in portfolio.")

    connection.close()
        
# Helper function - get stock price
def price(ticker):
    stock = yf.Ticker(ticker)
    return float(stock.info.get("regularMarketPrice"))

# Portfolio display
@bot.command()
async def portfolio(ctx):
    connection = sqlite3.connect('portfolio.db')
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM stats")
    all_users = cursor.fetchall()
    for user in all_users:
        if user[0] == ctx.author.id:
            cash_amount = user[2]
    portfolio_value = cash_amount
    for row in cursor.execute("SELECT Ticker, Unit FROM portfolio WHERE ID=?", (ctx.author.id,)):
        stock_value = price(row[0])*row[1]
        portfolio_value += stock_value
        await ctx.send("Ticker: " + row[0] + ". Total Value: $" + str(round(stock_value,2)))
    await ctx.send("Total portfolio value: " + str(portfolio_value))
    connection.commit()
    connection.close()

# Helper function - get user portfolio data
def user_portfolio():
    all_portfolio_data = {}
    connection = sqlite3.connect('portfolio.db')
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM stats")
    all_users = cursor.fetchall()
    for user in all_users:
        user_id = user[0]
        portfolio_value = user[2]
        for row in cursor.execute("SELECT Ticker, Unit FROM portfolio WHERE ID=?", (user_id,)):
            portfolio_value += price(row[0])*row[1]
        all_portfolio_data[user_id] = portfolio_value

    connection.commit()
    connection.close()

    return all_portfolio_data

# Ranking System
@bot.command()
async def ranking(ctx):
    all_user = user_portfolio()
    sorted(all_user.items(), key=lambda x: x[1], reverse=True)
    rank = 1
    for user in all_user.items():
        total_return_percentage = (user[1]-1000000)/1000000*100
        await ctx.send(str(rank) +" - " + str(bot.get_user(user[0])) + ": $" + str(user[1]) + ". Percentage returns: " + str(total_return_percentage) + "%.")

'''
# Compare with major indices
@bot.command()
async def returns(ctx, arg1):
'''

bot.run(token)