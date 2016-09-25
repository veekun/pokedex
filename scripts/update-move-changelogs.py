from __future__ import print_function

import csv
import sys

fields = ['type_id', 'power', 'pp', 'accuracy', 'priority', 'target_id', 'effect_id', 'effect_chance']

def main():
    old = csv.DictReader(open(sys.argv[1], 'rb'))
    new = csv.DictReader(open(sys.argv[2], 'rb'))
    version_group_id = int(sys.argv[3])

    moves = {}

    for row in new:
        moves[row['id']] = row

    for row in old:
        if row['id'] not in moves:
            print("move %d disappeared!", file=sys.stderr)
            continue

        oldmove = row
        newmove = moves[row['id']]

        if int(oldmove['id']) > 10000:
            print("skipping shadow moves", file=sys.stderr)
            continue

        changed_fields = []
        for field in fields:
            if oldmove[field] == newmove[field]:
                continue
            if field == 'power' and oldmove['power'] in "01":
                if newmove['power'] == "":
                    # expected
                    # we used to store variable-power moves as 0 or 1,
                    # now we store NULL
                    continue
                else:
                    print("%s: %s changed from %s to %s" % (oldmove['identifier'], field, oldmove[field], newmove[field]), file=sys.stderr)
            if oldmove[field] == '':
                print("%s: %s changed from NULL to %s" % (oldmove['identifier'], field, newmove[field]), file=sys.stderr)
                continue
            #print("%s: %s changed from %s to %s" % (oldmove['identifier'], field, oldmove[field], sql_list([newmove[field]])))
            changed_fields.append(field)

        if changed_fields:
            print("INSERT INTO move_changelog (move_id, changed_in_version_group_id, %s) VALUES (%s, %s, %s); -- %s (%s)" %
                (sql_list(changed_fields), row['id'], version_group_id,
                 sql_list(map(oldmove.__getitem__, changed_fields)),
                 oldmove['identifier'],
                 sql_list(map(newmove.__getitem__, changed_fields))))

def sql_list(values):
    return ", ".join(x if x != "" else "NULL" for x in values)

main()
