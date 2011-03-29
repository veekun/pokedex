# encoding: utf8
"""Provides `romanize()` for romanizing simple Japanese text.

Also provides available romanizers in a dictionary keyed by language identifier.
"""

class Romanizer(object):
    def __init__(self, parent=None, **tables):
        """Create a Romanizer

        parent: A LookupTables to base this one on
        tables: Dicts that become the object's attributes. If a parent is given,
            its tables are used, and updated with the given ones
        """
        self.parent = parent
        if parent:
            self.tables = parent.tables
            for name, table in tables.items():
                # Take a copy -- don't want to clobber the parent's tables
                self.tables[name] = dict(self.tables[name])
                self.tables[name].update(table)
        else:
            self.tables = tables

        for name, table in self.tables.items():
            setattr(self, name, table)

    def romanize(self, string):
        """Convert a string of kana to roomaji."""

        vowels = ['a', 'e', 'i', 'o', 'u', 'y']

        characters = []
        last_kana = None  # Used for ー; っ or ッ; ん or ン
        last_char = None  # Used for small kana combos
        for char in string:
            # Full-width Latin
            if 0xff01 <= ord(char) <= 0xff5e:
                if last_kana == 'sokuon':
                    raise ValueError("Sokuon cannot precede Latin characters.")

                # XXX Real Unicode decomposition would be nicer
                char = chr(ord(char) - 0xff01 + 0x21)
                characters.append(char)

                last_kana = None

            # Small vowel kana
            elif char in self.roomaji_small_kana:
                combo = last_char + char
                if combo in self.roomaji_small_kana_combos:
                    characters[-1] = self.roomaji_small_kana_combos[combo]

                else:
                    # If we don't know what it is...  act dumb and treat it as a
                    # full-size vowel.  Better than bailing, and seems to occur a
                    # lot, e.g. ピィ is "pii"
                    characters.append(self.roomaji_small_kana[char])

                last_kana = self.roomaji_small_kana[char]

            # Youon
            elif char in self.roomaji_youon:
                if not last_kana or last_kana[-1] != 'i' or last_kana == 'i':
                    raise ValueError("Youon must follow an -i sound.")

                # Drop the -i and append the ya/yu/yo sound
                new_sound = self.roomaji_youon[char]
                if last_kana in self.y_drop:
                    # Strip the y-
                    new_char = self.y_drop[last_kana] + new_sound[1:]
                else:
                    new_char = last_kana[:-1] + new_sound

                characters[-1] = new_char
                last_kana = new_char

            # Sokuon
            elif char in (u'っ', u'ッ'):
                # Remember it and double the consonant next time around
                last_kana = 'sokuon'

            # Extended vowel or n
            elif char == u'ー':
                if last_kana[-1] not in vowels:
                    raise ValueError(u"'ー' must follow by a vowel.")
                if last_kana[-1] in self.lengthened_vowels:
                    characters[-1] = characters[-1][:-1]
                    characters.append(self.lengthened_vowels[last_kana[-1]])
                else:
                    characters.append(last_kana[-1])

                last_kana = None

            # Regular ol' kana
            elif char in self.roomaji_kana:
                kana = self.roomaji_kana[char]

                if last_kana == 'sokuon':
                    if kana[0] in vowels:
                        raise ValueError("Sokuon cannot precede a vowel.")

                    characters.append(kana[0])
                elif last_kana == 'n' and kana[0] in vowels:
                    characters.append("'")

                # Special characters fo doubled kana
                if kana[0] in self.lengthened_vowels and characters and kana == characters[-1][-1]:
                    kana = self.lengthened_vowels[kana[0]]
                    characters[-1] = characters[-1][:-1]

                characters.append(kana)

                last_kana = kana

            # Not Japanese?
            else:
                if last_kana == 'sokuon':
                    raise ValueError("Sokuon must be followed by another kana.")

                characters.append(char)

                last_kana = None

            last_char = char


        if last_kana == 'sokuon':
            raise ValueError("Sokuon cannot be the last character.")

        return unicode(''.join(characters))


