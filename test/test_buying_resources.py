# pylint: disable=protected-access
import json
import unittest
from typing import Sequence

from power_grid.simple_types import Resource, PlayerColor, RequestError, PhaseStatus
from power_grid.power_plant import PowerPlant, PowerPlantNumber
from power_grid.store_resources import StoreResources
from power_grid.resource_market import ResourceMarket
from power_grid.player_money import PlayerMoney
from power_grid.interfaces import InterfaceResourcePoolResourceMarket
from power_grid.player_resources import PlayerRescources
from power_grid.buying_resources import BuyingResources


class ResourcePoolFake(InterfaceResourcePoolResourceMarket):

    def can_take_resources_from_storage_space(self, resources: Sequence[Resource]) -> bool:
        return False

    def get_from_storage_space(self, resources: Sequence[Resource]) -> None:
        assert False

    def take_resources(self, resources: Sequence[Resource]) -> list[Resource]:
        return []

    def to_string(self) -> str:
        return json.dumps("FakePool")


RED = PlayerColor.RED
BLUE = PlayerColor.BLUE
GREEN = PlayerColor.GREEN


class TestBuyingResources(unittest.TestCase):

    def setUp(self) -> None:
        refilling_pattern = {step: {resource: 0 for resource in Resource}
                             for step in (1, 2, 3)}
        # one market shared by all players: 24 coal, cheapest coal costs 1
        self.market = ResourceMarket(ResourcePoolFake(), 24 * [Resource.COAL],
                                     refilling_pattern)

        self.money: dict[PlayerColor, PlayerMoney] = {}
        self.players: dict[PlayerColor, PlayerRescources] = {}
        for color in (RED, BLUE, GREEN):
            # every player has one coal plant that stores up to 4 coal
            plant = PowerPlant(PowerPlantNumber(10), [Resource.COAL], 2, 2)
            self.money[color] = PlayerMoney(color, 50)
            self.players[color] = PlayerRescources(
                [], [plant], StoreResources(), self.market, self.money[color])

        self.phase = BuyingResources(self.players)

    # ---------- startPhase ----------

    def test_start_phase_reverses_order(self) -> None:
        # RED leads, so GREEN (last place) buys first
        self.phase.startPhase([RED, BLUE, GREEN])

        self.assertEqual(self.phase._player_order, [GREEN, BLUE, RED])
        self.assertEqual(self.phase._current, 0)

    def test_start_phase_again_resets_for_new_round(self) -> None:
        self.phase.startPhase([RED, BLUE, GREEN])
        self.phase.buyResources(GREEN, [])
        self.phase.buyResources(BLUE, [])
        self.phase.buyResources(RED, [])

        # next round, BLUE took the lead
        self.phase.startPhase([BLUE, GREEN, RED])

        self.assertEqual(self.phase.buyResources(RED, []), PhaseStatus.PHASE_CONTINUES)

    # ---------- buyResources ----------

    def test_buy_before_start_phase(self) -> None:
        result = self.phase.buyResources(GREEN, [Resource.COAL])

        self.assertIsInstance(result, RequestError)
        self.assertEqual(self.players[GREEN]._resources, [])

    def test_full_round(self) -> None:
        self.phase.startPhase([RED, BLUE, GREEN])

        self.assertEqual(self.phase.buyResources(GREEN, [Resource.COAL]),
                         PhaseStatus.PHASE_CONTINUES)
        self.assertEqual(self.phase.buyResources(BLUE, [Resource.COAL]),
                         PhaseStatus.PHASE_CONTINUES)
        self.assertEqual(self.phase.buyResources(RED, [Resource.COAL]),
                         PhaseStatus.PHASE_ENDS)

    def test_purchase_goes_to_right_player(self) -> None:
        self.phase.startPhase([RED, BLUE, GREEN])

        self.phase.buyResources(GREEN, [Resource.COAL, Resource.COAL])

        self.assertEqual(self.players[GREEN]._resources, [Resource.COAL, Resource.COAL])
        self.assertEqual(self.money[GREEN].current_money, 48)
        self.assertEqual(self.players[BLUE]._resources, [])
        self.assertEqual(self.money[BLUE].current_money, 50)
        self.assertEqual(self.market._resources[Resource.COAL], 22)

    def test_wrong_player(self) -> None:
        self.phase.startPhase([RED, BLUE, GREEN])

        result = self.phase.buyResources(RED, [Resource.COAL])

        self.assertIsInstance(result, RequestError)
        self.assertEqual(self.players[RED]._resources, [])
        self.assertEqual(self.money[RED].current_money, 50)

    def test_player_cannot_buy_twice(self) -> None:
        self.phase.startPhase([RED, BLUE, GREEN])
        self.phase.buyResources(GREEN, [Resource.COAL])

        result = self.phase.buyResources(GREEN, [Resource.COAL])

        self.assertIsInstance(result, RequestError)
        self.assertEqual(len(self.players[GREEN]._resources), 1)

    def test_buy_nothing_counts_as_turn(self) -> None:
        self.phase.startPhase([RED, BLUE, GREEN])

        self.assertEqual(self.phase.buyResources(GREEN, []), PhaseStatus.PHASE_CONTINUES)
        self.assertEqual(self.phase.buyResources(BLUE, []), PhaseStatus.PHASE_CONTINUES)

    def test_failed_purchase_keeps_turn(self) -> None:
        self.phase.startPhase([RED, BLUE, GREEN])

        # 5 coal do not fit on a plant that stores 4
        result = self.phase.buyResources(GREEN, 5 * [Resource.COAL])

        self.assertIsInstance(result, RequestError)
        self.assertEqual(self.players[GREEN]._resources, [])
        self.assertEqual(self.money[GREEN].current_money, 50)
        # still GREEN's turn, BLUE cannot buy yet
        self.assertIsInstance(self.phase.buyResources(BLUE, []), RequestError)
        # GREEN can try again
        self.assertEqual(self.phase.buyResources(GREEN, [Resource.COAL]),
                         PhaseStatus.PHASE_CONTINUES)

    def test_failed_purchase_not_enough_money(self) -> None:
        self.money[GREEN].spend_money(50)
        self.phase.startPhase([RED, BLUE, GREEN])

        result = self.phase.buyResources(GREEN, [Resource.COAL])

        self.assertIsInstance(result, RequestError)
        self.assertEqual(self.market._resources[Resource.COAL], 24)

    def test_buy_after_phase_ended(self) -> None:
        self.phase.startPhase([RED, BLUE, GREEN])
        self.phase.buyResources(GREEN, [])
        self.phase.buyResources(BLUE, [])
        self.phase.buyResources(RED, [])

        result = self.phase.buyResources(GREEN, [Resource.COAL])

        self.assertIsInstance(result, RequestError)
        self.assertEqual(self.players[GREEN]._resources, [])

    def test_one_player_game(self) -> None:
        self.phase.startPhase([RED])

        self.assertEqual(self.phase.buyResources(RED, []), PhaseStatus.PHASE_ENDS)

    # ---------- getState ----------

    def test_get_state_during_phase(self) -> None:
        self.phase.startPhase([RED, BLUE, GREEN])
        self.phase.buyResources(GREEN, [])

        state = self.phase.getState()

        self.assertIn('["GREEN", "BLUE", "RED"]', state)
        self.assertIn("current_player= BLUE", state)

    def test_get_state_after_phase_ended(self) -> None:
        self.phase.startPhase([RED, BLUE, GREEN])
        self.phase.buyResources(GREEN, [])
        self.phase.buyResources(BLUE, [])
        self.phase.buyResources(RED, [])

        state = self.phase.getState()

        self.assertIn('["GREEN", "BLUE", "RED"]', state)

    def test_get_state_before_start_phase(self) -> None:
        state = self.phase.getState()

        self.assertIsInstance(state, str)


if __name__ == "__main__":
    unittest.main()
