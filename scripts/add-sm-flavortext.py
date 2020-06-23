# Generates SQL to add flavor text from the text dump to the database.
#
# Usage: python add-sm-flavortext.py path/to/text | psql pokedex

import os.path
import sys
import re

textdir = sys.argv[1]
#VERSION = 'sun'
#FILE = '119'
VERSION = 'ultra-moon'
FILE = '125'

NUM_SPECIES = 807

lang_idents = {
    'ja-kana': 'ja-Hrkt',
    'ja-kanji': 'ja',
}

flavor_texts = []
for lang in 'ja-kana', 'ja-kanji', 'en', 'fr', 'it', 'de', 'es', 'ko', 'zh-Hant', 'zh-Hans':
    f = open(os.path.join(textdir, lang, FILE))
    flavor_texts.append((lang_idents.get(lang, lang), f))

print("BEGIN;")

for lang, text in flavor_texts:
    print("\echo '%s'" % lang)
    print("WITH lang AS (SELECT id FROM languages WHERE identifier = '%s')," % lang)
    print("     version AS (SELECT id FROM versions WHERE identifier = '%s')" % VERSION) 
    print("INSERT INTO pokemon_species_flavor_text (species_id, version_id, language_id, flavor_text) VALUES");
    first = True
    for i, line in enumerate(text):
        if i == 0:
            continue
        if i > NUM_SPECIES:
            break
        if line == '\n':
            continue
        line = line.strip('\n')
        line = line.replace("\\ue07f", "\\u202f") # nbsp
        if '\\x' in line or '\\r' in line or '\\u' in line.replace("\\u202f",""):
            print("warning: %s %d: %r" % (lang, i, line), file=sys.stderr)

        if first:
            first = False
        else:
            print(",\n", end="")
        print("    (%d, (select id from version), (select id from lang), E'%s')" % (i, line), end="")
    print(";")

print("COMMIT;")
#print("ROLLBACK;")
