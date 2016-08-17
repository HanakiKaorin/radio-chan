#!/usr/bin/env python

from __future__ import unicode_literals
import sys
import os
import time
import logging
import builtins
import glob
import asyncio
import hashlib
from random import randint, choice

import discord
import youtube_dl
import mutagen
from PIL import Image, ImageFont, ImageDraw

from settings import *

from colorama import init, Fore, Back, Style
init(autoreset=True)

def dprint(request):
    print(Style.DIM + time.strftime('<%Y/%m/%d %H:%M:%S> ') + Style.BRIGHT + request)

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

def yt_format(vid, title, uploader, dur):
    print(vid + '\n' + title + '\n' + uploader + '\n' + dur)
    return vid

async def yt_queue(s, m):
    global prev, song, voice, player, yt

    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'nocheckcertificate': True,
        'quiet': True,
        #'outtmpl': yt_format('%(id)s', '%(title)s', '%(uploader)s', '%(duration)s'),
        'outtmpl': ytDir + '%(id)s',
        'default_search': 'auto'
    }

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        meta = ydl.extract_info(s, download=False)
    yt[meta['id']] = {
        'id': meta['id'],
        'title': meta['title'],
        'artist': meta['uploader'],
        'album': 'YouTube',
        'composer': None, # meta['view_count'] / meta['like_count'] / meta['dislike_count']
        'length': meta['duration'],
        'file': meta['id']
    }

    if (meta['id'] in prev):
        mainMessage = '[' + m.author.display_name + ']　The song [YT] _' + meta['title'] + '_ has already been played recently'
    elif (meta['id'] in queue):
        mainMessage = '[' + m.author.display_name + ']　The song [YT] _' + meta['title'] + '_ is already in the queue'
    elif (meta['duration'] > 900):
        mainMessage = '[' + m.author.display_name + ']　The song [YT] _' + meta['title'] + '_ is too long (max 15 minutes)'
    else:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([s])
        queue.append(meta['id'])
        dprint(Fore.MAGENTA + m.author.display_name + ' queued:' + Style.NORMAL + ' [YT] ' + meta['uploader'] + ' - ' +  meta['title'])
        mainMessage = '[' + m.author.display_name + ']　Queued [YT] _' + meta['title'] + '_'

    await client.send_message(m.channel, mainMessage)
    if (m.server): await client.delete_message(m)

async def radio_play(s):
    global prev, song, voice, player

    if (len(s) > 4):
        song = yt[s]
        player = voice.create_ffmpeg_player(ytDir + song['file'], before_options='-hide_banner -loglevel panic', options='-b:a 64k -bufsize 64k')
        player.start()
        dprint(Fore.MAGENTA + 'Playing:' + Style.NORMAL + ' [YT] ' + song['artist'] + ' - ' +  song['title'])
    else:
        song = songListByID[s]
        player = voice.create_ffmpeg_player(musicDir + song['file'], before_options='-hide_banner -loglevel panic', options='-b:a 64k -bufsize 64k')
        player.start()
        if (song['artist']):
            dprint(Fore.MAGENTA + 'Playing:' + Style.NORMAL + ' [' + song['id'] + '] ' + song['artist'] + ' - ' + song['title'])
        else:
            dprint(Fore.MAGENTA + 'Playing:' + Style.NORMAL + ' [' + song['id'] + '] ' + song['title'])

    await client.change_status(game=discord.Game(name=song['title'], url='', type=0), idle=False)
    prev.append(song['id'])
    if (len(prev) > 5):
        prev.remove(prev[0])
    return player

async def radio():
    global prev, queue, voice, player, vote, listening, playing
    await client.wait_until_ready()
    builtins.voice = await client.join_voice_channel(discord.Object(id=voiceChannel))
    refresh_listeners(echo=False)
    player = None
    #while (voice.is_connected()):
    while True:
        if (not player or player.is_done()):
            vote = []
            if (len(prev) > 0):
                if (len(prev[-1]) > 4):
                    try:
                        os.remove(ytDir + prev[-1])
                        del yt[prev[-1]]
                    except OSError:
                        pass
            refresh_listeners(echo=False)
            if (len(listening) > 0):
                if (not playing):
                    dprint(Fore.YELLOW + 'Resumed Radio-chan')
                playing = True
                if (len(queue) > 0):
                    x = queue[0]
                    queue.remove(queue[0])
                else:
                    i = 0
                    while True:
                        #x = randint(0,(songs-1))
                        x = choice(list(songListByID.keys()))
                        if (not x in prev):
                            break
                        i += 1
                        if (i > 20):
                            break
                player = await radio_play(x)
            else:
                if (playing):
                    dprint(Fore.YELLOW + 'Pausing Radio-chan')
                    await client.change_status(game=None, idle=False)
                playing = False
        await asyncio.sleep(1)

