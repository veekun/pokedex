Installing the pokedex library
==============================

Quick startup with Ubuntu/Debian-like systems
---------------------------------------------

Run the following from an empty directory::

    $ sudo apt-get install git python python-pip python-sqlalchemy
    $ git clone git://github.com/veekun/pokedex.git
    $ pip install -E env -e pokedex
    $ source env/bin/activate
    (env)$ pokedex setup -v
    (env)$ pokedex lookup eevee

If it all goes smoothly, you can now use ``env/bin/pokedex``, the command-line
tool, and ``env/bin/python``, a Python interpreter configured to use the
pokedex library.

That is all you need. Feel free to skip the rest of this chapter if you're not
interested in the details.

Prerequisites
-------------

Linux
^^^^^

Ubuntu/Debian users should run the following::

    $ sudo apt-get install git python python-pip

With other Linuxes, install the packages for git, python (2.6 or 2.7,
*not* 3.x), and python-pip.

If you succeeded, skip the Detailed instructions.

Detailed instructions
^^^^^^^^^^^^^^^^^^^^^

You should know what a command line is and how to work with it.
The here we assume you're using Linux [#]_, if that's not the case, make
sure you have enough computer knowledge to translate the instructions to your
operating system.

Pokedex is distributed via Git_. So, get Git.

You will also need Python_ 2; the language pokedex is written in. Be sure to get
version **2.6** or **2.7**. Pokedex does not work with Python 3.x yet, and it
most likely won't work with 2.5 or earlier.

Next, get pip_, a tool to install Python packages. Experts can use another
tool, of course.

Make sure git and pip are on your path.

Optionally you can install SQLAlchemy_, `Python markdown`_, Whoosh_,
or construct_. If you don't, pip will atuomatically download and install a copy
for you, but some are pretty big so you might want to install it system-wide.
(Unfortunately, many distros have outdated versions of these libraries, so pip
will install pokedex's own copy anyway.)

Getting and installing pokedex
------------------------------

Run the following from an empty directory::

    $ git clone git://github.com/veekun/pokedex.git
    $ pip install -E env -e pokedex

This will give you two directories: pokedex (containing the source code and
data), and env (a virtualenv_).

In env/bin, there are three interesting files:

* pokedex: The pokedex program
* python: A copy of Python that knows about pokedex and its prerequisites.
* activate: Typing ``source env/bin/activate`` in a shell will put
  pokedex and our bin/python on the $PATH, and generally set things up to work
  with them. Your prompt will change to let you know of this. You can end such
  a session by typing ``deactivate``.

This documentation will assume that you've activated the virtualenv, so
``pokedex`` means ``env/bin/pokedex``.

Advanced
^^^^^^^^

You can of course install into an existing virtualenv, by either using its pip
and leaving out the ``-E env``, or running the setup script directly::

    (anotherenv)$ cd pokedex
    (anotherenv)pokedex$ python setup.py develop

It is also possible to install pokedex system-wide. There are problems with
that. Don't do it. The only time you need ``sudo`` is for getting the
prerequisites.

Loading the database
--------------------

Before you can do anything useful with pokedex, you need to load the database::

    $ pokedex setup -v

This will load the data into a default SQLite database and create a default
Whoosh index.

Advanced
^^^^^^^^

If you want to use another database, make sure you have the corresponding
`SQLAlchemy engine`_ for it and either use the ``-e`` switch, (e.g.
``-e postgresql://@/pokedex``), or set the ``POKEDEX_DB_ENGINE`` environment
variable.

To use another lookup index directory, specify it with ``-i`` or the
``POKEDEX_INDEX_DIR`` variable.

Make sure you always use the same options whenever you use pokedex.

If you're confused about what pokedex thinks its settings are, check
``pokedex status``.

See ``pokedex help`` for even more options.

All done
--------

To verify that all went smoothly, check that the pokedex tool finds your
favorite pokémon::

    $ pokedex lookup eevee

Yes, that was a bit anti-climatic. The command-line tool doesn't do much,
currently.






.. _Git: http://git-scm.com/
.. _Python: http://www.python.org/
.. _pip: http://pypi.python.org/pypi/pip
.. _SQLAlchemy: www.sqlalchemy.org/
.. _`Python markdown`: http://www.freewisdom.org/projects/python-markdown/
.. _Whoosh: http://whoosh.ca/
.. _construct: pypi.python.org/pypi/construct
.. _virtualenv: http://www.virtualenv.org/en/latest/
.. _`SQLAlchemy engine`: http://www.sqlalchemy.org/docs/core/engines.html

.. rubric:: Footnotes
.. [#] If you write instructions for another OS, well be happy to include them
    here. The reason your OS is not listed here is because the author doesn't
    use it, so naturally he can't write instructions for it.
