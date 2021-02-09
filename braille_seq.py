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
import braille
import os
import math
import argparse
import asyncio
import time
from PIL import Image, ImageFilter


class _Args:
    source_url: str
    source_file_path: str

    reverse: bool
    size_percent: float
    max_x: int
    max_y: int

    sensitivity_r: float
    sensitivity_g: float
    sensitivity_b: float
    sensitivity_a: float

    enable_padding: bool
    pad_size_x: int
    pad_size_y: int

    enable_processing: bool

    pre_process_sobel: bool

    fps: int
    resume: int
    audio_file: str
    output: str
    subtitles: str

    no_compress: bool
    input_path: str
    until_frame: int

    log_prefix: str


def embed_audio(output):
    print('Embedding audio...')
    audio = open(args.audio_file, 'rb')
    size = audio.seek(0, 2)
    audio.seek(0, 0)  # back to start
    output.write('#audio\n'.encode())
    output.write(str(size).encode() + b'\n')
    output.write(audio.read())
    print('Embedded audio!')

def get_subtitle_for_frame(subs: list, frame: int) -> str:
    for s in subs:
        if s[1] < frame < s[2]:
            return s[0]
    return ''

def _parse_ts(text: str, fps: float):
    hour, minute, second = text.split(':')
    hour = int(hour)
    minute = int(minute)
    second = float(second)

    frames = (hour * 360 + minute * 60 + second) * fps
    return frames

def parse_subtitles(path: str, fps: float):
    subs = [
        ['Meta: ', 0, 0]
    ]
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if '-->' in line:
                start, end = line.split('-->', 1)
                start = math.floor(_parse_ts(start, fps))
                end = math.ceil(_parse_ts(end, fps))
                subs.append(['', start, end])
            else:
                subs[-1][0] += line
    return subs


_print = print


async def main():
    global print
    if args.log_prefix:
        print = lambda *a, **kw: _print(args.log_prefix, *a, **kw)
    images = sorted(os.listdir(args.input_path))

    output = open(args.output, 'ab' if args.resume else 'wb')
    output.write(f'#meta frames={len(images)};fps={args.fps}\n'.encode())
    if not args.resume and args.audio_file:
        embed_audio(output)
    if args.subtitles:
        subs = parse_subtitles(args.subtitles, args.fps)
        print(subs)
    else:
        subs = []
    target_speed = args.fps

    last_frame = ['']*1024

    start = time.monotonic()
    for num, fname in enumerate(images):
        if args.resume > num:
            continue
        if args.until_frame < num:
            break
        path = os.path.join(args.input_path, fname)
        _img = Image.open(path)
        if args.pre_process_sobel:
            _img = _img.convert('RGBA')
            _img = _img.filter(ImageFilter.FIND_EDGES)
        txt = await braille.to_braille_from_image(
            _img,
            reverse=args.reverse,
            size_percent=args.size_percent,
            max_x=args.max_x,
            max_y=args.max_y,
            sensitivity=(args.sensitivity_r, args.sensitivity_g, args.sensitivity_b, args.sensitivity_a),
            enable_padding=args.enable_padding,
            pad_size=(args.pad_size_x, args.pad_size_y),
            enable_processing=args.enable_processing
        )
        header, txt = txt.split('\n', 1)
        frame_text = ''
        
        frame_text += txt
        frame_text += get_subtitle_for_frame(subs, num) + '\n'
        #frame_text += '#next\n'
        frame_text = frame_text.split('\n')
        for lnum, line in enumerate(frame_text):
            if args.no_compress or num % (2*args.fps) == 0:
                o = line
            elif line == last_frame[lnum]:
                o = ''
            else:
                count_same = 0
                for cnum, char in enumerate(line):
                    if len(last_frame[lnum]) >= len(line) and char == last_frame[lnum][cnum]:
                        count_same += 1
                    else:
                        break

                if count_same == 0:
                    o = line
                else:
                    o = f'\033[{count_same}C' + line[count_same:]
            output.write(o.encode() + b'\n')
            last_frame[lnum] = line

        output.write('#next\n'.encode())
        current = time.monotonic()
        taken = current - start
        speed = num/taken
        print(f'Done with frame #{num} ({num/len(images)*100:.2f}%) {taken:.2f}s taken, {speed:.2f} fps, {speed/target_speed * 100:.2f}% speed. {header}')
    output.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--reverse', action='store_true', dest='reverse', help='Reverse the result')
    p.add_argument('--input', dest='input_path')

    size_group = p.add_mutually_exclusive_group(required=True)
    size_group.add_argument('--size_percent', dest='size_percent', type=float,
                            help='Resize image to SIZE_PERCENT width and height.')
    size_group.add_argument('--max_x', dest='max_x', type=int, metavar='SIZE')
    p.add_argument('--max_y', dest='max_y', type=int, metavar='SIZE')

    p.add_argument('--sensitivity_r', '-Sr', dest='sensitivity_r', type=float, default=2, metavar='RED',
                   help='Sensitivity for red channel')
    p.add_argument('--sensitivity_g', '-Sg', dest='sensitivity_g', type=float, default=2, metavar='GREEN',
                   help='Sensitivity for green channel')
    p.add_argument('--sensitivity_b', '-Sb', dest='sensitivity_b', type=float, default=2, metavar='BLUE',
                   help='Sensitivity for blue channel')
    p.add_argument('--sensitivity_a', '-Sa', dest='sensitivity_a', type=float, default=1, metavar='ALPHA',
                   help='Sensitivity for alpha channel')

    p.add_argument('--disable_padding', dest='enable_padding', action='store_false',
                   help='Disable padding the image during the process of converting it to braille.')

    p.add_argument('--pad_size_x', '-Px', dest='pad_size_x', type=int, default=60, metavar='SIZE')
    p.add_argument('--pad_size_y', '-Py', dest='pad_size_y', type=int, default=60, metavar='SIZE')

    p.add_argument('--disable_processing', '-p', dest='enable_processing', action='store_false',
                   help='Disable all processing of the image')

    p.add_argument('--sobel', '-s', dest='pre_process_sobel', action='store_true',
                   help='Apply an edge detection filter before converting the image.')


    p.add_argument('--fps', '-f', dest='fps', type=int,
                   help='Changes the fps for progress/speed display')
    p.add_argument('--resume-from', '-r', dest='resume', type=int, default=0)
    p.add_argument('--audio', dest='audio_file', type=str)
    p.add_argument('--output', dest='output', type=str, default='output')
    p.add_argument('--subtitles', dest='subtitles', type=str)
    p.add_argument('--no-compress', dest='no_compress', action='store_true')
    p.add_argument('--until-frame', dest='until_frame', type=int)
    p.add_argument('--log-prefix', dest='log_prefix')
    args = p.parse_args(namespace=_Args())

    asyncio.get_event_loop().run_until_complete(main())
