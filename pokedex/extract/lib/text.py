def merge_japanese_texts(kanji, kana, html=False):
    """Combine a (presuambly equivalent) pair of kanji and kana strings into a
    single string of kanji with furigana.

    If `html` is truthy, the return value will contain HTML ruby tags;
    otherwise it will use the Unicode "interlinear annotation" characters.

    This relies on the Needleman–Wunsch algorithm for sequence alignment:
    https://en.wikipedia.org/wiki/Needleman%E2%80%93Wunsch_algorithm
    """
    # TODO maybe this is faster, but then -1 doesn't work
    #table = [
    #    [None for _ in range(len(kana))]
    #    for _ in range(len(kanji))
    #]
    table = {}
    # continue left, continue up, are the characters equivalent, score for this
    # cell
    table[-1, -1] = False, False, True, 0

    isjunk = {}
    for ch in kanji + kana:
        isjunk[ch] = ch.isspace() or ch in '。␤'

    # initialize, TODO, something about scoring compared to a gap
    for i, ch in enumerate(kanji):
        table[i, -1] = True, False, False, -1 - i
    for i, ch in enumerate(kana):
        table[-1, i] = False, True, False, -1 - i
    for a, ach in enumerate(kanji):
        for b, bch in enumerate(kana):
            options = []
            # Continue diagonally means two characters together, either a match
            # or a mismatch
            if ach == bch or (isjunk[ach] and isjunk[bch]):
                equiv = True
                score = 1
            else:
                equiv = False
                score = -1
            options.append((True, True, equiv, table[a - 1, b - 1][2] + score))

            # Continue from or side means an indel...  -1
            if isjunk[ach]:
                score = 0
            else:
                score = -1
            options.append((True, False, equiv, table[a - 1, b][2] + score))
            if isjunk[bch]:
                score = 0
            else:
                score = -1
            options.append((False, True, equiv, table[a, b - 1][2] + score))

            # Strictly speaking, in the case of a tie, all of the "best"
            # choices are supposed to be preserved.  But we should never have a
            # tie, and we have an arbitrary choice of which to use in the end
            # anyway, so screw it.
            table[a, b] = max(options, key=lambda opt: opt[2])

    if html:
        ruby_format = "<ruby><rb>{}</rb><rt>{}</rt></ruby>"
    else:
        ruby_format = "\ufff9{}\ufffa{}\ufffb"

    def add_mismatches(mismatch_a, mismatch_b, final):
        # Need to pop out any extra junk characters at the beginning or end --
        # but only the kanji ones stay, since kanji is "canonical"
        while mismatch_a and isjunk[mismatch_a[0]]:
            final.append(mismatch_a.pop(0))
        while mismatch_b and isjunk[mismatch_b[0]]:
            mismatch_b.pop(0)
        endjunk = []
        while mismatch_a and isjunk[mismatch_a[-1]]:
            endjunk.append(mismatch_a.pop())
        while mismatch_b and isjunk[mismatch_b[-1]]:
            mismatch_b.pop()
        final.append(ruby_format.format(
            ''.join(reversed(mismatch_a)),
            ''.join(reversed(mismatch_b)),
        ))
        final.extend(endjunk)
        del mismatch_a[:]
        del mismatch_b[:]

    final = []
    mismatch_a = []
    mismatch_b = []
    a = len(kanji) - 1
    b = len(kana) - 1
    while True:
        walk_left, walk_up, equiv, score = table[a, b]
        if walk_left and walk_up:
            if equiv:
                if mismatch_a or mismatch_b:
                    add_mismatches(mismatch_a, mismatch_b, final)
                final.append(kanji[a])
            else:
                mismatch_a.append(kanji[a])
                mismatch_b.append(kana[b])
            a -= 1
            b -= 1
        elif walk_left:
            mismatch_a.append(kanji[a])
            a -= 1
        elif walk_up:
            mismatch_b.append(kana[b])
            b -= 1
        else:
            break

    if mismatch_a or mismatch_b:
        add_mismatches(mismatch_a, mismatch_b, final)

    return ''.join(reversed(final))
