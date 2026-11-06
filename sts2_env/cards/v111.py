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
