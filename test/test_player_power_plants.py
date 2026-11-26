from __future__ import annotations

import unittest

from power_grid.interfaces import InterfacePlayerPowerPlantsPlayerBoard
from power_grid.player_board_facade import (
    PAYMENT_TABLE,
    PlayerBoardContext,
    PlayerBoardFacade,
)
from power_grid.player_money import PlayerMoney
from power_grid.player_power_plants import PlayerPowerPlants
from power_grid.power_plant import PowerPlant, PowerPlantNumber
from power_grid.resource_market import ResourceMarket
from power_grid.resource_pool import ResourcePool
from power_grid.simple_types import PlayerColor, RequestError, Resource


def _make_plant(
    number: int,
    accepted: list[Resource],
    amount: int,
    cities: int,
) -> PowerPlant:
    return PowerPlant(PowerPlantNumber(number), accepted, amount, cities)


def _plant_numbers(plants: PlayerPowerPlants) -> list[int]:
    return [plant.number.number for plant in plants.power_plants]


class TestPlayerPowerPlantsOwnership(unittest.TestCase):

    def test_default_empty_init(self) -> None:
        plants = PlayerPowerPlants()
        self.assertEqual(plants.power_plants, [])
        self.assertEqual(plants.best_power_plant().number, 0)

    def test_init_and_property_defensive_copies(self) -> None:
        first = _make_plant(3, [Resource.OIL], 2, 1)
        second = _make_plant(4, [Resource.COAL], 2, 1)
        source = [first, second]
        plants = PlayerPowerPlants(source)

        source.append(_make_plant(5, [Resource.COAL, Resource.OIL], 2, 1))
        source.pop(0)
        self.assertEqual(_plant_numbers(plants), [3, 4])

        returned = plants.power_plants
        returned.clear()
        self.assertEqual(_plant_numbers(plants), [3, 4])

        tuple_plants = PlayerPowerPlants((first, second))
        self.assertEqual(_plant_numbers(tuple_plants), [3, 4])

    def test_init_invalid_max_plants_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            PlayerPowerPlants(max_plants=0)
        with self.assertRaises(ValueError):
            PlayerPowerPlants(max_plants=-2)

    def test_init_duplicate_plant_numbers_raises_value_error(self) -> None:
        plant_a = _make_plant(4, [Resource.COAL], 2, 1)
        plant_b = _make_plant(4, [Resource.OIL], 1, 1)
        with self.assertRaises(ValueError):
            PlayerPowerPlants([plant_a, plant_b])

    def test_best_power_plant(self) -> None:
        empty = PlayerPowerPlants()
        self.assertEqual(empty.best_power_plant().number, 0)

        single = PlayerPowerPlants([_make_plant(7, [Resource.OIL], 3, 2)])
        self.assertEqual(single.best_power_plant().number, 7)

        unsorted = PlayerPowerPlants([
            _make_plant(12, [Resource.COAL, Resource.OIL], 2, 2),
            _make_plant(5, [Resource.COAL, Resource.OIL], 2, 1),
            _make_plant(25, [Resource.COAL], 2, 5),
            _make_plant(8, [Resource.COAL], 3, 2),
        ])
        self.assertEqual(unsorted.best_power_plant().number, 25)

    def test_receive_power_plant_limit_behavior(self) -> None:
        plants = PlayerPowerPlants()
        self.assertTrue(
            plants.receive_power_plant(_make_plant(3, [Resource.OIL], 2, 1))
        )
        self.assertTrue(
            plants.receive_power_plant(_make_plant(4, [Resource.COAL], 2, 1))
        )
        self.assertTrue(
            plants.receive_power_plant(
                _make_plant(5, [Resource.COAL, Resource.OIL], 2, 1)
            )
        )
        self.assertFalse(
            plants.receive_power_plant(_make_plant(6, [Resource.GARBAGE], 1, 1))
        )
        self.assertEqual(_plant_numbers(plants), [3, 4, 5, 6])

        two_player_plants = PlayerPowerPlants(max_plants=4)
        for num in (10, 11, 12, 13):
            self.assertTrue(
                two_player_plants.receive_power_plant(
                    _make_plant(num, [Resource.COAL], 1, 1)
                )
            )
        self.assertFalse(
            two_player_plants.receive_power_plant(
                _make_plant(14, [Resource.GARBAGE], 2, 2)
            )
        )
        self.assertEqual(_plant_numbers(two_player_plants), [10, 11, 12, 13, 14])

    def test_receive_duplicate_plant_raises_without_mutation(self) -> None:
        original = _make_plant(4, [Resource.COAL], 2, 1)
        other = _make_plant(7, [Resource.OIL], 3, 2)
        plants = PlayerPowerPlants([original, other])

        duplicate = _make_plant(4, [Resource.COAL], 2, 1)
        with self.assertRaises(ValueError):
            plants.receive_power_plant(duplicate)

        self.assertEqual(_plant_numbers(plants), [4, 7])
        self.assertIs(plants.power_plants[0], original)

    def test_remove_power_plant_success_cases(self) -> None:
        coal_plant = _make_plant(4, [Resource.COAL], 2, 1)
        hybrid_plant = _make_plant(
            5, [Resource.COAL, Resource.OIL], 2, 1
        )
        eco_plant = _make_plant(13, [], 0, 1)
        plants = PlayerPowerPlants([coal_plant, hybrid_plant, eco_plant])

        kept_resources = [
            Resource.COAL,
            Resource.COAL,
            Resource.OIL,
            Resource.OIL,
        ]
        self.assertIsNone(
            plants.remove_power_plant(PowerPlantNumber(4), kept_resources)
        )
        self.assertEqual(_plant_numbers(plants), [5, 13])

        self.assertIsNone(plants.remove_power_plant(PowerPlantNumber(5), []))
        self.assertEqual(_plant_numbers(plants), [13])

        self.assertIsNone(plants.remove_power_plant(PowerPlantNumber(13), []))
        self.assertEqual(plants.power_plants, [])
        self.assertEqual(plants.best_power_plant().number, 0)

    def test_remove_power_plant_errors_and_atomicity(self) -> None:
        empty_plants = PlayerPowerPlants()
        empty_err = empty_plants.remove_power_plant(PowerPlantNumber(3), [])
        self.assertIsInstance(empty_err, RequestError)
        self.assertEqual(empty_plants.power_plants, [])

        coal_plant = _make_plant(4, [Resource.COAL], 2, 1)
        oil_plant = _make_plant(3, [Resource.OIL], 2, 1)
        plants = PlayerPowerPlants([coal_plant, oil_plant])

        unowned_err = plants.remove_power_plant(PowerPlantNumber(99), [])
        self.assertIsInstance(unowned_err, RequestError)
        self.assertEqual(_plant_numbers(plants), [4, 3])

        overflow_err = plants.remove_power_plant(
            PowerPlantNumber(4),
            [Resource.COAL, Resource.COAL],
        )
        self.assertIsInstance(overflow_err, RequestError)
        self.assertEqual(_plant_numbers(plants), [4, 3])

        retry_err = plants.remove_power_plant(PowerPlantNumber(4), [])
        self.assertIsNone(retry_err)
        self.assertEqual(_plant_numbers(plants), [3])


