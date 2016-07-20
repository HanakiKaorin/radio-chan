#!/usr/bin/env python

import sys
import os
import time
import logging
import builtins
import glob
import asyncio
from random import randint

import discord
import mutagen
from PIL import Image, ImageFont, ImageDraw

from settings import *

from colorama import init, Fore, Back, Style
init(autoreset=True)

def dprint(request):
    print(time.strftime('<%Y/%m/%d %H:%M:%S> ') + request)

client = discord.Client(max_messages=100)

logging.basicConfig(level=logging.WARNING)
loop = asyncio.get_event_loop()

OPUS_LIBS = ['libopus-0.x86.dll', 'libopus-0.x64.dll', 'libopus-0.dll', 'libopus.so.0', 'libopus.0.dylib']
def load_opus_lib(opus_libs=OPUS_LIBS):
    if discord.opus.is_loaded():
        return True
    for discord.opus_lib in opus_libs:
        try:
            discord.opus.load_opus(opus_lib)
            return
        except OSError:
            pass
    raise RuntimeError('Could not load an opus lib. Tried %s' % (', '.join(opus_libs)))
load_opus_lib()

@client.event
async def on_ready():
    dprint(Fore.GREEN + 'Connected as ' + client.user.name + ' (' + client.user.id + ')')
    await client.change_status(game=None, idle=False)

"""def radio_song(fn):
    if ('#' in fn):
        return fn.split('#')
    else:
        return [fn, None]"""

async def radio_play(s):
    global prev, song, voice, player
    song = songListByID[s]
    player = voice.create_ffmpeg_player(musicDir + song['file'])
    player.start()
    if (song['artist']): dprint(Fore.MAGENTA + 'Playing: ' + song['artist'] + ' - ' + song['title'])
    else: dprint(Fore.MAGENTA + 'Playing: ' + song['title'])
    await client.change_status(game=discord.Game(name=song['title'], url='', type=0), idle=False)
    prev.append(song['id'])
    if (len(prev) > 5):
        prev.remove(prev[0])
    return player

async def radio():
    global prev, queue, voice, player, vote
    await client.wait_until_ready()
    builtins.voice = await client.join_voice_channel(discord.Object(id=voiceChannel))
    player = None
    #while (voice.is_connected()):
    while True:
        if (not player or player.is_done()):
            vote = []
            i = 0
            while True:
                x = randint(0,(songs-1))
                if (not x in prev):
                    break
                i += 1
                if (i > 20):
                    break
            player = await radio_play(x)
        await asyncio.sleep(1)

