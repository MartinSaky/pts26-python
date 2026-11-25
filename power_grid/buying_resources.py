from power_grid.simple_types import Resource, RequestError, PlayerColor,PhaseStatus
from power_grid.player_resources import PlayerRescources
from typing import Optional
import json

class BuyingResources:
    def __init__(self, # pylint: disable=too-many-arguments
                     resources: dict[PlayerColor,PlayerRescources]) -> None:
            self._resources = resources
            self._player_order: list[PlayerColor] = []
            self._current = 0


    def startPhase(self,playerOrder: list[PlayerColor]) -> None:
          self._player_order = list(reversed(playerOrder))
          self._current = 0


    def buyResources(self,player: PlayerColor, removedResources: list[Resource]) -> PhaseStatus | RequestError:
          if self._current >= len(self._player_order):
                return RequestError("buying phase is not running")
          
          if player != self._player_order[self._current]:
              return RequestError("not that player's turn")

          player_resources = self._resources[player]
          buy = player_resources.buyResources(removedResources)

          if isinstance(buy, RequestError):
              return buy
         
          self._current += 1
          if self._current == len(self._player_order):
               return PhaseStatus.PHASE_ENDS
          return PhaseStatus.PHASE_CONTINUES
    
    def getState(self) -> str:
         if self._current >= len(self._player_order):
              current = None
         else:
              current = self._player_order[self._current].name
         
         names = [color.name for color in self._player_order]
         return f"player_order= {json.dumps(names)}, current_player= {current}"







