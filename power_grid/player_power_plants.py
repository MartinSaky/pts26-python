from __future__ import annotations

from collections.abc import Sequence

from power_grid.maximum_number_of_usable_power_plants import MaximumNumberOfUsablePowerPlants
from power_grid.power_plant import PowerPlant, PowerPlantNumber
from power_grid.simple_types import RequestError, Resource
from power_grid.store_resources import StoreResources
from power_grid.use_power_plants import UsePowerPlants


class PlayerPowerPlants:

    def __init__(
        self, power_plants: Sequence[PowerPlant] = (), max_plants: int = 3
    ) -> None:
        if max_plants < 1:
            raise ValueError("max_plants must be at least 1")
        initial_plants = list(power_plants)
        seen_numbers: set[int] = set()
        for plant in initial_plants:
            if plant.number.number in seen_numbers:
                raise ValueError(
                    "power_plants cannot contain duplicate power plant numbers"
                )
            seen_numbers.add(plant.number.number)
        self._power_plants: list[PowerPlant] = initial_plants
        self._max_plants = max_plants
        self._store_resources = StoreResources()
        self._max_usable_power_plants = MaximumNumberOfUsablePowerPlants()
        self._use_power_plants = UsePowerPlants()

    @property
    def power_plants(self) -> list[PowerPlant]:
        return list(self._power_plants)

    def best_power_plant(self) -> PowerPlantNumber:
        if not self._power_plants:
            return PowerPlantNumber(0)
        best = max(self._power_plants, key=lambda plant: plant.number.number)
        return PowerPlantNumber(best.number.number)

    def receive_power_plant(self, power_plant: PowerPlant) -> bool:
        if any(
            existing.number.number == power_plant.number.number
            for existing in self._power_plants
        ):
            raise ValueError(
                f"Player already owns power plant {power_plant.number.number}"
            )
        self._power_plants.append(power_plant)
        return len(self._power_plants) <= self._max_plants

    def remove_power_plant(
        self, ppn: PowerPlantNumber, new_resources: list[Resource]
    ) -> RequestError | None:
        target_index = next(
            (
                index
                for index, plant in enumerate(self._power_plants)
                if plant.number.number == ppn.number
            ),
            None,
        )
        if target_index is None:
            return RequestError("You do not have a power plant with this number")
        remaining_plants = [
            plant
            for index, plant in enumerate(self._power_plants)
            if index != target_index
        ]
        if not self._store_resources.can_store_resources(
            list(new_resources), remaining_plants
        ):
            return RequestError("Cannot store your resources")
        self._power_plants = remaining_plants
        return None

    def number_of_connectable_cities(self, resources: list[Resource]) -> int:
        return self._max_usable_power_plants.number_of_suppliable_towns(
            list(resources), list(self._power_plants)
        )

    def can_store_resources(self, resources: list[Resource]) -> bool:
        return self._store_resources.can_store_resources(
            list(resources), list(self._power_plants)
        )

    def use_power_plant(
        self, ppns: list[PowerPlantNumber], resources_to_burn: list[Resource]
    ) -> int | RequestError:
        plants_by_number = {
            plant.number.number: plant for plant in self._power_plants
        }
        seen_numbers: set[int] = set()
        chosen_plants: list[PowerPlant] = []
        for ppn in ppns:
            if ppn.number in seen_numbers:
                return RequestError(
                    f"Power plant {ppn.number} cannot be used more than once"
                )
            plant = plants_by_number.get(ppn.number)
            if plant is None:
                return RequestError(
                    f"Player does not own power plant {ppn.number}"
                )
            seen_numbers.add(ppn.number)
            chosen_plants.append(plant)
        return self._use_power_plants.number_of_suppliable_towns(
            list(resources_to_burn), chosen_plants
        )