@client.event
async def on_message(message):
    global song, vote, queue, prev, voice, listening, player

    if (message.content == '/radio'):
        mainMessage = '[' + message.author.display_name + ']　**Radio-chan**'
        mainMessage += '\n・`/radio`　This help message'
        mainMessage += '\n・`/song`　Information about currently playing song'
        #mainMessage += '\n・`/song -t`　Information about currently playing song in plain text'
        #mainMessage += '\n・`/song [request]`　Search for song by ~~Name, Artist or~~ ID'
        mainMessage += '\n・`/queue [request]`　Queue song by ~~Name, Artist or~~ ID (first match) _(listeners only)_'
        mainMessage += '\n・`/yt [request]`　Queue song by YouTube video URL _(listeners only)_'
        mainMessage += '\n・`/next` or `/skip` or `/vote`　Vote to skip currently playing song _(listeners only)_'

        await client.send_message(message.channel, mainMessage)
        if (message.server): await client.delete_message(message)

    elif (message.content == '/next' or message.content == '/skip' or message.content == '/vote'):
        if (message.server):
            refresh_listeners(echo=False)

            if (message.author.id in listening):
                if (not message.author.id in vote):
                    vote.append(message.author.id)

                mainMessage = '[' + message.author.display_name + ']　**' + str(len(vote)) + ' / ' + str(len(listening)) + '** voted to skip the current song.'
                if (len(vote) / len(listening) > 0.5):
                    mainMessage += ' Enough votes received. Skipping song...'
                    player.stop()
                    player = None
                    vote = []
                else:
                    mainMessage += ' More votes required to skip.'
                await client.send_message(message.channel, mainMessage)
            else:
                await client.send_message(message.channel, '[' + message.author.display_name + ']　You are not currently listening to the radio.')
            await client.delete_message(message)

    elif (message.content == '/next -f' or message.content == '/skip -f' or message.content == '/vote -f'):
        if (message.author.id in admins):
            player.stop()
            player = None
            vote = []
            refresh_listeners(echo=False)
            mainMessage = '[' + message.author.display_name + ']　**ｘ / ' + str(len(listening)) + '** voted to skip the current song. Skipping song...'
            await client.send_message(message.channel, mainMessage)
            if (message.server): await client.delete_message(message)
            dprint(Fore.MAGENTA + message.author.display_name + ' forced a song skip')

    elif (message.content == '/refreshradio'):
        if (message.author.id in admins):
            refresh_songs()
            await client.send_message(message.channel, '[' + message.author.display_name + ']　Radio-chan has been refreshed.')
            if (message.server): await client.delete_message(message)

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

        # CLEAR MEMORY
        base = None
        txt = None
        coverImage = None
        baseMask = None
        out = None

    elif (message.content[:4] == '/yt '):
        refresh_listeners(echo=False)
        if (message.author.id in listening):
            request = message.content[4:]
            await yt_queue(request, message)

    elif (message.content[:6] == '/song ' and message.content != '/song ' or message.content[:7] == '/queue ' and message.content != '/queue '):
        if (message.content[:6] == '/song '):
            request = message.content[6:]
            mode = 'search'
        else:
            request = message.content[7:]
            mode = 'queue'

        if (request in songListByID):
            if (songListByID[request]['id'] in prev):
                mainMessage = '[' + message.author.display_name + ']　The song [' + songListByID[request]['id'] + '] _' + songListByID[request]['title'] + '_ has already been played recently'
            elif (songListByID[request]['id'] in queue):
                mainMessage = '[' + message.author.display_name + ']　The song [' + songListByID[request]['id'] + '] _' + songListByID[request]['title'] + '_ is already in the queue'
            else:
                queue.append(songListByID[request]['id'])

                if (songListByID[request]['artist']):
                    dprint(Fore.MAGENTA + message.author.display_name + ' queued:' + Style.NORMAL + ' [' + songListByID[request]['id'] + '] ' + songListByID[request]['artist']  + ' - ' + songListByID[request]['title'])
                    mainMessage = '[' + message.author.display_name + ']　Queued [' + songListByID[request]['id'] + '] _' + songListByID[request]['artist'] + ' - ' + songListByID[request]['title'] + '_'
                else:
                    dprint(Fore.MAGENTA + message.author.display_name + ' queued:' + Style.NORMAL + ' [' + songListByID[request]['id'] + '] ' + songListByID[request]['title'])
                    mainMessage = '[' + message.author.display_name + ']　Queued [' + songListByID[request]['id'] + '] _' + songListByID[request]['title'] + '_'
            await client.send_message(message.channel, mainMessage)

        if (message.server): await client.delete_message(message)

def refresh_listeners(echo=True):
    global listening, voice
    listening = []
    for x in voice.channel.voice_members:
        if (x.id != client.user.id and not x.bot):
            listening.append(x.id)

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
            #y['id'] = i
            y['id'] = hashlib.md5(fn[len(musicDir):].encode()).hexdigest()[:4]
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
                #'id': i,
                'id': hashlib.md5(fn[len(musicDir):].encode()).hexdigest()[:4],
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
    builtins.yt              = {}
    builtins.songs           = 0
    builtins.prev            = []
    builtins.queue           = []
    builtins.vote            = []
    builtins.listening       = []
    builtins.playing         = False

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
