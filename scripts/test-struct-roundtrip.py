#! /usr/bin/env python
"""
This is an ad-hoc testing script. YMMV
"""

import os
import sys
import pprint
import binascii
import traceback
import subprocess
import tempfile
import itertools

import yaml  # you need to pip install pyyaml
from blessings import Terminal  # you need to pip install blessings

from pokedex import struct
from pokedex.db import connect

session = connect(engine_args=dict(echo=False))

if len(sys.argv) < 1:
    print 'Give this script a bunch of PKM files to test roundtrips on.'
    print 'A number (e.g. "4") will be interpreted as the generation of'
    print 'the following files, until a new generation is given.'
    print 'Use "./5" for a file named 5.'
    print
    print 'If mismatches are found, your screen will be filled with colorful'
    print 'reports. You need the colordiff program for this.'

def printable(c):
    if ord(' ') < ord(c) < ord('~'):
        return c
    else:
        return '.'

def colordiff(str1, str2, prefix='tmp-'):
    if str1 != str2:
        with tempfile.NamedTemporaryFile(prefix=prefix + '.', suffix='.a') as file1:
            with tempfile.NamedTemporaryFile(prefix=prefix + '.', suffix='.b') as file2:
                file1.write(str1)
                file2.write(str2)
                file1.flush()
                file2.flush()
                p = subprocess.Popen(['colordiff', '-U999', file1.name, file2.name])
                p.communicate()
    else:
        print prefix, 'match:'
        print str1

Class = struct.save_file_pokemon_classes[5]

filenames_left = list(reversed(sys.argv[1:]))

while filenames_left:
    filename = filenames_left.pop()
    print filename

    try:
        generation = int(filename)
    except ValueError:
        pass
    else:
        Class = struct.save_file_pokemon_classes[generation]
        continue

    if os.path.isdir(filename):
        for name in sorted(os.listdir(filename), reverse=True):
            joined = os.path.join(filename, name)
            if name.endswith('.pkm') or os.path.isdir(joined):
                filenames_left.append(joined)
        continue

    with open(filename) as f:
        blob = f.read()[:0x88]

    if blob[0] == blob[1] == blob[2] == blob[3] == '\0':
        print binascii.hexlify(blob)
        print 'Probably not a PKM file'

    try:
        orig_object = Class(blob, session=session)
        dict_ = orig_object.export_dict()
    except Exception:
        traceback.print_exc()
        print binascii.hexlify(blob)
        continue
    orig_object.blob
    new_object = Class(dict_=dict_, session=session)
    try:
        blob_again = new_object.blob
        dict_again = new_object.export_dict()
    except Exception:
        colordiff(yaml.dump(orig_object.structure), yaml.dump(new_object.structure), 'struct')
        traceback.print_exc()
        continue

    if (dict_ != dict_again) or (blob != blob_again):
        colordiff(yaml.dump(orig_object.structure), yaml.dump(new_object.structure), 'struct')
        colordiff(yaml.safe_dump(dict_), yaml.safe_dump(dict_again), 'yaml')
        t = Terminal()
        for pass_number in 1, 2, 3:
            for i, (a, b) in enumerate(itertools.izip_longest(blob, blob_again, fillvalue='\xbb')):
                if (i - 8) % 32 == 0:
                    # Block boundary
                    sys.stdout.write(' ')
                a_hex = binascii.hexlify(a)
                b_hex = binascii.hexlify(b)
                if a != b:
                    if pass_number == 1:
                        sys.stdout.write(t.green(printable(a)))
                        sys.stdout.write(t.red(printable(b)))
                    elif pass_number == 2:
                        sys.stdout.write(t.green(a_hex))
                    elif pass_number == 3:
                        sys.stdout.write(t.red(b_hex))
                else:
                    if pass_number == 1:
                        sys.stdout.write(printable(a))
                        sys.stdout.write(printable(b))
                    else:
                        sys.stdout.write(a_hex)
            print
        print