class TestPlayerPowerPlantsOperations(unittest.TestCase):

    def test_can_store_resources_capacity_and_types(self) -> None:
        empty = PlayerPowerPlants()
        self.assertTrue(empty.can_store_resources([]))
        self.assertFalse(empty.can_store_resources([Resource.COAL]))

        coal_plant = _make_plant(8, [Resource.COAL], 2, 1)
        plants = PlayerPowerPlants([coal_plant])
        self.assertTrue(plants.can_store_resources([]))
        self.assertTrue(plants.can_store_resources(2 * [Resource.COAL]))
        self.assertTrue(plants.can_store_resources(4 * [Resource.COAL]))
        self.assertFalse(plants.can_store_resources(5 * [Resource.COAL]))
        self.assertFalse(plants.can_store_resources([Resource.OIL]))

    def test_can_store_resources_hybrid_and_ecological(self) -> None:
        eco_only = PlayerPowerPlants([_make_plant(13, [], 0, 1)])
        self.assertTrue(eco_only.can_store_resources([]))
        self.assertFalse(eco_only.can_store_resources([Resource.GARBAGE]))

        hybrid = _make_plant(12, [Resource.COAL, Resource.OIL], 2, 2)
        plants = PlayerPowerPlants([_make_plant(13, [], 0, 1), hybrid])
        self.assertTrue(
            plants.can_store_resources([
                Resource.COAL,
                Resource.COAL,
                Resource.OIL,
                Resource.OIL,
            ])
        )
        self.assertFalse(
            plants.can_store_resources(
                3 * [Resource.COAL] + 2 * [Resource.OIL]
            )
        )

    def test_number_of_connectable_cities_basics(self) -> None:
        empty = PlayerPowerPlants()
        self.assertEqual(empty.number_of_connectable_cities([]), 0)
        self.assertEqual(
            empty.number_of_connectable_cities([Resource.URANIUM]), 0
        )

        eco_and_fuel = PlayerPowerPlants([
            _make_plant(13, [], 0, 1),
            _make_plant(8, [Resource.COAL], 3, 2),
        ])
        self.assertEqual(eco_and_fuel.number_of_connectable_cities([]), 1)
        self.assertEqual(
            eco_and_fuel.number_of_connectable_cities(2 * [Resource.COAL]), 1
        )
        self.assertEqual(
            eco_and_fuel.number_of_connectable_cities(3 * [Resource.COAL]), 3
        )

    def test_number_of_connectable_cities_optimal_allocation(self) -> None:
        competing = PlayerPowerPlants([
            _make_plant(4, [Resource.COAL], 2, 1),
            _make_plant(15, [Resource.COAL], 2, 3),
        ])
        self.assertEqual(
            competing.number_of_connectable_cities(2 * [Resource.COAL]), 3
        )

        two_vs_one = PlayerPowerPlants([
            _make_plant(20, [Resource.COAL], 3, 3),
            _make_plant(10, [Resource.COAL], 2, 2),
            _make_plant(25, [Resource.COAL], 1, 2),
        ])
        self.assertEqual(
            two_vs_one.number_of_connectable_cities(3 * [Resource.COAL]), 4
        )

        mixed_plants = PlayerPowerPlants([
            _make_plant(14, [Resource.GARBAGE, Resource.URANIUM], 2, 4),
            _make_plant(6, [Resource.GARBAGE], 2, 2),
            _make_plant(11, [Resource.URANIUM], 1, 2),
        ])
        resources = [Resource.GARBAGE, Resource.GARBAGE, Resource.URANIUM]
        self.assertEqual(
            mixed_plants.number_of_connectable_cities(resources), 6
        )
        self.assertEqual(
            resources,
            [Resource.GARBAGE, Resource.GARBAGE, Resource.URANIUM],
        )

    def test_use_power_plant_success_and_preserves_inputs(self) -> None:
        plants = PlayerPowerPlants([
            _make_plant(4, [Resource.COAL], 2, 1),
            _make_plant(12, [Resource.COAL, Resource.OIL], 2, 3),
            _make_plant(13, [], 0, 1),
        ])
        self.assertEqual(plants.use_power_plant([], []), 0)
        self.assertEqual(
            plants.use_power_plant(
                [PowerPlantNumber(4)], [Resource.COAL, Resource.COAL]
            ),
            1,
        )

        ppns = [
            PowerPlantNumber(4),
            PowerPlantNumber(12),
            PowerPlantNumber(13),
        ]
        burn = [
            Resource.COAL,
            Resource.COAL,
            Resource.OIL,
            Resource.OIL,
        ]
        result = plants.use_power_plant(ppns, burn)
        self.assertEqual(result, 5)
        self.assertEqual([ppn.number for ppn in ppns], [4, 12, 13])
        self.assertEqual(
            burn,
            [Resource.COAL, Resource.COAL, Resource.OIL, Resource.OIL],
        )

    def test_use_power_plant_ownership_and_duplicate_errors(self) -> None:
        plants = PlayerPowerPlants([
            _make_plant(4, [Resource.COAL], 2, 1),
            _make_plant(13, [], 0, 1),
        ])

        unowned = plants.use_power_plant(
            [PowerPlantNumber(9)], [Resource.COAL]
        )
        self.assertIsInstance(unowned, RequestError)

        same_ref = PowerPlantNumber(4)
        dup_same = plants.use_power_plant(
            [same_ref, same_ref], 4 * [Resource.COAL]
        )
        self.assertIsInstance(dup_same, RequestError)

        dup_fresh = plants.use_power_plant(
            [PowerPlantNumber(4), PowerPlantNumber(4)], 4 * [Resource.COAL]
        )
        self.assertIsInstance(dup_fresh, RequestError)

        no_plants_with_fuel = plants.use_power_plant([], [Resource.COAL])
        self.assertIsInstance(no_plants_with_fuel, RequestError)

    def test_use_power_plant_resource_mismatch_errors(self) -> None:
        plants = PlayerPowerPlants([
            _make_plant(8, [Resource.COAL], 2, 2),
        ])

        too_few = plants.use_power_plant(
            [PowerPlantNumber(8)], [Resource.COAL]
        )
        self.assertIsInstance(too_few, RequestError)

        too_many = plants.use_power_plant(
            [PowerPlantNumber(8)], 3 * [Resource.COAL]
        )
        self.assertIsInstance(too_many, RequestError)

        wrong_type = plants.use_power_plant(
            [PowerPlantNumber(8)], [Resource.OIL, Resource.OIL]
        )
        self.assertIsInstance(wrong_type, RequestError)


