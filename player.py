#  This is a tool that can convert videos to braille art
#  Copyright (C) 2021 Mm2PL
# 
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
# 
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import argparse
import time
import sys
import io
import subprocess as sp
import atexit

def spawn_vlc():
    proc =  sp.Popen(['vlc', 'fd://0', '--no-one-instance', '-I', 'dummy', '--no-repeat'], stdin=sp.PIPE)
    atexit.register(proc.kill)
    return proc

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('-i', '--input', dest='target', type=str, required=True)
    p.add_argument('-f', '--fps', dest='fps', type=float)
    p.add_argument('--no-audio', dest='no_audio', action='store_true')
    p.add_argument('-s', '--skip', dest='skip', type=float)
    args = p.parse_args()
    if args.target == '-':
        file = sys.stdin.buffer
    else:
        file = open(args.target, 'rb')

    print('Loading audio...')
    audio = io.BytesIO()
    count_bytes = 0
    bytes_read = 0
    next_line = None
    meta = {}
    for line in file:
        if next_line == 'audio_len':
            line = line.decode().strip()
            count_bytes = int(line)
            print(count_bytes, '...')
            next_line = 'data'
            audio.write(file.read(count_bytes))
            break
        elif next_line is None:
            line = line.decode()
            if line == '#audio\n':
                next_line = 'audio_len'
            elif line.startswith('#meta'):
                _, metadata = line.rstrip().split(' ', 1)
                meta = {(o:=i.split('=', 1))[0]: o[1] for i in metadata.split(';')}
    else:
        file.seek(0)
    
    print('Read audio bytes...')
    if count_bytes and not args.no_audio:
        vlc = spawn_vlc()
        audio.seek(0)
        vlc.stdin.write(audio.read())
        print('Audio written!')

    start = time.monotonic()
    now = time.monotonic()
    frame_time = time.monotonic()

    args.fps = args.fps or int(meta.get('fps', 24))
    length = int(meta.get('len', 0)) / args.fps

    frame = 0
    FRAME_COUNT = 20
    frame_times = [0] * FRAME_COUNT
    no_sleep_frame_times = [0] * FRAME_COUNT
    remaining = 0
    sys.stdout.write('\033[H\033[2J')
    if args.skip:
        remaining = args.skip

    for num, line in enumerate(file):
        line = line.decode()
        if line == '#next\n':
            now = time.monotonic()
            draw_time = now - frame_time
            sleep_time = 1/args.fps - draw_time + remaining
            if sleep_time > 0:
                time.sleep(sleep_time)
                remaining = 0
            else:
                remaining = sleep_time

            sys.stdout.flush()
            now = time.monotonic()
            taken = now - start
            frame_taken = now - frame_time
            frame_times[frame % FRAME_COUNT] = frame_taken
            sys.stdout.write(f'\033[H\033[2K{taken:.2f}s / {length}s, {num/taken:.2f} lps, {1/frame_taken:.2f} fps, {FRAME_COUNT/sum(frame_times):.2f} avg fps from last {FRAME_COUNT} frames ±{remaining}s\n')
            frame += 1
            frame_time = time.monotonic()
        else:
            sys.stdout.write(line)
