"""Cards added in the verified v0.111.0 reference."""
from sts2_env.cards.registry import register_effect
from sts2_env.core.enums import CardId, CardType, PowerId


def make_abundance(upgraded=False):
    from sts2_env.cards.factory import create_reference_card
    return create_reference_card(CardId.ABUNDANCE, upgraded, allow_generation=True)


def make_sidestep(upgraded=False):
    from sts2_env.cards.factory import create_reference_card
    return create_reference_card(CardId.SIDESTEP, upgraded, allow_generation=True)


def make_dowsing(upgraded=False):
    from sts2_env.cards.factory import create_reference_card
    return create_reference_card(CardId.DOWSING, False, allow_generation=True)


@register_effect(CardId.SIDESTEP)
def sidestep(card, combat, target):
    owner = card.owner or combat.primary_player
    combat.apply_power_to(owner, PowerId.ENERGY_NEXT_TURN, card.effect_vars["energy"])


@register_effect(CardId.ABUNDANCE)
def abundance(card, combat, target):
    from sts2_env.cards.factory import create_distinct_character_cards
    owner = card.owner or combat.primary_player
    state = combat.combat_player_state_for(owner)
    choices = create_distinct_character_cards(
        state.character_id, combat.combat_card_generation_rng, 3,
        card_type=CardType.POWER, generation_context="combat",
        is_multiplayer=combat.is_multiplayer,
    )
    for candidate in choices:
        combat.upgrade_card(candidate)
    if not choices:
        return
    def resolve(selected):
        if selected is not None:
            selected.set_temporary_cost_for_turn(0)
            combat.add_generated_card_to_creature_hand(owner, selected)
    combat.request_card_choice(prompt="Choose an upgraded Power", cards=choices,
        source_pile="generated", resolver=resolve, allow_skip=True)


def advance_dowsing(player):
    """Called once per successful unknown map-node entry, before room effects."""
    for card in list(player.deck):
        if card.card_id is CardId.DOWSING:
            remaining = card.effect_vars.get("rooms", 5) - 1
            card.effect_vars["rooms"] = remaining
            if remaining <= 0:
                player._transform_selected_cards_to([card], CardId.ABUNDANCE)


def make_blade_symphony(upgraded=False):
    from sts2_env.cards.factory import create_reference_card
    return create_reference_card(CardId.BLADE_SYMPHONY, upgraded, allow_generation=True)


def make_blaze(upgraded=False):
    from sts2_env.cards.factory import create_reference_card
    return create_reference_card(CardId.BLAZE, upgraded, allow_generation=True)


def make_cacophony(upgraded=False):
    from sts2_env.cards.factory import create_reference_card
    return create_reference_card(CardId.CACOPHONY, upgraded, allow_generation=True)


def make_concoct(upgraded=False):
    from sts2_env.cards.factory import create_reference_card
    return create_reference_card(CardId.CONCOCT, upgraded, allow_generation=True)


def make_constellation(upgraded=False):
    from sts2_env.cards.factory import create_reference_card
    return create_reference_card(CardId.CONSTELLATION, upgraded, allow_generation=True)


def make_fade(upgraded=False):
    from sts2_env.cards.factory import create_reference_card
    return create_reference_card(CardId.FADE, upgraded, allow_generation=True)


def make_hibernate(upgraded=False):
    from sts2_env.cards.factory import create_reference_card
    return create_reference_card(CardId.HIBERNATE, upgraded, allow_generation=True)


def make_imitation_learning(upgraded=False):
    from sts2_env.cards.factory import create_reference_card
    return create_reference_card(CardId.IMITATION_LEARNING, upgraded, allow_generation=True)


def make_midnight(upgraded=False):
    from sts2_env.cards.factory import create_reference_card
    return create_reference_card(CardId.MIDNIGHT, upgraded, allow_generation=True)


def make_one_for_all(upgraded=False):
    from sts2_env.cards.factory import create_reference_card
    return create_reference_card(CardId.ONE_FOR_ALL, upgraded, allow_generation=True)


def make_outrage(upgraded=False):
    from sts2_env.cards.factory import create_reference_card
    return create_reference_card(CardId.OUTRAGE, upgraded, allow_generation=True)


def make_plot(upgraded=False):
    from sts2_env.cards.factory import create_reference_card
    return create_reference_card(CardId.PLOT, upgraded, allow_generation=True)


def make_soulbound(upgraded=False):
    from sts2_env.cards.factory import create_reference_card
    return create_reference_card(CardId.SOULBOUND, upgraded, allow_generation=True)


def make_the_ball(upgraded=False):
    from sts2_env.cards.factory import create_reference_card
    return create_reference_card(CardId.THE_BALL, upgraded, allow_generation=True)


def make_tutor(upgraded=False):
    from sts2_env.cards.factory import create_reference_card
    return create_reference_card(CardId.TUTOR, upgraded, allow_generation=True)


def make_underworld(upgraded=False):
    from sts2_env.cards.factory import create_reference_card
    return create_reference_card(CardId.UNDERWORLD, upgraded, allow_generation=True)


from sts2_env.core.enums import ValueProp
from sts2_env.cards.base import _get_next_id, increase_base_damage
from sts2_env.cards.registry import register_after_card_exhausted_hook, register_after_card_entered_combat_hook, register_self_mutating_damage


def _owner(card, combat):
    return card.owner or combat.primary_player