@client.event
async def on_message(message):
    global song, vote, queue, prev, voice, listening, player

    if (message.content == '/next' or message.content == '/skip' or message.content == '/vote'):

        if (message.server):
            listening = []
            for x in voice.channel.voice_members:
                if (x.id != client.user.id):
                    listening.append(x.id)

            if (message.author.id in listening):
                if (not message.author.id in vote):
                    vote.append(message.author.id)

                mainMessage = str(len(vote)) + '/' + str(len(listening)) + ' voted to skip the current song.'
                if (len(vote) / len(listening) > 0.5):
                    mainMessage += ' Enough votes received. Skipping song...'
                    player.stop()
                    player = None
                    vote = []
                else:
                    mainMessage += ' More votes required to skip.'
                await client.send_message(message.channel, mainMessage)

    elif (message.content == '/refreshradio'):
        refresh_songs()

    elif (message.content == '/song'):
        black     = (33,  33,  33,  255)
        grey      = (117, 117, 117, 255)
        white     = (249, 249, 249, 255)
        fontTitle = ImageFont.truetype(imageDir + 'NotoSansCJKjp-Medium.otf',  18, encoding='utf-8')
        fontMain  = ImageFont.truetype(imageDir + 'NotoSansCJKjp-Regular.otf', 14, encoding='utf-8')

        base = Image.open(imageDir + 'base.png')

        txt = Image.new('RGBA', base.size, (255,255,255,0))
        d   = ImageDraw.Draw(txt)

        # TITLE
        d.text((24, 17), song['title'], font=fontTitle, fill=black)

        # ARTIST
        if (song['artist']): artist = song['artist']
        else:                artist = 'Unknown'
        d.text((24, 41), artist, font=fontMain, fill=black)

        # ALBUM
        if (song['album']): album = song['album']
        else:               album = 'Unknown'
        d.text((74, 70), album, font=fontMain, fill=black)

        # COMPOSER
        if (song['composer']): composer = song['composer']
        else:                  composer = 'Unknown'
        d.text((74, 88), composer, font=fontMain, fill=black)

        # LENGTH
        m, s   = divmod(int(song['length']), 60)
        length = '%d:%02d' % (m, s)
        d.text((74, 104), length, font=fontMain, fill=black)

        # COVER IMAGE
        if (os.path.exists(coverDir + song['file'][:(len(song['file'])-4)] + '.jpg')):
            cover = coverDir + song['file'][:(len(song['file'])-4)] + '.jpg'
        else:
            cover = imageDir + 'default_cover.png'
        coverImage = Image.open(cover).resize((125, 125), Image.BILINEAR)
        baseMask   = Image.open(imageDir + 'cover_mask.png')
        base.paste(coverImage, (268, 8), mask=baseMask)

        # FINAL IMAGE
        out = Image.alpha_composite(base, txt)
        out.save(imageDir + 'output.png', 'PNG')

        # POST IMAGE
        await client.send_file(message.channel, imageDir + 'output.png', filename=None, content=None, tts=False)

        # DELETE MESSAGE
        if (message.server): await client.delete_message(message)

def refresh_songs(echo=True):
    global songList, songListByID, songListByTitle, songs, prev, queue
    prev  = []
    queue = []
    if (echo): dprint(Fore.CYAN + 'Refreshing songs...')
    i = 0
    for fn in glob.glob(musicDir + '*.mp3'):
        x = mutagen.File(fn)
        y = {}
        if (x.tags):
            y['id'] = i
            if ('TIT2' in x.tags): y['title']    = x.tags['TIT2'].text[0]
            else:                  y['title']    = fn[len(musicDir):]
            if ('TPE1' in x.tags): y['artist']   = x.tags['TPE1'].text[0]
            else:                  y['artist']   = None
            if ('TALB' in x.tags): y['album']    = x.tags['TALB'].text[0]
            else:                  y['album']    = None
            if ('TCOM' in x.tags): y['composer'] = x.tags['TCOM'].text[0]
            else:                  y['composer'] = None
            y['length'] = x.info.length
            y['file'] = fn[len(musicDir):]
        else:
            y = {
                'id': i,
                'title': fn[len(musicDir):],
                'artist': None,
                'album': None,
                'composer': None,
                'length': x.info.length,
                'file': fn[len(musicDir):]
            }
        songList.append(y)
        i += 1
    songs = i
    for x in songList:
        songListByID[x['id']]       = x
        songListByTitle[x['title']] = x
    if (echo): dprint(Fore.GREEN + 'Songs refreshed')

if __name__ == '__main__':
    dprint(Fore.CYAN + 'Radio-chan is starting')
    dprint(Fore.CYAN + 'Timezone is ' + time.strftime('%Z'))

    builtins.songList        = []
    builtins.songListByID    = {}
    builtins.songListByTitle = {}
    builtins.songs           = 0
    builtins.prev            = []
    builtins.queue           = []
    builtins.vote            = []

    refresh_songs(echo=False)

    dprint(Fore.YELLOW + 'Connecting to Discord')
    try:
        radio_task = loop.create_task(radio())
        loop.run_until_complete(client.login(discordToken))
        loop.run_until_complete(client.connect())
    except KeyboardInterrupt:
        loop.run_until_complete(client.logout())
    finally:
        loop.close()
