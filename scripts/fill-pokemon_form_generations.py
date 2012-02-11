# Encoding: UTF-8
"""Fill the pokemon_form_generations table

This is an unmaintained one-shot script, only included in the repo for reference.


"""


from sqlalchemy.sql import exists, func
from sqlalchemy.orm import lazyload, eagerload, eagerload_all
from sqlalchemy import and_, or_, not_

from pokedex.db import connect, tables, load

session = connect()

session.query(tables.PokemonFormGeneration).delete()

generations = list(session.query(tables.Generation).order_by(
        tables.Generation.id))

q = session.query(tables.PokemonForm)
q = q.options(eagerload_all('pokemon', 'species'))
q = q.order_by(tables.PokemonForm.order)

form_orders = dict(
    unown=list('abcdefghijklmnopqrstuvwxyz') + ['exclamation', 'question'],

    deoxys=['normal', 'attack', 'defense', 'speed'],

    burmy=['plant', 'sandy', 'trash'],
    wormadam=['plant', 'sandy', 'trash'],

    shellos=['west', 'east'],
    gastrodon=['west', 'east'],

    rotom=[None, 'heat', 'wash', 'frost', 'fan', 'mow'],

    giratina=['altered', 'origin'],

    shaymin=['land', 'sky'],

    castform=[None, 'sunny', 'rainy', 'snowy'],
    basculin=['red-striped', 'blue-striped'],
    darmanitan=['standard', 'zen'],
    deerling=['spring', 'summer', 'autumn', 'winter'],
    sawsbuck=['spring', 'summer', 'autumn', 'winter'],
    meloetta=['aria', 'pirouette'],
    genesect=[None, 'douse', 'shock', 'burn', 'chill'],
    cherrim=['overcast', 'sunshine'],
)

arceus = {4: '''normal fighting flying poison ground rock bug ghost steel
    unknown fire water grass electric psychic ice dragon dark'''.split()}
arceus[5] = list(arceus[4])
arceus[5].remove('unknown')

for form in q:
    species_ident = form.species.identifier
    form_ident = form.form_identifier
    is_default = form.is_default and form.pokemon.is_default
    print form_ident, species_ident
    for gen in generations:
        game_index = None
        if gen.id >= form.version_group.generation_id:
            if gen.id < 4:
                # forms not really implemented yet
                if species_ident == 'pichu':
                    if is_default:
                        game_index = 0
                    else:
                        continue
                elif species_ident in ('unown', 'castform'):
                    lst = form_orders[species_ident]
                    game_index = lst.index(form_ident)
                elif species_ident == 'deoxys':
                    game_index = 0
                elif is_default:
                    game_index = 0
            else:
                try:
                    lst = form_orders[species_ident]
                except KeyError:
                    if species_ident == 'pichu' and form_ident == 'spiky-eared':
                        if gen.id == 4:
                            game_index = 1
                        else:
                            continue
                    elif species_ident == 'cherrim':
                        if gen.id < 5:
                            if is_default:
                                game_index = 0
                            else:
                                continue
                        else:
                            lst = ['overcast', 'sunshine']
                            game_index = lst.index(form_ident)
                    elif species_ident == 'castform':
                        if gen.id < 5:
                            if is_default:
                                game_index = 0
                            else:
                                continue
                        else:
                            lst = [None, 'sunny', 'rainy', 'snowy']
                            game_index = lst.index(form_ident)
                    elif species_ident == 'arceus':
                        if gen.id >= 5 and form_ident == 'unknown':
                            continue
                        else:
                            lst = arceus[gen.id]
                            game_index = lst.index(form_ident)
                    elif form.is_default and form.pokemon.is_default:
                        game_index = 0
                    else:
                        raise AssertionError()
                else:
                    game_index = lst.index(form_ident)
            obj = tables.PokemonFormGeneration(form=form, generation=gen,
                    game_index=game_index)
            session.add(obj)

q = session.query(tables.PokemonFormGeneration)
for species in session.query(tables.PokemonSpecies).options(
        eagerload_all('forms', 'pokemon_form_generations')):
    if len(species.forms) > 1:
        print species.name
    for gen in generations:
        if len(species.forms) == 1:
            pfg = q.get((species.forms[0].id, gen.id))
            assert pfg is None or pfg.game_index == 0
            continue
        forms = [(q.get((f.id, gen.id)), f) for f in species.forms if q.get((f.id, gen.id))]
        forms = [(pfg.game_index, f) for pfg, f in forms if pfg]
        if forms:
            forms.sort()
            pl = ["%s=%s" % (gi, f.form_identifier) for gi, f in forms]
            print '   ', gen.id, ' '.join(pl)

load.dump(session, tables=['pokemon_form_generations'])
print "Dumped to CSV, rolling back transaction"
session.rollback()
