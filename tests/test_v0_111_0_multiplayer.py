"""Behavioral cases read from the pinned v0.111.0 card and power models."""
import pytest
from sts2_env.cards.factory import create_card
from sts2_env.core.enums import CardId, PowerId, CombatSide, ValueProp
from sts2_env.core.hooks import fire_after_turn_end, fire_after_player_turn_start
from sts2_env.run.run_state import PlayerState
from tests.test_necrobinder_parity import _make_combat


def setup():
    combat = _make_combat()
    enemy = combat.enemies[0]
    enemy.current_hp = enemy.max_hp = 1000
    ally = combat.add_ally_player(PlayerState(player_id=2, character_id="Defect", max_hp=70, current_hp=70))
    for owner in (combat.player, ally):
        state = combat.combat_player_state_for(owner)
        for pile in state.all_piles:
            pile.clear()
    return combat, ally, enemy


def play(combat, cid, target=None, upgraded=False, owner=None):
    owner = owner or combat.primary_player
    state = combat.combat_player_state_for(owner)
    card = create_card(cid, upgraded)
    card.owner = owner
    state.hand.append(card)
    state.energy = 20
    assert combat.auto_play_card(card, target=target)
    return card


@pytest.mark.parametrize("upgraded,strength,dex,block", [(False,5,6,9),(True,7,9,12)])
def test_ally_buffs_and_constellation(upgraded,strength,dex,block):
    c, ally, _ = setup()
    play(c, CardId.BLAZE, ally, upgraded)
    assert ally.get_power_amount(PowerId.STRENGTH) == strength
    play(c, CardId.FADE, ally, upgraded)
    assert ally.get_power_amount(PowerId.DEXTERITY) == dex
    state = c.combat_player_state_for(ally)
    marker = create_card(CardId.STRIKE_DEFECT)
    marker.owner = ally
    state.draw.append(marker)
    state.energy = 0
    play(c, CardId.CONSTELLATION, ally, upgraded)
    assert marker in state.hand
    assert state.energy == 1
    assert ally.block == block  # Dexterity belongs to the caster, not the recipient.
    assert c.player.block == 0
    fire_after_turn_end(CombatSide.PLAYER, c)
    assert ally.get_power_amount(PowerId.DEXTERITY) == 0


@pytest.mark.parametrize("upgraded,damage,draw", [(False,9,2),(True,13,3)])
def test_blade_symphony_outrage_and_plot(upgraded,damage,draw):
    c, ally, enemy = setup()
    play(c, CardId.BLADE_SYMPHONY, upgraded=upgraded)
    state = c.combat_player_state_for(ally)
    assert [x.card_id for x in state.hand] == [CardId.SHIV]*2
    card = play(c, CardId.OUTRAGE, enemy, upgraded)
    assert enemy.current_hp == 1000-damage
    assert len(state.discard) == 1
    clone = state.discard[0]
    assert clone is not card and clone.owner is ally and clone.upgraded == upgraded
    play(c, CardId.PLOT, upgraded=upgraded)
    assert ally.get_power_amount(PowerId.DRAW_CARDS_NEXT_TURN) == draw
    assert c.player.get_power_amount(PowerId.DRAW_CARDS_NEXT_TURN) == 0


@pytest.mark.parametrize("upgraded,poison", [(False,3),(True,4)])
def test_concoct_only_unblocked_powered_ally_hits_and_expires(upgraded,poison):
    c, ally, enemy = setup()
    play(c, CardId.CONCOCT, ally, upgraded)
    enemy.block = 100
    c.deal_damage(ally, enemy, 6, ValueProp.MOVE)
    assert not enemy.has_power(PowerId.POISON)
    enemy.block = 0
    c.deal_damage(c.player, enemy, 6, ValueProp.MOVE)
    c.deal_damage(ally, enemy, 6, ValueProp.UNPOWERED)
    assert not enemy.has_power(PowerId.POISON)
    c.deal_damage(ally, enemy, 6, ValueProp.MOVE)
    assert enemy.get_power_amount(PowerId.POISON) == poison
    fire_after_turn_end(CombatSide.ENEMY, c)
    assert not ally.has_power(PowerId.CONCOCT)