def _attack(card, combat, target):
    from sts2_env.core.damage import calculate_damage, apply_damage
    owner = _owner(card, combat)
    if target is not None and owner.is_alive:
        damage = calculate_damage(card.base_damage, owner, target, ValueProp.MOVE, combat)
        apply_damage(target, damage, ValueProp.MOVE, combat, owner)


@register_effect(CardId.BLADE_SYMPHONY)
def blade_symphony(card, combat, target):
    from sts2_env.cards.factory import create_card
    for ally in combat.get_player_allies_of(_owner(card, combat)):
        for _ in range(card.effect_vars["cards"]):
            combat.add_generated_card_to_creature_hand(ally, create_card(CardId.SHIV))


@register_effect(CardId.BLAZE)
def blaze(card, combat, target):
    combat.apply_power_to(target, PowerId.STRENGTH, card.effect_vars["strength"], applier=_owner(card, combat))


@register_effect(CardId.CACOPHONY)
def cacophony(card, combat, target):
    combat.apply_power_to(_owner(card, combat), PowerId.CACOPHONY, card.base_damage)


@register_effect(CardId.CONCOCT)
def concoct(card, combat, target):
    combat.apply_power_to(target, PowerId.CONCOCT, card.effect_vars["concoct_power"], applier=_owner(card, combat))


@register_effect(CardId.CONSTELLATION)
def constellation(card, combat, target):
    from sts2_env.core.damage import calculate_block
    from sts2_env.core.hooks import fire_after_block_gained
    combat.draw_cards(target, card.effect_vars["cards"])
    combat.gain_energy(target, card.effect_vars["energy"])
    block = calculate_block(card.base_block, target, ValueProp.MOVE, combat, card_source=card)
    before = target.block
    target.gain_block(block)
    if target.block > before:
        fire_after_block_gained(target, target.block-before, combat, ValueProp.MOVE, combat.active_card_play_token)


@register_effect(CardId.FADE)
def fade(card, combat, target):
    combat.apply_power_to(target, PowerId.FADE, card.effect_vars["dexterity"], applier=_owner(card, combat))


@register_effect(CardId.HIBERNATE)
def hibernate(card, combat, target):
    owner = _owner(card, combat)
    combat.apply_power_to(owner, PowerId.HIBERNATE, 1)
    for _ in range(card.effect_vars["repeat"]):
        combat.channel_orb(owner, "Frost")


@register_effect(CardId.IMITATION_LEARNING)
def imitation_learning(card, combat, target):
    owner = _owner(card, combat)
    combat.apply_power_to(owner, PowerId.IMITATION_LEARNING, card.effect_vars["imitation_learning_power"])
    owner.powers[PowerId.IMITATION_LEARNING].add_target(target, card.effect_vars["imitation_learning_power"])


@register_effect(CardId.MIDNIGHT)
def midnight(card, combat, target):
    _attack(card, combat, target)


@register_after_card_exhausted_hook(CardId.MIDNIGHT)
def midnight_exhausted(card, exhausted, combat):
    card.cost = max(0, card.cost - 1)
    card.combat_vars["_combat_cost_override"] = card.cost


@register_after_card_entered_combat_hook(CardId.MIDNIGHT)
def midnight_entered(card, entered, owner, combat):
    if card is entered and not card.combat_vars.get("_is_clone") and not card.combat_vars.get("midnight_initialized"):
        card.combat_vars["midnight_initialized"] = True
        count = combat.cards_exhausted_this_combat
        card.cost = max(0, card.cost - count)
        card.combat_vars["_combat_cost_override"] = card.cost


@register_effect(CardId.ONE_FOR_ALL)
def one_for_all(card, combat, target):
    owner = _owner(card, combat)
    for player in [owner, *combat.get_player_allies_of(owner)]:
        combat.apply_power_to(player, PowerId.ONE_FOR_ALL, card.effect_vars["one_for_all_power"], applier=owner)


@register_effect(CardId.OUTRAGE)
def outrage(card, combat, target):
    _attack(card, combat, target)
    for ally in combat.get_player_allies_of(_owner(card, combat)):
        clone = card.clone(_get_next_id())
        clone.owner = ally
        combat.add_generated_card_to_creature_discard(ally, clone)


@register_effect(CardId.PLOT)
def plot(card, combat, target):
    for ally in combat.get_player_allies_of(_owner(card, combat)):
        combat.apply_power_to(ally, PowerId.DRAW_CARDS_NEXT_TURN, card.effect_vars["cards"])


@register_effect(CardId.SOULBOUND)
def soulbound(card, combat, target):
    combat.apply_power_to(target, PowerId.SOULBOUND, 1, applier=_owner(card, combat))


@register_effect(CardId.THE_BALL)
def the_ball(card, combat, target):
    _attack(card, combat, target)
    increase_base_damage(card, card.effect_vars["increase"])

register_self_mutating_damage(CardId.THE_BALL)


@register_effect(CardId.TUTOR)
def tutor(card, combat, target):
    state = combat.combat_player_state_for(target)
    if not state.draw:
        return
    def resolve(selected):
        if selected is not None:
            combat.move_card_to_creature_hand(target, selected)
    combat.request_card_choice(prompt="Choose a card from the ally's draw pile", cards=list(state.draw), source_pile="draw", resolver=resolve, allow_skip=False)


@register_effect(CardId.UNDERWORLD)
def underworld(card, combat, target):
    combat.apply_power_to(_owner(card, combat), PowerId.UNDERWORLD, 1)
