# Encoding: UTF-8

import csv

from pokedex.db import translations, tables

fake_version_names = (
    'version_id,local_language_id,name',
    '1,0,name1',
    '2,0,name2',
    '3,0,name3',
    '3,1,othername3',
)

fake_translation_csv = (
    'language_id,table,id,column,source_crc,string',
    '0,Version,1,name,,name1',
    '0,Version,2,name,,name2',
    '0,Version,3,name,,name3',
    '1,Version,3,name,,othername3',
)

def test_yield_source_csv_messages():
    check_version_message_stream(translations.yield_source_csv_messages(
        tables.Version.names_table,
        tables.Version,
        csv.reader(iter(fake_version_names)),
    ))

def test_yield_guessed_csv_messages():
    check_version_message_stream(translations.yield_guessed_csv_messages(
        iter(fake_translation_csv),
    ))

def test_yield_translation_csv_messages():
    check_version_message_stream(translations.yield_translation_csv_messages(
        iter(fake_translation_csv),
    ))

def check_version_message_stream(messages):
    messages = list(messages)
    assert messages[0].string == 'name1'
    assert messages[1].string == 'name2'
    assert messages[2].string == 'name3'
    assert messages[3].string == 'othername3'
    for message in messages[:3]:
        assert message.language_id == 0
    assert messages[3].language_id == 1
    for id, message in zip((1, 2, 3, 3), messages):
        assert message.merge_key == ('Version', id, 'name'), message.key

def get_messages(*rows):
    return list(translations.yield_translation_csv_messages(iter(rows), True))

def test_merge_translations():
    source = get_messages(
        '0,Table,1,col,,none',
        '0,Table,2,col,,new',
        '0,Table,3,col,,existing',
        '0,Table,4,col,,both',
        '0,Table,5,col,,(gap)',
        '0,Table,6,col,,new-bad',
        '0,Table,7,col,,existing-bad',
        '0,Table,8,col,,both-bad',
        '0,Table,9,col,,new-bad-ex-good',
        '0,Table,10,col,,new-good-ex-bad',
        '0,Table,11,col,,(gap)',
        '0,Table,12,col,,"Numbers: 1, 2, and 003"',
        '0,Table,13,col,,"Numbers: 3, 2, and 001"',
    )
    new = get_messages(
        '0,Table,2,col,%s,new' % translations.crc('new'),
        '0,Table,4,col,%s,new' % translations.crc('both'),
        '0,Table,6,col,%s,new' % translations.crc('----'),
        '0,Table,8,col,%s,new' % translations.crc('----'),
        '0,Table,9,col,%s,new' % translations.crc('----'),
        '0,Table,10,col,%s,new' % translations.crc('new-good-ex-bad'),
        '0,Table,12,col,%s,{num} {num} {num}' % translations.crc('Numbers: {num}, {num}, and {num}'),
        '0,Table,13,col,%s,{num} {num} {num}' % translations.crc('----'),
        '0,Table,100,col,%s,unused' % translations.crc('----'),
    )
    new[-3].number_replacement = True
    new[-3].source = 'Numbers: 1, 2, and 003'
    new[-2].number_replacement = True
    new[-2].source = '----'
    existing = get_messages(
        '0,Table,3,col,%s,existing' % translations.crc('existing'),
        '0,Table,4,col,%s,existing' % translations.crc('both'),
        '0,Table,7,col,%s,existing' % translations.crc('----'),
        '0,Table,8,col,%s,existing' % translations.crc('----'),
        '0,Table,9,col,%s,existing' % translations.crc('new-bad-ex-good'),
        '0,Table,10,col,%s,existing' % translations.crc('----'),
        '0,Table,100,col,%s,unused' % translations.crc('----'),
    )
    expected_list = (
        ('none', None, None),
        ('new', True, 'new'),
        ('existing', True, 'existing'),
        ('both', True, 'new'),
        ('(gap)', None, None),
        ('new-bad', False, 'new'),
        ('existing-bad', False, 'existing'),
        ('both-bad', False, 'new'),
        ('new-bad-ex-good', True, 'existing'),
        ('new-good-ex-bad', True, 'new'),
        ('(gap)', None, None),
        ('Numbers: 1, 2, and 003', True, '1 2 003'),
        ('Numbers: 3, 2, and 001', False, '3 2 001'),
    )
    unused = []
    result_stream = list(translations.merge_translations(source, new, [], existing, unused=unused.append))
    for result, expected in zip(result_stream, expected_list):
        res_src, res_crc, res_str, res_match = result
        exp_src, exp_match, exp_str = expected
        print result, expected
        assert res_src.string == exp_src
        assert res_str == exp_str, (res_str, exp_str)
        if exp_match is None:
            assert res_crc is None
        elif exp_match is True:
            assert res_crc == translations.crc(res_src.string)
        elif exp_match is False:
            assert res_crc == translations.crc('----')
        assert res_match == exp_match
    print 'unused:', unused
    for message in unused:
        assert message.string == 'unused'
        assert message.id == 100

def test_merge():
    check_merge((0, 1, 2, 3))
    check_merge((0, 1), (2, 3))
    check_merge((2, 3), (0, 1))
    check_merge((0, 2), (1, 3))
    check_merge((0, 3), (1, 2))
    check_merge((0, 1), (2, 3), (2, 3))

def check_merge(*sequences):
    merged = list(translations.Merge(*sequences))
    concatenated = [val for seq in sequences for val in seq]
    assert merged == sorted(concatenated)

def test_merge_dynamic_add():
    merge = translations.Merge((1, 2, 3))
    def adder():
        for val in (1, 2, 3):
            yield val
            merge.add_iterator([4])
    merge.add_iterator(adder())
    assert tuple(merge) == (1, 1, 2, 2, 3, 3, 4, 4, 4)

def test_merge_adjacent():
    messages = get_messages(
            '0,Table,1,col,,strA',
            '0,Table,2,col,,strB',
            '0,Table,2,col,,strC',
            '0,Table,2,col,,strB',
            '0,Table,2,col,,strD',
            '0,Table,3,col,,strE',
        )
    result = [m.string for m in translations.merge_adjacent(messages)]
    expected = ['strA', 'strB\n\nstrC\n\nstrD', 'strE']
    assert result == expected

def test_leftjoin():
    check_leftjoin([], [], [], [])
    check_leftjoin([], [1], [], [1])
    check_leftjoin([], [1, 2], [], [1, 2])
    check_leftjoin([1], [], [(1, None)], [])
    check_leftjoin([1], [1], [(1, 1)], [])
    check_leftjoin([1], [2], [(1, None)], [2])
    check_leftjoin([1, 2], [1], [(1, 1), (2, None)], [])
    check_leftjoin([1, 2], [1, 2], [(1, 1), (2, 2)], [])
    check_leftjoin([1], [1, 2], [(1, 1)], [2])
    check_leftjoin([1, 2], [1, 3], [(1, 1), (2, None)], [3])
    check_leftjoin([1, 2, 3], [1, 3], [(1, 1), (2, None), (3, 3)], [])
    check_leftjoin([1, 2, 2, 3], [1, 3], [(1, 1), (2, None), (2, None), (3, 3)], [])
    check_leftjoin([1, 2, 2, 3], [2, 2, 2], [(1, None), (2, 2), (2, 2), (3, None)], [2])

def check_leftjoin(seqa, seqb, expected, expected_unused):
    unused = []
    result = list(translations.leftjoin(seqa, seqb, unused=unused.append))
    assert result == list(expected)
    assert unused == list(expected_unused)
