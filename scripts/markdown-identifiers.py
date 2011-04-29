# Encoding: UTF-8
"""Rewrite markdown links from [Label]{category:thing} to just {category:thing}

There was a version of this script that rewrote stuff from an even earlier
format. Git log should find it without problems.

This is an unmaintained one-shot script, only included in the repo for
reference.

"""

from functools import partial
import sys
import re

from sqlalchemy.orm.exc import MultipleResultsFound
from sqlalchemy.sql.expression import func

from pokedex.db import connect, tables, util

sanity_re = re.compile(ur"^[-A-Za-z0-9 é\[\]{}.%':;,×/()\"|–`—!*♂♀\\]$")

# RE that matches anything that might look like a link
fuzzy_link_re = re.compile(r"""
    \[
        [^]]+
    \]?
    \{
        [^}]+
    \}""", re.VERBOSE)

# Very specific RE that matches links that appear in source Markdown strings
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
            :
                (?P<target>
                    [-a-z 0-9]{,40}
                )
            \}
        """, re.VERBOSE)

# Format of the resulting links
result_link_re = re.compile(r"""
        ^
            \[
                (?P<label>
                    [^]]*
                )
            \]
            \{
                (?P<category>
                    [a-z]+
                )
            :
                (?P<target>
                    [-a-z0-9]+
                )
            \}
        $
        """, re.VERBOSE)

english_id = 9

manual_replacements = {
        '[Pewter Museum of Science]{location:pewter-city}':
                'the Museum of Science in {location:pewter-city}',
        '[Oreburgh Mining Museum]{location:mining-museum}':
                '{location:mining-museum} in {location:oreburgh-city}',
    }

def is_md_col(column):
    return column.info.get('format') == 'markdown'

def get_replacement(session, entire_text, context, matchobj):
    label = matchobj.group('label')
    category = matchobj.group('category')
    target = matchobj.group('target') or label
    try:
        result = manual_replacements[matchobj.group(0)]
    except KeyError:
        if category == 'mechanic':
            target = target.lower()
            target = target.replace(' ', '-')
            wanted_label = ''
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
            elif category == 'location':
                table = tables.Location
            else:
                print
                print repr(entire_text)
                print repr(matchobj.group(0))
                raise ValueError('Category %s not implemented' % category)
            try:
                thingy = util.get(session, table, target)
                wanted_label = thingy.name
            except:
                print
                print repr(entire_text)
                print repr(matchobj.group(0))
                raise
        if wanted_label.lower() == label.lower():
            result = "[]{%s:%s}" % (category, target)
        else:
            result = "[%s]{%s:%s}" % (label, category, target)
            if wanted_label:
                print
                print context
                print "%-40s" % matchobj.group(0),
                print '%s != %s' % (label, wanted_label)
        assert result_link_re.match(result), result
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
                        assert strict_link_re.findall(link), (strict_link_re.findall(link), [link])
                    # Do the replacement
                    context = '%s %s %s' % (translation_class.__name__, row.foreign_id, column.name)
                    replaced = strict_link_re.sub(
                            partial(get_replacement, session, text, context),
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
