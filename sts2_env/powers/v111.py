"""v0.111.0 multiplayer powers, ported from the matching C# models."""
from sts2_env.powers.base import PowerInstance
from sts2_env.powers.turn_effects import TemporaryDexterityPower
from sts2_env.core.enums import PowerId, CombatSide, ValueProp, CardId, CardType
from sts2_env.core.creature import register_power_class
from sts2_env.cards.base import _get_next_id


class FadePower(TemporaryDexterityPower):
    def __init__(self, amount):
        PowerInstance.__init__(self, PowerId.FADE, amount)


class HibernatePower(PowerInstance):
    def __init__(self, amount):
        super().__init__(PowerId.HIBERNATE, amount)

    def after_player_turn_start(self, owner, combat):
        self.amount = max(0, self.amount - 1)


class ConcoctPower(PowerInstance):
    def __init__(self, amount):
        super().__init__(PowerId.CONCOCT, amount)

    def after_damage_given(self, owner, dealer, target, damage, props, combat):
        if dealer is owner and props.is_powered_attack() and damage > 0:
            combat.apply_power_to(target, PowerId.POISON, self.amount, applier=owner)

    def after_turn_end(self, owner, side, combat):
        if side != owner.side:
            self.amount = 0


class UnderworldPower(PowerInstance):
    def __init__(self, amount):
        super().__init__(PowerId.UNDERWORLD, amount)

    def after_damage_given(self, owner, dealer, target, damage, props, combat):
        result = getattr(combat, "_active_damage_result", None)
        damage = result.total_damage if result is not None else damage
        if dealer is not None and dealer.side == owner.side and dealer is not owner and getattr(dealer, "pet_owner", None) is not owner and props.is_powered_attack() and damage > 0:
            combat.apply_power_to(target, PowerId.DOOM, damage * self.amount, applier=owner)

    def after_turn_end(self, owner, side, combat):
        if side == CombatSide.ENEMY:
            self.amount = 0


class OneForAllPower(PowerInstance):
    def __init__(self, amount):
        super().__init__(PowerId.ONE_FOR_ALL, amount)

    def modify_damage_additive(self, owner, dealer, target, props):
        return self.modify_damage_additive_from_card(owner, dealer, target, props, owner.combat_state.active_card_source)

    def modify_damage_additive_from_card(self, owner, dealer, target, props, card):
        combat = owner.combat_state
        if not props.is_powered_attack() or card is None or card.owner is not owner or card.has_energy_cost_x:
            return 0
        ctx = combat.active_card_play_token
        energy = card.energy_spent if ctx is not None and ctx["card"] is card else combat.modified_card_cost(owner, card)
        return self.amount if energy == 0 else 0


class CacophonyPower(PowerInstance):
    def __init__(self, amount):
        super().__init__(PowerId.CACOPHONY, amount)
        self.instances = [[33, amount]]

    def after_power_amount_changed(self, owner, target, power_id, amount, applier, source, combat):
        if owner is target and power_id == self.power_id and self.amount != amount and amount > 0:
            self.instances.append([33, amount])

    def on_card_drawn(self, owner, card, from_hand_draw, combat):
        for state in self.instances:
            state[0] -= 1
            if state[0] <= 0:
                state[0] = 33  # reset BEFORE damage hooks can recursively draw
                enemy = combat.random_enemy_of(owner)
                if enemy is not None:
                    combat.deal_damage(owner, enemy, state[1], ValueProp.UNPOWERED)


class SoulboundPower(PowerInstance):
    def __init__(self, amount):
        super().__init__(PowerId.SOULBOUND, amount)
        self.adding = False

    def after_card_generated_for_combat(self, owner, card, added_by_player, combat):
        if not added_by_player or getattr(combat, "_active_generation_creator", card.owner) is not self.applier or card.card_id != CardId.SOUL or self.adding:
            return
        from sts2_env.cards.factory import create_card
        self.adding = True
        try:
            for _ in range(self.amount):
                combat.add_generated_card_to_creature_draw_pile(owner, create_card(CardId.SOUL), random_position=True, creator=owner)
        finally:
            self.adding = False


class ImitationLearningPower(PowerInstance):
    def __init__(self, amount):
        super().__init__(PowerId.IMITATION_LEARNING, amount)
        self.targets = []
        self.pending = []

    def add_target(self, target, amount):
        self.targets.append([target, amount])

    def before_card_played(self, owner, card, combat):
        ctx = combat.active_card_play_token
        first = ctx is None or ctx["remaining_plays"] == ctx["play_count"]
        if not first or card.card_type != CardType.POWER:
            return
        for instance in self.targets:
            if instance[0] is card.owner and instance[1] > 0:
                clone = card.clone(_get_next_id())
                clone.owner = owner
                self.pending.append((card, clone, instance))

    def after_card_played(self, owner, card, combat):
        matches = [p for p in self.pending if p[0] is card]
        for match in matches:
            self.pending.remove(match)
            match[2][1] -= 1
            self.amount = sum(instance[1] for instance in self.targets)
            state = combat.combat_player_state_for(owner)
            state.hand.append(match[1])
            ctx = combat.active_card_play_token
            if ctx is None:
                combat.auto_play_card(match[1])
            else:
                ctx.setdefault("after_play_autoplays", []).append(match[1])



for pid, cls in {
    PowerId.FADE: FadePower, PowerId.HIBERNATE: HibernatePower,
    PowerId.CONCOCT: ConcoctPower, PowerId.UNDERWORLD: UnderworldPower,
    PowerId.ONE_FOR_ALL: OneForAllPower, PowerId.CACOPHONY: CacophonyPower,
    PowerId.SOULBOUND: SoulboundPower, PowerId.IMITATION_LEARNING: ImitationLearningPower,
}.items():
    register_power_class(pid, cls)
