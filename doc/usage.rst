Using pokedex
=============

The pokédex is, first and foremost, a Python library. To get the most of it,
you'll need to learn `Python`_ and `SQLAlchemy`_.

Here is a small example of using pokedex:

.. testcode::

    from pokedex.db import connect, tables, util
    session = connect()
    pokemon = util.get(session, tables.PokemonSpecies, u'bulbasaur')
    print u'{0.name}, the {0.genus} Pokemon'.format(pokemon)

Running this will give you some Bulbasaur info:

.. testoutput::

    Bulbasaur, the Seed Pokemon

Connecting
----------

To get information out of the Pokédex, you will need to create a
:class:`Session <pokedex.db.multilang.MultilangSession>`. To do that, use
:func:`pokedex.db.connect`. For simple uses, you don't need to give it any
arguments: it uses the database that ``pokedex load`` fills up by default. If
you need to select another database, give its URI as the first argument.

The object :func:`~pokedex.db.connect` gives you is actually a
:class:`SQLAlchemy session <sqlalchemy.orm.session.Session>`, giving you the
full power of SQLAlchemy for working with the data. We'll cover some basics
here, but if you intend to do some serious work, do read SQLAlchemy's docs.

Pokédex tables
--------------

Data in the pokédex is organized in tables, defined in
:mod:`pokedex.db.tables`.
There is quite a few or them. To get you started, here are a few common ones:

* :class:`~pokedex.db.tables.PokemonSpecies`
* :class:`~pokedex.db.tables.Move`
* :class:`~pokedex.db.tables.Item`
* :class:`~pokedex.db.tables.Type`

Getting things
--------------

If you know what you want from the pokédex, you can use the
:func:`pokedex.db.util.get` function. It looks up a thing in a table, based on
its identifier, name, or ID, and returns it.

.. testcode::

    def print_pokemon(pokemon):
        print u'{0.name}, the {0.genus} Pokemon'.format(pokemon)

    print_pokemon(util.get(session, tables.PokemonSpecies, identifier=u'eevee'))
    print_pokemon(util.get(session, tables.PokemonSpecies, name=u'Ho-Oh'))
    print_pokemon(util.get(session, tables.PokemonSpecies, id=50))

    def print_item(item):
        print u'{0.name}: ${0.cost}'.format(item)

    print_item(util.get(session, tables.Item, identifier=u'great-ball'))
    print_item(util.get(session, tables.Item, name=u'Potion'))
    print_item(util.get(session, tables.Item, id=30))

.. testoutput::

    Eevee, the Evolution Pokemon
    Ho-Oh, the Rainbow Pokemon
    Diglett, the Mole Pokemon
    Great Ball: $600
    Potion: $300
    Fresh Water: $200

Querying
--------

So, how do you get data from the session? You use the session's
:meth:`~sqlalchemy.orm.session.Session.query` method, and give it a pokédex
Table as an argument. This will give you a :class:`SQLAlchemy query
<sqlalchemy.orm.query.Query>`.

Ordering
^^^^^^^^

As always with SQL, you should not rely on query results being in some
particular order – unless you have ordered the query first. This means that
you'll want to sort just about every query you will make.

For example, you can get a list of all pokémon species, sorted by their
:attr:`~pokedex.db.tables.PokemonSpecies.id`, like so:

.. testcode::

    for pokemon in session.query(tables.PokemonSpecies).order_by(tables.PokemonSpecies.id):
        print pokemon.name

.. testoutput::

    Bulbasaur
    Ivysaur
    Venusaur
    Charmander
    Charmeleon
    ...
    Xerneas
    Yveltal
    Zygarde

Or to order by :attr:`~pokedex.db.tables.PokemonSpecies.name`:

.. testcode::

    for pokemon in session.query(tables.PokemonSpecies).order_by(tables.PokemonSpecies.name):
        print pokemon.name

.. testoutput::

        Abomasnow
        ...
        Zygarde


Filtering
^^^^^^^^^

Another major operation on queries is filtering, using the query's
:meth:`~sqlalchemy.orm.query.Query.filter` or
:meth:`~sqlalchemy.orm.query.Query.filter_by` methods:

.. testcode::

    for move in session.query(tables.Move).filter(tables.Move.power > 200):
        print move.name

.. testoutput::

    Explosion

Joining
^^^^^^^

The final operation we'll cover here is joining other tables to the query,
using the query's :meth:`~sqlalchemy.orm.query.Query.join`.
You will usually want to join on a relationship, such as in the following
example:

.. testcode::

    query = session.query(tables.Move)
    query = query.join(tables.Move.type)
    query = query.filter(tables.Type.identifier == u'grass')
    query = query.filter(tables.Move.power >= 100)
    query = query.order_by(tables.Move.power)
    query = query.order_by(tables.Move.name)

    print 'The most powerful Grass-type moves:'
    for move in query:
        print u'{0.name} ({0.power})'.format(move)

.. testoutput::

    The most powerful Grass-type moves:
    Petal Dance (120)
    Power Whip (120)
    Seed Flare (120)
    Solar Beam (120)
    Wood Hammer (120)
    Leaf Storm (130)
    Frenzy Plant (150)

That concludes our brief tutorial.
If you need to do more, consult the `SQLAlchemy documentation`_.

API documentation
-----------------

.. autofunction:: pokedex.db.connect

    See :class:`sqlalchemy.orm.session.Session` for more documentation on the
    returned object.

.. autofunction:: pokedex.db.util.get


.. _Python: http://www.python.org
.. _SQLAlchemy: http://www.sqlalchemy.org
.. _`SQLAlchemy documentation`: http://www.sqlalchemy.org/docs/orm/tutorial.html