def test_underworld_includes_blocked_damage_but_excludes_caster_and_pet():
    c, ally, enemy = setup()
    play(c, CardId.UNDERWORLD)
    enemy.block = 100
    c.deal_damage(ally, enemy, 6, ValueProp.MOVE)
    assert enemy.get_power_amount(PowerId.DOOM) == 6
    c.deal_damage(c.player, enemy, 8, ValueProp.MOVE)
    c.summon_osty(c.player, 5)
    c.deal_damage(c.osty, enemy, 8, ValueProp.MOVE)
    c.deal_damage(ally, enemy, 8, ValueProp.UNPOWERED)
    assert enemy.get_power_amount(PowerId.DOOM) == 6
    fire_after_turn_end(CombatSide.ENEMY, c)
    assert not c.player.has_power(PowerId.UNDERWORLD)


@pytest.mark.parametrize("upgraded,increase", [(False,10),(True,15)])
def test_ball_grows_and_transfers_to_other_players_draw(upgraded,increase):
    c, ally, enemy = setup()
    ball = play(c, CardId.THE_BALL, enemy, upgraded)
    assert enemy.current_hp == 990
    assert ball.base_damage == 10+increase
    assert ball.owner is ally
    assert ball in c.combat_player_state_for(ally).draw
    assert ball not in c.discard_pile


def test_midnight_uses_history_even_after_exhausted_card_leaves_pile():
    c, ally, enemy = setup()
    exhausted = create_card(CardId.STRIKE_IRONCLAD)
    exhausted.owner = ally
    c.combat_player_state_for(ally).hand.append(exhausted)
    c.exhaust_card(exhausted)
    c.move_card_to_creature_hand(ally, exhausted)
    midnight = create_card(CardId.MIDNIGHT)
    c.add_generated_card_to_creature_hand(c.player, midnight)
    assert midnight.cost == 11
    c.exhaust_card(exhausted)
    assert midnight.cost == 10
    clone = midnight.clone(999999)
    c.add_generated_card_to_creature_hand(c.player, clone)
    assert clone.cost == 10
    assert c.auto_play_card(midnight, target=enemy)
    assert enemy.current_hp == 940


def test_tutor_moves_chosen_card_without_draw_hooks_and_handles_full_hand():
    c, ally, _ = setup()
    state = c.combat_player_state_for(ally)
    markers = [create_card(CardId.STRIKE_DEFECT), create_card(CardId.DEFEND_DEFECT)]
    for card in markers:
        card.owner = ally
    state.draw.extend(markers)
    state.hand.extend(create_card(CardId.SHIV) for _ in range(10))
    play(c, CardId.TUTOR, ally)
    assert c.pending_choice is not None
    assert c.resolve_pending_choice(1)
    assert state.draw == [markers[0]]
    assert markers[1] in state.discard
    assert len(state.hand) == 10


def test_soulbound_duplicates_only_appliers_generated_souls():
    c, ally, _ = setup()
    play(c, CardId.SOULBOUND, ally)
    c.add_generated_card_to_creature_hand(c.player, create_card(CardId.SOUL))
    state = c.combat_player_state_for(ally)
    assert [card.card_id for card in state.draw] == [CardId.SOUL]
    c.add_generated_card_to_creature_hand(ally, create_card(CardId.SOUL))
    c.add_generated_card_to_creature_hand(c.player, create_card(CardId.SHIV))
    assert len(state.draw) == 1


@pytest.mark.parametrize("upgraded,count", [(False,2),(True,3)])
def test_hibernate_frost_blocks_both_players_until_next_turn(upgraded,count):
    c, ally, _ = setup()
    play(c, CardId.HIBERNATE, upgraded=upgraded, owner=ally)
    state = c.combat_player_state_for(ally)
    assert len(state.orb_queue.orbs) == count
    with c.acting_player_view(ally):
        for orb in state.orb_queue.orbs:
            orb.on_passive(c)
    assert c.player.block == ally.block == 2*count
    fire_after_player_turn_start(ally,c)
    assert not ally.has_power(PowerId.HIBERNATE)


