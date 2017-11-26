# -*- coding: utf-8 -*-
"""
Created on Wed Nov 22 11:04:59 2017

@author: Sam Hajnos

https://discordapp.com/api/oauth2/authorize?client_id=383289305101107210&permissions=268757056&redirect_uri=https%3A%2F%2Fgithub.com%2FFonzo18%2FSnowbot&scope=bot
self.command(attrs)(coro)
"""
import discord
from discord.ext import commands
import random
import itertools
import asyncio
from io import StringIO
import json
import argparse
import aiohttp
import configparser
import os

class Snowbot(commands.Bot):
    
    def __init__(self,path=r"C:\Python\snowbot",**options):
        """Populate attrs from config"""
        
        os.chdir(path)
        self.__config = configparser.ConfigParser()
        self.__config.read("config.ini")
        

        
        
        with open('players.json') as json_file:  
            data = json.load(json_file)
        self.__players = data
        
        with open('teams.json') as json_file:  
            data = json.load(json_file)
            for rec in data:
                lead = data[rec]["leader"]
                self.__players[lead]["team"] = rec
        self.__teams = data

        with open('events.json') as json_file:  
            data = json.load(json_file)
        self.__snow_events = data
        
        
        self.__death_color = discord.Color(int(self.__config["game"]["death-color"],16))
        self.__death_color = discord.Color(int(self.__config["game"]["event-color"],16))
        self.__trigger_rate= float(self.__config["game"]["trigger-rate"])
        
        self.__color = discord.Color(int(self.__config["snowbot"]["color"],16))
        self.__gamestatus = self.__config["snowbot"]["gamestatus"]
        self.__reaping_active = False
        pref = self.__config["snowbot"]["prefix"]
        desc = self.__config["snowbot"]["description"]
        
        
        
        
        
        
        super().__init__(command_prefix=pref,description=desc,**options)
        
        
        
    async def on_ready(self):
        self.__main_server = self.get_server(self.__config["servers"]["main"])
        
        self.__mod_console = self.get_channel(self.__config["channels"]["mod-console"])
        self.__public_console = self.get_channel(self.__config["channels"]["public-console"])
        self.__log_channel = self.get_channel(self.__config["channels"]["log"])
        self.__arena_channel = self.get_channel(self.__config["channels"]["arena"])
        
        self.__all_players_role = discord.utils.get(self.__main_server.roles, id=self.__config["roles"]["all-players"])
        self.__alive_players_role = discord.utils.get(self.__main_server.roles, id=self.__config["roles"]["alive-players"])
        
        self.register_snowbot_commands()
        
        if self.__config["snowbot"].getboolean("notify-startup"):
            
            embed = discord.Embed(title=self.__config["snowbot"]["restart-text"], colour=self.__color,url="https://discord.gg/5HZE9A4")
            
            embed.set_footer(text="Snowbot version " + self.__config["snowbot"]["version"])
        
            embed.add_field(name="Snowbot discord", value="http://discord.gg/5HZE9A4")
    
            await self.send_message(self.__public_console,embed=embed)
        await self.change_presence(game=discord.Game(name=self.__gamestatus,type=0))
    
    
    async def on_message(self,message):
       if message.channel.id in self.__watched_channels and not self.__reaping_active:
           i = random.random()*100
           if(i<self.__trigger_rate):
               await self.__trig()
       try:
           await self.process_commands(message)
       except (InvalidArgument, CommandInvokeError):
           pass
        
    
    
    
    
    def register_snowbot_commands(self):
        self.command(name="remaining_tributes",checks=[self.public_command],pass_context=True,aliases=['list','alive','tributes','survs','survivors'])(self.remaining_tributes)    
        self.command(name="team",checks=[self.public_command],pass_context=True,aliases=['district','dist'])(self.team)
        self.command(name="list_teams",checks=[self.public_command],pass_context=True,aliases=['teams','districts'])(self.list_teams)
        self.command(name="is_alive",checks=[self.public_command],pass_context=True,aliases=["status","dead"])(self.is_alive)
        self.command(name="join_team",checks=[self.public_command],pass_context=True,aliases=['join','enlist','set_team'])(self.join_team)
        
        self.command(name="reload",checks=[self.mod_command],pass_context=True,aliases=['refresh','update'])(self.reload)
        #self.command(name="fix_leaders",checks=[self.mod_command],pass_context=True)
        
        self.command(name="reap",checks=[self.mod_command],pass_context=True,aliases=['start','begin','reaping'])(self.reap)
        self.command(name="cull",checks=[self.mod_command],pass_context=True,aliases=['end','reset','cancel','finish'])(self.cull)
        self.command(name="trig",checks=[self.mod_command],pass_context=True,aliases=['trigger','event','go','trig'])
        self.command(name="list_events",checks=[self.mod_command],pass_context=True,aliases=['events'])
        #self.command(name="set_trigger_rate",checks=[self.mod_command],pass_context=False,aliases=['feminism','rate'])(self.set_trigger_rate)
        
    def run(self):
        snowkey = self.__config["discordapp"]["token"]        
        super().run(snowkey)
        
    def random_event(self,n=1):
        return random.sample(list(filter(lambda x: self.__snow_events[x]["actors"] <= n and self.__snow_events[x]["actors"] > 0, self.__snow_events)),1)[0]
    
    async def execute_event(self,event_name : str):
        e = self.__snow_events[event_name]
        actors = await self.randusers(e["actors"])
        names = self.actors_str(actors) 
        msg = e["text"].format(*names)
        img = e["img_url"]
        pingstr = " ".join([a.mention for a in actors])
        evm = discord.Embed(title="Event Log",description=msg, colour=self.__event_color)
        if(img != None):
            evm.set_thumbnail(url=img)
        await self.send_message(destination=self.__arena_channel,embed=evm,content=pingstr)
        for i in e["dies"]:
            who = actors[i]
            self.add_death(who)
            await self.remove_roles(who,self.__alive_players_role)
            pillc = self.__death_color
            em = discord.Embed(title="A tribute has died.",description="Team " + self.district(who), colour=pillc)
            em.set_author(name=who.display_name, icon_url=who.avatar_url)
            ft = "Remaining tributes: " + str(self.user_cnt())
            em.set_footer(text=ft)
            #await bot.send_message(destination=arenac,content=who.mention)
            await self.send_message(destination=self.__arena_channel,embed=em)
            
        #print("\n")
        for k in e["kills"]:
            killer = actors[int(k)]
            for v in e["kills"][k]:
                self.__add_kill(who)
                victim = actors[v]
                if(victim != killer):
                    await self.send_message(destination=self.__log_channel,content= killer.display_name + " just killed " + victim.display_name + ".")
                    
        self.__save_files()     
    
    
    
    
    
    
        
        
    
    def mod_command(self):
        def predicate(ctx):
            return ctx.message.channel.id == self.__config["channels"]["mod-console"]
        return commands.check(predicate)
    
    def public_command(self):
        def predicate(ctx):
            return ctx.message.channel.id in set([self.__config["channels"]["mod-console"],self.__config["channels"]["public-console"]])
        return commands.check(predicate)
    
    
    
    
    
    
    
    
    
    async def trig(self):
        if(not self.__reaping_active):
            n = self.user_cnt()
            if(n>1):
                e = self.random_event(n)
                await self.execute_event(e)
                #event_list = all_events()    
                #valid_events = list(itertools.chain.from_iterable(event_list[:n]))
                #await random.choice(valid_events)()
            if(n==1):
                victor = list(filter(lambda u: self.__alive_players_role in u.roles, self.__main_server.members))[0]
                self.add_win(victor)
                await self.announce_victor(victor)
                msg = victor.display_name + " has won. They now have " + str(self.__get_wins(victor))
                await self.send_message(destination=self.__arena_channel,content=msg)
    
            
    async def announce_victor(self,victor : discord.Member):
        arenac = self.__arena_channel
        pillc = self.teamcolor(victor)
        tribute_role = self.__alive_players_role
        
        em = discord.Embed(title="Only one tribute remains", colour=pillc)
        em.set_author(name=victor.display_name, icon_url=victor.avatar_url)
        em.set_thumbnail(url=victor.avatar_url)
        ft = "Congratulations " + self.district(victor)
        em.set_footer(text=ft)
    
        await self.remove_roles(victor,tribute_role)
        await self.send_message(destination=arenac,embed=em)
    
            




        
    def district(self,who : discord.User):
        tid = self.__snow_players[who.id]["team"]
        if not tid in self.__teams:
            self.__give_team(who)    
        return self.__teams[tid]["name"]
    
    def teamcolor(self,who : discord.User):
        tid = self.__snow_players[who.id]["team"]
        if not tid in self.__teams:
            self.__give_team(who) 
        col = int(self.__teams[tid]["color"],16)
        return discord.Color(col)
    
    def teampic(self,who : discord.User):
        tid = self.__snow_players[who.id]["team"]
        if not tid in self.__teams:
            self.__give_team(who) 
        return self.__teams[tid]["image"]
    
    def tagline(self,who : discord.User):
        tid = self.__snow_players[who.id]["team"]
        if not tid in self.__teams:
            self.__give_team(who) 
        return self.__teams[tid]["description"]
    
    async def randusers(self,n=1):
        tribute_role = self.__alive_players_role
        alive_users = list(filter(lambda u: tribute_role in u.roles, self.__main_server.members))
        return random.sample(alive_users,n)
    
    def user_cnt(self):
        tribute_role = self.__alive_players_role
        return len(list(filter(lambda u: tribute_role in u.roles, self.__main_server.members)))
    
    async def kill(self,who : discord.Member, fire_cannon=True):
        tribute_role = self.__alive_players_role
        deathcol= self.__death_color
        arenac = self.__arena_channel
        await self.remove_roles(who,tribute_role)
        if(fire_cannon):
            pillc = deathcol
            em = discord.Embed(title="A tribute has died.",description="from team " + self.district(who), colour=pillc)
            em.set_author(name=who.display_name, icon_url=who.avatar_url)
            ft = "Remaining tributes: " + str(self.user_cnt())
            em.set_footer(text=ft)
            await self.send_message(destination=arenac,embed=em)

    def namelist(names_in):
        names = names_in
        names[-1] = "and " + names[-1]
        kstr = ", ".join(names)
        return kstr
    
    def actors_str(actors):
        if isinstance(actors, list):        
            return [a.mention for a in actors]
        else:
            return [actors.mention]
        
    async def event_msg(self,msg : str,pin=True,img=None,who2ping=None):
        arenac = self.__arena_channel
        eventcol = self.__event_color
        
        if(who2ping != None):
            if isinstance(who2ping, list):  
                pingstr = " ".join([a.mention for a in who2ping])
            else:
                pingstr = who2ping.mention
        em = discord.Embed(title="Event Log",description=msg, colour=eventcol)
        if(img != None):
            em.set_thumbnail(url=img)
        await self.send_message(destination=arenac,embed=em,content=pingstr)
    
    
    def status(self,who : discord.Member):
        tribute_role = self.__alive_players_role
        volunteer_role = self.__all_players_role
        if(tribute_role in who.roles):
            return "alive"
        elif(volunteer_role in who.roles):
            return "dead"
        else:
            return "missing"
    
    
    def team_embed(self,tid):
        player_info = self.__players
        teams = self.__teams
        main_server = self.__main_server
        
        teammates = list(filter(lambda u: player_info[u]["team"] == tid,player_info))
        tlead = main_server.get_member(teams[tid]["leader"])
        mates = " ".join(["<@!" + a + ">" for a in teammates])
        if len(mates) > 1000:
            mates = "Team too large to list members."
        embed = discord.Embed(title=teams[tid]["name"], colour=discord.Colour(int(teams[tid]["color"],16)), description=teams[tid]["description"])
    
        embed.set_thumbnail(url=teams[tid]["image"])
        embed.set_footer(text=tlead.display_name, icon_url=tlead.avatar_url)
        cnt = len(teammates)
        embed.add_field(name=str(cnt)+ " Members", value=mates)
        return embed
    
    
    
    
    def add_player(self,who : discord.User,status=None,team=None):
        whom = self.__main_server.get_member(who.id)
        if who.id not in self.__players:
            self.__players[who.id] = {"wins":0,"kills":0,"deaths":0}
            
        if "team" not in self.__players[who.id]:
            self.give_team(who)
        if "wins" not in self.__players[who.id]:
            self.__players[who.id]["wins"] = 0
        if "kills" not in self.__players[who.id]:
            self.__players[who.id]["kills"] = 0
        if "deaths" not in self.__players[who.id]:
            self.__players[who.id]["deaths"] = 0
        if "status" not in self.__players[who.id]:
            if status is not None:
                self.__players[who.id]["status"] = status
            elif self.__alive_players_role in whom.roles:
                self.__players[who.id]["status"] = "Alive"
            elif self.__all_players_role in whom.roles:
                self.__players[who.id]["status"] = "Dead"
            else:
                self.__players[who.id]["status"] = "Not a tribute"
        if "games" not in self.__players[who.id]:
            self.__players[who.id]["games"] = 0
            
    def add_win(self,who : discord.User):
        self.add_player(who)
        self.__players[who.id]["wins"] = self.__players[who.id]["wins"] + 1
    
    def add_kill(self,who : discord.User):
        self.add_player(who)
        self.__players[who.id]["kills"] = self.__players[who.id]["kills"] + 1
    
    def add_death(self,who : discord.User):
        self.add_player(who)
        self.__players[who.id]["deaths"] = self.__players[who.id]["deaths"] + 1
    
    def add_game(self,who : discord.User):
        self.add_player(who)
        self.__players[who.id]["games"] = self.__players[who.id]["games"] + 1
    
    def get_wins(self,who : discord.User):
        self.add_player(who)
        return self.__players[who.id]["wins"]
    
    def get_kills(self,who : discord.User):
        self.add_player(who)
        return self.__players[who.id]["kills"]
    
    def get_deaths(self,who : discord.User):
        self.add_player(who)
        return self.__players[who.id]["deaths"]
        
    def set_team(self,who : discord.User, team="0"):
        self.add_player(who)
        if team in self.__teams:
            self.__players[who.id]["team"] = team
        else:
            self.give_team(who)
    
    def give_team(self,who : discord.User):
        self.__players[who.id]["team"] = random.choice(["1","2"])
    #                                                                       
    #                                                                       
    #    _   _   ___    ___   _ __                                          
    #   | | | | / __|  / _ \ | '__|                                         
    #   | |_| | \__ \ |  __/ | |                                            
    #    \__,_| |___/  \___| |_|                                            
    #                                                                       
    #                                                                       
    #                                                               _       
    #                                                              | |      
    #     ___    ___    _ __ ___    _ __ ___     __ _   _ __     __| |  ___ 
    #    / __|  / _ \  | '_ ` _ \  | '_ ` _ \   / _` | | '_ \   / _` | / __|
    #   | (__  | (_) | | | | | | | | | | | | | | (_| | | | | | | (_| | \__ \
    #    \___|  \___/  |_| |_| |_| |_| |_| |_|  \__,_| |_| |_|  \__,_| |___/
    #                                                                       
    #
    
    #@bot.command(pass_context=True,aliases=['list','alive','tributes','survs','survivors'])
    async def remaining_tributes(self,ctx):
        tribute_role = self.__alive_players_role
        current_server = self.__main_server
        
        vols = list(filter(lambda u: tribute_role in u.roles, current_server.members))
        i = 0
        n = self.user_cnt()
        if len(vols) < 10:
            for trib in vols:
                i = i + 1
                pillc = self.teamcolor(trib)
                em = discord.Embed(title="From district " + self.district(trib), colour=pillc)
                em.set_author(name=trib.display_name, icon_url=trib.avatar_url)
                em.set_footer(text=str(i) + " of " + str(n))
                await self.say(embed=em)
        else:
            msg_str = "Living Tributes:"
            for trib in vols:
                i = i + 1
                msg_str = msg_str + "\n**" + trib.display_name + "** in *" + self.district(trib) + "*"
                if i > 24:
                    await self.say(msg_str)
                    msg_str = "Living tributes (continued):"
                    i = 0
            if i>0:
                await self.say(msg_str)
    
    
    async def team(self,ctx, team_id="0"):
        teams = self.__teams
        player_info = self.__players
        if team_id in teams:
            await self.say(content=teams[team_id]["name"] + "*TID#" + team_id + "*", embed=self.team_embed(team_id))
        elif len(ctx.message.mentions) == 1:
            for m in ctx.message.mentions:
                if m.id in player_info:
                    tid = player_info[m.id]["team"]
                    await self.say(content=m.mention + " is a member of " + teams[tid]["name"] + " *TID#" + tid + "*", embed=self.team_embed(tid))
                else:
                    await self.say(content=m.mention + " is not a member of any team.")
        else: 
            tid = player_info[ctx.message.author.id]["team"]
            await self.say(content=ctx.message.author.mention + " is a member of " + teams[tid]["name"] + "*TID#" + tid + "*", embed=self.team_embed(tid))

    
    
    async def is_alive(self,ctx):
        if len(ctx.message.mentions) == 0:
            who = [ctx.message.author]
        else:
            who = ctx.message.mentions
        msg_str = "\n".join([a.display_name + " is " + self.status(a) for a in who])
        await self.say(msg_str)
    
    async def list_teams(self,ctx):
        teams = self.__teams
        msg_str = "\n".join([tid + ". " + teams[tid]["name"] for tid in teams])
        msg_str = "Teams\n" + msg_str
        await self.say(content=msg_str)
        
    
    async def join_team(self,ctx, team_id="0"):
        player_info = self.__players
        teams = self.__teams
        who = ctx.message.author
        if not who.id in player_info:
            self.add_player(who.id)
        leader_of = list(filter(lambda tid: teams[tid]["leader"] == ctx.message.author.id, teams))
        
        if team_id in teams:
            if len(leader_of) > 0:
                msg_str = "You can't leave a team that you lead!"
                await self.say(content=msg_str)
            else:
                self.set_team(who,team_id)
                msg_str = who.display_name + " has joined " + teams[team_id]["name"]
                await self.say(content=msg_str,embed=self.team_embed(team_id))
        else:
            msg_str = "\n".join([tid + "." + teams[tid]["name"] for tid in teams])
            msg_str = "Teams\n" + msg_str
            await self.say(content=msg_str)
        self.save_files()
    
    
    
    #        _           _                               
    #       | |         | |                              
    #     __| |   __ _  | |_    __ _                     
    #    / _` |  / _` | | __|  / _` |                    
    #   | (_| | | (_| | | |_  | (_| |                    
    #    \__,_|  \__,_|  \__|  \__,_|                    
    #                                                    
    #                                                    
    #          _                                         
    #         | |                                        
    #    ___  | |_    ___    _ __    __ _    __ _    ___ 
    #   / __| | __|  / _ \  | '__|  / _` |  / _` |  / _ \
    #   \__ \ | |_  | (_) | | |    | (_| | | (_| | |  __/
    #   |___/  \__|  \___/  |_|     \__,_|  \__, |  \___|
    #                                        __/ |       
    #                                       |___/        
    
    
    async def reload(self,ctx):
        if(self.__reaping_active):
            self.say("Please wait until I finish reaping.")
        else:
            self.save_files()
            self.reload_files() 
            
            
    def reload_files(self):
        self.__config = configparser.ConfigParser()
        self.__config.read("config.ini")
        

        
        
        
        with open('teams.json') as json_file:  
            data = json.load(json_file)
        self.__teams = data
        with open('players.json') as json_file:  
            data = json.load(json_file)
        self.__players = data
        with open('events.json') as json_file:  
            data = json.load(json_file)
        self.__snow_events = data
        
        
        self.__death_color = discord.Color(int(self.__config["game"]["death-color"],16))
        self.__death_color = discord.Color(int(self.__config["game"]["event-color"],16))
        self.__trigger_rate= float(self.__config["game"]["trigger-rate"])
        
        self.__color = discord.Color(int(self.__config["snowbot"]["color"],16))
        self.__gamestatus = self.__config["snowbot"]["gamestatus"]
        
    def save_files(self):
        data = self.__players
        with open('players.json',"w") as json_file:  
            json.dump(data,json_file)
            


    #                                                                                      
    #                                                                                      
    #     __ _    __ _   _ __ ___     ___                                                  
    #    / _` |  / _` | | '_ ` _ \   / _ \                                                 
    #   | (_| | | (_| | | | | | | | |  __/                                                 
    #    \__, |  \__,_| |_| |_| |_|  \___|                                                 
    #     __/ |                                                                            
    #    |___/                                                                             
    #                                                                                  _   
    #                                                                                 | |  
    #    _ __ ___     __ _   _ __     __ _    __ _    ___   _ __ ___     ___   _ __   | |_ 
    #   | '_ ` _ \   / _` | | '_ \   / _` |  / _` |  / _ \ | '_ ` _ \   / _ \ | '_ \  | __|
    #   | | | | | | | (_| | | | | | | (_| | | (_| | |  __/ | | | | | | |  __/ | | | | | |_ 
    #   |_| |_| |_|  \__,_| |_| |_|  \__,_|  \__, |  \___| |_| |_| |_|  \___| |_| |_|  \__|
    #                                         __/ |                                        
    #                                        |___/                                         
    #                                                               _                      
    #                                                              | |                     
    #     ___    ___    _ __ ___    _ __ ___     __ _   _ __     __| |  ___                
    #    / __|  / _ \  | '_ ` _ \  | '_ ` _ \   / _` | | '_ \   / _` | / __|               
    #   | (__  | (_) | | | | | | | | | | | | | | (_| | | | | | | (_| | \__ \               
    #    \___|  \___/  |_| |_| |_| |_| |_| |_|  \__,_| |_| |_|  \__,_| |___/               
    #                                                                                      
    #   
    async def reap(self,ctx):
        self.__reaping_active = True
        self.say("Reaping...")
        
        vols = list(filter(lambda u: self.__alive_players_role in u.roles, self.__main_server.members))
        for trib in vols:
            await self.remove_roles(trib,self.__alive_players_role)
        i = len(vols)
        await self.say(str(i)+" contestants removed from the game.")
        vols = list(filter(lambda u: self.__all_players_role in u.roles, self.__main_server.members))
        for trib in vols:
            await self.add_roles(trib,self.__alive_players_role)
            self.add_player(trib,status="Alive")
        i = len(vols)
        await self.say(str(i)+" contestants added to the game.")    
        await self.say("Done,announcing contestants")
        
        vols = list(filter(lambda u: self.__alive_players_role in u.roles, self.__main_server.members))
        for trib in vols:
            pillc = self.__teamcolor(trib)
            em = discord.Embed(title="Tribute seleted from team " + self.__district(trib), colour=pillc)
            em.set_author(name=trib.display_name, icon_url=trib.avatar_url)
            em.set_footer(text=self.tagline(trib),icon_url=self.teampic(trib))
            await self.send_message(destination=self.__arena_channel,embed=em)
        self.__reaping_active = False
    
    async def cull(self,ctx):
        self.say("Culling...")
        vols = list(filter(lambda u: self.__alive_players_role in u.roles, self.__main_server.members))
        for trib in vols:
            await self.remove_roles(trib,self.__alive_players_role)
        i = len(vols)
        await self.say(str(i)+" contestants removed from the game.")
    
    async def trigger_event(self,ctx):
        if not self.__reaping_active:  
            await self.trig()
            await self.say("Event triggered.")
    
    async def list_events(self,ctx):
        s = "Events:"
        for e in self.__snow_events:
            x = self.__snow_events[e]["actors"]
            s = s + "\n" + e + " (" + str(x) + ")"
        await self.say(s)
    