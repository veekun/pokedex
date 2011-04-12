# Encoding: UTF-8
"""Rewrite Markdown strings to use identifiers instead of names

This is an unmaintained one-shot script, only included in the repo for reference.

"""

from functools import partial
import sys
import re

from sqlalchemy.orm.exc import MultipleResultsFound
from sqlalchemy.sql.expression import func

from pokedex.db import connect, tables

sanity_re = re.compile(ur"^[-A-Za-z0-9 é\[\]{}.%':;,×/()\"|–`—!*♂♀\\]$")

# RE that matches anything that might look like a link
fuzzy_link_re = re.compile(r"""
    \[
        [^]]+
    \]
    \{
        [^}]+
    \}""", re.VERBOSE)

# Very specific RE that matches links that appear in our Markdown strings
strict_link_re = re.compile(r"""
            \[
                (?P<label>
                    [-A-Za-z 0-9'.]{,30}
                )
            \]
            \{
                (?P<category>
                    [a-z]{,20}
                )
                (
                    :
                    (?P<target>
                        [A-Za-z 0-9]{,20}
                    )
                )?
            \}
        """, re.VERBOSE)

english_id = 9

def is_md_col(column):
    return column.info.get('format') == 'markdown'

manual_replacements = {
    (
        u'Used in battle\n:   Attempts to [catch]{mechanic} a wild Pok\xe9mon, using a catch rate of 1.5\xd7.\n\nThis item can only be used in the [Great Marsh]{location} or [Safari Zone]{location}.',
        u'[Safari Zone]{location}',
    ): 'in a Safari Zone',
    (
        u'Used outside of battle\n:   Transports the trainer to the last-entered dungeon entrance.  Cannot be used outside, in buildings, or in [Distortion World]{location}, [Hall of Origin]{location}, [Spear Pillar]{location}, or [Turnback Cave]{location}.',
        u'[Hall of Origin]{location}',
    ): '[Hall of Origin]{location:hall-of-origin-1}',
    (
        u'Give to the [Wingull]{pokemon} on [Route 13]{location}, along with [Gram 2]{item} and [Gram 3]{item}, to receive [TM89]{item}.',
        u'[Route 13]{location}',
    ): u'[Route 13]{location:unova-route-13}',
    (
        u'Give to the [Wingull]{pokemon} on [Route 13]{location}, along with [Gram 1]{item} and [Gram 3]{item}, to receive [TM89]{item}.',
        u'[Route 13]{location}',
    ): u'[Route 13]{location:unova-route-13}',
    (
        u'Give to the [Wingull]{pokemon} on [Route 13]{location}, along with [Gram 1]{item} and [Gram 2]{item}, to receive [TM89]{item}.',
        u'[Route 13]{location}',
    ): u'[Route 13]{location:unova-route-13}',
    (
        u"Forms have different stats and movepools.  In Generation III, Deoxys's form depends on the game: Normal Forme in Ruby and Sapphire, Attack Forme in FireRed, Defense Forme in LeafGreen, and Speed Forme in Emerald.  In Generation IV, every form exists: form is preserved when transferring via [Pal Park]{location}, and meteorites in the southeast corner of [Veilstone City]{location} or at the west end of [Route 3]{location} can be used to switch between forms.",
        u'[Route 3]{location}',
    ): u'[Route 3]{location:kanto-route-13}',
}

def get_replacement(session, entire_text, matchobj):
    print "%-30s" % matchobj.group(0),
    label = matchobj.group('label')
    category = matchobj.group('category')
    target = matchobj.group('target') or label
    try:
        result = manual_replacements[entire_text, matchobj.group(0)]
    except KeyError:
        if category == 'mechanic':
            target = target.lower()
        else:
            query = None
            if category == 'item':
                table = tables.Item
            elif category == 'ability':
                table = tables.Ability
            elif category == 'move':
                table = tables.Move
            elif category == 'type':
                table = tables.Type
            elif category == 'pokemon':
                table = tables.Pokemon
                query = session.query(table).filter(tables.Pokemon.id < 10000)
            elif category == 'location':
                table = tables.Location
            else:
                print
                print repr(entire_text)
                print repr(matchobj.group(0))
                raise ValueError('Category %s not implemented' % category)
            if not query:
                query = session.query(table)
            query = query.join(table.names_local)
            query = query.filter(func.lower(table.names_table.name) == target.lower())
            try:
                thingy = query.one()
                target = thingy.identifier
            except:
                print
                print repr(entire_text)
                print repr(matchobj.group(0))
                raise
    result = "[%s]{%s:%s}" % (label, category, target)
    print result
    return result

def main(argv):
    session = connect()
    for cls in tables.mapped_classes:
        for translation_class in cls.translation_classes:
            columns = translation_class.__table__.c
            md_columns = [c for c in columns if c.info.get('format') == 'markdown']
            if not md_columns:
                continue
            for row in session.query(translation_class):
                if row.local_language_id != english_id:
                    continue
                for column in md_columns:
                    markdown = getattr(row, column.name)
                    if not markdown:
                        continue
                    text = unicode(markdown)
                    # Make sure everything that remotely looks like a link is one
                    links = fuzzy_link_re.findall(text)
                    if not links:
                        continue
                    for link in links:
                        assert strict_link_re.findall(link), [link]
                    # Do the replacement
                    replaced = strict_link_re.sub(
                            partial(get_replacement, session, text),
                            text,
                        )
                    setattr(row, column.name, replaced)

    if argv and argv[0] == '--commit':
        session.commit()
        print 'Committed'
    else:
        print 'Run with --commit to commit changes'

if __name__ == '__main__':
    main(sys.argv[1:])