def test_cacophony_counts_both_players_draws_and_resets_each_instance():
    c, ally, enemy = setup()
    play(c, CardId.CACOPHONY)
    play(c, CardId.CACOPHONY, upgraded=True)
    for i in range(66):
        owner = ally if i%2 else c.player
        state = c.combat_player_state_for(owner)
        state.hand.clear()
        card = create_card(CardId.DEFEND_IRONCLAD)
        card.owner = owner
        state.draw.append(card)
        c.draw_cards(owner,1)
        assert enemy.current_hp == 1000 - ((i+1)//33)*165


def test_one_for_all_applies_to_caster_and_ally_zero_energy_attacks():
    c, ally, enemy = setup()
    play(c, CardId.ONE_FOR_ALL)
    assert c.player.get_power_amount(PowerId.ONE_FOR_ALL) == ally.get_power_amount(PowerId.ONE_FOR_ALL) == 3
    # Auto-play actually spends zero, even though Strike's printed cost is one.
    play(c, CardId.STRIKE_DEFECT, enemy, owner=ally)
    assert enemy.current_hp == 991
    c.deal_damage(ally, enemy, 6, ValueProp.MOVE)
    assert enemy.current_hp == 985


def test_imitation_learning_copies_once_per_series_and_preserves_parent_play():
    c, ally, _ = setup()
    play(c, CardId.IMITATION_LEARNING, ally)
    card = create_card(CardId.INFLAME)
    card.base_replay_count = 1
    card.owner = ally
    c.combat_player_state_for(ally).hand.append(card)
    assert c.auto_play_card(card)
    assert ally.get_power_amount(PowerId.STRENGTH) == 4
    # Clone retains the replay count but consumes only one imitation charge.
    assert c.player.get_power_amount(PowerId.STRENGTH) == 4
    assert c.player.get_power_amount(PowerId.IMITATION_LEARNING) == 1
    assert c._pending_play is None


def test_imitation_instances_each_copy_one_power():
    c, ally, _ = setup()
    play(c, CardId.IMITATION_LEARNING, ally)
    play(c, CardId.IMITATION_LEARNING, ally)
    play(c, CardId.INFLAME, owner=ally)
    assert ally.get_power_amount(PowerId.STRENGTH) == 2
    assert c.player.get_power_amount(PowerId.STRENGTH) == 4
    assert c.player.get_power_amount(PowerId.IMITATION_LEARNING) == 2


def test_soulbound_uses_creator_even_when_recipient_differs():
    c, ally, _ = setup()
    play(c, CardId.SOULBOUND, ally)
    state = c.combat_player_state_for(ally)
    c.add_generated_card_to_creature_draw_pile(ally, create_card(CardId.SOUL), creator=c.player)
    assert len(state.draw) == 2
    c.add_generated_card_to_creature_draw_pile(c.player, create_card(CardId.SOUL), creator=ally)
    assert len(state.draw) == 2


def test_one_for_all_and_tracking_preview_use_explicit_card_source():
    from sts2_env.core.hooks import modify_damage
    c, ally, enemy = setup()
    play(c, CardId.ONE_FOR_ALL)
    strike = create_card(CardId.STRIKE_IRONCLAD)
    strike.owner = c.player
    assert modify_damage(6,c.player,enemy,ValueProp.MOVE,c,card_source=strike) == 6
    strike.cost = 0
    assert modify_damage(6,c.player,enemy,ValueProp.MOVE,c,card_source=strike) == 9
    c.apply_power_to(c.player,PowerId.TRACKING,50)
    c.apply_power_to(enemy,PowerId.WEAK,1)
    assert modify_damage(6,c.player,enemy,ValueProp.MOVE,c,card_source=strike) == 13
    assert modify_damage(6,c.player,enemy,ValueProp.MOVE,c) == 6


def test_imitation_choice_resumes_all_copies_and_parent(monkeypatch):
    from sts2_env.cards.registry import _CARD_EFFECTS
    c, ally, _ = setup()
    play(c, CardId.IMITATION_LEARNING, ally)
    play(c, CardId.IMITATION_LEARNING, ally)
    resolved = []
    def choosing_power(card, combat, target):
        marker = create_card(CardId.SHIV)
        combat.request_card_choice(prompt="Copy continuation", cards=[marker, create_card(CardId.DEFEND_IRONCLAD)],
            source_pile="generated", allow_skip=False,
            resolver=lambda selected: resolved.append(card.owner))
    monkeypatch.setitem(_CARD_EFFECTS, CardId.INFLAME, choosing_power)
    play(c, CardId.INFLAME, owner=ally)
    for _ in range(3):
        assert c.pending_choice is not None
        assert c.resolve_pending_choice(0)
    assert resolved == [ally, c.player, c.player]
    assert c._pending_play is None
    assert c.pending_choice is None
    assert c.player.get_power_amount(PowerId.IMITATION_LEARNING) == 2