romanizers = dict()

romanizers['en'] = Romanizer(
    roomaji_kana={
        # Hiragana
        u'あ': 'a',     u'い': 'i',     u'う': 'u',     u'え': 'e',     u'お': 'o',
        u'か': 'ka',    u'き': 'ki',    u'く': 'ku',    u'け': 'ke',    u'こ': 'ko',
        u'さ': 'sa',    u'し': 'shi',   u'す': 'su',    u'せ': 'se',    u'そ': 'so',
        u'た': 'ta',    u'ち': 'chi',   u'つ': 'tsu',   u'て': 'te',    u'と': 'to',
        u'な': 'na',    u'に': 'ni',    u'ぬ': 'nu',    u'ね': 'ne',    u'の': 'no',
        u'は': 'ha',    u'ひ': 'hi',    u'ふ': 'fu',    u'へ': 'he',    u'ほ': 'ho',
        u'ま': 'ma',    u'み': 'mi',    u'む': 'mu',    u'め': 'me',    u'も': 'mo',
        u'や': 'ya',                    u'ゆ': 'yu',                    u'よ': 'yo',
        u'ら': 'ra',    u'り': 'ri',    u'る': 'ru',    u'れ': 're',    u'ろ': 'ro',
        u'わ': 'wa',    u'ゐ': 'wi',                    u'ゑ': 'we',    u'を': 'wo',
                                                                        u'ん': 'n',
        u'が': 'ga',    u'ぎ': 'gi',    u'ぐ': 'gu',    u'げ': 'ge',    u'ご': 'go',
        u'ざ': 'za',    u'じ': 'ji',    u'ず': 'zu',    u'ぜ': 'ze',    u'ぞ': 'zo',
        u'だ': 'da',    u'ぢ': 'ji',    u'づ': 'dzu',   u'で': 'de',    u'ど': 'do',
        u'ば': 'ba',    u'び': 'bi',    u'ぶ': 'bu',    u'べ': 'be',    u'ぼ': 'bo',
        u'ぱ': 'pa',    u'ぴ': 'pi',    u'ぷ': 'pu',    u'ぺ': 'pe',    u'ぽ': 'po',

        # Katakana
        u'ア': 'a',     u'イ': 'i',     u'ウ': 'u',     u'エ': 'e',     u'オ': 'o',
        u'カ': 'ka',    u'キ': 'ki',    u'ク': 'ku',    u'ケ': 'ke',    u'コ': 'ko',
        u'サ': 'sa',    u'シ': 'shi',   u'ス': 'su',    u'セ': 'se',    u'ソ': 'so',
        u'タ': 'ta',    u'チ': 'chi',   u'ツ': 'tsu',   u'テ': 'te',    u'ト': 'to',
        u'ナ': 'na',    u'ニ': 'ni',    u'ヌ': 'nu',    u'ネ': 'ne',    u'ノ': 'no',
        u'ハ': 'ha',    u'ヒ': 'hi',    u'フ': 'fu',    u'ヘ': 'he',    u'ホ': 'ho',
        u'マ': 'ma',    u'ミ': 'mi',    u'ム': 'mu',    u'メ': 'me',    u'モ': 'mo',
        u'ヤ': 'ya',                    u'ユ': 'yu',                    u'ヨ': 'yo',
        u'ラ': 'ra',    u'リ': 'ri',    u'ル': 'ru',    u'レ': 're',    u'ロ': 'ro',
        u'ワ': 'wa',    u'ヰ': 'wi',                    u'ヱ': 'we',    u'ヲ': 'wo',
                                                                        u'ン': 'n',
        u'ガ': 'ga',    u'ギ': 'gi',    u'グ': 'gu',    u'ゲ': 'ge',    u'ゴ': 'go',
        u'ザ': 'za',    u'ジ': 'ji',    u'ズ': 'zu',    u'ゼ': 'ze',    u'ゾ': 'zo',
        u'ダ': 'da',    u'ヂ': 'ji',    u'ヅ': 'dzu',   u'デ': 'de',    u'ド': 'do',
        u'バ': 'ba',    u'ビ': 'bi',    u'ブ': 'bu',    u'ベ': 'be',    u'ボ': 'bo',
        u'パ': 'pa',    u'ピ': 'pi',    u'プ': 'pu',    u'ペ': 'pe',    u'ポ': 'po',
                                        u'ヴ': 'vu',
    },

    roomaji_youon={
        # Hiragana
        u'ゃ': 'ya',                    u'ゅ': 'yu',                    u'ょ': 'yo',

        # Katakana
        u'ャ': 'ya',                    u'ュ': 'yu',                    u'ョ': 'yo',
    },

    # XXX If romanize() ever handles hiragana, it will need to make sure that the
    # preceding character was a katakana
    # This does not include every small kana combination, but should include every
    # one used in a Pokémon name.  An exhaustive list would be..  very long
    roomaji_small_kana={
        u'ァ': 'a',     u'ィ': 'i',     u'ゥ': 'u',     u'ェ': 'e',     u'ォ': 'o',
    },
    roomaji_small_kana_combos={
        # These are, by the way, fairly arbitrary.  "shi xi" to mean "sy" is
        # particularly weird, but it seems to be what GF intends

        # Simple vowel replacement
                        u'ウィ': 'wi',  u'ウゥ': 'wu',  u'ウェ': 'we',  u'ウォ': 'wo',
        u'ヴァ': 'va',  u'ヴィ': 'vi',                  u'ヴェ': 've',  u'ヴォ': 'vo',
                                                        u'チェ': 'che',
                                                        u'シェ': 'she',
                                                        u'ジェ': 'je',
        u'テァ': 'tha', u'ティ': 'ti',  u'テゥ': 'thu', u'テェ': 'tye', u'テォ': 'tho',
        u'デァ': 'dha', u'ディ': 'di',  u'デゥ': 'dhu', u'デェ': 'dye', u'デォ': 'dho',
        u'ファ': 'fa',  u'フィ': 'fi',  u'ホゥ': 'hu',  u'フェ': 'fe',  u'フォ': 'fo',

        # Not so much
        u'シィ': 'sy',
        u'ミィ': 'my',
        u'ビィ': 'by',
        u'ピィ': 'py',
    },
    lengthened_vowels={},
    y_drop={'chi': 'ch', 'shi': 'sh', 'ji': 'j'},
)

