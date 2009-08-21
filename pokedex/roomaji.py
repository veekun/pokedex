# encoding: utf8
"""Provides `romanize()` for romanizing simple Japanese text."""

_roomaji_kana = {
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
}

_roomaji_youon = {
    u'ャ': 'ya',                    u'ュ': 'yu',                    u'ョ': 'yo',
    u'ゃ': 'ya',                    u'ゅ': 'yu',                    u'ょ': 'yo',
}

# XXX If romanize() ever handles hiragana, it will need to make sure that the
# preceding character was a katakana
# This does not include every small kana combination, but should include every
# one used in a Pokémon name.  An exhaustive list would be..  very long
_roomaji_small_kana = {
    u'ァ': 'a',     u'ィ': 'i',     u'ゥ': 'u',     u'ェ': 'e',     u'ォ': 'o',
}
_roomaji_small_kana_combos = {
                                                    u'チェ': 'che',
                                                    u'シェ': 'she',
    u'テァ': 'tha', u'ティ': 'ti',  u'テゥ': 'thu', u'テェ': 'tye', u'テォ': 'tho',
    u'デァ': 'dha', u'ディ': 'di',  u'デゥ': 'dhu', u'デェ': 'dye', u'デォ': 'dho',
    u'ファ': 'fa',  u'フィ': 'fi',  u'ホゥ': 'hu',  u'フェ': 'fe',  u'フォ': 'fo',
}

def romanize(string):
    """Converts a string of kana to roomaji."""

    vowels = ['a', 'e', 'i', 'o', 'u', 'y']

    characters = []
    last_kana = None  # Used for ー; っ or ッ; ん or ン
    last_char = None  # Used for small kana combos
    for char in string:
        # Full-width Latin
        if ord(char) >= 0xff11 and ord(char) <= 0xff5e:
            if last_kana == 'sokuon':
                raise ValueError("Sokuon cannot precede Latin characters.")

            char = chr(ord(char) - 0xff11 + 0x31)
            characters.append(char)

            last_kana = None

        # Small vowel kana
        elif char in _roomaji_small_kana:
            combo = last_char + char
            if combo in _roomaji_small_kana_combos:
                characters[-1] = _roomaji_small_kana_combos[combo]

            else:
                # If we don't know what it is...  act dumb and treat it as a
                # full-size vowel.  Better than bailing, and seems to occur a
                # lot, e.g. ピィ is "pii"
                characters.append(_roomaji_small_kana[char])

        # Youon
        elif char in _roomaji_youon:
            if last_kana[-1] != 'i' or last_kana == 'i':
                raise ValueError("Youon must follow an -i sound.")

            # Drop the -i and append the ya/yu/yo sound
            new_sound = _roomaji_youon[char]
            if last_kana in ['shi', 'ji']:
                # Strip the y-
                new_char = last_kana[:-1] + new_sound[1:]
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
            characters.append(last_kana[-1])

            last_kana = None

        # Regular ol' kana
        elif char in _roomaji_kana:
            kana = _roomaji_kana[char]

            if last_kana == 'sokuon':
                if kana[0] in vowels:
                    raise ValueError("Sokuon cannot precede a vowel.")

                characters.append(kana[0])
            elif last_kana == 'n' and kana[0] in vowels:
                characters.append("'")

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