class TestPlayerPowerPlantsIntegration(unittest.TestCase):

    def test_protocol_conformance_annotation(self) -> None:
        plants = PlayerPowerPlants([_make_plant(3, [Resource.OIL], 2, 1)])
        interface_ref: InterfacePlayerPowerPlantsPlayerBoard = plants

        self.assertEqual(interface_ref.best_power_plant().number, 3)
        self.assertTrue(interface_ref.can_store_resources([Resource.OIL]))
        self.assertEqual(
            interface_ref.number_of_connectable_cities(2 * [Resource.OIL]), 1
        )

    def test_player_board_lifecycle_integration(self) -> None:
        pool = ResourcePool([], [])
        refill_pattern: dict[int, dict[Resource, int]] = {
            step: {
                Resource.COAL: 2,
                Resource.OIL: 2,
                Resource.GARBAGE: 1,
                Resource.URANIUM: 1,
            }
            for step in (1, 2, 3)
        }
        starting_resources = 24 * [Resource.COAL] + 24 * [Resource.OIL]
        market = ResourceMarket(pool, starting_resources, refill_pattern)

        plants = PlayerPowerPlants()
        interface_ref: InterfacePlayerPowerPlantsPlayerBoard = plants
        money = PlayerMoney(PlayerColor.BLUE, 50)
        context = PlayerBoardContext(
            resource_market=market,
            resource_pool=pool,
        )
        board = PlayerBoardFacade(money, interface_ref, context)

        self.assertTrue(
            board.receive_power_plant(_make_plant(3, [Resource.OIL], 2, 1), 3)
        )
        self.assertTrue(
            board.receive_power_plant(_make_plant(4, [Resource.COAL], 2, 1), 4)
        )
        self.assertTrue(
            board.receive_power_plant(_make_plant(13, [], 0, 1), 13)
        )
        self.assertEqual(board.outstanding_money(), 30)
        self.assertEqual(board.best_power_plant_number().number, 13)

        buy_err = board.buy_resources(
            [Resource.OIL, Resource.OIL, Resource.COAL, Resource.COAL]
        )
        self.assertIsNone(buy_err)
        self.assertEqual(board.outstanding_money(), 26)
        self.assertEqual(board.number_of_connectable_cities(), 3)

        self.assertFalse(
            board.receive_power_plant(
                _make_plant(10, [Resource.COAL], 2, 2), 10
            )
        )
        self.assertEqual(board.outstanding_money(), 16)
        self.assertEqual(len(board.power_plants), 4)

        failed_discard = board.remove_power_plant(PowerPlantNumber(3), [])
        self.assertIsInstance(failed_discard, RequestError)
        self.assertEqual(len(board.power_plants), 4)
        self.assertEqual(pool.resources, [])

        discard_err = board.remove_power_plant(
            PowerPlantNumber(3), [Resource.OIL, Resource.OIL]
        )
        self.assertIsNone(discard_err)
        self.assertEqual(_plant_numbers(plants), [4, 13, 10])
        self.assertEqual(board.resources, [Resource.COAL, Resource.COAL])
        self.assertEqual(pool.resources, [Resource.OIL, Resource.OIL])
        self.assertEqual(board.best_power_plant_number().number, 13)
        self.assertEqual(board.number_of_connectable_cities(), 3)

        bureaucracy_err = board.use_power_plants(
            [PowerPlantNumber(10), PowerPlantNumber(13)],
            [Resource.COAL, Resource.COAL],
        )
        self.assertIsNone(bureaucracy_err)
        self.assertEqual(board.outstanding_money(), 16 + PAYMENT_TABLE[3])
        self.assertEqual(board.resources, [])
        self.assertEqual(
            pool.resources,
            [Resource.OIL, Resource.OIL, Resource.COAL, Resource.COAL],
        )
        self.assertEqual(board.number_of_connectable_cities(), 1)