romanizers['cs'] = Romanizer(parent=romanizers['en'],
    roomaji_kana={
        u'し': u'ši', u'ち': u'či', u'つ': u'cu',
        u'や': u'ja', u'ゆ': u'ju', u'よ': u'jo',
        u'じ': u'dži', u'ぢ': u'dži',
        u'シ': u'ši', u'チ': u'či', u'ツ': u'cu',
        u'ヤ': u'ja', u'ユ': u'ju', u'ヨ': 'jo',
        u'ジ': u'dži', u'ヂ': u'dži',
    },
    roomaji_youon={
        u'ゃ': 'ja', u'ゅ': 'ju', u'ょ': 'jo',
        u'ャ': 'ja', u'ュ': 'ju', u'ョ': 'jo',
    },
    roomaji_small_kana_combos={
        u'チェ': u'če', u'シェ': u'še', u'ジェ': u'dže',
        u'テェ': u'tje', u'デェ': u'dje',
        u'シィ': u'sí', u'ミィ': u'mí', u'ビィ': u'bí', u'ピィ': u'pí',
    },
    lengthened_vowels={'a': u'á', 'e': u'é', 'i': u'í', 'o': u'ó', 'u': u'ú'},
    y_drop={u'či': u'č', u'ši': u'š', u'dži': u'dž', u'ni': u'ňj'},
)

def romanize(string, lang='en'):
    """Convert a string of kana to roomaji."""

    # Get the correct romanizer; fall back to English
    romanizer = romanizers.get(lang, 'en')

    # Romanize away!
    return romanizer.romanize(string)
