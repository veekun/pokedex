/*
Pokémon species order: National dex order, except that families are grouped
together around whichever member has the lowest National ID, and then ordered
by evolutionary stage.

pokemon_species.id happens to match National ID, and it so happens that the
only time Pokémon are out of evolutionary order if you sort by Nat'l ID is when
they're pre-evos added to an already-existing family, which are always babies.
So sort babies first, and then the rest of the family in Nat'l order.  (Evo
chain IDs happen to already be in the right order, too.)
*/

UPDATE pokemon_species ps
SET "order" = ps_order."order"
FROM (
    SELECT ps_sub.id, ROW_NUMBER() OVER (ORDER BY ps_sub.evolution_chain_id,
        ps_sub.is_baby DESC, ps_sub.id) "order"
    FROM pokemon_species ps_sub
) ps_order
WHERE ps.id = ps_order.id;


/*
Pokémon form order: Same as species order, with a species' forms ordered as
specified by pokemon_forms.form_order.  Since form_order can have duplicate
orders to indicate that they should fall back on ordering by name, so can
pokemon_forms.order.
*/

UPDATE pokemon_forms pf
SET "order" = pf_order."order"
FROM (
    SELECT pf_sub.id, DENSE_RANK() OVER (ORDER BY ps."order",
        pf_sub.form_order) "order"
    FROM pokemon_forms pf_sub
    JOIN pokemon p ON pf_sub.pokemon_id = p.id
    JOIN pokemon_species ps ON p.species_id = ps.id
) pf_order
WHERE pf.id = pf_order.id;


/*
[Functional] Pokémon order: Same as form order, except not all forms have their
own functional Pokémon, so we need to close the gaps.

These aren't supposed to have duplicate orders, but this query will give them
duplicate orders where applicable anyway so that the unique constraint can
complain if needed instead of the query silently ordering things arbitrarily.
*/

UPDATE pokemon p
SET "order" = p_order."order"
FROM (
    SELECT p_sub.id, DENSE_RANK() OVER (ORDER BY pf."order") "order"
    FROM pokemon p_sub
    JOIN pokemon_forms pf ON p_sub.id = pf.pokemon_id AND pf.is_default = True
) p_order
WHERE p.id = p_order.id;
